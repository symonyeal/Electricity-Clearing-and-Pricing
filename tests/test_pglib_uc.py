# Verification for the pglib-uc reference unit commitment.
#
# The external check is the reference implementation the library publishes, uc_model.py,
# run on the same committed instance. Its linear relaxation is a deterministic number: it
# has no integer solution to choose between and no gap to stop at, so two implementations
# of the same formulation must land on it. Every piecewise point, every start-up category
# and every row enters that number, which is why it catches the loader defect this model
# exists to rule out.
#
# LEGEND
#   D,F       : the committed instance directory and file
#   SHA       : the official file's SHA-256
#   LP        : the reference implementation's linear relaxation objective
#   MIP1      : an incumbent the reference formulation admits at a 1% gap
#   ld,_sy,cl : read one instance, assemble its rows, clear it
#   d         : one parsed instance      x : one unit record
#   c,A,b     : objective, inequality rows and right side
#   Ae,be     : equality rows and right side    lb,ub,it : bounds and integrality
#   r,z       : a solver result and its objective
#   q         : a scratch copy used to break one field
#   px,Px     : price one clearing, and the record it returns
#   two       : a two-unit instance whose prices are arithmetic by hand
#   pe,pr     : energy price and reserve price, per period
#   pay       : what demand and reserve pay at those prices

import hashlib
import json
from pathlib import Path

import pytest
import numpy as np
from scipy.optimize import linprog

from models.pglib_uc import _hold, _ix, _run, _sy, cl, ld, px

D = Path(__file__).resolve().parent.parent / "data" / "pglib_uc"
F = D / "rts_gmlc_2020-03-05.json"
SHA = "0F89BF93327B5F90BB7381C1E7AE08614B60DEF2390E2E8940F40B9CF825045F"
LP = 2480427.041110388
MIP1 = 2520108.887153369


def test_file():
    """The committed instance is the official file, byte for byte."""
    assert hashlib.sha256(F.read_bytes()).hexdigest().upper() == SHA


def test_read():
    """Every field the instance carries is represented, and the shape is the published one."""
    d = ld(F)
    assert d["T"] == 48
    assert len(d["th"]) == 73
    assert len(d["re"]) == 81
    assert len(d["demand"]) == 48
    assert len(d["reserves"]) == 48
    assert sum(len(x["piecewise_production"]) for x in d["th"]) > 73
    assert sum(len(x["startup"]) for x in d["th"]) > 73


def test_reject():
    """An unread field is refused rather than dropped. That is the whole point of the gate."""
    d = json.loads(F.read_text(encoding="utf-8"))
    q = dict(d, storage={})
    F.with_suffix(".tmp").write_text(json.dumps(q), encoding="utf-8")
    with pytest.raises(ValueError, match="does not represent"):
        ld(F.with_suffix(".tmp"))
    q = json.loads(F.read_text(encoding="utf-8"))
    next(iter(q["thermal_generators"].values()))["fuel"] = "gas"
    F.with_suffix(".tmp").write_text(json.dumps(q), encoding="utf-8")
    with pytest.raises(ValueError, match="unread fields"):
        ld(F.with_suffix(".tmp"))
    F.with_suffix(".tmp").unlink()


def test_size():
    """The assembled program has one column per variable the reference model declares."""
    d = ld(F)
    c, A, _b, Ae, _be, _lb, _ub, it = _sy(d)
    T, th, re = d["T"], d["th"], d["re"]
    n = 6 * len(th) * T + sum(len(x["startup"]) for x in th) * T
    n += sum(len(x["piecewise_production"]) for x in th) * T + len(re) * T
    assert len(c) == n
    assert int(it.sum()) == 3 * len(th) * T + sum(len(x["startup"]) for x in th) * T
    assert A.shape[1] == n and Ae.shape[1] == n


def test_relaxation():
    """The external gate: the same linear relaxation as the published reference model.

    Run on 2026-09-15 against pglib-uc's own uc_model.py under HiGHS, with its integrality
    relaxed: 2480427.041110388. Dropping a piecewise point or a start-up category moves
    this number, which is how a quietly lossy loader is caught.
    """
    d = ld(F)
    c, A, b, Ae, be, lb, ub, _it = _sy(d)
    r = linprog(c, A_ub=A, b_ub=b, A_eq=Ae, b_eq=be, bounds=list(zip(lb, ub)))
    assert r.status == 0
    assert float(r.fun) == pytest.approx(LP, rel=1e-9)


@pytest.mark.slow
def test_clear():
    """Clearing at the reference script's own 1% gap lands inside the gap it asks for.

    The optimum is not pinned here: at a 1% gap the solver may return any incumbent within
    it, so an equality would assert the solver's search order rather than the model. What
    is asserted is that the incumbent is no cheaper than the relaxation and no dearer than
    the gap allows. A model missing a cost or a restriction fails the lower bound.
    """
    r = cl(ld(F), 0.01)
    z = r.z
    assert z >= LP
    assert z <= MIP1 * 1.01
    assert LP - 1e-6 <= r.lb <= z + 1e-6
    assert 0 <= r.gap <= 0.01
    assert r.gap == pytest.approx((z - r.lb) / abs(z), abs=1e-9)
    assert r.st == ("opt" if r.gap == 0 else "gap")


def test_certificate(monkeypatch):
    """Report the solver's bound and gap, never echo the requested stopping tolerance."""
    from types import SimpleNamespace
    monkeypatch.setattr("models.pglib_uc._sy", lambda d:
                        (np.ones(1), np.zeros((0, 1)), [], np.zeros((0, 1)), [],
                         np.zeros(1), np.ones(1), np.ones(1)))
    monkeypatch.setattr("models.pglib_uc.milp", lambda *a, **k:
                        SimpleNamespace(success=True, fun=100, mip_gap=0.005, mip_dual_bound=99.5))
    r = cl({}, 0.01)
    assert (r.z, r.gap, r.lb, r.st) == (100, 0.005, 99.5, "gap")


@pytest.mark.parametrize("gap", [-1, np.inf, np.nan])
def test_gap(gap):
    with pytest.raises(ValueError, match="gap"):
        cl({}, gap)


def test_renewable_only():
    """A continuous instance has an LP certificate; SciPy leaves its MIP fields None."""
    r = cl({"T": 1, "th": [], "re": [{"power_output_minimum": [0],
            "power_output_maximum": [2]}], "demand": [1], "reserves": [0]})
    assert (r.z, r.lb, r.gap, r.st) == (0, 0, 0, "opt")


def test_lossy():
    """The gate is sensitive to the two defects it exists to catch.

    Both are real: ConvexHullPricing.jl's loader reads piecewise_production[1] and
    startup[1] and keeps nothing else. Truncating the piecewise curve to its first point
    leaves (21) forcing pg to zero, so the instance cannot meet demand at all; truncating
    the start-up categories to the first leaves a cheaper program, 2474234.88 against
    2480427.04 on 2026-09-15. Directions are asserted rather than the values, which move
    with the solver. Dropping a start-up tier can lower cost; dropping piecewise points
    can remove feasible output instead, which is why both failure directions are checked.
    """
    d = ld(F)
    for x in d["th"]:
        x["piecewise_production"] = x["piecewise_production"][:1]
    c, A, b, Ae, be, lb, ub, _it = _sy(d)
    assert linprog(c, A_ub=A, b_ub=b, A_eq=Ae, b_eq=be,
                   bounds=list(zip(lb, ub))).status == 2

    d = ld(F)
    for x in d["th"]:
        x["startup"] = x["startup"][:1]
    c, A, b, Ae, be, lb, ub, _it = _sy(d)
    r = linprog(c, A_ub=A, b_ub=b, A_eq=Ae, b_eq=be, bounds=list(zip(lb, ub)))
    assert r.status == 0
    assert float(r.fun) < LP - 1.0


def two(res=0.0, dem=(60.0, 140.0)):
    """Two units whose clearing and prices are arithmetic.

    Both are off at t0 with a one-period minimum run and down time, so the commitment is
    free and the dispatch is the merit order. The cheap unit carries 10 to 80 MW at 20/MWh
    over a 200 no-load and a 500 start-up; the dear unit the same band at 45/MWh over 300
    and 900. Demand 60 then 140 commits the cheap unit alone, then both.
    """
    def th(name, lo, hi, c, nl, su):
        return {
            "must_run": 0, "power_output_minimum": lo, "power_output_maximum": hi,
            "ramp_up_limit": hi, "ramp_down_limit": hi,
            "ramp_startup_limit": hi, "ramp_shutdown_limit": hi,
            "time_up_minimum": 1, "time_down_minimum": 1,
            "power_output_t0": 0.0, "unit_on_t0": 0, "time_down_t0": 8, "time_up_t0": 0,
            "startup": [{"lag": 1, "cost": su}],
            "piecewise_production": [{"mw": lo, "cost": nl},
                                     {"mw": hi, "cost": nl + c * (hi - lo)}],
            "name": name,
        }
    return {"T": len(dem), "demand": np.asarray(dem, dtype=float),
            "reserves": np.asarray([res] * len(dem), dtype=float),
            "th": [th("cheap", 10.0, 80.0, 20.0, 200.0, 500.0),
                   th("dear", 10.0, 80.0, 45.0, 300.0, 900.0)],
            "re": []}


def test_price_by_hand():
    """Energy price is the marginal offer, and the dear unit's start-up is left unpaid.

    Demand 60 is met by the cheap unit alone, so the price is its 20/MWh. Demand 140 needs
    both, so the price is the dear unit's 45/MWh. At those prices the dear unit earns
    45 x 60 = 2,700 against a cost of 2,550 plus a 900 start-up, and is 750 short. That
    shortfall is the nonconvexity this formulation does not price away.
    """
    r = px(two())
    assert r.pe == pytest.approx([20.0, 45.0])
    assert r.pr == pytest.approx([0.0, 0.0])
    assert r.z == pytest.approx(6750.0)
    assert r.ct == pytest.approx([3300.0, 3450.0])
    assert r.rev == pytest.approx([4800.0, 2700.0])
    assert r.mw == pytest.approx([0.0, 750.0])


def test_price_identity():
    """What demand and reserve pay is exactly what the resources earn.

    Payment less as-cleared cost is the market's total profit, not its make-whole. The two
    coincide on this instance only because one unit's surplus happens to equal the other's
    shortfall; they are asserted apart so that coincidence cannot pass for an identity.
    """
    d = two(res=10.0)
    r = px(d)
    pay = float(r.pe @ d["demand"] + r.pr @ d["reserves"])
    assert pay == pytest.approx(float(r.rev.sum()) + r.wr, rel=1e-9)
    assert r.mw == pytest.approx(np.maximum(r.ct - r.rev, 0.0))
    assert pay >= float(r.ct.sum()) - 1e-6
    assert float((r.rev - r.ct).sum()) == pytest.approx(pay - float(r.ct.sum()), rel=1e-9)


def test_price_reserve_is_free_when_slack():
    """A reserve requirement inside the committed headroom costs nothing and prices at zero.

    Reserve carries no cost of its own in this formulation; it competes only for capacity.
    With headroom to spare the requirement is not binding, so its dual is zero and the
    energy price is unmoved. The reserve price is nonnegative by construction: (3) enters
    the priced program as an equality with a surplus column.
    """
    a, b = px(two(res=0.0)), px(two(res=10.0))
    assert b.pr == pytest.approx([0.0, 0.0], abs=1e-9)
    assert b.pe == pytest.approx(a.pe)
    assert b.z == pytest.approx(a.z)
    assert (b.pr >= -1e-9).all()


def test_price_holds_the_cleared_commitment():
    """Pricing pins the integers it cleared, and pins nothing else."""
    d = two()
    res, q = _run(d, 0.0)
    _c, _A, _b, _Ae, _be, lb, ub = _hold(q, res.x)
    k = np.asarray(q[7], dtype=float) > 0
    assert (lb[k] == ub[k]).all()
    assert lb[k] == pytest.approx(np.round(np.asarray(res.x)[k]))
    assert (lb[~k] == np.asarray(q[5])[~k]).all()
    assert (ub[~k] == np.asarray(q[6])[~k]).all()


def test_reserve_row_index():
    """_ix finds the reserve row only for the periods that carry a requirement."""
    assert list(_ix({"T": 3, "reserves": [0.0, 5.0, 0.0]})) == [-1, 0, -1]
    assert list(_ix({"T": 2, "reserves": [1.0, 2.0]})) == [0, 1]
    assert list(_ix({"T": 2, "reserves": [0.0, 0.0]})) == [-1, -1]


@pytest.mark.slow
def test_price_rts():
    """The committed instance prices, and the money balances to the cent.

    Measured on 2026-09-16 at the reference script's 1% gap: the energy price runs from 0
    to 55.5092/MWh, and the reserve price is positive in 4 of the 48 periods, reaching
    27.7546/MWh. Reserve is scarce only where capacity is, which is the behaviour the
    formulation implies rather than an assumption of this test. Neither price is asserted
    to a value: the commitment is a 1% incumbent, so the prices follow the incumbent. What
    is asserted is the accounting identity, the sign, and that the nonconvexity shows up as
    make-whole rather than being priced away.
    """
    d = ld(F)
    r = px(d, 0.01)
    assert r.tag == "pay"
    assert (r.pe >= -1e-6).all() and (r.pr >= -1e-6).all()
    pay = float(r.pe @ d["demand"] + r.pr @ d["reserves"])
    assert pay == pytest.approx(float(r.rev.sum()) + r.wr, rel=1e-9)
    assert r.mw == pytest.approx(np.maximum(r.ct - r.rev, 0.0))
    assert float(r.ct.sum()) == pytest.approx(r.z, rel=1e-9)
    assert pay >= float(r.ct.sum())
    assert float(r.mw.sum()) > 0.0
    assert 0 < int((r.pr > 1e-9).sum()) < len(r.pr)
