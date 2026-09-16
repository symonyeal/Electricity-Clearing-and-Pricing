# Independent physics, settlement, information and risk checks for storage.
# Synthetic cases state the property they are meant to exhibit.

import numpy as np
import pytest
from scipy.optimize import linprog

from models.storage import B, cvar, en, st


def ck(b, da, rt, pr, h, r, a=0.95, w=0.0, fix=False):
    """Audit returned schedules directly, without either formulation's row builder.

    A fixed position is contractual, so only the scenario paths are physical.
    """
    i = 1 if fix else 0
    c, d = r.c[i:], r.d[i:]
    assert np.all(c >= -1e-7) and np.all(c <= b.c + 1e-7)
    assert np.all(d >= -1e-7) and np.all(d <= b.d + 1e-7)
    assert np.max(np.minimum(c, d)) < 1e-7
    e = b.e0 + b.dt * np.cumsum(b.ec * c - d / b.ed, axis=1)
    assert r.e[i:] == pytest.approx(e, abs=1e-7)
    assert np.all(e >= -1e-7) and np.all(e <= b.e + 1e-7)
    assert e[:, -1] == pytest.approx(np.full(len(e), b.ef), abs=1e-7)
    assert np.isnan(r.e[0]).all() if fix else np.all(np.isfinite(r.e[0]))
    assert r.q == pytest.approx(r.d[0] - r.c[0])
    z = b.dt * (np.asarray(da) @ r.q + (np.asarray(rt) * (r.d[1:] - r.c[1:] - r.q)
                                      - b.k * (r.c[1:] + r.d[1:])).sum(axis=1))
    assert r.r == pytest.approx(z)
    assert r.mu == pytest.approx(np.asarray(pr) @ z)
    assert r.cv == pytest.approx(cvar(z, pr, a))
    assert r.z == pytest.approx((1 - w) * r.mu - w * r.cv)
    assert r.ub >= r.z - 1e-7 and r.gap >= 0
    for t in range(len(da)):
        for i in range(len(pr)):
            for j in range(i):
                if h is None or h[i, t] == h[j, t]:
                    assert r.c[i + 1, t] == pytest.approx(r.c[j + 1, t], abs=1e-7)
                    assert r.d[i + 1, t] == pytest.approx(r.d[j + 1, t], abs=1e-7)


@pytest.mark.parametrize("f", [st, en])
def test_cycle(f):
    """Buy 1 MW for two hours; export 0.72 MW for two hours after 72% round-trip efficiency."""
    b = B(2, 1, 1, 0.8, 0.9, k=2, dt=2)
    da, rt, pr = [10, 100], [[10, 100]], [1]
    r = f(b, da, rt, pr)
    assert r.mu == pytest.approx(2 * (100 * 0.72 - 10 - 2 * 1.72))
    ck(b, da, rt, pr, None, r)


@pytest.mark.parametrize("f", [st, en])
def test_negative_price(f):
    """A cyclic one-period battery cannot earn revenue by dissipating energy internally."""
    b = B(1, 1, 1, 0.9, 0.9)
    r = f(b, [-100], [[-100]], [1])
    assert r.z == pytest.approx(0)
    ck(b, [-100], [[-100]], [1], None, r)
    lp = linprog([-100, 100], A_eq=[[0.9, -1 / 0.9]], b_eq=[0], bounds=[(0, 1)] * 2)
    assert -lp.fun == pytest.approx(19)


@pytest.mark.parametrize("f", [st, en])
def test_terminal(f):
    b = B(2, 1, 1, 1, 1, e0=1, ef=0.5)
    r = f(b, [100], [[100]], [1])
    assert r.mu == pytest.approx(50)
    ck(b, [100], [[100]], [1], None, r)


@pytest.mark.parametrize("f", [st, en])
def test_settlement(f):
    """Forward sale pays 40, physical energy pays 100, deviation buys back the sale at 100."""
    b = B(1, 1, 1, 1, 1, e0=1)
    r = f(b, [40], [[100]], [1], q=[1])
    assert r.q == pytest.approx([1])
    assert r.r == pytest.approx([40])
    ck(b, [40], [[100]], [1], None, r, fix=True)


@pytest.mark.parametrize("f", [st, en])
def test_information(f):
    """Knowing tomorrow's sign today creates 45 of foresight value; learning tomorrow does not."""
    b, da, rt, pr = B(1, 1, 1, 1, 1), [10, 0], [[10, 100], [10, -100]], [0.5, 0.5]
    late = np.array([[0, 1], [0, 2]])
    early = np.array([[0, 0], [1, 1]])
    for h in (None, late):
        r = f(b, da, rt, pr, h, q=[0, 0])
        assert r.mu == pytest.approx(0)
        ck(b, da, rt, pr, h, r, fix=True)
    r = f(b, da, rt, pr, early, q=[0, 0])
    assert r.mu == pytest.approx(45)
    ck(b, da, rt, pr, early, r, fix=True)


@pytest.mark.parametrize("f", [st, en])
def test_risk(f):
    """Expected-value dispatch risks a loss of 110; a physical forward hedge locks in 30."""
    b, da, rt, pr = B(1, 1, 1, 1, 1), [10, 40], [[10, 100], [10, -100]], [0.8, 0.2]
    r = f(b, da, rt, pr, a=0.8)
    assert r.mu == pytest.approx(50)
    assert r.cv == pytest.approx(110)
    for w in [0.5, 1.0]:
        r = f(b, da, rt, pr, a=0.8, w=w)
        assert r.r == pytest.approx([30, 30])
        ck(b, da, rt, pr, None, r, 0.8, w)


@pytest.mark.parametrize("f", [st, en])
def test_offer_versus_obligation(f):
    """An offer must be deliverable now; an obligation already sold only settles."""
    b, da, rt, pr = B(1, 1, 1, 1, 1), [100], [[10]], [1]
    assert f(b, da, rt, pr).q == pytest.approx([0])
    r = f(b, da, rt, pr, q=[1])
    assert r.r == pytest.approx([90])
    assert np.all(r.c[1:] == 0) and np.all(r.d[1:] == 0)
    ck(b, da, rt, pr, None, r, fix=True)


@pytest.mark.parametrize("f", [st, en])
def test_obligation_after_deviation(f):
    """Real time left the battery empty; the sold hour settles instead of failing."""
    b, da, rt, pr, q = B(1, 1, 1, 1, 1), [50, 10], [[80, 5]], [1], [1, -1]
    r = f(b, da, rt, pr, q=q)
    assert r.r == pytest.approx([50 - 10 - 80 + 5])
    assert np.all(r.e[1:] == pytest.approx(0))
    ck(b, da, rt, pr, None, r, fix=True)


@pytest.mark.parametrize("f", [st, en])
def test_scenario_day_ahead(f):
    """The forward price is not known when the offer is made, so it varies by scenario."""
    b = B(1, 1, 1, 1, 1, e0=1)
    da, rt, pr = [[100, 10], [60, 10]], [[50, 50], [50, 50]], [0.5, 0.5]
    r = f(b, da, rt, pr)
    assert r.q == pytest.approx([1, 0])
    assert r.r == pytest.approx([100, 60])
    assert r.mu == pytest.approx(80)
    ck(b, da, rt, pr, None, r)


def test_cvar():
    """The worst 25% includes all 20% of loss 10 and 5% of loss 0."""
    assert cvar([-10, 0, 20], [0.2, 0.3, 0.5], 0.75) == pytest.approx(8)
    assert cvar([-10, 0, 20], [0.2, 0.3, 0.5], 0) == pytest.approx(-8)
    assert cvar([5, 5], [0.4, 0.6], 0.9) == pytest.approx(-5)
    assert cvar([-10, 0, 20], [0.2, 0.3, 0.5], 0.99) == pytest.approx(10)


@pytest.mark.parametrize("seed", range(12))
def test_routes(seed):
    rng = np.random.default_rng(seed)
    b = B(2, 1.5, 1, 0.8, 0.9, e0=0.5, ef=0.5, k=1, dt=0.5)
    da, rt, pr = rng.uniform(-100, 150, 3), rng.uniform(-100, 150, (2, 3)), [0.3, 0.7]
    h = np.array([[0, 1, 2], [0, 1, 3]]) if seed % 2 else None
    a, w = 0.6, (seed % 3) / 2
    r, v = st(b, da, rt, pr, h, a, w), en(b, da, rt, pr, h, a, w)
    assert r.z == pytest.approx(v.z, abs=1e-7)
    assert r.ub == pytest.approx(r.z, abs=1e-7)
    ck(b, da, rt, pr, h, r, a, w)
    ck(b, da, rt, pr, h, v, a, w)


@pytest.mark.parametrize("seed", range(12))
def test_routes_fixed(seed):
    """Both routes dispatch the same way against a position they cannot deliver."""
    rng = np.random.default_rng(100 + seed)
    b = B(2, 1.5, 1, 0.8, 0.9, e0=0.5, ef=0.5, k=1, dt=0.5)
    da, rt, pr = rng.uniform(-100, 150, 3), rng.uniform(-100, 150, (2, 3)), [0.3, 0.7]
    h = np.array([[0, 1, 2], [0, 1, 3]]) if seed % 2 else None
    a, w, q = 0.6, (seed % 3) / 2, rng.uniform(-3, 3, 3)
    r, v = st(b, da, rt, pr, h, a, w, q), en(b, da, rt, pr, h, a, w, q)
    assert r.z == pytest.approx(v.z, abs=1e-7)
    assert r.ub == pytest.approx(r.z, abs=1e-7)
    ck(b, da, rt, pr, h, r, a, w, fix=True)
    ck(b, da, rt, pr, h, v, a, w, fix=True)


@pytest.mark.parametrize("kw", [
    {"pr": [0, 1]}, {"pr": [0.4, 0.4]}, {"pr": [1]}, {"rt": [[1]]},
    {"da": [np.nan, 2]}, {"w": -1}, {"a": 1}, {"q": [np.inf, 0]},
    {"h": [[0, 0], [1, 0]]}, {"h": [[0.1, 0.1], [0.2, 0.2]]},
    {"da": [[1, 2], [1, 2], [1, 2]]}, {"da": [[[1, 2], [1, 2]]]}, {"da": [1, 2, 3]},
    {"b": B(1, 1, 1, ec=0)}, {"b": B(1, 1, 1, dt=0)}, {"b": B(1, 1, 1, ef=2)},
    {"b": B(1, -1, 1)}, {"b": B(1, 1, 1, k=-1)}, {"b": B(1, 1, 1, ed=1.1)},
])
def test_inputs(kw):
    args = {"b": B(1, 1, 1), "da": [1, 2], "rt": [[1, 2], [1, 3]], "pr": [0.5, 0.5]}
    args.update(kw)
    for f in (st, en):
        with pytest.raises(ValueError):
            f(**args)


def test_limits():
    with pytest.raises(ValueError, match="enumeration exceeds"):
        en(B(1, 1, 1), [1] * 7, [[1] * 7], [1])
    for f in (st, en):
        with pytest.raises(ValueError):
            f(B(2, 1, 1, ef=2), [1], [[1]], [1])


def test_zero_capacity():
    for f in (st, en):
        r = f(B(0, 0, 0), [1, 2], [[1, 2]], [1])
        assert r.z == pytest.approx(0)


def test_failure(monkeypatch):
    """An incumbent without a gap certificate must never be returned as an optimum."""
    from types import SimpleNamespace
    monkeypatch.setattr("models.storage.milp", lambda *a, **k:
                        SimpleNamespace(success=False, message="time limit", x=np.zeros(10)))
    with pytest.raises(ValueError, match="requested gap"):
        st(B(1, 1, 1), [1], [[1]], [1])
