# Two-stage stochastic clearing: one commitment, many demands.
#
# models/joint.py clears one demand. Here the demand is a scenario tree one branch deep:
# the commitment is chosen before the scenario is known and is common to all of them, and
# dispatch, storage and flows answer each scenario separately. That is the standard
# here-and-now / wait-and-see split, and it is what "the price scenarios are exogenous"
# stopped short of: the system itself now carries the uncertainty.
#
# The scenario blocks are joint's system repeated, so nothing about a single scenario is
# rewritten here. What is new is the non-anticipativity that binds the commitment columns
# across blocks, the probability weights, and an optional Rockafellar-Uryasev tail on the
# scenario costs.
#
# A weighted balance row has a weighted dual: scenario s's balance enters the objective
# already multiplied by p_s, so its dual is p_s times that scenario's price. px divides it
# back out, and refuses a zero probability rather than dividing by it.
#
# LEGEND
#   Sc           : one clearing: cost, commitment, per-scenario dispatch, risk, prices
#   _bd          : block-diagonal stack of one system per scenario
#   _na          : the rows that hold the commitment common across scenarios
#   _rk          : the CVaR epigraph columns and rows
#   ck           : validate a stochastic market
#   cl           : clear it as one integer program
#   _held        : the program under (w, al) with the cleared integers held by bounds
#   lmp          : hold the commitment, re-dispatch every scenario, read the balance duals
#   Cv,cvd       : the duals of the risk-averse program itself, integers held
#   _te          : CVaR's dual weights in closed form: the risk envelope's maximiser
#   S,G,R,T,B    : scenarios, units, resources, periods, buses
#   pr,w,al      : scenario probabilities, risk weight, CVaR confidence
#   ns,es,ms     : columns, equality rows and inequality rows in one scenario block
#   cs           : scenario s's own cost vector over its own columns
#   zt,xi        : the CVaR level and the per-scenario excess above it
#   y,mu,om      : raw balance duals; epigraph multipliers; om = (1 - w) pr + mu
#   lam,th       : y / om, the scenario price where om > 0; the envelope's weights
#   q            : scenario costs at the solution
#   sm,md        : whether the storage mode is common across scenarios, and its held values
#   gap,lb       : achieved relative gap and certified cost lower bound
#   sq,why       : the clearing's own certificate, and why a solve failed

import numpy as np
from scipy.sparse import block_diag, csc_array, csr_array, hstack, vstack

from models.joint import _sy, ck as _jck
from models.uc_price import _mi, _px

from typing import NamedTuple


class Sc(NamedTuple):
    """One stochastic clearing.

    z is the objective of the program that produced this result, mean the
    probability-weighted cost and cv the CVaR of cost at al; with w = 0 the objective is the
    mean. q carries each scenario's own cost. p, sc, sd, se and sm are indexed by scenario
    first. pi is (S, B, T), each scenario's own price with its probability weight divided
    out.

    A field a route does not compute is nan, not a stand-in value: cl prices nothing and
    returns pi as nan, and lmp fixes no risk tail and returns cv as nan. z therefore names
    different programs on the two routes, which is why the risk weight belongs with the
    result that was minimised under it and not with the one that was priced.

    gap and lb carry the solve certificate as numbers. On the integer clearing they are
    the achieved relative gap and certified cost lower bound. On the linear re-dispatch
    gap is zero and lb is its determined objective.
    """

    z: float
    mean: float
    cv: float
    q: np.ndarray
    u: np.ndarray
    p: np.ndarray
    sc: np.ndarray
    sd: np.ndarray
    se: np.ndarray
    sm: np.ndarray
    pi: np.ndarray
    st: str = ""
    gap: float = 0.0
    lb: float = float("nan")


def ck(g, st, d, pr=None, net=None, w=0.0, al=0.95):
    """Validate a stochastic market: joint's checks per scenario, plus the risk parameters."""
    d = np.asarray(d, dtype=float)
    if d.ndim == 2:
        d = d[:, None, :]
    if d.ndim != 3 or not d.size:
        raise ValueError("demand must be (scenarios, buses, periods)")
    S = d.shape[0]
    pr = np.full(S, 1.0 / S) if pr is None else np.asarray(pr, dtype=float)
    if pr.shape != (S,):
        raise ValueError("one probability per scenario")
    if not np.isfinite(pr).all() or (pr <= 0).any():
        raise ValueError("every scenario probability must be positive")
    if abs(float(pr.sum()) - 1.0) > 1e-9:
        raise ValueError("scenario probabilities must sum to one")
    if not 0.0 <= float(w) <= 1.0:
        raise ValueError("the risk weight must lie in [0, 1]")
    if not 0.0 <= float(al) < 1.0:
        raise ValueError("the CVaR confidence must lie in [0, 1)")
    out = [_jck(g, st, d[s], net) for s in range(S)]
    g, stt, net = out[0][0], out[0][1], out[0][3]
    return g, stt, np.array([q[2] for q in out]), net, pr, float(w), float(al)


def _bd(g, st, d, net, pr, f):
    """One joint system per scenario, stacked block-diagonally with the balance rows last.

    _px reads the balance rows off the end of the equality block, so the per-scenario
    balances are gathered there rather than left inside their own blocks.
    """
    S, B, T = len(pr), net.nb, d.shape[2]
    q = [_sy(g, st, d[s], net, f) for s in range(S)]
    ns, es = q[0][0].size, q[0][4].size
    nb = B * T
    A = block_diag([csc_array(y[1]) for y in q], format="csc")
    b = np.concatenate([np.asarray(y[2], dtype=float) for y in q])
    Ae = [csr_array(y[3]) for y in q]
    be = [np.asarray(y[4], dtype=float) for y in q]
    Ae = vstack([block_diag([x[: es - nb, :] for x in Ae], format="csc"),
                 block_diag([x[es - nb :, :] for x in Ae], format="csc")], format="csc")
    be = np.concatenate([np.concatenate([y[: es - nb] for y in be]),
                         np.concatenate([y[es - nb :] for y in be])])
    c = np.concatenate([pr[s] * np.asarray(q[s][0], dtype=float) for s in range(S)])
    lb = np.concatenate([np.asarray(y[5], dtype=float) for y in q])
    ub = np.concatenate([np.asarray(y[6], dtype=float) for y in q])
    it = np.concatenate([np.asarray(y[7], dtype=float) for y in q])
    cs = [np.asarray(q[s][0], dtype=float) for s in range(S)]
    return c, A, b, Ae, be, lb, ub, it, q[0][8], q[0][9], ns, es, nb, cs


def _na(S, ns, T, ou, sm, os):
    """Rows holding the commitment, and optionally the storage mode, common to every scenario."""
    ri, ci, va, r = [], [], [], 0
    blk = [(o + T, 3 * T) for o in ou] + ([(o + 3 * T, T) for o in os] if sm else [])
    for s in range(1, S):
        for o, k in blk:
            for j in range(k):
                ri.extend([r, r])
                ci.extend([o + j, s * ns + o + j])
                va.extend([1.0, -1.0])
                r += 1
    return csc_array((va, (ri, ci)), shape=(r, S * ns)), np.zeros(r)


def _rk(n, S, ns, cs):
    """Append the CVaR level and per-scenario excess, and the rows that define them.

    zt is the level; xi_s is the excess of scenario s's own cost over it. The rows are
    cs . x_s - zt - xi_s <= 0 with xi_s >= 0, the Rockafellar-Uryasev epigraph, so that
    zt + sum_s p_s xi_s / (1 - al) is the CVaR of cost at al.
    """
    ri, ci, va = [], [], []
    for s in range(S):
        k = np.nonzero(cs[s])[0]
        ri.extend([s] * len(k))
        ci.extend(s * ns + k)
        va.extend(cs[s][k])
        ri.extend([s, s])
        ci.extend([n, n + 1 + s])
        va.extend([-1.0, -1.0])
    return csc_array((va, (ri, ci)), shape=(S, n + 1 + S)), np.zeros(S)


def _pad(A, n):
    """Widen a sparse block to n columns."""
    A = csc_array(A)
    return A if A.shape[1] == n else csc_array(hstack([A, csc_array((A.shape[0], n - A.shape[1]))]))


def _sys(g, st, d, net, pr, w, al, f, sm):
    """The whole stochastic system: scenario blocks, non-anticipativity and the risk tail."""
    S, T = len(pr), d.shape[2]
    c, A, b, Ae, be, lb, ub, it, ou, os, ns, es, nb, cs = _bd(g, st, d, net, pr, f)
    n = S * ns
    N, bn = _na(S, ns, T, ou, sm, os)
    if w > 0.0:
        Ar, br = _rk(n, S, ns, cs)
        m = n + 1 + S
        c = np.r_[(1.0 - w) * c, w, w * pr / (1.0 - al)]
        lb = np.r_[lb, -np.inf, np.zeros(S)]
        ub = np.r_[ub, np.inf, np.full(S, np.inf)]
        it = np.r_[it, 0.0, np.zeros(S)]
        A = vstack([_pad(A, m), Ar], format="csc")
        b = np.r_[b, br]
        Ae = _pad(Ae, m)
        N = _pad(N, m)
    Ae = vstack([Ae, N], format="csc")
    be = np.r_[be, bn]
    return c, A, b, Ae, be, lb, ub, it, ou, os, ns, es, nb, cs


def _order(Ae, be, nb, S, nna):
    """Move the S x nb balance rows to the end of the equality block, ahead of nothing."""
    Ae = csr_array(Ae)
    e = Ae.shape[0]
    k = e - nna - S * nb
    ix = np.r_[np.arange(k), np.arange(e - nna, e), np.arange(k, e - nna)]
    return csc_array(Ae[ix, :]), be[ix]


def _out(G, R, T, S, ns, y, ou, os):
    """Split a solved vector into the shared commitment and each scenario's own dispatch."""
    p = np.zeros((S, G, T))
    u = np.zeros((S, G, T))
    q = np.zeros((4, S, R, T))
    for s in range(S):
        o = s * ns
        for i in range(G):
            p[s, i] = y[o + ou[i] : o + ou[i] + T]
            u[s, i] = y[o + ou[i] + T : o + ou[i] + 2 * T]
        for j in range(R):
            for k in range(4):
                q[k, s, j] = y[o + os[j] + k * T : o + os[j] + (k + 1) * T]
    return np.where(np.abs(p) < 1e-9, 0.0, p), u, q


def cl(g, st, d, pr=None, net=None, w=0.0, al=0.95, sm=False):
    """Clear one commitment against every scenario, risk-neutral or with a CVaR tail."""
    g, st, d, net, pr, w, al = ck(g, st, d, pr, net, w, al)
    S, G, R, T = len(pr), len(g), len(st), d.shape[2]
    c, A, b, Ae, be, lb, ub, it, ou, os, ns, _es, _nb, cs = _sys(
        g, st, d, net, pr, w, al, True, sm)
    res, ag, bd, sq = _mi(c, it, lb, ub, A, b, Ae, be,
                          "this demand did not clear stochastically")
    y = np.asarray(res.x, dtype=float)
    p, u, q = _out(G, R, T, S, ns, y, ou, os)
    z = np.array([float(cs[s] @ y[s * ns : (s + 1) * ns]) for s in range(S)])
    return Sc(float(res.fun), float(pr @ z), _cv(z, pr, al), z, np.rint(u[0]), p,
              q[0], q[1], q[2], np.rint(q[3]), np.full((S, net.nb, T), np.nan), sq,
              ag, bd)


def _cv(z, pr, al):
    """CVaR of the scenario costs at al, by the weighted tail, splitting the atom at the
    quantile. This does not read the epigraph columns, so it is an independent reading."""
    k = np.argsort(z)
    y, p = z[k], pr[k]
    c = np.cumsum(p)
    j = int(np.searchsorted(c, al, side="left"))
    j = min(j, len(y) - 1)
    m = 1.0 - al
    if m <= 0:
        return float(y[-1])
    q = np.r_[c[j] - al, p[j + 1 :]]
    return float((q @ y[j:]) / m)


def _held(g, st, d, s, pr, net, w, al, sm):
    """The program under (w, al) with every integer the clearing s fixed held by its bounds.

    The commitment is held in every scenario block, and so is the storage mode, whether or
    not sm tied it across scenarios: leaving an integer free would price a relaxation of
    the program that cleared rather than that program. The balance rows are moved last.
    """
    S, G, R, T = len(pr), len(g), len(st), d.shape[2]
    u = np.atleast_2d(np.asarray(s.u, dtype=float)).reshape(G, T)
    md = np.asarray(s.sm, dtype=float).reshape(S, R, T) if R else np.zeros((S, 0, T))
    if not np.isin(u, [0.0, 1.0]).all() or not np.isin(md, [0.0, 1.0]).all():
        raise ValueError("the held commitment and mode must be binary")
    c, A, b, Ae, be, lb, ub, _it, ou, os, ns, es, nb, cs = _sys(
        g, st, d, net, pr, w, al, False, sm)
    lb, ub = np.array(lb, dtype=float), np.array(ub, dtype=float)
    for q in range(S):
        for i in range(G):
            v = np.r_[u[i, 0] - g[i].u0, np.diff(u[i])]
            o = q * ns + ou[i]
            for k, y in enumerate((u[i], np.maximum(v, 0.0), np.maximum(-v, 0.0)), start=1):
                lb[o + k * T : o + (k + 1) * T] = y
                ub[o + k * T : o + (k + 1) * T] = y
        for j in range(R):
            o = q * ns + os[j]
            lb[o + 3 * T : o + 4 * T] = md[q, j]
            ub[o + 3 * T : o + 4 * T] = md[q, j]
    nna = Ae.shape[0] - (es * S)
    Ae, be = _order(Ae, be, nb, S, nna)
    return c, A, b, Ae, be, lb, ub, ou, os, ns, nb, cs, u, md


def lmp(g, st, d, s, pr=None, net=None, sm=False):
    """Hold the cleared commitment, re-dispatch every scenario, and read the balance duals.

    Every integer column is pinned by its own bounds, the commitment and the storage mode
    alike, so what remains is a linear program over dispatch, storage flows and the
    network. The mode is pinned whether or not sm tied it across scenarios: leaving any
    integer free would price a relaxation of the program that cleared rather than that
    program, and its objective could fall below the clearing it is meant to price.

    Scenario s's balance row carries the weight p_s, so its dual is p_s times that
    scenario's price; the weight is divided back out here. The commitment is common, so a
    price is still one price per bus and period in each scenario.

    The re-dispatch is risk-neutral whatever risk chose the commitment. Under a CVaR tail
    the balance dual of the program cl minimised carries om_s = (1 - w) p_s + mu_s, mu_s
    being scenario s's epigraph multiplier, and cvd reads it from that program. With the
    integers held, both programs minimise each scenario's cost wherever om_s > 0, so
    y_s / om_s and this price lie on the same scenario dual face: docs/RISK.md derives it
    and the tests check it. Settling a risk-averse commitment at the duals of its
    expected-cost re-dispatch is the market design; z is that program's objective, not the
    one cl minimised, and cv is returned as nan because no confidence applies to it.
    """
    g, st, d, net, pr, _w, _al = ck(g, st, d, pr, net, 0.0, 0.95)
    S, G, R, T, B = len(pr), len(g), len(st), d.shape[2], net.nb
    c, A, b, Ae, be, lb, ub, ou, os, ns, nb, cs, u, md = _held(
        g, st, d, s, pr, net, 0.0, 0.95, sm)
    why = []
    res = _px(c, A, b, Ae, be, lb, ub, S * nb, why)
    if res is None:
        raise ValueError(f"the held commitment did not re-dispatch [{why[0]}]")
    y = np.asarray(res[1], dtype=float)
    p, _u, q = _out(G, R, T, S, ns, y, ou, os)
    pi = np.asarray(res[2], dtype=float)[-S * nb :].reshape(S, B, T)
    pi = pi / pr[:, None, None]
    z = np.array([float(cs[k] @ y[k * ns : (k + 1) * ns]) for k in range(S)])
    return Sc(res[0], float(pr @ z), np.nan, z, u, p,
              q[0], q[1], q[2], md, pi, res[3], 0.0, res[0])


class Cv(NamedTuple):
    """The risk-averse clearing's own program with its integers held: primal and duals.

    z is that program's objective, (1 - w) E[C] + w (zt + E[xi] / (1 - al)); q the
    scenario costs of its dispatch p; zt and xi the CVaR level and the excesses. y is the
    raw dual of each scenario's balance rows, (S, B, T): the derivative of z in that
    scenario's demand, no probability divided out. mu is each epigraph row's multiplier and
    om = (1 - w) pr + mu the weight the program puts on each scenario's cost; om sums to
    one. lam = y / om is the scenario price wherever om > 0 and nan where om = 0: there the
    program puts no weight on the scenario's cost, its balance dual is zero, and no
    normalisation recovers a price from it.
    """

    z: float
    q: np.ndarray
    p: np.ndarray
    zt: float
    xi: np.ndarray
    y: np.ndarray
    mu: np.ndarray
    om: np.ndarray
    lam: np.ndarray
    st: str


def cvd(g, st, d, s, pr=None, net=None, w=0.0, al=0.95, sm=False):
    """The duals of the program cl minimised under (w, al), its integers held at s.

    The epigraph rows C_s - zt - xi_s <= 0 are written as equalities with a surplus column
    each, so their multipliers come out of _px's one selected dual vector together with
    the balance duals, and mu_s = -dual >= 0. KKT then gives, per scenario block, that the
    block's own cost weighted by om_s is priced by y_s. Stationarity in zt gives
    sum_s mu_s = w, and in xi_s, mu_s <= w p_s / (1 - al). lam = y / om is nan where
    om_s <= 1e-9, a weight read as zero.
    """
    g, st, d, net, pr, w, al = ck(g, st, d, pr, net, w, al)
    S, G, R, T, B = len(pr), len(g), len(st), d.shape[2], net.nb
    c, A, b, Ae, be, lb, ub, ou, os, ns, nb, cs, _u, _md = _held(
        g, st, d, s, pr, net, w, al, sm)
    n, k = S * ns, Ae.shape[0] - S * nb
    if w > 0.0:
        m = len(c) + S
        E = csr_array(hstack([csr_array(A)[-S:], csc_array(np.eye(S))]))
        A, b = _pad(csr_array(A)[:-S], m), b[:-S]
        Ae = csr_array(Ae)
        Ae = vstack([_pad(Ae[:k], m), E, _pad(Ae[k:], m)], format="csc")
        be = np.r_[be[:k], np.zeros(S), be[k:]]
        c, lb, ub = np.r_[c, np.zeros(S)], np.r_[lb, np.zeros(S)], np.r_[ub, np.full(S, np.inf)]
    why = []
    res = _px(c, A, b, Ae, be, lb, ub, S * nb, why)
    if res is None:
        raise ValueError(f"the held risk-averse program did not solve [{why[0]}]")
    x, e = np.asarray(res[1], dtype=float), np.asarray(res[2], dtype=float)
    y = e[-S * nb :].reshape(S, B, T)
    mu = -e[k : k + S] if w > 0.0 else np.zeros(S)
    om = (1.0 - w) * pr + mu
    lam = np.full(y.shape, np.nan)
    h = om > 1e-9
    lam[h] = y[h] / om[h, None, None]
    p, _u, _q = _out(G, R, T, S, ns, x, ou, os)
    q = np.array([float(cs[j] @ x[j * ns : (j + 1) * ns]) for j in range(S)])
    return Cv(res[0], q, p, float(x[n]) if w > 0.0 else np.nan,
              x[n + 1 : n + 1 + S] if w > 0.0 else np.zeros(S), y, mu, om, lam, res[3])


def _te(q, pr, al):
    """CVaR's dual weights at the costs q: the maximiser of th'q over the risk envelope
    0 <= th_s <= p_s / (1 - al), sum th = 1. It fills the envelope from the dearest
    scenario down, so th'q is the weighted upper tail _cv computes; mu = w th wherever the
    tail's boundary does not fall on a tie.
    """
    th, m = np.zeros(len(q)), 1.0 - al
    for j in np.argsort(-np.asarray(q, dtype=float), kind="stable"):
        th[j] = min(pr[j], m)
        m -= th[j]
    return th / (1.0 - al)
