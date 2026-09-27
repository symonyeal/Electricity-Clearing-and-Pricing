# Verification for the prices of a risk-averse clearing: stoch.cvd and models/risk.py.
#
# The risk-averse program, integers held, is a linear program; its KKT conditions give
# every identity asserted here. With om_s = (1 - w) p_s + mu_s the weight on scenario s's
# cost, the balance dual is y_s = om_s lam_s, lam_s a dual of scenario s's own re-dispatch;
# stationarity in the CVaR level gives sum mu = w, and in each excess mu_s <= w p_s/(1-al).
# The independent routes are stoch.lmp, which prices the expected-cost re-dispatch and
# shares no risk row with cvd, and the closed-form risk envelope _te, which reads only the
# scenario costs. The examples' numbers are arithmetic in their docstrings. Prices are
# compared to 1e-4/MWh and money to a tenth of a cent, the tolerances of test_uc_price.
#
# LEGEND
#   K          : models/risk.py                 EX : its five examples
#   g,st,d,pr  : units, resources, scenario demand, probabilities    w,al : risk weight, level
#   s0,s       : the risk-neutral and the risk-averse clearing
#   c          : cvd at the risk-averse clearing      L0,L : lmp at s0 and at s
#   e0,e       : settlements at the expected-cost price under s0 and under s
#   v          : the value-of-information record

import numpy as np
import pytest

import models.risk as K
from models.stoch import _te, cl, cvd, lmp
from models.uc_price import mk
from tests.test_uc_price import CENT

EX = [K.r1, K.r2, K.r3, K.r4, K.r5]


def _all(f):
    g, st, d, pr, w, al = f()
    s0, s = cl(g, st, d, pr), cl(g, st, d, pr, w=w, al=al)
    return g, st, d, pr, w, al, s0, s, lmp(g, st, d, s0, pr), lmp(g, st, d, s, pr), \
        cvd(g, st, d, s, pr, w=w, al=al)


@pytest.mark.parametrize("f", EX)
def test_the_held_program_is_the_one_that_cleared(f):
    """Holding the integers of the risk-averse clearing leaves its value unchanged."""
    *_, s, _L0, _L, c = _all(f)
    assert c.z == pytest.approx(s.z, rel=1e-9)


def _tie():
    """r2's market with the spike removed: two equal scenarios, so every envelope point ties."""
    g, st, d, pr, w, al = K.r2()
    return g, st, np.stack([d[0], d[0]]), pr, w, al


@pytest.mark.parametrize("f", EX + [_tie])
def test_the_multipliers_form_a_risk_measure(f):
    """sum mu = w, 0 <= mu <= w p / (1 - al), so om = (1 - w) p + mu is a probability."""
    _g, _st, _d, pr, w, al, *_, c = _all(f)
    assert c.mu.sum() == pytest.approx(w, abs=1e-9)
    assert (c.mu >= -1e-9).all() and (c.mu <= w * pr / (1.0 - al) + 1e-9).all()
    assert c.om.sum() == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("f", EX + [_tie])
def test_the_multipliers_are_the_risk_envelope(f):
    """mu / w maximises th'q over 0 <= th <= p / (1 - al), sum th = 1: it attains CVaR.

    _te is one maximiser, filled from the dearest scenario; it reads only q, never a dual.
    The previous test is feasibility, so an equal objective makes mu / w optimal. With
    distinct costs the maximiser is unique and mu = w th; at a tie the program may select
    any point of the optimal face.
    """
    _g, _st, _d, pr, w, al, *_, c = _all(f)
    th = _te(c.q, pr, al)
    assert c.mu @ c.q == pytest.approx(w * th @ c.q, rel=1e-9)
    if len(np.unique(c.q)) == len(c.q):
        assert c.mu == pytest.approx(w * th, abs=1e-9)


@pytest.mark.parametrize("f", [K.r1, K.r2, K.r3, K.r5, _tie])
def test_the_raw_dual_is_the_weighted_scenario_price(f):
    """y_s = om_s lam_s, and lam_s is the expected-cost re-dispatch's price.

    Where om_s > 0 both programs minimise scenario s's cost over the held integers, so both
    duals lie on that scenario's dual face. Here the face is a point: the examples' ramps
    equal their capacities, so a unit strictly inside (0, hi) binds no row, and
    complementary slackness (BT Theorem 4.5) sets every optimal dual's price to its cost.
    Every scenario and period has such a unit.
    """
    g, *_, L, c = _all(f)
    x = [mk(q) for q in g]
    assert all(q.ru == q.rd == q.sr == q.dr == q.hi for q in x)
    for k, t in np.ndindex(L.p.shape[0], L.p.shape[2]):
        assert any(1e-6 < L.p[k, i, t] < q.hi - 1e-6 and abs(L.pi[k, 0, t] - q.c) < 1e-4
                   for i, q in enumerate(x))
    assert c.lam == pytest.approx(L.pi, abs=1e-4)
    assert c.y == pytest.approx(c.om[:, None, None] * L.pi, abs=1e-4)


def test_the_views_agree_when_the_tail_is_the_whole_distribution():
    """r1, al = 0: CVaR is the mean, mu = w p, om = p, and y / p is already the price."""
    *_, pr, _w, _al, _s0, _s, _L0, L, c = _all(K.r1)
    assert c.om == pytest.approx(pr, abs=1e-9)
    assert c.y / pr[:, None, None] == pytest.approx(L.pi, abs=1e-4)


def test_the_views_part_when_the_tail_is_not():
    """r2: om = (0.85, 0.15), so y / p scales the prices (20, 20 | 20, 40) by om / p.

    The base scenario's price falls to 18.889, below the cheap unit's own 20, and the spike
    scenario's doubles in period 1 to 30. Neither is a dual of any scenario's program.
    """
    *_, pr, _w, _al, _s0, _s, _L0, L, c = _all(K.r2)
    assert c.om == pytest.approx([0.85, 0.15], abs=1e-9)
    assert L.pi.reshape(2, -1) == pytest.approx(np.array([[20.0, 20.0], [20.0, 40.0]]),
                                                abs=1e-4)
    assert (c.y / pr[:, None, None]).reshape(2, -1) == pytest.approx(
        np.array([[170.0 / 9.0, 170.0 / 9.0], [30.0, 60.0]]), abs=1e-4)


def test_a_scenario_outside_the_tail_carries_no_price():
    """r4, w = 1: the base scenario lies below the quantile, so om = 0 and y = 0 there.

    Nothing then determines that scenario's cost: every dispatch with cost at most the
    level 5,200 is optimal, and the program's value is the spike's cost alone. The
    expected-cost re-dispatch prices the scenario at (20, 20) at cost 1,600; the program
    that cleared carries no price for it, and lam is nan by construction, not by failure.
    """
    *_, s, _L0, L, c = _all(K.r4)
    assert c.om == pytest.approx([0.0, 1.0], abs=1e-9)
    assert c.y[0] == pytest.approx(0.0, abs=1e-9) and np.isnan(c.lam[0]).all()
    assert c.z == pytest.approx(s.z) == pytest.approx(5200.0) == pytest.approx(c.q[1])
    assert L.q[0] == pytest.approx(1600.0) and c.q[0] <= c.zt + 1e-6
    assert c.lam[1] == pytest.approx(L.pi[1], abs=1e-4)


def test_risk_can_change_the_commitment_and_no_price():
    """r3: M is committed only under risk, and every expected-cost price is unchanged.

    Load pays 1,592 in expectation either way. M's 1,000 is covered by its 22,000 margin in
    the spike and by make-whole in the base scenario, 980 in expectation; the 540 the hedge
    adds to expected cost is exactly what the units' expected profit loses.
    """
    g, _st, d, pr, *_, s0, s, L0, L, _c = _all(K.r3)
    assert (s0.u[1], s.u[1]) == pytest.approx(([0.0], [1.0]))
    assert L.pi == pytest.approx(L0.pi, abs=1e-4)
    e0, e = K.se(g, d, pr, s0.u, L0.p, L0.pi), K.se(g, d, pr, s.u, L.p, L.pi)
    assert (e0.EL, e.EL) == pytest.approx((1592.0, 1592.0), abs=CENT)
    assert (e0.Emw, e.Emw) == pytest.approx((0.0, 980.0), abs=CENT)
    assert e0.Er - e.Er == pytest.approx(L.mean - L0.mean, abs=CENT) == pytest.approx(540.0)


def test_risk_can_change_the_commitment_and_the_price():
    """r5: committing M moves the spike's price from P's 500 to M's 40.

    Expected load payment falls from 1,592 to 488 while expected make-whole rises from 0 to
    1,000: the hedge is paid for outside the energy price.
    """
    g, _st, d, pr, *_, s0, s, L0, L, _c = _all(K.r5)
    assert (L0.pi[1, 0, 0], L.pi[1, 0, 0]) == pytest.approx((500.0, 40.0), abs=1e-4)
    e0, e = K.se(g, d, pr, s0.u, L0.p, L0.pi), K.se(g, d, pr, s.u, L.p, L.pi)
    assert (e0.EL, e.EL) == pytest.approx((1592.0, 488.0), abs=CENT)
    assert (e0.Emw, e.Emw) == pytest.approx((0.0, 1000.0), abs=CENT)


def test_the_raw_dual_prices_the_hedge_under_the_planner_s_measure():
    """r3: at the scenario prices M loses 540 in expectation under p and gains 3,830 under om.

    y_s is the price, paid ex ante, of 1 MWh delivered in scenario s: om_s lam_s. Settled
    ex post as y_s / p_s it has the same expectation, sum_s y_s d_s = 12,916 against the
    1,592 load pays at scenario marginal cost. That is a settlement under the planner's
    measure om, not under the scenarios' probabilities.
    """
    g, _st, d, pr, *_, s, _L0, L, c = _all(K.r3)
    e = K.se(g, d, pr, s.u, L.p, L.pi)
    assert pr @ e.r[:, 1] == pytest.approx(-540.0, abs=CENT)
    assert c.om @ e.r[:, 1] == pytest.approx(3830.0, abs=CENT)
    assert float((c.y * d).sum()) == pytest.approx(12916.0, abs=CENT)
    assert K.se(g, d, pr, s.u, c.p, c.y / pr[:, None, None]).EL == pytest.approx(12916.0,
                                                                                abs=CENT)


@pytest.mark.parametrize("f", EX)
def test_the_value_of_information_chains_hold_under_both_measures(f):
    """WS <= SP <= EEV under E and under rho, each on the same scenario cost vectors."""
    g, st, d, pr, w, al = f()
    v = K.vi(g, st, d, pr, None, w, al)
    assert v.ws <= v.sp + 1e-6 <= v.ee + 2e-6
    assert v.wsr <= v.spr + 1e-6 <= v.eer + 2e-6
    assert v.mr >= v.sp - 1e-6


def test_the_two_measures_disagree_about_information():
    """r4 values perfect information at 900 in expectation and at 0 under rho; r3's
    mean-value commitment is the stochastic one in expectation, VSS 0, and 3,830 worse
    under rho. Each number belongs to its own objective and they do not compare."""
    v = K.vi(*K.r4()[:4], None, *K.r4()[4:])
    assert (v.evpi, v.evpir) == pytest.approx((900.0, 0.0), abs=1e-6)
    v = K.vi(*K.r3()[:4], None, *K.r3()[4:])
    assert (v.vss, v.vssr) == pytest.approx((0.0, 3830.0), abs=1e-6)
