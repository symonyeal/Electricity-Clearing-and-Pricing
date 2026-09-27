# Storage cleared inside the market: what it changes, and who is paid for it.
#
# models/joint.py clears thermal units and storage in one program and prices the result by
# pinning the integers. This module does not rewrite that program. It reads joint's rows
# through _sy, _sr, _se and _sb, as stoch.py does, and adds four things:
#
#   1. the storage resource under three descriptions of its feasible set, the thermal
#      commitment integer in all three: X, binary modes; R, the modes relaxed to the
#      per-period cut c/C + d/D <= 1; H = conv(X), by Balas' union over the 2^T mode
#      patterns. X is inside H and H inside R, so z_X >= z_H >= z_R;
#   2. two market designs for the same resource: its price-taking schedule imposed on the
#      clearing in full, and that schedule offered as a market/bid.py curve and accepted
#      where the cleared price supports it;
#   3. settlement at the pinned-integer price: load payment, unit profit, make-whole and
#      lost opportunity, storage profit and lost opportunity, and congestion rent, the
#      last also from line flows reconstructed from nodal injections alone;
#   4. seven small cases, each built to move one of those quantities.
#
# The settlement identity, the flow reconstruction and the storage profit bound are
# mathematics. Pinning the integers to price, the reference bus of the energy/congestion
# split, and the curve's reference price are market-design assumptions, named where made.
#
# LEGEND
#   Cl,St      : one clearing, and one settlement of it at one price
#   _ext       : joint's system with columns and rows appended, balance rows kept last
#   _hb        : one resource's hull H as Balas columns and rows
#   _sys       : joint's system under one storage description or market design
#   _ub        : a resource's best profit at a price over X, R, or its held-mode polytope
#   _fl        : DC line flows from nodal injections, without the angle columns
#   _out       : a solved vector split into units and resources, with its true cost
#   cl,px,stl  : clear; price with the integers held; settle
#   ps         : a resource's price-taking schedule against a price it does not move
#   _net,_mkt  : the three-bus network, and the common fleet and load
#   _sur       : the two-period surplus market of s6 and s7
#   s1..s7     : the seven cases
#   sy         : a system as the list [c, A, b, Ae, be, lb, ub, it]
#   how        : "X", "R", "H"; "fix", a held schedule; "bid", a curve offer
#   g,st,d,net : units, storage resources, nodal demand, network
#   G,R,T,B    : units, resources, periods, buses
#   ou,os      : first column of each unit's and each resource's block in joint's system
#   nb         : the first balance row          n2 : columns appended
#   c2,lb2,ub2 : the appended columns' costs and bounds
#   Ai,bi,Aq,bq: rows appended over all columns, inequalities and equalities
#   Bb         : the appended columns' coefficients in the balance rows
#   m          : one mode pattern               q : held schedules (c, d, e, m), or positions
#   ref,kk,sp  : a curve's reference price, step count and spread, as market/bid.py names
#                the last two k and sp
#   pi         : price per bus and period       L : load payment
#   r,mw,loc   : unit profit, make-whole, lost opportunity (uc_price.pay)
#   rs,ls      : storage profit, and its lost opportunity against X
#   ov         : how much R's best profit exceeds X's at the same price
#   rent,rf    : congestion rent as a payment difference, and from reconstructed flows
#   en,cn      : storage profit at the reference bus's price, and the congestion remainder
#   z          : the true cost of a dispatch, unit costs plus storage throughput cost

from itertools import product
from typing import NamedTuple

import numpy as np
from scipy.sparse import block_diag, csc_array, csr_array, hstack, vstack

from market.bid import curve
from models.joint import S, _sb, _se, _sr, _sy, ck
from models.uc_price import U, Net, _mi, _px, pay


class Cl(NamedTuple):
    """One clearing: joint's Jt fields, the true cost z of its dispatch, and the objective.

    obj is what the program minimised. Under a curve offer it carries bid prices, not the
    resource's cost, so welfare is read from z and never from obj. sm is nan under H,
    whose weights are not modes. st, gap and lb are the solve's certificate, as uc_price's.
    """

    z: float
    obj: float
    p: np.ndarray
    u: np.ndarray
    sc: np.ndarray
    sd: np.ndarray
    se: np.ndarray
    sm: np.ndarray
    st: str
    gap: float
    lb: float


class St(NamedTuple):
    """One settlement of a clearing at a price; every figure is money over the horizon.

    L is what load pays; r, mw and loc each unit's profit, make-whole and lost opportunity;
    rs and ls each resource's profit and lost opportunity against X; ov how far R's best
    profit exceeds X's at this price; rent the congestion rent as a payment difference, rf
    the same from reconstructed flows; en and cn the storage profit at the reference bus's
    price and the congestion remainder.
    """

    z: float
    L: float
    r: np.ndarray
    mw: np.ndarray
    loc: np.ndarray
    rs: np.ndarray
    ls: np.ndarray
    ov: np.ndarray
    rent: float
    rf: float
    en: np.ndarray
    cn: np.ndarray


def _ext(sy, B, T, c2, lb2, ub2, Ai, bi, Aq, bq, Bb):
    """joint's system with n2 columns appended.

    Ai x <= bi and Aq x = bq are new rows over all columns; Bb holds the new columns'
    coefficients in the balance rows. The new equalities go before the balance rows, which
    stay last, as _px reads them.
    """
    c, A, b, Ae, be, lb, ub, it = sy
    n2, nb = len(c2), Ae.shape[0] - B * T
    A = vstack([hstack([csr_array(A), csc_array((A.shape[0], n2))]), csc_array(Ai)])
    Y = csr_array(hstack([csr_array(Ae), vstack([csc_array((nb, n2)), csc_array(Bb)])]))
    Ae = vstack([Y[:nb], csc_array(Aq), Y[nb:]])
    return (np.r_[c, c2], csc_array(A), np.r_[b, bi], csc_array(Ae), np.r_[be[:nb], bq, be[nb:]],
            np.r_[lb, lb2], np.r_[ub, ub2], np.r_[it, np.zeros(n2)])


def _hb(x, T):
    """One resource's hull H = conv(X): Balas' union of its 2^T mode-pattern polytopes.

    P_m is joint's own rows with the mode fixed at m: _sr's rows, _se's recursion, _sb's
    bounds. Each is a polytope, so y in conv(union P_m) iff y = sum_m y^m with
    y^m in lam_m P_m, lam_m >= 0, sum_m lam_m = 1 (Balas 1998). Columns per pattern are
    [c|d|e|lam]. Returns the pattern rows, the convexity row, the columns' net injection
    d - c by period, and their costs.
    """
    A, b = _sr(x, T)
    Ae, be = _se(x, T)
    lb, ub = _sb(x, T)
    n, h = 3 * T, lb[: 3 * T] > 0
    P = [np.array(m) for m in product((0.0, 1.0), repeat=T)]
    Ai = block_diag([csr_array(np.block([[A[:, :n], -(b - A[:, n:] @ m)[:, None]],
                                         [np.eye(n), -ub[:n, None]],
                                         [-np.eye(n)[h], lb[:n][h, None]]])) for m in P],
                    format="csr")
    Aq = block_diag([csr_array(np.c_[Ae[:, :n], -be[:, None]]) for _ in P], format="csr")
    cv = np.tile(np.r_[np.zeros(n), 1.0], len(P))
    Bb = np.tile(np.c_[-np.eye(T), np.eye(T), np.zeros((T, T + 1))], len(P))
    k = np.tile(np.r_[np.full(2 * T, x.k), np.zeros(T + 1)], len(P))
    return Ai, Aq, cv, Bb, k


def _sys(g, st, d, net, how, f, q=None, ref=None, kk=1, sp=0.0):
    """joint's system under one storage description or market design; f keeps integers.

    X is joint's system itself. R clears the mode columns' integrality and leaves the cut
    row _sr carries. H takes the resources out of joint's system and appends _hb's columns
    in their place. fix holds each resource's schedule q[j] = (c, d, e, m) by its bounds.
    bid offers each period's position q[j][t] = d - c as market/bid.py's curve around
    ref[j][t]: the offered side is a sum of slices, a slice offered at reservation price v
    costing v and a slice bid at v worth v, so the program accepts what a single clearing
    price would; the other side is held at zero, and the throughput cost leaves the
    objective, which the bids now carry. Returns the system and the unit offsets, with the
    resource offsets joint's, or under H each resource's first Balas column.
    """
    T, B = d.shape[1], net.nb
    c, A, b, Ae, be, lb, ub, it, ou, os = _sy(g, [] if how == "H" else st, d, net, f)
    sy = [c, A, b, Ae, be, lb, ub, np.zeros(len(c)) if it is None else np.asarray(it)]
    if how == "R":
        for o in os:
            sy[7][o + 3 * T : o + 4 * T] = 0.0
    if how == "fix":
        for j, o in enumerate(os):
            sy[5][o : o + 4 * T] = sy[6][o : o + 4 * T] = np.concatenate(q[j])
    if how == "H":
        os = []
        for x in st:
            Ai, Aq, cv, Bb, k = _hb(x, T)
            n = len(sy[0])
            os.append(n)
            Z = np.zeros((B * T, Bb.shape[1]))
            Z[int(x.bus) * T : (int(x.bus) + 1) * T] = Bb
            sy = _ext(sy, B, T, k, np.zeros(len(k)), np.full(len(k), np.inf),
                      hstack([csc_array((Ai.shape[0], n)), Ai]), np.zeros(Ai.shape[0]),
                      vstack([hstack([csc_array((Aq.shape[0], n)), Aq]),
                              hstack([csc_array((1, n)), csc_array(cv[None, :])])]),
                      np.r_[np.zeros(Aq.shape[0]), 1.0], Z)
    if how == "bid":
        for j, (x, o) in enumerate(zip(st, os)):
            sy[0][o : o + 2 * T] = 0.0
            for t in range(T):
                y = curve(q[j][t], ref[j][t], kk, sp)
                sy[6][o + t if q[j][t] >= 0 else o + T + t] = 0.0
                if not len(y):
                    sy[6][o + t] = sy[6][o + T + t] = 0.0
                    continue
                n = len(sy[0])
                a = np.zeros((1, n + len(y)))
                a[0, o + T + t if q[j][t] > 0 else o + t] = 1.0
                a[0, n:] = -1.0
                sy = _ext(sy, B, T, np.sign(q[j][t]) * y[:, 0], np.zeros(len(y)),
                          np.abs(y[:, 1]), csc_array((0, n + len(y))), np.zeros(0), a,
                          np.zeros(1), np.zeros((B * T, len(y))))
    return (*sy, ou, os)


def _out(g, st, d, how, y, ou, os):
    """Unit output and commitment, resource charge, discharge, energy and mode, true cost."""
    G, T = len(g), d.shape[1]
    p = np.array([y[o : o + T] for o in ou]).reshape(G, T)
    u = np.array([y[o + T : o + 2 * T] for o in ou]).reshape(G, T)
    v = np.array([y[o + 2 * T : o + 3 * T] for o in ou]).reshape(G, T)
    Q = []
    for o in os:
        if how == "H":
            w = y[o : o + 2**T * (3 * T + 1)].reshape(2**T, 3 * T + 1)[:, : 3 * T].sum(0)
            Q.append([w[:T], w[T : 2 * T], w[2 * T :], np.full(T, np.nan)])
        else:
            Q.append([y[o + k * T : o + (k + 1) * T] for k in range(4)])
    Q = np.array(Q, dtype=float).reshape(len(st), 4, T).transpose(1, 0, 2)
    z = sum(x.c * p[i].sum() + x.nl * u[i].sum() + x.su * v[i].sum() for i, x in enumerate(g))
    z += sum(x.k * (Q[0][j] + Q[1][j]).sum() for j, x in enumerate(st))
    return np.where(np.abs(p) < 1e-9, 0.0, p), u, np.where(np.abs(Q) < 1e-9, 0.0, Q), float(z)


def cl(g, st, d, net=None, how="X", q=None, ref=None, kk=1, sp=0.0):
    """Clear units and storage as one integer program, the thermal commitment always integer.

    how selects the resource's feasible set, X, R or H, or the market design, fix or bid;
    q, ref, kk and sp are _sys's. The certificate is _mi's.
    """
    g, st, d, net = ck(g, st, d, net)
    c, A, b, Ae, be, lb, ub, it, ou, os = _sys(g, st, d, net, how, True, q, ref, kk, sp)
    res, ag, bd, sq = _mi(c, it, lb, ub, A, b, Ae, be, "this demand did not clear with storage")
    p, u, Q, z = _out(g, st, d, how, res.x, ou, os)
    return Cl(z, float(res.fun), p, np.rint(u), Q[0], Q[1], Q[2],
              Q[3] if how in ("H", "R") else np.rint(Q[3]), sq, ag, bd)


def px(g, st, d, s, net=None, how="X", q=None, ref=None, kk=1, sp=0.0):
    """Hold every integer the clearing s fixed, re-dispatch, and read the balance duals.

    The thermal commitment is held under every how, and the mode wherever it is an integer:
    X, fix and bid. Under R the mode is continuous in the clearing and stays free; under H
    there is no mode. This is joint.lmp's rule applied to each description, and it is the
    market-design choice every price here is taken under. Returns the price, the
    re-dispatch's objective, and _px's selection tag.
    """
    g, st, d, net = ck(g, st, d, net)
    T = d.shape[1]
    c, A, b, Ae, be, lb, ub, _it, ou, os = _sys(g, st, d, net, how, False, q, ref, kk, sp)
    lb, ub = np.array(lb, dtype=float), np.array(ub, dtype=float)
    for i, o in enumerate(ou):
        w = np.r_[s.u[i, 0] - g[i].u0, np.diff(s.u[i])]
        for k, y in enumerate((s.u[i], np.maximum(w, 0.0), np.maximum(-w, 0.0)), start=1):
            lb[o + k * T : o + (k + 1) * T] = ub[o + k * T : o + (k + 1) * T] = y
    if how in ("X", "fix", "bid"):
        for j, o in enumerate(os):
            lb[o + 3 * T : o + 4 * T] = ub[o + 3 * T : o + 4 * T] = s.sm[j]
    why = []
    res = _px(c, A, b, Ae, be, lb, ub, d.size, why)
    if res is None:
        raise ValueError(f"the held clearing did not re-dispatch [{why[0]}]")
    return res[2][-d.size :].reshape(d.shape), res[0], res[3]


def _ub(x, T, pi, how="X", m=None):
    """A resource's best profit at its bus price pi: max pi'(d - c) - k(c + d).

    Over X the modes are binary, over R they are relaxed and the cut remains, and over P
    they are held at m. The rows are joint's. The value is built from the program's
    certified bound, as _om builds a unit's, so a best profit is never understated.
    """
    A, b = _sr(x, T)
    Ae, be = _se(x, T)
    lb, ub = _sb(x, T)
    if how == "P":
        lb[3 * T :] = ub[3 * T :] = m
    it = np.r_[np.zeros(3 * T), np.full(T, 1.0 if how == "X" else 0.0)]
    _res, _ag, v, _st = _mi(np.r_[x.k + pi, x.k - pi, np.zeros(2 * T)], it, lb, ub, A, b, Ae,
                            be, "a resource has no schedule", True)
    return -v


def ps(x, T, pi):
    """A resource's price-taking schedule (c, d, e, m) against a price it does not move."""
    A, b = _sr(x, T)
    Ae, be = _se(x, T)
    lb, ub = _sb(x, T)
    res, _ag, _v, _st = _mi(np.r_[x.k + pi, x.k - pi, np.zeros(2 * T)],
                            np.r_[np.zeros(3 * T), np.ones(T)], lb, ub, A, b, Ae, be,
                            "a resource has no schedule", True)
    y = np.where(np.abs(res.x) < 1e-9, 0.0, res.x)
    return [y[k * T : (k + 1) * T] for k in range(3)] + [np.rint(y[3 * T :])]


def _fl(net, s):
    """DC line flows from nodal net injections s (B x T): solve B theta = s, theta_0 = 0.

    B is the network's susceptance Laplacian, so a flow is (theta_a - theta_q) / x from a
    to q, and a bus's injection is its net outflow. The clearing's angle columns are not
    read. Any flows that balance s give sum f_aq (pi_q - pi_a) = -pi's, so the rent from
    them checks the payments, not the prices or the reactances.
    """
    if net.fm != "dc":
        raise ValueError("flows follow from injections only under the dc line model")
    Y = np.zeros((net.nb, net.nb))
    for a, q, x, _ in net.ln:
        Y[np.ix_([a, q], [a, q])] += np.array([[1.0, -1.0], [-1.0, 1.0]]) / x
    th = np.zeros_like(s)
    th[1:] = np.linalg.solve(Y[1:, 1:], s[1:])
    return np.array([(th[a] - th[q]) / x for a, q, x, _ in net.ln])


def stl(g, st, d, s, pi, net=None, ref=0):
    """Settle clearing s at price pi: every payment, and the identities they must satisfy.

    L - z = sum(r) + sum(rs) + rent is the accounting identity: what load pays less what
    the dispatch cost is the units' profit, the resources' profit and the congestion rent.
    rent is a payment difference and rf the same rent from the line flows the nodal
    injections imply; they agree on any balanced dispatch at any price. Splitting rs into en
    and cn prices the resource's net injection at bus ref: the split moves with ref, and
    the total does not.
    """
    g, st, d, net = ck(g, st, d, net)
    G, T = len(g), d.shape[1]
    pi = np.asarray(pi, dtype=float).reshape(d.shape)
    P = pay(g, s, pi, net)
    L = float((pi * d).sum())
    b = [int(x.bus) for x in st]
    y = [s.sd[j] - s.sc[j] for j in range(len(st))]
    k = [x.k * (s.sc[j] + s.sd[j]).sum() for j, x in enumerate(st)]
    rs = np.array([pi[b[j]] @ y[j] - k[j] for j in range(len(st))])
    ls = np.array([_ub(x, T, pi[b[j]]) - rs[j] for j, x in enumerate(st)])
    ov = np.array([_ub(x, T, pi[b[j]], "R") - _ub(x, T, pi[b[j]]) for j, x in enumerate(st)])
    rent = L - sum(pi[net.bus[i]] @ s.p[i] for i in range(G))
    rent -= sum(pi[b[j]] @ y[j] for j in range(len(st)))
    inj = -d.copy()
    for i in range(G):
        inj[net.bus[i]] += s.p[i]
    for j in range(len(st)):
        inj[b[j]] += y[j]
    rf = 0.0
    if net.ln:
        f = _fl(net, inj)
        rf = float(sum(f[q] @ (pi[e[1]] - pi[e[0]]) for q, e in enumerate(net.ln)))
    en = np.array([pi[ref] @ y[j] - k[j] for j in range(len(st))])
    return St(s.z, L, P.r, P.mw, P.loc, rs, ls, ov, float(rent), rf, en, rs - en)


def _net(a, b):
    """Generation bus 0, load bus 1, storage spur bus 2: line 0-1 limited to a, 1-2 to b."""
    return Net([0, 1, 1], ((0, 1, 1.0, a), (1, 2, 1.0, b)), 3)


def _mkt():
    """The common fleet and load. A: cheap, 70 MW, at bus 0. B: a peaker at bus 1 with a
    10 MW floor and a 600 start-up. C: flexible at bus 1, dear, 80/MWh. Load at bus 1 is
    40, 40, 100, 40: the peak needs 30 MW beyond A, which B serves at 50 plus its start-up.
    """
    d = np.zeros((3, 4))
    d[1] = [40.0, 40.0, 100.0, 40.0]
    return [U(0.0, 70.0, 10.0), U(10.0, 60.0, 50.0, su=600.0), U(0.0, 60.0, 80.0)], d


def s1():
    """At the load bus, no congestion: 40 MWh, 30 MW, lossless.

    It charges 30 MWh from A off-peak and meets the peak itself, so B is never started.
    Cost falls from 4,000 to 2,200. It earns nothing at every optimal price: it charges and
    discharges the same energy at one price. The face leaves the charging and peak periods
    anywhere in [10, 80]; the payment rule prices them at 10.
    """
    g, d = _mkt()
    return g, [S(40.0, 30.0, 30.0, 1.0, 1.0, bus=1)], d, _net(200.0, 200.0)


def s2():
    """Behind a constrained line: the same resource on a spur bus whose line carries 15 MW.

    It delivers 15 MW at the peak, B is not started and C serves the other 15 at 80. Cost
    falls to 3,250. The spur binds, so the spur bus prices at 10 in every period and the
    resource earns nothing; the 1,050 of spur rent is what its energy was worth.
    """
    g, d = _mkt()
    return g, [S(40.0, 30.0, 30.0, 1.0, 1.0, bus=2)], d, _net(200.0, 15.0)


def s3():
    """At the cheap generation bus, behind an 85 MW line.

    Without the resource A's 70 MW never fills the line. With it, A and the resource send
    85 MW at the peak and the line binds: bus 0 prices at 10, bus 1 at 80. The resource
    earns nothing, A loses the 2,800 it earned at 50, and the rent is 5,950.
    """
    g, d = _mkt()
    return g, [S(40.0, 30.0, 30.0, 1.0, 1.0, bus=0)], d, _net(85.0, 200.0)


def s4():
    """At the load bus with 20 MWh of energy: the energy limit binds, power does not.

    It covers 20 MW of the peak, C the other 10, and B is not started. Cost falls to
    2,900 and the peak price rises from 50 to 80, set by C: the resource earns 70 on each
    of its 20 MWh, 1,400, more than the 1,100 it saved.
    """
    g, d = _mkt()
    return g, [S(20.0, 30.0, 30.0, 1.0, 1.0, bus=1)], d, _net(200.0, 200.0)


def s5():
    """At the load bus with 15 MW of power, behind a 70 MW import line: power binds.

    The line already binds at the peak without the resource. It discharges 15 MW, C serves
    15 and B is not started: cost 3,250, peak 80 at bus 1 and 10 at bus 0. The resource's
    1,050 is all congestion value against bus 0 and all energy value against bus 1.
    """
    g, d = _mkt()
    return g, [S(60.0, 15.0, 15.0, 1.0, 1.0, bus=1)], d, _net(70.0, 200.0)


def _sur(e0):
    """Two periods, 40 then 100 MW, and A must stay above 45 MW or pay 2,000 to restart.

    The 5 MW A cannot shed in period 1 must be stored, or A must stop. The resource holds
    20 MWh at 30 MW and 80% efficiency each way, starting at e0.
    """
    g, _ = _mkt()
    g = [U(45.0, 70.0, 10.0, su=2000.0, u0=1, p0=45.0)] + g[1:]
    d = np.zeros((3, 2))
    d[1] = [40.0, 100.0]
    return g, [S(20.0, 30.0, 30.0, 0.8, 0.8, e0=e0, bus=1)], d, _net(200.0, 200.0)


def s6():
    """The mode cut is exact: the resource starts empty and stores A's surplus by charging.

    X, H and R clear at the same 2,470. No period needs charge and discharge together.
    """
    return _sur(0.0)


def s7():
    """The mode cut is not exact: the resource starts full, so its energy bound binds.

    No schedule, nor any mixture of schedules, absorbs energy into a full store: X and H
    stop A and restart it at 6,000. R charges 13.889 and discharges 8.889 in the same
    period, which leaves the store full and destroys 5 MWh as loss, and clears at 2,270.
    """
    return _sur(20.0)
