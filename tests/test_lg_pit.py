# Verification for the Lerchs-Grossmann pit model.
#
# LEGEND
#   test_* : one verification case           np,pytest,Path : test support
#   v : economic block value vector      C : blocks inside the ultimate pit
#   E : precedence arcs                  z : pit value
#   x : the linear program's solution vector
#   z1,z2 : objective values from two methods
#   C1,C2 : pits returned by two methods
#   D : MineLib data path                 S : official MineLib pit
#   SMALL : small model dimensions
#   b,p : block and required block        dims : block model dimensions
#   i,j,k : block coordinates             ip,jp,kp : required-block coordinates
#   n : block count                       sc : exact decimal scale
#   deg : number of requirements by block
#   val : hand-instance ore value             o : ore-block count
#   w : waste-block count                 sr : waste-to-ore strip ratio
#   lost : profitable blocks outside the pit

from pathlib import Path

import numpy as np
import pytest

from models.lg_pit import bf, c_m, lp, mc, mc_nx, mk_E, mk_hand, mk_v
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


@pytest.mark.parametrize("val", [40.0, 10.0, 18.0, 18.01])
def test_hand_z(val):
    """Against exhaustive search, which is only affordable at this size."""
    v, E = mk_hand(val), mk_E(3, 3, 2)
    assert mc(v, E)[0] == pytest.approx(bf(v, E)[0])


@pytest.mark.parametrize("val", [40.0, 10.0, 18.01])
def test_hand_C(val):
    """The chosen blocks agree too, wherever the optimum is unique.

    val = 18.0 is excluded on purpose: nine waste blocks at c_m cost exactly 18, so
    the empty pit and the full pit are both worth zero and the two methods are
    free to return different sets. The value test above still covers that case.
    """
    v, E = mk_hand(val), mk_E(3, 3, 2)
    assert mc(v, E)[1] == bf(v, E)[1]


@pytest.mark.parametrize("dims", SMALL)
def test_mc_lp(dims):
    """The flow and linear-program encodings must have the same value."""
    v, E = mk_v(*dims), mk_E(*dims)
    assert mc(v, E)[0] == pytest.approx(lp(v, E)[0], abs=1e-6)


@pytest.mark.parametrize("dims", SMALL)
def test_mc_nx(dims):
    """Integer scaling keeps both the value and the chosen pit unchanged."""
    v, E = mk_v(*dims), mk_E(*dims)
    z1, C1 = mc(v, E)
    z2, C2 = mc_nx(v, E)
    assert z1 == pytest.approx(z2)
    assert C1 == C2


@pytest.mark.parametrize("dims", SMALL)
def test_lp_int(dims):
    """The constraint matrix is a network matrix, so the relaxation needs no branching.

    This checks the formulation's expected structure. Arc direction and geometry
    are checked separately because integrality alone cannot establish either one.
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


def test_flat():
    """All-zero ties return an empty pit; all-positive blocks return the full pit."""
    dims = (3, 3, 2)
    n = int(np.prod(dims))
    E = mk_E(*dims)
    assert mc(np.zeros(n), E) == (0.0, [])
    assert mc(np.ones(n), E) == (float(n), list(range(n)))


def test_econ():
    """The published synthetic geometry must produce a non-trivial pit."""
    dims = (30, 30, 12)
    v, E = mk_v(*dims), mk_E(*dims)
    z, C = mc(v, E)
    o = sum(v[b] > 0 for b in C)
    w = len(C) - o
    sr = w / o
    lost = int((v > 0).sum()) - o
    assert z > 0
    assert 2.0 <= sr <= 3.0
    assert lost > 0


def test_E_dir():
    """Directly test the meaning and direction of every generated arc."""
    dims = (4, 5, 3)
    E = mk_E(*dims)
    for b, p in E:
        i, j, k = np.unravel_index(int(b), dims)
        ip, jp, kp = np.unravel_index(int(p), dims)
        assert kp == k - 1
        assert abs(ip - i) <= 1
        assert abs(jp - j) <= 1


def test_E_edge():
    """A centre has nine requirements; a corner has four; surface blocks have none."""
    dims = (3, 3, 2)
    E = mk_E(*dims)
    n = np.prod(dims)
    deg = np.bincount(E[:, 0], minlength=n)
    assert deg[np.ravel_multi_index((1, 1, 1), dims)] == 9
    assert deg[np.ravel_multi_index((0, 0, 1), dims)] == 4
    assert not deg.reshape(dims)[:, :, 0].any()


def test_E_mem():
    """Keep one compact representation for all solvers."""
    E = mk_E(8, 9, 4)
    assert E.dtype == np.int32
    assert E.shape == ((4 - 1) * (3 * 8 - 2) * (3 * 9 - 2), 2)


def test_bad():
    """Bad values and dangling precedence blocks must not produce plausible answers."""
    with pytest.raises(ValueError, match="non-empty"):
        mc(np.array([]), np.empty((0, 2), dtype=int))
    with pytest.raises(ValueError, match="finite vector"):
        mc(np.array([1.0, np.nan]), np.empty((0, 2), dtype=int))
    with pytest.raises(ValueError, match="outside v"):
        lp(np.array([1.0]), np.array([[0, 1]]))
    with pytest.raises(ValueError, match="two columns"):
        mc(np.array([1.0]), np.array([]))
    with pytest.raises(ValueError, match="integer block"):
        mc(np.array([1.0]), np.array([[0.0, 0.0]]))
    with pytest.raises(ValueError, match="positive integer"):
        mc(np.array([1.0]), np.empty((0, 2), dtype=int), True)
    with pytest.raises(ValueError, match="exact multiples"):
        mc(np.array([1.001]), np.empty((0, 2), dtype=int))
    with pytest.raises(OverflowError, match="int64"):
        mc(np.array([float(1 << 62)]), np.empty((0, 2), dtype=int), 2)


def test_bf_n():
    """The exact checker has a stated 20-block ceiling."""
    with pytest.raises(ValueError, match="20 blocks"):
        bf(np.ones(21), np.empty((0, 2), dtype=int))


def test_ml():
    """External check against MineLib's published value and official selected pit."""
    v, E, sc = rd(D / "newman1.upit", D / "newman1.prec")
    z, C = mc(v, E, sc)
    S = sorted(int(b) for b in (D / "newman1_upit.sol").read_text().split())
    assert len(v) == 1060
    assert len(E) == 3922
    assert sc == 100_000
    assert z == pytest.approx(26_086_899.025970)
    assert round(z) == 26_086_899
    assert C == S
    assert z == pytest.approx(mc_nx(v, E)[0])
    assert z == pytest.approx(lp(v, E)[0])
    assert sum(v[b] for b in C) == pytest.approx(z)
