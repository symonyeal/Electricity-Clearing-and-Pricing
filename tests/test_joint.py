# Verification for the joint clearing of generation and storage.
#
# Two independent checks carry this module. The first is models/uc_price.py: given no
# storage resource, the joint program must be the same program, so its cost, its dispatch
# and its locational prices must match unit for unit on seeded markets. The second is
# arithmetic: a battery that moves energy from a 20/MWh period to an 80/MWh period saves
# exactly the spread it moved, and a battery behind a congested line delivers only what the
# line carries. Neither check reads the joint row builder.
#
# LEGEND
#   g,st,d,net : units, storage resources, nodal demand, network
#   a,b        : the same market cleared two ways
#   y,z        : one clearing and its priced re-dispatch
#   sd         : the seed of a synthetic market
#   R          : one resource used by several cases

import numpy as np
import pytest

from models.joint import S, ck, cl, lmp, rx
from models.uc_price import Net, U, mk_g
from models.uc_price import lmp as ulmp
from models.uc_price import uc

G = [U(lo=0.0, hi=60.0, c=20.0), U(lo=0.0, hi=60.0, c=80.0)]
D = [30.0, 30.0, 90.0, 30.0]
R = S(e=40.0, c=20.0, d=20.0, ec=1.0, ed=1.0, e0=0.0, k=0.0, bus=0)


@pytest.mark.parametrize("sd", [0, 1, 2, 3, 5, 8])
def test_no_resource_is_uc_price(sd):
    """With no storage the joint program is uc_price's program, cost, dispatch and price.

    This is the regression that keeps the new columns from changing the old answer. It is
    asserted on the clearing and on the priced re-dispatch, because a balance row that
    gained a term would move the second while leaving the first intact.

    Prices are held to 1e-4/MWh, the tolerance docs/PRICING.md states for two routes onto
    one dual face. The two programs are not the same matrix, so where the face has more
    than one point the solver may reach either vertex; the objective is held to 1e-9.
    """
    g, d = mk_g(6, 8, sd)
    a, b = uc(g, d), cl(g, [], d)
    assert b.z == pytest.approx(a.z, rel=1e-9)
    assert b.gap == a.gap == 0.0
    assert b.lb == pytest.approx(b.z, rel=1e-9)
    assert b.p == pytest.approx(a.p, abs=1e-6)
    assert b.u == pytest.approx(a.u)
    assert b.sc.shape == (0, 8) and b.sd.shape == (0, 8)
    assert lmp(g, [], d, b).pi == pytest.approx(ulmp(g, d, a).pi, abs=1e-4)


def test_arbitrage_is_the_spread():
    """The saving is the price spread times the energy moved, to the cent.

    Demand 30/30/90/30 against a 60 MW unit at 20/MWh and a 60 MW unit at 80/MWh prices the
    peak at 80 and every other period at 20. A lossless 20 MW battery charges 20 MW off
    peak and discharges 20 MW on peak, so the clearing must fall by 20 x (80 - 20) = 1,200.
    """
    a, b = cl(G, [], D), cl(G, [R], D)
    assert a.z == pytest.approx(5400.0)
    assert b.z == pytest.approx(4200.0)
    assert b.sc[0].sum() == pytest.approx(20.0)
    assert b.sd[0].sum() == pytest.approx(20.0)
    assert lmp(G, [], D, a).pi.ravel() == pytest.approx([20.0, 20.0, 80.0, 20.0])


def test_deliverability_strands_energy():
    """A resource behind a congested line delivers only what the line carries.

    One 5 MW line joins the load bus to the bus carrying the dear unit. A full 40 MWh
    battery at the load bus delivers all of it and clears at 2,300; the same battery behind
    the line delivers 5 MW in each of four periods, 20 MWh, and clears at 2,700. The 400 is
    the cost of the energy that cannot be delivered. The congested bus prices at zero while
    the load bus prices at 20, which is the same fact read off the duals.
    """
    net = Net(bus=np.array([0, 1]), ln=((0, 1, 0.1, 5.0),), nb=2, fm="dc")
    d = np.array([[30.0, 30.0, 65.0, 30.0], [0.0, 0.0, 0.0, 0.0]])
    out = []
    for bus in (0, 1):
        st = [S(e=40.0, c=20.0, d=20.0, ec=1.0, ed=1.0, e0=40.0, k=0.0, bus=bus)]
        y = cl(G, st, d, net)
        out.append((y, lmp(G, st, d, y, net)))
    assert out[0][0].z == pytest.approx(2300.0)
    assert out[1][0].z == pytest.approx(2700.0)
    assert out[0][0].sd[0].sum() == pytest.approx(40.0)
    assert out[1][0].sd[0].sum() == pytest.approx(20.0)
    assert (out[1][0].sd[0] <= 5.0 + 1e-6).all()
    assert out[1][1].pi[0] == pytest.approx([20.0] * 4)
    assert out[1][1].pi[1] == pytest.approx([0.0] * 4, abs=1e-6)


@pytest.mark.parametrize("sd", [0, 4, 9])
def test_modes_exclude_and_energy_follows(sd):
    """Charge and discharge never run together, and stored energy follows its recursion."""
    g, d = mk_g(4, 6, sd)
    st = [S(e=30.0, c=10.0, d=10.0, ec=0.92, ed=0.9, e0=5.0, k=1.0, bus=0)]
    y = cl(g, st, d, None)
    assert (y.sc[0] * y.sd[0] == pytest.approx(0.0, abs=1e-9))
    assert np.isin(y.sm, [0.0, 1.0]).all()
    e = np.r_[5.0, y.se[0][:-1]] + 0.92 * y.sc[0] - y.sd[0] / 0.9
    assert y.se[0] == pytest.approx(e, abs=1e-9)
    assert (y.se[0] >= -1e-9).all() and (y.se[0] <= 30.0 + 1e-9).all()


def test_terminal_energy_is_held():
    """A required terminal energy is enforced, and costs what returning it costs."""
    a = cl(G, [S(e=40.0, c=20.0, d=20.0, ec=1.0, ed=1.0, e0=0.0, ef=None, k=0.0)], D)
    b = cl(G, [S(e=40.0, c=20.0, d=20.0, ec=1.0, ed=1.0, e0=0.0, ef=20.0, k=0.0)], D)
    assert a.se[0][-1] == pytest.approx(0.0, abs=1e-6)
    assert b.se[0][-1] == pytest.approx(20.0)
    assert b.z >= a.z - 1e-6


def test_relaxation_bounds_the_clearing():
    """Relaxing every binary cannot cost more than clearing with them."""
    a, b = cl(G, [R], D), rx(G, [R], D)
    assert b.z <= a.z + 1e-6
    assert a.gap == b.gap == 0.0
    assert a.lb == pytest.approx(a.z)
    assert b.lb == pytest.approx(b.z)
    assert b.pi.shape == (1, 4)


def test_held_commitment_reproduces_the_clearing():
    """Pinning the cleared commitment and mode re-dispatches to the same cost."""
    y = cl(G, [R], D)
    z = lmp(G, [R], D, y)
    assert z.z == pytest.approx(y.z, rel=1e-9)
    assert z.gap == 0.0 and z.lb == pytest.approx(z.z)
    assert z.u == pytest.approx(y.u)
    assert z.sm == pytest.approx(y.sm)


def test_capacity_counts_discharge():
    """Demand above generation alone is accepted when a resource can cover the rest."""
    g = [U(lo=0.0, hi=40.0, c=20.0)]
    d = [20.0, 50.0]
    with pytest.raises(ValueError, match="exceeds"):
        cl(g, [], d)
    y = cl(g, [S(e=40.0, c=20.0, d=20.0, ec=1.0, ed=1.0, e0=40.0)], d)
    assert y.sd[0][1] >= 10.0 - 1e-6


@pytest.mark.parametrize(
    "kw,msg",
    [
        ({"e": 0.0}, "must be positive"),
        ({"c": -1.0}, "must be positive"),
        ({"dt": 0.0}, "must be positive"),
        ({"ec": 0.0}, "efficiencies"),
        ({"ed": 1.5}, "efficiencies"),
        ({"e0": 50.0}, "initial energy"),
        ({"ef": -1.0}, "terminal energy"),
        ({"k": -1.0}, "throughput"),
        ({"bus": 3}, "sit at a bus"),
        ({"e": np.inf}, "must be finite"),
    ],
)
def test_refused(kw, msg):
    """Every storage field is checked before a solver sees it."""
    q = {"e": 40.0, "c": 20.0, "d": 20.0, "ec": 1.0, "ed": 1.0, "e0": 0.0}
    with pytest.raises(ValueError, match=msg):
        ck(G, [S(**{**q, **kw})], D)


def test_resource_tuple_is_accepted():
    """A plain tuple is read as a resource, as a plain tuple is read as a unit."""
    a = cl(G, [R], D)
    b = cl(G, [(40.0, 20.0, 20.0, 1.0, 1.0, 0.0, None, 0.0, 0, 1.0)], D)
    assert b.z == pytest.approx(a.z)
