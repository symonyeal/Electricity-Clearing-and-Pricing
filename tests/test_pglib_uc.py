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

import hashlib
import json
from pathlib import Path

import pytest
import numpy as np
from scipy.optimize import linprog

from models.pglib_uc import _sy, cl, ld

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
