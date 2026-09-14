# Lerchs-Grossmann ultimate pit limit, solved as maximum closure -> minimum cut.
#
# Lerchs & Grossmann, CIM Bulletin 58(633) (1965) 47-54.
# Picard, Management Science 22 (1976) 1268-1272  (maximum closure == minimum cut).
#
# LEGEND
#   nx_,ny_,nz_ : block model dimensions, nz_ counted downward from surface k=0
#   i,j,k       : block coordinates                 di,dj : horizontal offsets
#   b           : block index, flattened from (i,j,k) as (i*ny_ + j)*nz_ + k
#   v           : economic block value vector, dollars; v[b] < 0 is waste
#   E           : int32 precedence matrix; row (b,p) means b needs p
#   n,m,r       : block count, arc count and current arc row
#   p           : a block required before b          a,c : neighbour coordinates
#   aa,cc       : valid neighbour coordinates        h : arcs for one (i,j) column
#   kk          : depth offsets                      p0 : predecessor column bases
#   M           : big capacity standing in for infinity on precedence arcs
#   G           : NetworkX reduction graph           s,t : source and sink
#   cut,S       : minimum-cut value and source-side nodes
#   C           : the maximum closure = the set of blocks inside the ultimate pit
#   z           : pit value, sum of v over C
#   p_pos       : sum of the positive block values; z = p_pos - mincut
#   d           : squared normalised ellipsoid radius, 0 at lens centre, 1 at rim
#   q           : relative grade at a block, 0 to about 1.3
#   g           : seeded random number generator      sd : random seed
#   ci,cj,ck    : ore-lens centre                    ri,rj,rk : ore-lens radii
#   c_m         : mining cost per block
#   c_p         : processing cost per ore block
#   rev         : gross revenue per ore block at q = 1
#   A           : sparse LP constraint matrix        x : LP block choices
#   ii,jj       : CSR row boundaries and column indices
#   y           : CSR coefficients, +1 for b and -1 for p
#   o           : SciPy solve result                 arg : best closure found by bf
#   P           : required blocks indexed by block   ord_ : requirements-first block order
#   take        : blocks in the current bf closure   best : best bf value
#   a_i         : position in ord_

import numpy as np
import networkx as nx
from scipy.optimize import linprog
from scipy.sparse import csr_matrix

c_m, c_p, rev = 2.0, 8.0, 34.0


def mk_v(nx_, ny_, nz_, sd=7):
    """Synthetic block values: an ellipsoidal ore lens under barren overburden."""
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
    return v.ravel()


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
    if v.ndim != 1 or not np.isfinite(v).all():
        raise ValueError("v must be a finite vector")
    if E.ndim != 2 or E.shape[1:] != (2,):
        raise ValueError("E must have two columns")
    if not np.issubdtype(E.dtype, np.integer):
        raise ValueError("E must contain integer block indices")
    if E.size and (E.min() < 0 or E.max() >= len(v)):
        raise ValueError("E contains a block outside v")
    return v, E.astype(np.int32, copy=False)


def mc(v, E):
    """Ultimate pit by minimum cut on the Picard reduction. Returns (z, C)."""
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
        G.add_edge(b, p, capacity=M)
    cut, (S, _) = nx.minimum_cut(G, s, t)
    C = sorted(x for x in S if x != s)
    return p_pos - cut, C


def lp(v, E):
    """Closure as an LP; its transposed node-arc matrix has whole-number vertices."""
    v, E = chk(v, E)
    n = len(v)
    m = len(E)
    ii = np.arange(0, 2 * m + 1, 2, dtype=np.int32)
    jj = E.ravel()
    y = np.tile([1.0, -1.0], m)
    A = csr_matrix((y, jj, ii), shape=(m, n))
    o = linprog(-v, A_ub=A, b_ub=np.zeros(len(E)), bounds=(0, 1), method="highs")
    if not o.success:
        raise RuntimeError(o.message)
    return -o.fun, o.x


def bf(v, E):
    """Generate every closure; ground truth up to 20 blocks."""
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
