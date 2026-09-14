# Verification for the Lerchs-Grossmann pit model.
#
# LEGEND
#   v : economic block value vector      C : blocks inside the ultimate pit
#   E : precedence arcs                  z : pit value
#   x : the linear program's solution vector

import numpy as np
import pytest

from models.lg_pit import bf, c_m, lp, mc, mk_E, mk_hand, mk_v

SMALL = [(8, 8, 4), (12, 12, 6), (16, 16, 8)]


def test_hand_ore_pays():
    """One ore block at $40 under nine waste blocks at $2 is worth mining: 40 - 18 = 22."""
    z, C = mc(mk_hand(40.0), mk_E(3, 3, 2))
    assert z == pytest.approx(40.0 - 9 * c_m)
    assert len(C) == 10


def test_hand_ore_does_not_pay():
    """The same block at $10 does not cover its own stripping, so the pit is empty."""
    z, C = mc(mk_hand(10.0), mk_E(3, 3, 2))
    assert z == pytest.approx(0.0)
    assert C == []


@pytest.mark.parametrize("o", [40.0, 10.0, 18.0, 18.001])
def test_hand_value_matches_enumeration(o):
    """Against exhaustive search, which is only affordable at this size."""
    v, E = mk_hand(o), mk_E(3, 3, 2)
    assert mc(v, E)[0] == pytest.approx(bf(v, E)[0])


@pytest.mark.parametrize("o", [40.0, 10.0, 18.001])
def test_hand_pit_matches_enumeration(o):
    """The chosen blocks agree too, wherever the optimum is unique.

    o = 18.0 is excluded on purpose: nine waste blocks at c_m cost exactly 18, so
    the empty pit and the full pit are both worth zero and the two methods are
    free to return different sets. The value test above still covers that case.
    """
    v, E = mk_hand(o), mk_E(3, 3, 2)
    assert mc(v, E)[1] == bf(v, E)[1]


@pytest.mark.parametrize("dims", SMALL)
def test_mincut_matches_lp(dims):
    """Two solvers, one answer. A disagreement means the reduction is wrong."""
    v, E = mk_v(*dims), mk_E(*dims)
    assert mc(v, E)[0] == pytest.approx(lp(v, E)[0], abs=1e-6)


@pytest.mark.parametrize("dims", SMALL)
def test_lp_is_integral(dims):
    """The constraint matrix is a network matrix, so the relaxation needs no branching.

    This is the property that lets the pit be solved as a flow problem at all. A
    fractional entry here means the precedence arcs no longer form a digraph
    incidence structure, which is a defect in mk_E, not a solver tolerance issue.
    """
    v, E = mk_v(*dims), mk_E(*dims)
    x = lp(v, E)[1]
    assert int(((x > 1e-6) & (x < 1 - 1e-6)).sum()) == 0


@pytest.mark.parametrize("dims", SMALL)
def test_reported_value_is_the_closure_value(dims):
    """z must equal the sum of v over C, not merely the max-flow arithmetic."""
    v, E = mk_v(*dims), mk_E(*dims)
    z, C = mc(v, E)
    assert sum(v[b] for b in C) == pytest.approx(z, abs=1e-6)


@pytest.mark.parametrize("dims", SMALL)
def test_pit_is_a_closure(dims):
    """Every block in the pit has everything above it in the pit. The slope constraint."""
    v, E = mk_v(*dims), mk_E(*dims)
    C = set(mc(v, E)[1])
    assert not [(b, p) for b, p in E if b in C and p not in C]


def test_richer_ore_never_shrinks_the_pit():
    """Monotonicity: raising every block value weakly grows the ultimate pit."""
    dims = (12, 12, 6)
    E = mk_E(*dims)
    v = mk_v(*dims)
    C1 = set(mc(v, E)[1])
    C2 = set(mc(v + 1.0, E)[1])
    assert C1 <= C2


def test_all_waste_gives_an_empty_pit():
    """No ore, no pit. The degenerate case that leaves the source isolated."""
    dims = (6, 6, 3)
    v = np.full(6 * 6 * 3, -c_m)
    z, C = mc(v, mk_E(*dims))
    assert z == pytest.approx(0.0)
    assert C == []
