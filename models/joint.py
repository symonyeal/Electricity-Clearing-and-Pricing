# Thermal commitment and storage cleared together, on a network.
#
# models/uc_price.py clears generation and prices it; models/storage.py values a battery
# against prices it does not move. Here both are in one program, so a resource's charge and
# discharge enter the nodal balance whose dual prices it. Deliverability is the network's:
# a battery behind a congested line absorbs only what that line carries.
#
# The unit rows, the network rows and the price selection are uc_price's, imported rather
# than rewritten, so a market with no storage clears exactly as it does there. What is new
# is the storage resource and the assembly that puts both kinds of resource in one balance.
#
# LEGEND
#   S            : one resource: usable MWh, charge and discharge MW, efficiencies,
#                  initial and terminal MWh, throughput cost per grid MWh, bus, hours
#   Jt           : one clearing: cost, unit output and commitment, resource flows, price
#   _sr,_sb      : one resource's rows and its variable bounds, over [c|d|e|m]
#   _sy          : assemble units, resources and network as one system
#   _out         : split a solved vector back into units and resources
#   ck           : validate a joint market
#   cl,rx        : clear it as one integer program; the same system with the binaries free
#   lmp          : hold the cleared commitment and mode, re-dispatch, read the balance duals
#   G,R,T,B      : units, resources, periods, buses
#   ou,os        : first column of unit i's block and of resource j's block
#   C,D,E,M      : the charge, discharge, energy and mode offsets inside a block
#   g,st,d,net   : units, resources, nodal demand, network
#   f            : keep the binaries integer
#   gap,lb       : achieved relative gap and certified cost lower bound
#   sq,why       : the clearing's own certificate, and why a solve failed
#   x,y          : one resource, one solved vector

import numpy as np
from scipy.sparse import csc_array

from models.uc_price import _eq, _fx, _ix, _mi, _nw, _px, _rw, ck as _ck

from typing import NamedTuple


class S(NamedTuple):
    """One storage resource, measured at the grid side. Efficiency applies inside it.

    ef is the energy required at the last period. None leaves the terminal state free,
    which lets a clearing empty the battery into the last period; a market that values the
    stored energy beyond the horizon sets ef.
    """

    e: float
    c: float
    d: float
    ec: float = 0.95
    ed: float = 0.95
    e0: float = 0.0
    ef: float | None = None
    k: float = 0.0
    bus: int = 0
    dt: float = 1.0


class Jt(NamedTuple):
    """Cost, unit output and commitment, resource charge, discharge, energy and mode, price.

    pi carries one price per bus per period. st is uc_price's price-selection tag on a
    priced route: only walk and probe are canonical. cl prices nothing, so there st carries
    that solve's own certificate instead, opt for a closed bound and gap for an incumbent.
    gap and lb carry that certificate as numbers. On a linear re-dispatch gap is zero and
    lb is its determined objective.
    """

    z: float
    p: np.ndarray
    u: np.ndarray
    sc: np.ndarray
    sd: np.ndarray
    se: np.ndarray
    sm: np.ndarray
    pi: np.ndarray
    st: str = ""
    gap: float = 0.0
    lb: float = float("nan")


def _sr(x, T):
    """One resource's inequalities over its own columns [c|d|e|m].

    The first two rows are the mode restriction: charging is possible only while m is one,
    discharging only while it is zero, so the two never run together. The third is their
    convex hull in one period, c/C + d/D <= 1, which the first two imply whenever m is
    integer and which is what remains of them when m is relaxed.

    That cut is the convex hull of the mode restriction alone. It is not claimed to be the
    hull of the resource's whole feasible set: the state-of-charge bounds couple the
    periods, and a convex combination of mode patterns can hold an average energy inside
    the battery while the patterns themselves do not. Where 0 <= e <= E is slack the cut is
    exact; where it binds the relaxation is a relaxation.
    """
    C, D, M = 0, T, 3 * T
    A, b = [], []

    def add(y=0.0):
        A.append(np.zeros(4 * T))
        b.append(y)
        return A[-1]

    for t in range(T):
        r = add(0.0)
        r[C + t], r[M + t] = 1.0, -x.c
        r = add(x.d)
        r[D + t], r[M + t] = 1.0, x.d
        r = add(1.0)
        r[C + t], r[D + t] = 1.0 / x.c, 1.0 / x.d
    return np.array(A), np.array(b)


def _se(x, T):
    """One resource's state-of-charge equalities over [c|d|e|m], and their right side."""
    C, D, E = 0, T, 2 * T
    A, b = np.zeros((T, 4 * T)), np.zeros(T)
    for t in range(T):
        A[t, E + t] = 1.0
        A[t, C + t] = -x.dt * x.ec
        A[t, D + t] = x.dt / x.ed
        if t:
            A[t, E + t - 1] = -1.0
        else:
            b[t] = x.e0
    return A, b


def _sb(x, T):
    """One resource's variable bounds, including a required terminal energy."""
    lb = np.zeros(4 * T)
    ub = np.r_[np.full(T, x.c), np.full(T, x.d), np.full(T, x.e), np.ones(T)]
    if x.ef is not None:
        lb[3 * T - 1] = ub[3 * T - 1] = float(x.ef)
    return lb, ub


def ck(g, st, d, net=None):
    """Validate a joint market and return its units, resources, nodal demand and network."""
    d = np.atleast_2d(np.asarray(d, dtype=float))
    if d.ndim != 2 or not d.size:
        raise ValueError("demand must be a non-empty vector, one value per period")
    if not np.isfinite(d).all() or (d < 0).any():
        raise ValueError("demand must be finite and non-negative")
    st = [x if isinstance(x, S) else S(*x) for x in st]
    # uc_price.ck refuses demand above generating capacity. Here a resource may carry part
    # of it, so the unit and network checks run against zero demand and the capacity check
    # is made below against generation plus discharge.
    g, _, net = _ck(g, np.zeros_like(d), net)
    for x in st:
        y = (x.e, x.c, x.d, x.ec, x.ed, x.e0, x.k, x.dt)
        if not all(np.isfinite(q) for q in y):
            raise ValueError("storage limits, costs and period length must be finite")
        if min(x.e, x.c, x.d, x.dt) <= 0:
            raise ValueError("storage energy, power and period length must be positive")
        if not 0 < x.ec <= 1 or not 0 < x.ed <= 1:
            raise ValueError("storage efficiencies must lie in (0, 1]")
        if not 0 <= x.e0 <= x.e:
            raise ValueError("initial energy must lie inside the battery")
        if x.ef is not None and not 0 <= x.ef <= x.e:
            raise ValueError("terminal energy must lie inside the battery")
        if x.k < 0:
            raise ValueError("throughput cost must be non-negative")
        if not 0 <= _ix(x.bus, "a resource's bus") < net.nb:
            raise ValueError("every storage resource must sit at a bus of the network")
    if d.sum(0).max() > sum(x.hi for x in g) + sum(x.d for x in st):
        raise ValueError("demand exceeds generating plus discharge capacity")
    return g, st, d, net


def _sy(g, st, d, net, f):
    """Assemble units, resources and network as one system; f keeps the binaries integer."""
    G, R, T, B = len(g), len(st), d.shape[1], net.nb
    ou = [4 * T * i for i in range(G)]
    os = [4 * T * (G + j) for j in range(R)]
    n = 4 * T * (G + R)
    c, lb, ub = np.zeros(n), np.zeros(n), np.zeros(n)
    ri, ci, va, b = [], [], [], []
    ei, ec, ev, be = [], [], [], []
    m = e = 0

    for i, x in enumerate(g):
        A, y = _rw(x, T)
        q, r = np.nonzero(A)
        ri.extend(m + q)
        ci.extend(ou[i] + r)
        va.extend(A[q, r])
        b.extend(y)
        m += len(A)
        A, y = _eq(x, T)
        q, r = np.nonzero(A)
        ei.extend(e + q)
        ec.extend(ou[i] + r)
        ev.extend(A[q, r])
        be.extend(y)
        e += T
        c[ou[i] : ou[i] + T] = x.c
        c[ou[i] + T : ou[i] + 2 * T] = x.nl
        c[ou[i] + 2 * T : ou[i] + 3 * T] = x.su
        lb[ou[i] : ou[i] + 4 * T], ub[ou[i] : ou[i] + 4 * T] = _fx(x, T)

    for j, x in enumerate(st):
        A, y = _sr(x, T)
        q, r = np.nonzero(A)
        ri.extend(m + q)
        ci.extend(os[j] + r)
        va.extend(A[q, r])
        b.extend(y)
        m += len(A)
        A, y = _se(x, T)
        q, r = np.nonzero(A)
        ei.extend(e + q)
        ec.extend(os[j] + r)
        ev.extend(A[q, r])
        be.extend(y)
        e += T
        c[os[j] : os[j] + 2 * T] = x.k
        lb[os[j] : os[j] + 4 * T], ub[os[j] : os[j] + 4 * T] = _sb(x, T)

    for i in range(G):
        for t in range(T):
            ei.append(e + net.bus[i] * T + t)
            ec.append(ou[i] + t)
            ev.append(1.0)
    for j, x in enumerate(st):
        for t in range(T):
            ei.extend([e + int(x.bus) * T + t] * 2)
            ec.extend([os[j] + T + t, os[j] + t])
            ev.extend([1.0, -1.0])
    be.extend(d.ravel())

    it = np.zeros(n)
    if f:
        for i in range(G):
            it[ou[i] + T : ou[i] + 4 * T] = 1.0
        for j in range(R):
            it[os[j] + 3 * T : os[j] + 4 * T] = 1.0
    A, b, Ae, c, lb, ub, it = _nw(
        net, T, n, csc_array((va, (ri, ci)), shape=(m, n)), np.array(b),
        csc_array((ev, (ei, ec)), shape=(e + B * T, n)), c, lb, ub, it)
    return c, A, b, Ae, np.array(be), lb, ub, it, ou, os


def _out(G, R, T, y, ou, os):
    """Split a solved vector into unit output and commitment, and resource flows."""
    p = np.array([y[ou[i] : ou[i] + T] for i in range(G)]).reshape(G, T)
    u = np.array([y[ou[i] + T : ou[i] + 2 * T] for i in range(G)]).reshape(G, T)
    q = [np.array([y[os[j] + k * T : os[j] + (k + 1) * T] for j in range(R)]).reshape(R, T)
         for k in range(4)]
    return np.where(np.abs(p) < 1e-9, 0.0, p), u, q


def cl(g, st, d, net=None):
    """Clear generation and storage as one integer program."""
    g, st, d, net = ck(g, st, d, net)
    G, R, T = len(g), len(st), d.shape[1]
    c, A, b, Ae, be, lb, ub, it, ou, os = _sy(g, st, d, net, True)
    res, ag, bd, sq = _mi(c, it, lb, ub, A, b, Ae, be,
                          "this demand did not clear jointly")
    p, u, q = _out(G, R, T, res.x, ou, os)
    return Jt(float(res.fun), p, np.rint(u), q[0], q[1], q[2], np.rint(q[3]),
              np.full(d.shape, np.nan), sq, ag, bd)


def rx(g, st, d, net=None):
    """Relax every binary and price the relaxation's balance rows."""
    g, st, d, net = ck(g, st, d, net)
    G, R, T = len(g), len(st), d.shape[1]
    c, A, b, Ae, be, lb, ub, _, ou, os = _sy(g, st, d, net, False)
    why = []
    res = _px(c, A, b, Ae, be, lb, ub, d.size, why)
    if res is None:
        raise ValueError(f"the relaxed joint clearing did not solve [{why[0]}]")
    p, u, q = _out(G, R, T, res[1], ou, os)
    return Jt(res[0], p, u, q[0], q[1], q[2], q[3],
              res[2][-d.size :].reshape(d.shape), res[3], 0.0, res[0])


def lmp(g, st, d, s, net=None):
    """Hold the cleared commitment and mode, re-dispatch, and read the balance duals.

    Every integer column is pinned by its own bounds, so what remains is a linear program
    over dispatch, storage flows and the network. Its balance duals are the locational
    marginal prices of the joint market: a resource settles at the price its own charge and
    discharge helped set, which is what clearing it rather than replaying it changes.
    """
    g, st, d, net = ck(g, st, d, net)
    G, R, T = len(g), len(st), d.shape[1]
    u = np.atleast_2d(np.asarray(s.u, dtype=float)).reshape(G, T)
    sm = np.asarray(s.sm, dtype=float).reshape(R, T) if R else np.zeros((0, T))
    if not np.isin(u, [0.0, 1.0]).all() or not np.isin(sm, [0.0, 1.0]).all():
        raise ValueError("the held commitment and mode must be binary")
    c, A, b, Ae, be, lb, ub, _, ou, os = _sy(g, st, d, net, False)
    lb, ub = np.array(lb, dtype=float), np.array(ub, dtype=float)
    for i in range(G):
        v = np.r_[u[i, 0] - g[i].u0, np.diff(u[i])]
        for k, y in enumerate((u[i], np.maximum(v, 0.0), np.maximum(-v, 0.0)), start=1):
            lb[ou[i] + k * T : ou[i] + (k + 1) * T] = y
            ub[ou[i] + k * T : ou[i] + (k + 1) * T] = y
    for j in range(R):
        lb[os[j] + 3 * T : os[j] + 4 * T] = sm[j]
        ub[os[j] + 3 * T : os[j] + 4 * T] = sm[j]
    why = []
    res = _px(c, A, b, Ae, be, lb, ub, d.size, why)
    if res is None:
        raise ValueError(f"the held commitment did not re-dispatch [{why[0]}]")
    p, _u, q = _out(G, R, T, res[1], ou, os)
    return Jt(res[0], p, u, q[0], q[1], q[2], sm,
              res[2][-d.size :].reshape(d.shape), res[3], 0.0, res[0])
