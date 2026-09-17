# Verification for the market interface: offer curves, charges and qualification.
#
# The load-bearing property is that the defaults change nothing. The replay's own
# assumption is full acceptance at no charge with every resource admitted, so bk = 0,
# tar = 0, qmin = 0 and qdur = 0 must reproduce the baseline run to the cent. The rest is
# arithmetic on a curve, which is checked against the slices by hand.
#
# LEGEND
#   CF,FX,fr   : the fixture configuration, its directory, the parsed frame
#   cv         : one offer curve
#   a,b        : the same replay under two configurations

import numpy as np
import pytest

from market import replay
from market.bid import accept, charge, clear, curve, qual
from market.cfg import Cf
from market.nyiso import frame

FX = "tests/fixtures/nyiso"
CF = Cf(root=FX, L=7, S=4, sp=12, lag=2, bt=(2, 6), bd=(6, 12),
        te=("2025-11-01", "2025-11-03"), rho=0.5)
LO, HI = "2025-10-25", "2025-11-03"


@pytest.fixture(scope="module")
def fr():
    return frame(CF.zone, LO, HI, FX, cache=False)


def test_curve_slices_the_position():
    """k slices of equal size, priced across the spread, monotone in the trading direction."""
    cv = curve(6.0, 100.0, 3, 0.2)
    assert cv[:, 1] == pytest.approx([2.0, 2.0, 2.0])
    assert cv[:, 0] == pytest.approx([80.0, 100.0, 120.0])
    assert (np.diff(cv[:, 0]) > 0).all()


def test_curve_reverses_for_a_buyer():
    """A charging position bids over the same band, best price first."""
    cv = curve(-6.0, 100.0, 3, 0.2)
    assert cv[:, 1] == pytest.approx([-2.0, -2.0, -2.0])
    assert cv[:, 0] == pytest.approx([120.0, 100.0, 80.0])


def test_curve_degenerates():
    """One step is a single block at the reference; no position is no curve."""
    assert curve(5.0, 40.0, 1, 0.5).ravel() == pytest.approx([40.0, 5.0])
    assert curve(0.0, 40.0, 3, 0.5).shape == (0, 2)
    for k, sp, msg in ((0, 0.1, "at least one step"), (2, -0.1, "non-negative")):
        with pytest.raises(ValueError, match=msg):
            curve(1.0, 40.0, k, sp)


def test_clear_takes_the_supported_slices():
    """A seller is taken where the price covers the reservation, a buyer where it does not."""
    cv = curve(6.0, 100.0, 3, 0.2)
    assert clear(cv, 70.0) == pytest.approx(0.0)
    assert clear(cv, 80.0) == pytest.approx(2.0)
    assert clear(cv, 110.0) == pytest.approx(4.0)
    assert clear(cv, 130.0) == pytest.approx(6.0)
    cb = curve(-6.0, 100.0, 3, 0.2)
    assert clear(cb, 130.0) == pytest.approx(0.0)
    assert clear(cb, 120.0) == pytest.approx(-2.0)
    assert clear(cb, 80.0) == pytest.approx(-6.0)
    assert clear(np.zeros((0, 2)), 50.0) == 0.0


def test_accept_is_identity_without_a_curve():
    """bk = 0 is the replay's own assumption: the position is taken in full."""
    q = np.array([1.0, -2.0, 0.0, 3.0])
    assert accept(q, np.full(4, 50.0), np.full(4, 10.0), 0, 0.5) == pytest.approx(q)


def test_accept_at_zero_spread_is_all_or_nothing():
    """With no spread the curve is one block, so the price either takes it or does not."""
    q = np.array([2.0, -2.0])
    ref = np.array([50.0, 50.0])
    assert accept(q, ref, np.array([60.0, 60.0]), 1, 0.0) == pytest.approx([2.0, 0.0])
    assert accept(q, ref, np.array([40.0, 40.0]), 1, 0.0) == pytest.approx([0.0, -2.0])
    assert accept(q, ref, ref, 1, 0.0) == pytest.approx([2.0, -2.0])


def test_accept_is_partial_across_the_spread():
    """A price inside the band takes part of the offer, which full acceptance cannot."""
    q = np.array([4.0])
    got = accept(q, np.array([100.0]), np.array([100.0]), 4, 0.3)
    assert 0.0 < float(got[0]) < 4.0


def test_accept_refuses_a_shape_mismatch():
    with pytest.raises(ValueError, match="share a shape"):
        accept(np.zeros(3), np.zeros(2), np.zeros(3), 2, 0.1)


def test_charge_is_metered_both_ways():
    """The charge falls on energy at the meter, so a round trip pays twice."""
    c, d = np.array([1.0, 0.0]), np.array([0.0, 1.0])
    assert charge(c, d, 3.0) == pytest.approx([3.0, 3.0])
    assert charge(c, d, 0.0) == pytest.approx([0.0, 0.0])
    with pytest.raises(ValueError, match="non-negative"):
        charge(c, d, -1.0)


def test_qual_screens():
    """Size and duration are screened; zero thresholds admit everything."""
    assert qual(1.0, 4.0, 0.0, 0.0) == (True, "")
    assert qual(1.0, 4.0, 1.0, 4.0)[0]
    assert not qual(1.0, 4.0, 5.0, 0.0)[0]
    assert "below the 5 MW minimum" in qual(1.0, 4.0, 5.0, 0.0)[1]
    assert not qual(1.0, 2.0, 0.0, 4.0)[0]
    assert "below the 4 h minimum" in qual(1.0, 2.0, 0.0, 4.0)[1]
    with pytest.raises(ValueError, match="must be positive"):
        qual(0.0, 4.0, 0.0, 0.0)


def test_defaults_reproduce_the_baseline(fr):
    """The market interface is off by default, to the cent and to the megawatt hour."""
    a = replay.run(fr, CF, "neutral", *CF.te)
    b = replay.run(fr, CF.rep(bk=0, bs=0.0, tar=0.0, qmin=0.0, qdur=0.0), "neutral", *CF.te)
    assert b.iv["q"] == pytest.approx(a.iv["q"])
    assert b.iv["c"] == pytest.approx(a.iv["c"])
    assert b.iv["d"] == pytest.approx(a.iv["d"])


def test_a_tariff_only_adds_cost(fr):
    """Charging metered energy cannot raise settlement, and raises the charge line."""
    a = replay.run(fr, CF, "neutral", *CF.te)
    b = replay.run(fr, CF.rep(tar=5.0), "neutral", *CF.te)
    fa = float(replay.settle(a.iv, CF)["fee"].sum())
    fb = float(replay.settle(b.iv, CF.rep(tar=5.0))["fee"].sum())
    assert fb > fa
    assert fb == pytest.approx(fa + 5.0 * float((b.iv["c"] + b.iv["d"]).sum()) / 12.0)


def test_an_offer_curve_cannot_take_more_than_the_position(fr):
    """Clearing an offer accepts a part of the position, never more than all of it."""
    a = replay.run(fr, CF, "neutral", *CF.te)
    b = replay.run(fr, CF.rep(bk=4, bs=0.25), "neutral", *CF.te)
    assert float(np.abs(b.iv["q"]).sum()) <= float(np.abs(a.iv["q"]).sum()) + 1e-6


def test_an_unqualified_resource_is_refused(fr):
    """A resource below the market's threshold never reaches a solver."""
    with pytest.raises(ValueError, match="does not qualify"):
        replay.run(fr, CF.rep(qmin=10.0), "neutral", *CF.te)
    with pytest.raises(ValueError, match="does not qualify"):
        replay.run(fr, CF.rep(qdur=8.0), "neutral", *CF.te)


@pytest.mark.parametrize(
    "kw,msg",
    [
        ({"bk": -1}, "negative number of steps"),
        ({"bk": 4, "bs": -0.1}, "bid spread"),
        ({"bs": float("inf")}, "bid spread"),
        ({"tar": -1.0}, "tariff rate"),
        ({"tar": float("nan")}, "tariff rate"),
    ],
)
def test_market_parameters_are_refused_before_a_solve(fr, monkeypatch, kw, msg):
    """A malformed market parameter stops the run, and stops it before any solving.

    Each of these would otherwise surface late or not at all: a negative spread inside the
    first day's offer, a negative rate inside its settlement, and a negative step count
    nowhere, because accept reads any step count below one as full acceptance. Counting
    calls into the solver is what separates refusing the configuration from discovering it
    partway through a replay; a wall clock would only say the fixture is small.
    """
    n = []
    monkeypatch.setattr(replay, "st", lambda *a, **k: n.append(1))
    with pytest.raises(ValueError, match=msg):
        replay.run(fr, CF.rep(**kw), "neutral", *CF.te)
    assert not n


@pytest.mark.parametrize("k", [1, 2, 3, 4, 5, 8])
@pytest.mark.parametrize("sp", [0.05, 0.25, 0.5])
def test_a_curve_centred_on_the_cleared_price_fills_half(k, sp):
    """At the reference price the fill is ceil(k/2)/k, whatever the spread.

    The curve is symmetric about ref and ties go to acceptance, so a cleared price landing
    exactly on ref takes the slices at or below it and no others. The spread moves where
    the slices sit, not how many are on each side, so it cancels out. This is the arithmetic
    behind the foresight caveat in docs/MARKET.md.
    """
    want = -(-k // 2) / k
    assert clear(curve(10.0, 50.0, k, sp), 50.0) == pytest.approx(10.0 * want)
    assert clear(curve(-10.0, 50.0, k, sp), 50.0) == pytest.approx(-10.0 * want)


def test_foresight_bids_into_its_own_price(fr):
    """Under fore the reference is the realized price, so an even curve fills exactly half.

    docs/MARKET.md warns that a foresight run with a curve stops being an upper reference.
    That is this: fore's scenario set is the realized path, so ref equals the cleared price
    in every hour and half the offered position is left behind for no informational reason.
    """
    a = replay.run(fr, CF, "fore", *CF.te)
    for k in (2, 4, 8):
        b = replay.run(fr, CF.rep(bk=k, bs=0.25), "fore", *CF.te)
        assert float(np.abs(b.iv["q"]).sum()) == pytest.approx(
            0.5 * float(np.abs(a.iv["q"]).sum()), rel=1e-9)


@pytest.mark.parametrize("ref", [80.0, -80.0])
@pytest.mark.parametrize("q", [10.0, -10.0])
def test_acceptance_is_monotone_at_a_negative_reference(ref, q):
    """Acceptance sweeps from nothing to the whole position as the cleared price rises.

    At a negative reference the rows are no longer sorted, which the docstring used to
    claim they were. Nothing reads the order, so the property that matters survives: a
    seller takes more as the price rises and a buyer takes less, which in signed terms is
    the same monotone sweep, from one end of the band to the other.
    """
    cv = curve(q, ref, 6, 0.3)
    lo, hi = float(cv[:, 0].min()), float(cv[:, 0].max())
    got = [clear(cv, p) for p in np.linspace(lo - 10.0, hi + 10.0, 60)]
    assert got == sorted(got)
    assert clear(cv, lo - 10.0) == pytest.approx(0.0 if q > 0 else q)
    assert clear(cv, hi + 10.0) == pytest.approx(q if q > 0 else 0.0)
