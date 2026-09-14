# Verification for the Lerchs-Grossmann pit model.
#
# LEGEND
#   v : economic block value vector      C : blocks inside the ultimate pit
#   E : precedence arcs                  z : pit value
#   x : the linear program's solution vector
#   D : MineLib data path                 SMALL : small model dimensions
#   b,p : block and required block        dims : block model dimensions
#   i,j,k : block coordinates             a,c,q : required-block coordinates
#   n : block count                       s : exact decimal scale
#   o : hand-instance ore value

from pathlib import Path

import numpy as np
import pytest

from models.lg_pit import bf, c_m, lp, mc, mk_E, mk_hand, mk_v
from models.minelib import rd

SMALL = [(8, 8, 4), (12, 12, 6), (16, 16, 8)]
D = Path(__file__).parents[1] / "data" / "minelib"


def test_hand_pos():
    """One ore block at $40 under nine waste blocks at $2 is worth mining: 40 - 18 = 22."""
    z, C = mc(mk_hand(40.0), mk_E(3, 3, 2))
    assert z == pytest.approx(40.0 - 9 * c_m)
    assert len(C) == 10


def test_hand_neg():
    """The same block at $10 does not cover its own stripping, so the pit is empty."""
    z, C = mc(mk_hand(10.0), mk_E(3, 3, 2))
    assert z == pytest.approx(0.0)
    assert C == []


@pytest.mark.parametrize("o", [40.0, 10.0, 18.0, 18.001])
def test_hand_z(o):
    """Against exhaustive search, which is only affordable at this size."""
    v, E = mk_hand(o), mk_E(3, 3, 2)
    assert mc(v, E)[0] == pytest.approx(bf(v, E)[0])


@pytest.mark.parametrize("o", [40.0, 10.0, 18.001])
def test_hand_C(o):
    """The chosen blocks agree too, wherever the optimum is unique.

    o = 18.0 is excluded on purpose: nine waste blocks at c_m cost exactly 18, so
    the empty pit and the full pit are both worth zero and the two methods are
    free to return different sets. The value test above still covers that case.
    """
    v, E = mk_hand(o), mk_E(3, 3, 2)
    assert mc(v, E)[1] == bf(v, E)[1]


@pytest.mark.parametrize("dims", SMALL)
def test_mc_lp(dims):
    """Two solvers, one answer. A disagreement means the reduction is wrong."""
    v, E = mk_v(*dims), mk_E(*dims)
    assert mc(v, E)[0] == pytest.approx(lp(v, E)[0], abs=1e-6)


@pytest.mark.parametrize("dims", SMALL)
def test_lp_int(dims):
    """The constraint matrix is a network matrix, so the relaxation needs no branching.

    This is the property that lets the pit be solved as a flow problem at all. A
    fractional entry here means the precedence arcs no longer form a digraph
    incidence structure, which is a defect in mk_E, not a solver tolerance issue.
    """
    v, E = mk_v(*dims), mk_E(*dims)
    x = lp(v, E)[1]
    assert int(((x > 1e-6) & (x < 1 - 1e-6)).sum()) == 0


@pytest.mark.parametrize("dims", SMALL)
def test_mc_z(dims):
    """z must equal the sum of v over C, not merely the max-flow arithmetic."""
    v, E = mk_v(*dims), mk_E(*dims)
    z, C = mc(v, E)
    assert sum(v[b] for b in C) == pytest.approx(z, abs=1e-6)


@pytest.mark.parametrize("dims", SMALL)
def test_closed(dims):
    """Every block in the pit has everything above it in the pit. The slope constraint."""
    v, E = mk_v(*dims), mk_E(*dims)
    C = set(mc(v, E)[1])
    assert not [(b, p) for b, p in E if b in C and p not in C]


def test_mono():
    """Monotonicity: raising every block value weakly grows the ultimate pit."""
    dims = (12, 12, 6)
    E = mk_E(*dims)
    v = mk_v(*dims)
    C1 = set(mc(v, E)[1])
    C2 = set(mc(v + 1.0, E)[1])
    assert C1 <= C2


def test_waste():
    """No ore, no pit. The degenerate case that leaves the source isolated."""
    dims = (6, 6, 3)
    v = np.full(6 * 6 * 3, -c_m)
    z, C = mc(v, mk_E(*dims))
    assert z == pytest.approx(0.0)
    assert C == []


def test_E_dir():
    """Directly test the meaning and direction of every generated arc."""
    dims = (4, 5, 3)
    E = mk_E(*dims)
    for b, p in E:
        i, j, k = np.unravel_index(int(b), dims)
        a, c, q = np.unravel_index(int(p), dims)
        assert q == k - 1
        assert abs(a - i) <= 1
        assert abs(c - j) <= 1


def test_E_edge():
    """A centre has nine requirements; a corner has four; surface blocks have none."""
    dims = (3, 3, 2)
    E = mk_E(*dims)
    n = np.prod(dims)
    k = np.bincount(E[:, 0], minlength=n)
    assert k[np.ravel_multi_index((1, 1, 1), dims)] == 9
    assert k[np.ravel_multi_index((0, 0, 1), dims)] == 4
    assert not k.reshape(dims)[:, :, 0].any()


def test_E_mem():
    """Keep one compact representation for all solvers."""
    E = mk_E(8, 9, 4)
    assert E.dtype == np.int32
    assert E.shape == ((4 - 1) * (3 * 8 - 2) * (3 * 9 - 2), 2)


def test_bad():
    """Bad values and dangling precedence blocks must not produce plausible answers."""
    with pytest.raises(ValueError, match="finite vector"):
        mc(np.array([1.0, np.nan]), np.empty((0, 2), dtype=int))
    with pytest.raises(ValueError, match="outside v"):
        lp(np.array([1.0]), np.array([[0, 1]]))


def test_bf_n():
    """The exact checker has a stated 20-block ceiling."""
    with pytest.raises(ValueError, match="20 blocks"):
        bf(np.ones(21), np.empty((0, 2), dtype=int))


def test_ml():
    """External check: MineLib publishes Newman1's rounded UPIT value as 26,086,899."""
    v, E, s = rd(D / "newman1.upit", D / "newman1.prec")
    z, C = mc(v, E)
    assert len(v) == 1060
    assert len(E) == 3922
    assert s == 100_000
    assert round(z) == 26_086_899
    assert sum(v[b] for b in C) == pytest.approx(z)
