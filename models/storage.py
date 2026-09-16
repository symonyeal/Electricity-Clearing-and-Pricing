# Storage offers with two settlements and Rockafellar-Uryasev CVaR.
# HydroBoost supplies the physical precedent; LOGOS supplies the risk precedent.
# The rows are written here in SciPy. Sources and restrictions: docs/TRADING.md.
#
# LEGEND
#   B             : usable MWh, charge/discharge MW, efficiencies, initial/final MWh,
#                   throughput cost per grid MWh, hours per period
#   da,rt,pr      : day-ahead prices (T) or (S,T), real-time prices (S,T), probabilities
#   h             : information node labels (S,T); equal labels share a decision
#   a,w           : CVaR confidence and risk weight in [0,1]
#   q             : fixed contractual MW position, or None to choose a deliverable offer
#   ix,pa,o       : path-to-node indices, each node's parent, 1 when a nominal path exists
#   c,d,e,u       : charge, discharge, stored energy, charge-mode binary
#   R,r           : scenario profit rows, realized scenario profits
#   k0,off        : fixed-position profit per scenario, its objective offset
#   z,mu,cv       : (1-w)*mean - w*CVaR(loss), mean profit, CVaR of loss
#   ub,gap,lim    : solver upper bound on z, achieved relative MIP gap, seconds allowed
#   st,en         : sparse MIP; independent signed-flow enumeration and cumulative LP
#   N,T,S         : nodes, periods, scenarios    C,D,E,U : variable offsets
#   A,lo,hi       : constraint matrix and row bounds    f : minimized objective
#   lb,ub,it      : variable bounds and integrality    v : solved vector

from itertools import product
from typing import NamedTuple

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp
from scipy.sparse import lil_matrix

LIM = 12


class B(NamedTuple):
    e: float
    c: float
    d: float
    ec: float = 0.95
    ed: float = 0.95
    e0: float = 0.0
    ef: float = 0.0
    k: float = 0.0
    dt: float = 1.0


class Sol(NamedTuple):
    z: float
    mu: float
    cv: float
    q: np.ndarray
    c: np.ndarray
    d: np.ndarray
    e: np.ndarray
    r: np.ndarray
    ub: float
    gap: float


def _ck(b, da, rt, pr, h, a, w, q):
    da, rt, pr = (np.asarray(x, dtype=float) for x in (da, rt, pr))
    if rt.ndim != 2 or not rt.size or da.ndim not in (1, 2):
        raise ValueError("prices must have shapes (T) or (S,T), and (S,T), with T > 0")
    S, T = rt.shape
    if da.shape not in ((T,), (S, T)):
        raise ValueError("day-ahead prices must be common or one curve per scenario")
    da = np.broadcast_to(da, (S, T))
    if not S or pr.shape != (S,) or not np.all(pr > 0) or abs(pr.sum() - 1) > 1e-12:
        raise ValueError("positive scenario probabilities must sum to one")
    if not all(np.isfinite(x).all() for x in (b, da, rt, pr, [a, w])):
        raise ValueError("inputs must be finite")
    if min(b.e, b.c, b.d, b.k) < 0 or not (0 < b.ec <= 1 and 0 < b.ed <= 1):
        raise ValueError("capacities and cost must be nonnegative; efficiencies in (0,1]")
    if not (0 <= b.e0 <= b.e and 0 <= b.ef <= b.e) or b.dt <= 0:
        raise ValueError("energy endpoints must be within capacity; duration must be positive")
    if not (0 <= a < 1 and 0 <= w <= 1):
        raise ValueError("CVaR confidence must be in [0,1), risk weight in [0,1]")
    h = np.zeros((S, T), dtype=int) if h is None else np.asarray(h)
    if h.shape != rt.shape or h.dtype.kind not in "iu":
        raise ValueError("information nodes must be an integer array of shape (S,T)")
    for t in range(1, T):
        for k in np.unique(h[:, t]):
            if np.unique(h[h[:, t] == k, t - 1]).size != 1:
                raise ValueError("information nodes may branch but cannot merge")
    if q is not None:
        q = np.asarray(q, dtype=float)
        if q.shape != (T,) or not np.isfinite(q).all():
            raise ValueError("fixed position must have T finite MW values")
    return da, rt, pr, h, q


def _tree(h, nom=True):
    """One column per information node; a chosen offer adds its own physical path."""
    S, T = h.shape
    o = 1 if nom else 0
    ix = np.empty((S + o, T), dtype=int)
    pa = list(range(-1, T - 1)) if nom else []
    if nom:
        ix[0] = np.arange(T)
    for t in range(T):
        for k in np.unique(h[:, t]):
            s = np.flatnonzero(h[:, t] == k) + o
            ix[s, t] = len(pa)
            pa.append(int(ix[s[0], t - 1]) if t else -1)
    return ix, pa


def cvar(r, pr, a):
    """Weighted upper tail of loss, including the fraction at a probability atom."""
    r, pr = np.asarray(r, dtype=float), np.asarray(pr, dtype=float)
    if (r.ndim != 1 or not r.size or pr.shape != r.shape or not 0 <= a < 1
            or not np.isfinite(r).all() or not np.isfinite(pr).all()
            or not np.all(pr > 0) or abs(pr.sum() - 1) > 1e-12):
        raise ValueError("finite profits, positive probabilities summing to one, 0 <= a < 1")
    i = np.argsort(r)
    p = pr[i]
    m = np.minimum(p, np.maximum(0, (1 - a) - np.r_[0, p.cumsum()[:-1]]))
    return float(-r[i] @ m / (1 - a))


def _out(b, da, rt, pr, a, w, ix, c, d, e, ub, gap, q=None):
    """Assemble the result. A fixed position has no physical path, so its energy is nan."""
    c, d, e = c[ix], d[ix], e[ix]
    if q is None:
        q = d[0] - c[0]
    else:
        c = np.vstack([np.maximum(-q, 0), c])
        d = np.vstack([np.maximum(q, 0), d])
        e = np.vstack([np.full(q.shape, np.nan), e])
    r = b.dt * (da @ q + ((d[1:] - c[1:] - q) * rt
                          - b.k * (c[1:] + d[1:])).sum(axis=1))
    mu, cv = float(pr @ r), cvar(r, pr, a)
    z = (1 - w) * mu - w * cv
    return Sol(z, mu, cv, q, c, d, e, r, z if ub is None else ub, gap)


def st(b, da, rt, pr, h=None, a=0.95, w=0.0, q=None, gap=0.0, lim=None):
    """Optimize one physically backed offer, or dispatch against a fixed position.

    No h means no scenario is revealed. Equal h[:,t] labels share all actions at t.
    Day-ahead prices may be one common curve or one per scenario, which is what a
    decision taken before the day-ahead market clears faces.
    With q=None the nominal path is a physical schedule, so a chosen offer is
    deliverable from the current energy. Passing q fixes an already contracted
    position: it settles but imposes no physical schedule, and dispatch adapts.
    Prices are exogenous, in currency/MWh. Only a solve reaching the requested gap
    is returned; ub and gap are achieved values. lim bounds solver seconds.
    """
    da, rt, pr, h, q = _ck(b, da, rt, pr, h, a, w, q)
    if not np.isfinite(gap) or gap < 0:
        raise ValueError("MIP gap must be finite and nonnegative")
    S, T = rt.shape
    o = int(q is None)
    ix, pa = _tree(h, nom=q is None)
    N = len(pa)
    C, D, E, U = 0, N, 2 * N, 3 * N
    n = 4 * N + 1 + S
    lb = np.zeros(n)
    ub = np.r_[np.full(N, b.c), np.full(N, b.d), np.full(N, b.e),
               np.ones(N), np.full(S + 1, np.inf)]
    lb[4 * N] = -np.inf
    it = np.zeros(n)
    it[U:U + N] = 1
    # Local mode bounds tightened by usable energy, with no arbitrary big M.
    cm, dm = min(b.c, b.e / (b.dt * b.ec)), min(b.d, b.e * b.ed / b.dt)
    A = lil_matrix((3 * N + len(np.unique(ix[:, -1])) + S, n))
    lo, hi = [], []

    def row(cols, vals, l, u):
        j = len(lo)
        A[j, cols] = vals
        lo.append(l)
        hi.append(u)

    for j, p in enumerate(pa):
        row([C + j, U + j], [1, -cm], -np.inf, 0)
        row([D + j, U + j], [1, dm], -np.inf, dm)
        cols, vals = [E + j, C + j, D + j], [1, -b.dt * b.ec, b.dt / b.ed]
        if p >= 0:
            cols.append(E + p)
            vals.append(-1)
        row(cols, vals, b.e0 if p < 0 else 0, b.e0 if p < 0 else 0)
    for j in np.unique(ix[:, -1]):
        row([E + j], [1], b.ef, b.ef)
    R = lil_matrix((S, n))
    k0 = np.zeros(S)
    for s in range(S):
        if q is None:
            for t in range(T):
                R[s, C + t] = b.dt * (rt[s, t] - da[s, t])
                R[s, D + t] = b.dt * (da[s, t] - rt[s, t])
        else:
            k0[s] = b.dt * float((da[s] - rt[s]) @ q)
        for t in range(T):
            j = ix[s + o, t]
            R[s, C + j] = -b.dt * (rt[s, t] + b.k)
            R[s, D + j] = b.dt * (rt[s, t] - b.k)
        j = len(lo)
        A[j] = -R[s]
        A[j, 4 * N], A[j, 4 * N + 1 + s] = -1, -1
        lo.append(-np.inf)
        hi.append(k0[s])
    f = -(1 - w) * np.asarray(pr @ R.tocsr()).ravel()
    f[4 * N], f[4 * N + 1:] = w, w * pr / (1 - a)
    off = (1 - w) * float(pr @ k0)
    opt = {"mip_rel_gap": gap} | ({"time_limit": float(lim)} if lim is not None else {})
    res = milp(f, integrality=it, bounds=Bounds(lb, ub),
               constraints=LinearConstraint(A.tocsc(), lo, hi), options=opt)
    if not res.success:
        raise ValueError(f"storage did not solve to the requested gap: {res.message}")
    v = res.x
    return _out(b, da, rt, pr, a, w, ix, v[C:C + N], v[D:D + N], v[E:E + N],
                off - float(res.mip_dual_bound), float(res.mip_gap), q)


def en(b, da, rt, pr, h=None, a=0.95, w=0.0, q=None):
    """Enumerate signed-flow orthants; energy is cumulative, with no SOC variables.

    This route builds neither the MIP rows nor its charge/discharge columns. It is
    exponential in information nodes and refused above LIM. Zero belongs to either mode.
    """
    da, rt, pr, h, q = _ck(b, da, rt, pr, h, a, w, q)
    S, T = rt.shape
    o = int(q is None)
    ix, pa = _tree(h, nom=q is None)
    N = len(pa)
    if N > LIM:
        raise ValueError(f"enumeration exceeds {LIM} information nodes")
    best = None
    for mode in product((0, 1), repeat=N):
        mode = np.asarray(mode)
        # y >= 0 exports; y <= 0 imports. Energy change is -dt*y/eta_d or -dt*eta_c*y.
        k = -b.dt * np.where(mode, 1 / b.ed, b.ec)
        lb, ub = np.where(mode, 0, -b.c), np.where(mode, b.d, 0)
        A, v, Ae, ve = [], [], [], []
        for path in ix:
            row = np.zeros(N + 1 + S)
            for j in path:
                row[j] = k[j]
                A.extend([row.copy(), -row.copy()])
                v.extend([b.e - b.e0, b.e0])
            Ae.append(row.copy())
            ve.append(b.ef - b.e0)
        R = np.zeros((S, N + 1 + S))
        k0 = np.zeros(S)
        for s in range(S):
            if q is None:
                R[s, :T] = b.dt * (da[s] - rt[s])
            else:
                k0[s] = b.dt * float((da[s] - rt[s]) @ q)
            for t, j in enumerate(ix[s + o]):
                R[s, j] = b.dt * (rt[s, t] - b.k * (1 if mode[j] else -1))
            row = -R[s].copy()
            row[N], row[N + 1 + s] = -1, -1
            A.append(row)
            v.append(k0[s])
        f = -(1 - w) * (pr @ R)
        f[N], f[N + 1:] = w, w * pr / (1 - a)
        res = linprog(f, A_ub=A, b_ub=v, A_eq=Ae, b_eq=ve,
                      bounds=list(zip(lb, ub)) + [(None, None)] + [(0, None)] * S)
        if res.status == 2:
            continue
        if not res.success:
            raise ValueError(f"enumerated storage LP failed: {res.message}")
        if best is None or res.fun < best[0]:
            best = res.fun, res.x[:N].copy(), k
    if best is None:
        raise ValueError("storage has no feasible schedule")
    _, y, k = best
    e = np.empty(N)
    for j, p in enumerate(pa):
        e[j] = (b.e0 if p < 0 else e[p]) + k[j] * y[j]
    return _out(b, da, rt, pr, a, w, ix, np.maximum(-y, 0), np.maximum(y, 0), e, None, 0.0, q)
