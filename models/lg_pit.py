# Lerchs-Grossmann ultimate pit limit, solved as maximum closure -> minimum cut.
#
# Lerchs & Grossmann, CIM Bulletin 58 (1965) 17-24.
# Picard, Management Science 22 (1976) 1268-1272  (maximum closure == minimum cut).
#
# LEGEND
#   nx_,ny_,nz_ : block model dimensions, nz_ counted downward from surface k=0
#   b           : block index, flattened from (i,j,k) as (i*ny_ + j)*nz_ + k
#   v           : economic block value vector, dollars; v[b] < 0 is waste
#   E           : precedence arcs (b, p) meaning "b cannot be mined before p"
#   M           : big capacity standing in for infinity on precedence arcs
#   s,t         : source, sink of the reduction network
#   C           : the maximum closure = the set of blocks inside the ultimate pit
#   z           : pit value, sum of v over C
#   p_pos       : sum of the positive block values; z = p_pos - mincut
#   d           : squared normalised ellipsoid radius, 0 at lens centre, 1 at rim
#   q           : relative grade at a block, 0 to about 1.3
#   c_m         : mining cost per block
#   c_p         : processing cost per ore block
#   rev         : gross revenue per ore block at q = 1

import numpy as np
import networkx as nx
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

c_m, c_p, rev = 2.0, 8.0, 34.0


def mk_v(nx_, ny_, nz_, seed=7):
    """Synthetic block values: an ellipsoidal ore lens under barren overburden."""
    g = np.random.default_rng(seed)
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
    def idx(i, j, k):
        return (i * ny_ + j) * nz_ + k

    E = []
    for i in range(nx_):
        for j in range(ny_):
            for k in range(1, nz_):
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        a, c = i + di, j + dj
                        if 0 <= a < nx_ and 0 <= c < ny_:
                            E.append((idx(i, j, k), idx(a, c, k - 1)))
    return E


def mc(v, E):
    """Ultimate pit by minimum cut on the Picard reduction. Returns (z, C)."""
    n = len(v)
    p_pos = float(v[v > 0].sum())
    M = p_pos + 1.0
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
    """The same problem as a linear program. Integral because the matrix is a network matrix."""
    n = len(v)
    r = np.repeat(np.arange(len(E)), 2)
    c = np.array(E).ravel()
    d = np.tile([1.0, -1.0], len(E))
    A = coo_matrix((d, (r, c)), shape=(len(E), n))
    o = linprog(-v, A_ub=A, b_ub=np.zeros(len(E)), bounds=(0, 1), method="highs")
    return -o.fun, o.x


def bf(v, E):
    """Exhaustive closure enumeration. Ground truth, tiny instances only."""
    n = len(v)
    best, arg = -np.inf, None
    for m in range(1 << n):
        S = {b for b in range(n) if m >> b & 1}
        if all(p in S for b, p in E if b in S):
            z = sum(v[b] for b in S)
            if z > best:
                best, arg = z, sorted(S)
    return best, arg
