# Convex hull prices by Dantzig-Wolfe column generation over each unit's schedule set.
#
# hc and hl write the unit hull in full. This module generates it: the master of docs/DW.md
# has one column per generated schedule of one unit, the priced coupling rows, and one
# convexity row per unit. Its value is the Lagrangian dual of the clearing and an optimal
# dual of the coupling rows is a convex hull price (Andrianesis et al. §III).
#
# The loop is written once, in _gen, and run over two unit classes. cg prices uc_price's
# class: its oracle reads _rw, _eq and _fx directly, as _om does, and its master keeps
# uc_price's network whole. cgp prices the pglib-uc class, energy and reserve together: its
# oracle reads pglib_uc's own rows for one unit, so no row builder is shared with cg.
#
# A price is reported only after the vector that will be reported has been priced against
# every unit by its integer program; a vector that fails and yields no new column is tagged
# stall. The Lagrangian value at that vector is then a lower bound on the hull value (Beck
# Theorem 12.3), to the oracle's accuracy, and the master value z an upper one. That
# bracket, not the master objective alone, is the certificate. BT Theorem 6.1 writes it as
# z + sum_g rho_g, which holds when the master's dual cost equals z; the selected dual is
# held to that only within _ce, so lb is computed from its definition.
#
# LEGEND
#   Dw,Dp      : one generated master on uc_price's class, and on pglib-uc's
#   _gen       : the general step: generate, select, reprice
#   _col,_in   : one uc_price column checked against its unit, and placed on its bus rows
#   _oc,_rm    : uc_price's oracle and restricted master
#   _ub,_op,_rp: one pglib unit's own rows, its oracle, and pglib's restricted master
#   cg,cgp     : the loop on each class
#   K          : columns per unit, each (a, k, x): priced-row coefficients, cost, schedule
#   y          : master weights, one per column
#   w          : duals of the priced rows; lam (energy) and sig (reserve) are its parts
#   pi         : convexity duals, one per unit; Sol.pi, the energy price, is lam here
#   rho        : per unit, a lower bound on the minimum reduced cost at w
#   v          : lower bound on min k - w'a over one unit: a bound route's mip_dual_bound
#   z,lb       : master value, and the Lagrangian value at w, a lower bound on the hull
#   eps,tau    : relative certificate tolerance; the per-unit reduced-cost tolerance it sets
#   AB         : the reduced-cost resolution the oracle's bound supports (docs/DW.md)
#   r          : the master's own dual residual, the most any column already in it prices out
#   sel        : whether the master's dual is selected on its face or read off the solver
#   R,J        : the oracle's answer for every unit at w; how many columns it adds
#   k,ng,nr    : master solves, columns generated, of which found by repricing a selection
#   nk,na      : columns in the final master, and those with positive weight
#   st         : _px's selection tag for the reported price, or stall
#   g,d,cap,net: units, demand, AIC ceilings, network, as uc_price takes them
#   D          : a parsed pglib-uc instance     jr : its periods with a reserve requirement
#   pm         : a pglib unit's minimum output  W : renewable columns, bounded, kept whole
#   Q,S,L      : each pglib unit's own rows, start-up tiers and curve points
#   od,ol      : first column of each unit's tier and curve blocks in pglib's full system
#   G,T,x,i,j  : unit and period counts, one unit, unit and column indices

from typing import NamedTuple

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import csc_array, csr_array

from models.pglib_uc import _run, _sy as _psy
from models.uc_price import Sol, _eq, _fx, _mi, _nq, _nw, _pl, _px, _rw, _vw, ck, uc

AB = 1e-5


class Dw(NamedTuple):
    """A generated master on uc_price's class: its Sol, then what it took.

    s.z is the master value and s.pi the reported price. s.lb is the Lagrangian dual value
    at that price, lam'd + sum(v) + _nq, from the oracle's bounds: a lower bound on the
    hull value, to the oracle's accuracy and whatever the master's. s.gap is
    (z - lb) / max(1, |z|). s.st is _px's selection tag, or stall when a reduced cost
    bounded below -tau produced no new column: the bound then sits further than AB from the
    schedule's value, and the certificate is only as good as lb says.
    """

    s: Sol
    k: int
    ng: int
    nr: int
    nk: int
    na: int
    rho: np.ndarray
    tau: float


class Dp(NamedTuple):
    """A generated master on the pglib-uc class: value and bound, energy and reserve prices.

    pr is zero in a period with no reserve requirement, as in pglib_uc.px. The remaining
    fields are Dw's.
    """

    z: float
    lb: float
    pe: np.ndarray
    pr: np.ndarray
    st: str
    k: int
    ng: int
    nr: int
    nk: int
    na: int
    rho: np.ndarray
    tau: float


def _gen(G, rm, oc, K, eps):
    """The general step, for any G blocks: generate, select, reprice.

    rm(K, sel) -> z, y, w, pi, st : the master over K: value, weights, priced-row duals,
                                    convexity duals, tag; sel applies _px's face rule
    oc(i, w)   -> (a, k, x), v    : block i's best column at w and a lower bound v on
                                    min k - w'a over the block

    (a) Solve the master, reading the solver's own dual while generating. (b) Price every
    block exactly at w. (c) Add each column whose reduced cost is below -tau. Once none
    prices out, select the canonical dual on the master's face and price that vector: it
    is reported only if it passes, and otherwise its violating columns are added and
    generation resumes. Stop: the selected dual prices every block to within -tau, where

        tau = max(eps max(1, |z|) / G, AB + r).

    The oracle's bound resolves a reduced cost only to AB, since HiGHS closes its search to
    an absolute 1e-6 and admits rows violated by its feasibility tolerance; the master's
    dual satisfies its own columns only to r. No finer tau can be certified: below it a
    column already in the master would read as a violation. If a bound below -tau yields no
    new column, the loop stops with st = stall and the vector is not certified. Terminates:
    every column the oracle returns is a vertex of a polytope fixed by its integers, a
    finite set, and a column already present never prices out by more than r.
    """
    k = ng = nr = 0
    sel = False
    while True:
        z, y, w, pi, st = rm(K, sel)
        k += 1
        r = max([0.0, *(pi[i] + w @ a - q for i in range(G) for a, q, _ in K[i])])
        tau = max(eps * max(1.0, abs(z)) / max(G, 1), AB + r)
        R = [oc(i, w) for i in range(G)]
        rho = np.array([R[i][1] - pi[i] for i in range(G)])
        if (rho >= -tau).all():
            if sel:
                break
            sel = True
            continue
        J = 0
        for i, ((a, q, _), _v) in enumerate(R):
            if q - w @ a - pi[i] < -tau and not any(
                    np.abs(a - b).max() <= 1e-9 and abs(q - c) <= 1e-9 * max(1.0, abs(q))
                    for b, c, _ in K[i]):
                K[i].append(R[i][0])
                J += 1
        if not J:
            st = "stall"
            break
        ng += J
        nr += J if sel else 0
        sel = False
    return z, y, w, st, [q[1] for q in R], k, ng, nr, rho, tau


def _col(x, T, p, u, cap=None):
    """One column: unit x's schedule (p, u), checked against its own rows, and its cost."""
    p, u = np.asarray(p, dtype=float), np.rint(np.asarray(u, dtype=float))
    v, w = _vw(x, u)
    q = _pl(x, T, u, v, w, cap)
    if q is None or (q[0] @ p > q[1] + 1e-6).any():
        raise ValueError("a seed column breaks a unit's own limits")
    return p, u, x.c * p.sum() + x.nl * u.sum() + x.su * v.sum()


def _in(net, i, T, c):
    """Column c = (p, u, k) of unit i as (a, k, (p, u)), its output on its own bus's rows."""
    a = np.zeros(net.nb * T)
    a[net.bus[i] * T : (net.bus[i] + 1) * T] = c[0]
    return a, c[2], c[:2]


def _oc(x, T, lam, cap=None):
    """min c_g(x) - lam'p over X_g: the best schedule, and a lower bound on the minimum.

    The integer program reads the unit's rows directly, as _om does, as a bound route of
    _mi, and v is its mip_dual_bound, never its incumbent. The commitment found is then
    held and the dispatch re-solved by simplex over _pl's polytope, so the column is a
    vertex of that polytope: exactly feasible, and drawn from a finite set.
    """
    A, b = _rw(x, T, cap)
    Ae, be = _eq(x, T)
    lb, ub = _fx(x, T)
    res, _ag, v, _st = _mi(np.r_[x.c - lam, np.full(T, x.nl), np.full(T, x.su), np.zeros(T)],
                           np.r_[np.zeros(T), np.ones(3 * T)], lb, ub, A, b, Ae, be,
                           "a unit has no self-schedule", True)
    u = np.rint(res.x[T : 2 * T])
    q = _pl(x, T, u, *_vw(x, u), cap)
    p = linprog(x.c - lam, A_ub=q[0], b_ub=q[1], bounds=(None, None), method="highs-ds").x
    return _col(x, T, np.where(np.abs(p) < 1e-9, 0.0, p), u, cap), v


def _rm(g, d, net, K, nt):
    """Restricted master over K; nt = 0 reads the solver's dual, nt = d.size selects on the face.

    Convexity rows come first and balance rows last, as _px reads them; _nw appends the
    network, whose flows stay in the master whole. Returns z, weights, w, pi, tag.
    """
    G = len(g)
    o = np.cumsum([0] + [len(q) for q in K])
    n = int(o[-1])
    c = np.array([k for q in K for (_, k, _) in q])
    ei, ec, ev = [], [], []
    for i in range(G):
        for j, (a, _, _) in enumerate(K[i]):
            t = np.flatnonzero(a)
            ei.extend([i, *(G + t)])
            ec.extend([o[i] + j] * (1 + len(t)))
            ev.extend([1.0, *a[t]])
    q = _nw(net, d.shape[1], n, csc_array((0, n)), np.zeros(0),
            csc_array((ev, (ei, ec)), shape=(G + d.size, n)), c, np.zeros(n), None, None)
    why = []
    res = _px(q[3], q[0], q[1], q[2], np.r_[np.ones(G), d.ravel()], q[4], q[5], nt, why)
    if res is None:
        raise ValueError(f"the restricted master did not solve [{why[0]}]")
    return res[0], res[1][:n], res[2][G:], res[2][:G], res[3]


def cg(g, d, cap=None, net=None, s=None, K=None, eps=1e-9):
    """Convex hull price by column generation; the price is repriced before it is reported.

    min sum_g sum_k c_g^k y_g^k  s.t.  sum_g sum_k p_g^k y_g^k = d  (lam),
                                       sum_k y_g^k = 1 per unit    (pi),  y >= 0.

    INPUT   g,d,cap,net .. the market, as hc takes it
            s ............ a clearing whose schedules seed the master; uc's when None
            K ............ seed schedules per unit, [(p, u), ...], in place of s
            eps .......... certificate tolerance, relative to the master value
    OUTPUT  Dw: Sol with z, hull output and commitment, price, tag, gap and lb; the counts;
            rho, each unit's reduced-cost bound at the reported price; and tau.

    _gen states the step and the stopping rule. Per iteration: G integer programs over 4T
    columns, and one master LP over the columns generated so far.
    """
    g, d, net = ck(g, d, net)
    G, T = len(g), d.shape[1]
    cq = [None if cap is None else cap[i] for i in range(G)]
    if K is None:
        s = uc(g, d, cap, net) if s is None else s
        K = [[(s.p[i], s.u[i])] for i in range(G)]
    K = [[_in(net, i, T, _col(x, T, p, u, cq[i])) for p, u in K[i]] for i, x in enumerate(g)]

    def oc(i, w):
        c, v = _oc(g[i], T, w[net.bus[i] * T : (net.bus[i] + 1) * T], cq[i])
        return _in(net, i, T, c), v

    z, y, w, st, V, k, ng, nr, rho, tau = _gen(
        G, lambda K, sel: _rm(g, d, net, K, d.size if sel else 0), oc, K, eps)
    lam = w.reshape(d.shape)
    o = np.cumsum([0] + [len(q) for q in K])
    P, U = np.zeros((G, T)), np.zeros((G, T))
    for i in range(G):
        for j, (_, _, (p, u)) in enumerate(K[i]):
            P[i] += y[o[i] + j] * p
            U[i] += y[o[i] + j] * u
    lb = float((lam * d).sum() + sum(V) + _nq(net, T, lam))
    return Dw(Sol(z, np.where(np.abs(P) < 1e-9, 0.0, P), U, lam, st,
                  (z - lb) / max(1.0, abs(z)), lb),
              k, ng, nr, int(o[-1]), int((y > 1e-9).sum()), rho, tau)


def _ub(x, T):
    """Unit x's own rows from pglib_uc's builder: x alone, its demand rows (2) dropped.

    _sy writes demand first, as the first T equality rows, and a zero reserve requirement
    writes no row (3), so what remains is (4) to (23) for this unit and nothing else.
    """
    c, A, b, Ae, be, lb, ub, it = _psy({"T": T, "th": [x], "re": [],
                                        "demand": np.zeros(T), "reserves": np.zeros(T)})
    return c, csr_array(A), b, csr_array(Ae)[T:], be[T:], lb, ub, it


def _op(q, pm, T, jr, w):
    """min c'x - lam'(pg + pm ug) - sig'rg[jr] over one pglib unit, then its vertex.

    As _oc: v is the bound route's mip_dual_bound, and the column is re-solved by simplex
    with the integers held, so it is a vertex of that polytope.
    """
    c, A, b, Ae, be, lb, ub, it = q
    f = c.copy()
    f[T : 2 * T] -= w[:T]
    f[3 * T : 4 * T] -= pm * w[:T]
    f[2 * T + jr] -= w[T:]
    res, _ag, v, _st = _mi(f, it, lb, ub, A, b, Ae, be, "a unit has no self-schedule", True)
    h = it > 0
    lo, hi = lb.copy(), ub.copy()
    lo[h] = hi[h] = np.rint(res.x[h])
    y = linprog(f, A_ub=A, b_ub=b, A_eq=Ae, b_eq=be, bounds=np.c_[lo, hi],
                method="highs-ds").x
    return (np.r_[y[T : 2 * T] + pm * y[3 * T : 4 * T], y[2 * T + jr]], float(c @ y), y), v


def _rp(D, jr, K, sel):
    """pglib's restricted master: unit columns, renewables whole, reserve with a surplus.

    Rows: convexity, then demand (2), then reserve (3) as an equality with a surplus column
    as pglib_uc.px writes it; demand and reserve are priced together, last, as px prices
    them. A reserve dual is clipped at zero, where its surplus column holds it.
    """
    T, G, W = D["T"], len(K), len(D["re"])
    o = np.cumsum([0] + [len(q) for q in K])
    n, m = int(o[-1]), T + len(jr)
    ei, ec, ev = [], [], []
    for i in range(G):
        for j, (a, _, _) in enumerate(K[i]):
            t = np.flatnonzero(a)
            ei.extend([i, *(G + t)])
            ec.extend([o[i] + j] * (1 + len(t)))
            ev.extend([1.0, *a[t]])
    for x in range(W):
        ei.extend(G + np.arange(T))
        ec.extend(n + x * T + np.arange(T))
        ev.extend(np.ones(T))
    ei.extend(G + T + np.arange(len(jr)))
    ec.extend(n + W * T + np.arange(len(jr)))
    ev.extend(-np.ones(len(jr)))
    N = n + W * T + len(jr)
    lo = np.concatenate([np.zeros(n), *[np.asarray(x["power_output_minimum"], dtype=float)
                                         * np.ones(T) for x in D["re"]], np.zeros(len(jr))])
    hi = np.concatenate([np.full(n, np.inf), *[np.asarray(x["power_output_maximum"], dtype=float)
                                               * np.ones(T) for x in D["re"]],
                         np.full(len(jr), np.inf)])
    c = np.r_[[k for q in K for (_, k, _) in q], np.zeros(N - n)]
    why = []
    res = _px(c, csc_array((0, N)), np.zeros(0), csc_array((ev, (ei, ec)), shape=(G + m, N)),
              np.r_[np.ones(G), D["demand"], D["reserves"][jr]], lo, hi, m if sel else 0, why)
    if res is None:
        raise ValueError(f"the restricted master did not solve [{why[0]}]")
    w = np.asarray(res[2][G:], dtype=float)
    w[T:] = np.maximum(w[T:], 0.0)
    return res[0], res[1][:n], w, res[2][:G], res[3]


def cgp(D, gap=0.01, eps=1e-9):
    """Convex hull energy and reserve prices of a pglib-uc instance, by column generation.

    The master couples the thermal units through demand (2) and reserve (3); renewables
    are bounded columns of the master itself. A unit's column is one feasible schedule of
    (4) to (23) carrying its energy pg + pm ug, its reserve rg, and its cost. The seed is
    pglib_uc's own clearing at gap, the reference script's 1%: any feasible schedule seeds
    the master, and the certificate does not depend on it.

    lb is L(lam, sig) = lam'd + sig'r + sum_g v_g + sum_w min over [lo, hi] of -lam'pw,
    the Lagrangian dual value at the reported prices. Per iteration: G integer programs
    over one unit's pglib columns, and one master LP.
    """
    T, th = D["T"], D["th"]
    G = len(th)
    jr = np.flatnonzero(np.asarray(D["reserves"], dtype=float) > 0.0)
    res, _q = _run(D, gap)
    Q = [_ub(x, T) for x in th]
    pm = [float(x["power_output_minimum"]) for x in th]
    S = [len(x["startup"]) for x in th]
    L = [len(x["piecewise_production"]) for x in th]
    od = 6 * G * T + np.cumsum([0] + [s * T for s in S])
    ol = od[-1] + np.cumsum([0] + [n * T for n in L])
    K = []
    for i, x in enumerate(th):
        c, A, b, Ae, be, lb, ub, it = Q[i]
        y = np.concatenate([*[res.x[k * G * T + i * T : k * G * T + (i + 1) * T]
                              for k in range(6)],
                            res.x[od[i] : od[i + 1]], res.x[ol[i] : ol[i + 1]]])
        y[it > 0] = np.rint(y[it > 0])
        if ((A @ y > b + 1e-6).any() or np.abs(Ae @ y - be).max() > 1e-6
                or (y < lb - 1e-6).any() or (y > ub + 1e-6).any()):
            raise ValueError("a seed column breaks a unit's own limits")
        a = np.r_[y[T : 2 * T] + pm[i] * y[3 * T : 4 * T], y[2 * T + jr]]
        K.append([(a, float(c @ y), y)])
    z, y, w, st, V, k, ng, nr, rho, tau = _gen(
        G, lambda K, sel: _rp(D, jr, K, sel), lambda i, w: _op(Q[i], pm[i], T, jr, w), K, eps)
    lam, pr = w[:T], np.zeros(T)
    pr[jr] = w[T:]
    lb = float(lam @ D["demand"] + pr @ D["reserves"] + sum(V)
               + sum(np.minimum(-lam * np.asarray(x["power_output_minimum"], dtype=float),
                                -lam * np.asarray(x["power_output_maximum"], dtype=float)).sum()
                     for x in D["re"]))
    return Dp(z, lb, lam, pr, st, k, ng, nr, int(sum(len(q) for q in K)), int((y > 1e-9).sum()),
              rho, tau)
