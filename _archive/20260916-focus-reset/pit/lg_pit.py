# Lerchs-Grossmann ultimate pit limit, solved as maximum closure -> minimum cut.
#
# Lerchs & Grossmann, CIM Bulletin 58(633) (1965) 47-54.
# Picard, Management Science 22 (1976) 1268-1272  (maximum closure == minimum cut).
#
# LEGEND
#   mk_v,mk_hand,mk_E : value, hand-case and precedence builders
#   chk,mc,mc_nx,lp,bf : validator and four exact solve routes
#   idx,go       : flat-index helper and closure-enumeration recursion
#   np,nx,mf     : array, graph and OR-Tools maximum-flow modules
#   linprog,csr_matrix : SciPy solver and sparse-matrix constructor
#   nx_,ny_,nz_ : block model dimensions, nz_ counted downward from surface k=0
#   i,j,k       : block coordinates
#   b           : block index, flattened from (i,j,k) as (i*ny_ + j)*nz_ + k
#   v           : economic block value vector, dollars; v[b] < 0 is waste
#   E           : int32 precedence matrix; row (b,p) means b needs p
#   n,m,r       : block count, arc count and current arc row
#   p           : a block required before b          a,c : neighbour coordinates
#   aa,cc       : valid neighbour coordinates        h : arcs for one (i,j) column
#   kk          : depth offsets                      p0 : predecessor column bases
#   M           : big capacity standing in for infinity on precedence arcs
#   G           : NetworkX reduction graph           F : OR-Tools flow solver
#   s,t         : source and sink                    st : solver status
#   sc          : exact integer units per dollar     w : scaled integer block values
#   sv          : v multiplied by sc                 lim : largest int64 value
#   pos,neg     : positive and negative block indices
#   a0,a1,u     : arc tails, heads and capacities    lo,hi : arc slice boundaries
#   cut,S       : minimum-cut value and source-side nodes
#   C           : the maximum closure = the set of blocks inside the ultimate pit
#   z           : pit value, sum of v over C
#   p_pos       : sum of the positive block values; z = p_pos - mincut
#   d           : squared normalised ellipsoid radius, 0 at lens centre, 1 at rim
#   q           : relative grade at a block, 0 to about 1.3
#   o           : ore value in the hand-worked instance
#   g           : seeded random number generator      sd : random seed
#   ci,cj,ck    : ore-lens centre                    ri,rj,rk : ore-lens radii
#   c_m         : mining cost per block
#   c_p         : processing cost per ore block
#   rev         : gross revenue per ore block at q = 1
#   A           : sparse LP constraint matrix        x : LP block choices
#   ii,jj       : CSR row boundaries and column indices
#   y           : CSR coefficients, +1 for b and -1 for p
#   res         : SciPy solve result                 arg : best closure found by bf
#   P           : required blocks indexed by block   ord_ : requirements-first block order
#   take        : blocks in the current bf closure   best : best bf value
#   a_i         : position in ord_

import numpy as np
import networkx as nx
from ortools.graph.python import max_flow as mf
from scipy.optimize import linprog
from scipy.sparse import csr_matrix

c_m, c_p, rev = 2.0, 8.0, 34.0


def mk_v(nx_, ny_, nz_, sd=7):
    """Synthetic cents-valued blocks: an ore lens under barren overburden."""
    g = np.random.default_rng(sd)
    v = np.full((nx_, ny_, nz_), -c_m)
    ci, cj, ck = nx_ / 2.0, ny_ / 2.0, nz_ * 0.35
    ri, rj, rk = nx_ * 0.18, ny_ * 0.18, nz_ * 0.25
    for i in range(nx_):
        for j in range(ny_):
            for k in range(nz_):
                d = ((i - ci) / ri) ** 2 + ((j - cj) / rj) ** 2 + ((k - ck) / rk) ** 2
                if d <= 1.0:
                    q = (1.0 - d) ** 0.4 * g.uniform(0.7, 1.3)
                    v[i, j, k] = rev * q - c_p - c_m
    return np.round(v.ravel(), 2)


def mk_hand(o):
    """3x3x2 with one ore block worth o under nine waste blocks. Hand-checkable."""
    v = np.full((3, 3, 2), -c_m)
    v[1, 1, 1] = o
    return v.ravel()


def mk_E(nx_, ny_, nz_):
    """45-degree slope: a block needs the 3x3 pattern one level above it."""
    if min(nx_, ny_, nz_) < 1:
        raise ValueError("block dimensions must be positive")

    def idx(i, j, k):
        return (i * ny_ + j) * nz_ + k

    n = nx_ * ny_ * nz_
    if n > np.iinfo(np.int32).max:
        raise ValueError("block count exceeds int32 indices")
    m = (nz_ - 1) * (3 * nx_ - 2) * (3 * ny_ - 2)
    E = np.empty((m, 2), dtype=np.int32)
    r = 0
    for i in range(nx_):
        for j in range(ny_):
            aa = range(max(0, i - 1), min(nx_, i + 2))
            cc = range(max(0, j - 1), min(ny_, j + 2))
            p0 = np.array([idx(a, c, 0) for a in aa for c in cc], dtype=np.int32)
            kk = np.arange(nz_ - 1, dtype=np.int32)
            h = len(p0) * len(kk)
            E[r:r + h, 0] = np.repeat(idx(i, j, 1) + kk, len(p0))
            E[r:r + h, 1] = np.tile(p0, len(kk)) + np.repeat(kk, len(p0))
            r += h
    return E


def chk(v, E):
    """Validate and normalise one closure instance."""
    v = np.asarray(v, dtype=float)
    E = np.asarray(E)
    if v.ndim != 1 or not len(v) or not np.isfinite(v).all():
        raise ValueError("v must be a non-empty finite vector")
    if E.ndim != 2 or E.shape[1:] != (2,):
        raise ValueError("E must have two columns")
    if not np.issubdtype(E.dtype, np.integer):
        raise ValueError("E must contain integer block indices")
    if E.size and (E.min() < 0 or E.max() >= len(v)):
        raise ValueError("E contains a block outside v")
    return v, E.astype(np.int32, copy=False)


def mc_nx(v, E):
    """Independent minimum cut, float capacities, NetworkX."""
    v, E = chk(v, E)
    n = len(v)
    p_pos = float(v[v > 0].sum())
    M = p_pos + max(1.0, p_pos)
    if not np.isfinite(M):
        raise OverflowError("positive block values are too large")
    G = nx.DiGraph()
    s, t = "s", "t"
    G.add_node(s)
    G.add_node(t)   # a model with no ore, or no waste, leaves one of them isolated
    for b in range(n):
        if v[b] > 0:
            G.add_edge(s, b, capacity=float(v[b]))
        elif v[b] < 0:
            G.add_edge(b, t, capacity=float(-v[b]))
    for b, p in E:
        G.add_edge(int(b), int(p), capacity=M)
    cut, (S, _) = nx.minimum_cut(G, s, t, flow_func=nx.algorithms.flow.preflow_push)
    C = sorted(b for b in S if b != s)
    return p_pos - cut, C


def mc(v, E, sc=100):
    """Default minimum cut, exact integer capacities. Returns (z, C)."""
    v, E = chk(v, E)
    if isinstance(sc, (bool, np.bool_)) or not isinstance(sc, (int, np.integer)) or sc < 1:
        raise ValueError("sc must be a positive integer")
    sv = v * sc
    lim = np.iinfo(np.int64).max
    if not np.isfinite(sv).all() or (np.abs(sv) >= float(1 << 63)).any():
        raise OverflowError("scaled block values exceed int64")
    w = np.rint(sv)
    if (np.abs(w / sc - v) > 4 * np.spacing(np.maximum(np.abs(v), 1.0))).any():
        raise ValueError(f"v must be exact multiples of 1/{sc}")
    w = w.astype(np.int64)
    n = len(v)
    s, t = n, n + 1
    pos = np.flatnonzero(w > 0).astype(np.int32)
    neg = np.flatnonzero(w < 0).astype(np.int32)
    p_pos = sum(int(x) for x in w[pos])
    if p_pos >= lim:
        raise OverflowError("positive scaled values exceed int64")
    M = p_pos + 1
    a0 = np.empty(len(pos) + len(neg) + len(E) + 1, dtype=np.int32)
    a1 = np.empty_like(a0)
    u = np.empty(len(a0), dtype=np.int64)
    lo, hi = len(pos), len(pos) + len(neg)
    a0[:lo], a1[:lo], u[:lo] = s, pos, w[pos]
    a0[lo:hi], a1[lo:hi], u[lo:hi] = neg, t, -w[neg]
    a0[hi:-1], a1[hi:-1], u[hi:-1] = E[:, 0], E[:, 1], M
    a0[-1], a1[-1], u[-1] = s, t, 0
    F = mf.SimpleMaxFlow()
    F.add_arcs_with_capacity(a0, a1, u)
    st = F.solve(s, t)
    if st != F.OPTIMAL:
        raise RuntimeError(f"OR-Tools maximum flow failed with status {st}")
    C = sorted(int(b) for b in F.get_source_side_min_cut() if 0 <= b < n)
    return (p_pos - F.optimal_flow()) / sc, C


def lp(v, E):
    """Closure as a linear program. Its transposed node-arc matrix is totally unimodular."""
    v, E = chk(v, E)
    n = len(v)
    m = len(E)
    ii = np.arange(0, 2 * m + 1, 2, dtype=np.int32)
    jj = E.ravel()
    y = np.tile([1.0, -1.0], m)
    A = csr_matrix((y, jj, ii), shape=(m, n))
    res = linprog(-v, A_ub=A, b_ub=np.zeros(len(E)), bounds=(0, 1), method="highs")
    if not res.success:
        raise RuntimeError(res.message)
    return -res.fun, res.x


def bf(v, E):
    """Enumerate every closed set; exact for at most 20 blocks."""
    v, E = chk(v, E)
    n = len(v)
    if n > 20:
        raise ValueError("bf is limited to 20 blocks")
    G = nx.DiGraph()
    G.add_nodes_from(range(n))
    G.add_edges_from((int(b), int(p)) for b, p in E)
    if not nx.is_directed_acyclic_graph(G):
        raise ValueError("bf requires acyclic precedences")
    ord_ = list(nx.topological_sort(G))[::-1]
    P = [[] for _ in range(n)]
    for b, p in E:
        P[int(b)].append(int(p))
    take = np.zeros(n, dtype=bool)
    best, arg = -np.inf, None

    def go(a_i, z):
        nonlocal best, arg
        if a_i == n:
            if z > best:
                best, arg = z, np.flatnonzero(take).tolist()
            return
        b = ord_[a_i]
        go(a_i + 1, z)
        if all(take[p] for p in P[b]):
            take[b] = True
            go(a_i + 1, z + v[b])
            take[b] = False

    go(0, 0.0)
    return best, arg
