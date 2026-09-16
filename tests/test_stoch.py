# Verification for the two-stage stochastic clearing.
#
# The independent checks are the two bounds every two-stage program satisfies, computed
# here by running models/joint.py once per scenario rather than by reading this module's
# rows. Writing SP for the stochastic optimum, WS for the wait-and-see value and EEV for
# the mean-value commitment evaluated against every scenario,
#
#     WS <= SP <= EEV,
#
# so the expected value of perfect information and the value of the stochastic solution are
# both non-negative. A commitment that failed to bind across scenarios would break the
# right inequality; a scenario block that leaked information would break the left.
#
# LEGEND
#   g,d,pr   : units, scenario demand, probabilities
#   a,b      : the same market cleared two ways
#   ws,sp,ee : the three values above
#   ub       : mean-value commitment

import numpy as np
import pytest

from models.joint import S
from models.joint import cl as jcl
from models.joint import lmp as jlmp
from models.stoch import Sc, ck, cl, lmp
from models.uc_price import Net, U

# A rare spike: demand is 20 nine times in ten and 120 once. The mid-merit unit costs
# 1,000 an hour merely to be on, so the mean demand of 30 does not justify committing it
# while the spike does. That gap is what makes the stochastic commitment differ from the
# deterministic one here.
G = [U(lo=0.0, hi=40.0, c=20.0),
     U(lo=0.0, hi=100.0, c=40.0, nl=1000.0),
     U(lo=0.0, hi=200.0, c=500.0)]
D = np.array([[[10.0, 20.0]], [[10.0, 120.0]]])
PR = np.array([0.9, 0.1])


def test_one_scenario_is_the_joint_clearing():
    """A single scenario of probability one is joint's own program, cost and price."""
    d = np.array([[30.0, 30.0, 90.0, 30.0]])
    g = G[:1] + [U(lo=0.0, hi=60.0, c=80.0)]
    a, b = jcl(g, [], d), cl(g, [], d[None, :, :])
    assert b.z == pytest.approx(a.z, rel=1e-9)
    assert b.mean == pytest.approx(a.z, rel=1e-9)
    assert lmp(g, [], d[None, :, :], b).pi.ravel() == pytest.approx(
        jlmp(g, [], d, a).pi.ravel(), abs=1e-4)


def test_identical_scenarios_change_nothing():
    """Repeating one demand cannot change the commitment or the expected cost."""
    d = np.array([[30.0, 30.0, 90.0, 30.0]])
    g = G[:1] + [U(lo=0.0, hi=60.0, c=80.0)]
    a = jcl(g, [], d)
    b = cl(g, [], np.repeat(d[None, :, :], 4, axis=0), np.full(4, 0.25))
    assert b.mean == pytest.approx(a.z, rel=1e-9)
    assert b.u == pytest.approx(a.u)


def test_commitment_is_common():
    """One commitment serves every scenario; only the dispatch answers the scenario."""
    r = cl(G, [], D, PR)
    assert r.u.shape == (3, 2)
    assert np.isin(r.u, [0.0, 1.0]).all()
    assert r.p.shape == (2, 3, 2)
    assert not np.allclose(r.p[0], r.p[1])
    assert float(PR @ r.q) == pytest.approx(r.mean, rel=1e-9)


def test_bounds_hold():
    """WS <= SP <= EEV, each computed by running the one-scenario model.

    WS solves every scenario knowing which one it is, so it cannot cost more. EEV commits
    to the mean demand and then meets each scenario with that commitment, so it cannot cost
    less. Both are computed with models/joint.py, which does not share an assembly with the
    module under test.
    """
    ws = float(PR @ np.array([jcl(G, [], D[s]).z for s in range(len(PR))]))
    r = cl(G, [], D, PR)
    ub = jcl(G, [], (PR[:, None, None] * D).sum(0)).u
    ee = lmp(G, [], D, Sc(*([0.0] * 4 + [ub] + [None] * 6 + [""])), PR).mean
    assert ws <= r.mean + 1e-6
    assert r.mean <= ee + 1e-6
    assert ws == pytest.approx(1060.0)
    assert r.mean == pytest.approx(1960.0)
    assert ee == pytest.approx(4640.0)
    assert r.mean - ws == pytest.approx(900.0)
    assert ee - r.mean == pytest.approx(2680.0)
    assert not np.array_equal(r.u, ub)


def test_scenario_prices_are_unweighted():
    """A balance dual carries its scenario's probability; the price divides it back out.

    With three demands served from the same merit order the marginal offer is the same in
    each, so the price must be the offer and not the offer times a probability.
    """
    g = [U(lo=0.0, hi=60.0, c=20.0), U(lo=0.0, hi=60.0, c=80.0)]
    d = np.array([[[30.0, 30.0, 70.0, 30.0]],
                  [[30.0, 30.0, 90.0, 30.0]],
                  [[30.0, 30.0, 110.0, 30.0]]])
    pr = np.array([0.3, 0.4, 0.3])
    r = cl(g, [], d, pr)
    q = lmp(g, [], d, r, pr)
    for s in range(3):
        assert q.pi[s].ravel() == pytest.approx([20.0, 20.0, 80.0, 20.0], abs=1e-4)


def test_risk_moves_the_tail():
    """Weighting the tail cannot leave a worse tail than ignoring it."""
    a = cl(G, [], D, PR, w=0.0, al=0.5)
    b = cl(G, [], D, PR, w=1.0, al=0.5)
    assert b.cv <= a.cv + 1e-6
    assert a.mean <= b.mean + 1e-6
    assert float(PR @ a.q) == pytest.approx(a.mean, rel=1e-9)


def test_cvar_matches_the_weighted_tail():
    """The reported CVaR is the weighted tail of the scenario costs, read independently."""
    r = cl(G, [], D, PR, w=0.0, al=0.5)
    y, p = r.q[np.argsort(r.q)], PR[np.argsort(r.q)]
    c = np.cumsum(p)
    j = int(np.searchsorted(c, 0.5, side="left"))
    tail = (np.r_[c[j] - 0.5, p[j + 1 :]] @ y[j:]) / 0.5
    assert r.cv == pytest.approx(float(tail), rel=1e-9)


def test_storage_answers_each_scenario():
    """A resource carries one initial state into every scenario and diverges after it."""
    st = [S(e=40.0, c=20.0, d=20.0, ec=1.0, ed=1.0, e0=20.0, k=0.0)]
    r = cl(G, st, D, PR)
    assert r.se.shape == (2, 1, 2)
    assert (r.sc * r.sd == pytest.approx(0.0, abs=1e-9))
    for s in range(2):
        e = np.r_[20.0, r.se[s, 0][:-1]] + r.sc[s, 0] - r.sd[s, 0]
        assert r.se[s, 0] == pytest.approx(e, abs=1e-9)


def test_network_is_carried_per_scenario():
    """Each scenario gets its own flows on the same network."""
    net = Net(bus=np.array([0, 1, 1]), ln=((0, 1, 0.1, 40.0),), nb=2, fm="dc")
    d = np.array([[[10.0, 50.0], [0.0, 0.0]], [[10.0, 30.0], [0.0, 0.0]]])
    r = cl(G, [], d, PR, net=net)
    assert r.p.shape == (2, 3, 2)
    q = lmp(G, [], d, r, PR, net=net)
    assert q.pi.shape == (2, 2, 2)


@pytest.mark.parametrize(
    "kw,msg",
    [
        ({"pr": [0.5, 0.6]}, "sum to one"),
        ({"pr": [0.5]}, "one probability per scenario"),
        ({"pr": [0.0, 1.0]}, "must be positive"),
        ({"w": 1.5}, "risk weight"),
        ({"al": 1.0}, "confidence"),
    ],
)
def test_refused(kw, msg):
    """Probabilities and risk parameters are checked before a solver sees them."""
    q = {"pr": PR, "w": 0.0, "al": 0.95}
    with pytest.raises(ValueError, match=msg):
        ck(G, [], D, **{**q, **kw})


def test_demand_shape_refused():
    with pytest.raises(ValueError, match="scenarios, buses, periods"):
        ck(G, [], np.zeros((2, 2, 2, 2)))
