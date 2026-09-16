# Storage offers with two settlements and Rockafellar-Uryasev CVaR.
# HydroBoost supplies the physical precedent; LOGOS supplies the risk precedent.
# The rows are written here in SciPy. Sources and restrictions: docs/TRADING.md.
#
# LEGEND
#   B             : usable MWh, charge/discharge MW, efficiencies, initial/final MWh,
#                   throughput cost per grid MWh, hours per period
#   da,rt,pr      : day-ahead prices (T), real-time prices (S,T), probabilities (S)
#   h             : information node labels (S,T); equal labels share a decision
#   a,w           : CVaR confidence and risk weight in [0,1]
#   q             : fixed day-ahead MW, or None to optimize a feasible schedule
#   ix,pa         : path-to-node indices (nominal first), each node's parent
#   c,d,e,u       : charge, discharge, stored energy, charge-mode binary
#   R,r           : scenario profit rows, realized scenario profits
#   z,mu,cv       : (1-w)*mean - w*CVaR(loss), mean profit, CVaR of loss
#   ub,gap        : solver upper bound on z and achieved relative MIP gap
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
    if da.ndim != 1 or not da.size or rt.ndim != 2 or rt.shape[1] != da.size:
        raise ValueError("prices must have shapes (T) and (S,T), with T > 0")
    S, T = rt.shape
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
        if q.shape != da.shape or not np.isfinite(q).all():
            raise ValueError("fixed offer must have T finite MW values")
    return da, rt, pr, h, q


def _tree(h):
    """One column per information node; the nominal offer is a separate path."""
    S, T = h.shape
    ix = np.empty((S + 1, T), dtype=int)
    ix[0] = np.arange(T)
    pa = list(range(-1, T - 1))
    for t in range(T):
        for k in np.unique(h[:, t]):
            s = np.flatnonzero(h[:, t] == k) + 1
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


def _out(b, da, rt, pr, a, w, ix, c, d, e, ub, gap):
    c, d, e = c[ix], d[ix], e[ix]
    q = d[0] - c[0]
    r = b.dt * (da @ q + ((d[1:] - c[1:] - q) * rt
                          - b.k * (c[1:] + d[1:])).sum(axis=1))
    mu, cv = float(pr @ r), cvar(r, pr, a)
    z = (1 - w) * mu - w * cv
    return Sol(z, mu, cv, q, c, d, e, r, z if ub is None else ub, gap)


def st(b, da, rt, pr, h=None, a=0.95, w=0.0, q=None, gap=0.0):
    """Optimize one physically backed offer and adapted real-time dispatch.

    No h means no scenario is revealed. Equal h[:,t] labels share all actions at t.
    Pass q to hold an existing offer fixed. Prices are exogenous, in currency/MWh.
    Only a solve reaching the requested gap is returned; ub and gap are achieved values.
    """
    da, rt, pr, h, q = _ck(b, da, rt, pr, h, a, w, q)
    if not np.isfinite(gap) or gap < 0:
        raise ValueError("MIP gap must be finite and nonnegative")
    S, T = rt.shape
    ix, pa = _tree(h)
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
    A = lil_matrix((3 * N + len(np.unique(ix[:, -1])) + (T if q is not None else 0)
                    + S, n))
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
    if q is not None:
        for t in range(T):
            row([D + t, C + t], [1, -1], q[t], q[t])
    R = lil_matrix((S, n))
    for s in range(S):
        for t in range(T):
            j = ix[s + 1, t]
            R[s, C + t], R[s, D + t] = b.dt * (rt[s, t] - da[t]), b.dt * (da[t] - rt[s, t])
            R[s, C + j], R[s, D + j] = -b.dt * (rt[s, t] + b.k), b.dt * (rt[s, t] - b.k)
        j = len(lo)
        A[j] = -R[s]
        A[j, 4 * N], A[j, 4 * N + 1 + s] = -1, -1
        lo.append(-np.inf)
        hi.append(0)
    f = -(1 - w) * np.asarray(pr @ R.tocsr()).ravel()
    f[4 * N], f[4 * N + 1:] = w, w * pr / (1 - a)
    res = milp(f, integrality=it, bounds=Bounds(lb, ub),
               constraints=LinearConstraint(A.tocsc(), lo, hi), options={"mip_rel_gap": gap})
    if not res.success:
        raise ValueError(f"storage did not solve to the requested gap: {res.message}")
    v = res.x
    return _out(b, da, rt, pr, a, w, ix, v[C:C + N], v[D:D + N], v[E:E + N],
                -float(res.mip_dual_bound), float(res.mip_gap))


def en(b, da, rt, pr, h=None, a=0.95, w=0.0, q=None):
    """Enumerate signed-flow orthants; energy is cumulative, with no SOC variables.

    This route builds neither the MIP rows nor its charge/discharge columns. It is
    exponential in information nodes and refused above LIM. Zero belongs to either mode.
    """
    da, rt, pr, h, q = _ck(b, da, rt, pr, h, a, w, q)
    S, T = rt.shape
    ix, pa = _tree(h)
    N = len(pa)
    if N > LIM:
        raise ValueError(f"enumeration exceeds {LIM} information nodes")
    best = None
    for mode in product((0, 1), repeat=N):
        mode = np.asarray(mode)
        # y >= 0 exports; y <= 0 imports. Energy change is -dt*y/eta_d or -dt*eta_c*y.
        k = -b.dt * np.where(mode, 1 / b.ed, b.ec)
        lb, ub = np.where(mode, 0, -b.c), np.where(mode, b.d, 0)
        if q is not None:
            if np.any(q < lb[:T]) or np.any(q > ub[:T]):
                continue
            lb[:T], ub[:T] = q, q
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
        for s in range(S):
            R[s, :T] = b.dt * (da - rt[s])
            for t, j in enumerate(ix[s + 1]):
                R[s, j] = b.dt * (rt[s, t] - b.k * (1 if mode[j] else -1))
            row = -R[s].copy()
            row[N], row[N + 1 + s] = -1, -1
            A.append(row)
            v.append(0)
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
    return _out(b, da, rt, pr, a, w, ix, np.maximum(-y, 0), np.maximum(y, 0), e, None, 0.0)
