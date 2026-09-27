# Verification for the generated master, models/dw.py.
#
# The independent checks are hc and hl, which write the same unit hull in full. The master
# reaches their value from above, and the Lagrangian value at the reported price bounds it
# from below, so every test asserts lb <= z_hull <= z. An LP optimum is exact only to
# HiGHS's feasibility tolerance: over the seeded family the bound exceeded hc's value by at
# most 2.8e-9 of it, so the bracket is asserted to 1e-8 relative. Where the hull's price is
# unique the prices agree; where the face is wide, which the AIC ceilings make it on some
# seeds, value and payment are what the data fix.
#
# The second group is about stopping. A restricted master whose value is already optimal
# can carry a price that is not a convex hull price, and a loop priced by an oracle that
# cannot see every schedule certifies a price that is not one. Only exact pricing at the
# vector that will be reported says so.
#
# LEGEND
#   W          : the module under test         cg,_rm,_oc,_col : its loop, master, oracle, column
#   g,d,net    : units, demand, network        s,cap : a clearing and the AIC ceilings
#   a,b        : the direct hull and the generated master on one market
#   K          : explicit master columns       z,lam,pi : master value, price, convexity duals
#   v,rho      : an oracle bound and a reduced cost
#   q          : a case constructor, or a tolerance
#   sd         : seed of the random family     CENT : money tolerance, as in test_uc_price

import numpy as np
import pytest
from scipy.optimize import linprog

import models.dw as W
import models.uc_price as M
from models.uc_price import U, ck, ex1, ex2, ex3, ex4, ex5, hc, hl, pay, pc, qd, uc
from tests.test_uc_price import AIC3, CENT, _clear


def _br(a, b):
    """lb <= z_hull <= z, and the stopping rule itself: every rho >= -tau."""
    q = 1e-8 * max(1.0, abs(a.z))
    assert b.s.lb - q <= a.z <= b.s.z + q
    assert (b.rho >= -b.tau).all()
    assert b.s.z - b.s.lb <= len(b.rho) * b.tau + q


@pytest.mark.parametrize("q", [ex1, ex2, ex3])
def test_published_cases(q):
    """The generated master reaches the published convex hull prices and certifies them.

    lb is the Lagrangian dual value at the reported price. qd evaluates the same function
    through _om, so the two must agree; hc supplies the value they both bound.
    """
    g, d = q()
    a, b = hc(g, d), W.cg(g, d)
    _br(a, b)
    assert b.s.pi.ravel() == pytest.approx(a.pi.ravel(), abs=1e-4)
    assert qd(g, d, b.s.pi) == pytest.approx(b.s.lb, rel=1e-8)
    assert b.na <= len(d) + len(g)


@pytest.mark.parametrize("q", [ex1, ex2, ex3])
def test_published_aic(q):
    """With pc's ceilings the same loop prices the restricted hull, AIC included."""
    g, d = q()
    s = uc(g, d)
    cap = pc(g, d, s, 1e-6)
    a, b = hc(g, d, cap), W.cg(g, d, cap, s=s)
    _br(a, b)
    assert b.s.pi.ravel() == pytest.approx(a.pi.ravel(), abs=1e-4)


@pytest.mark.parametrize("q", [ex4, ex5])
def test_networks(q):
    """The flows stay in the master whole, so the balance rows price by bus.

    The bound then carries the network subproblem as well: qd adds _nq, and lb equals it
    because the master's line duals already solve that subproblem at the reported price.
    """
    g, d, net = q()
    a, b = hc(g, d, net=net), W.cg(g, d, net=net)
    _br(a, b)
    assert b.s.pi == pytest.approx(a.pi, abs=1e-4)
    assert qd(g, d, b.s.pi, net=net) == pytest.approx(b.s.lb, rel=1e-8)


@pytest.mark.parametrize("sd", range(0, 141, 3))
def test_seeded_family(sd):
    """Every third seed of the 141-seed family, uncapped and capped.

    Uncapped, the convex hull price is unique on this family, so price and uplift agree
    with hc. Capped, the face can be wide (seeds 36, 61, 70, 103): there the two routes may
    report different points of it, so what is asserted is what the face determines, value,
    demand payment and dual optimality. run_dw.py reports the whole family.
    """
    q = _clear(sd)
    if q is None:
        return
    g, d, s = q
    a, b = hc(g, d), W.cg(g, d, s=s)
    _br(a, b)
    assert b.s.pi.ravel() == pytest.approx(a.pi.ravel(), abs=1e-4)
    assert pay(g, s, b.s.pi).up.sum() == pytest.approx(pay(g, s, a.pi).up.sum(), abs=CENT)
    assert b.na <= len(d) + len(g)
    cap = pc(g, d, s, 1e-6)
    a, b = hc(g, d, cap), W.cg(g, d, cap, s=s)
    _br(a, b)
    assert (b.s.pi * d).sum() == pytest.approx((a.pi * d).sum(), rel=1e-7)
    assert qd(g, d, b.s.pi, cap) == pytest.approx(b.s.lb, rel=1e-8)


def _hand():
    """One period, 50 MW. A dear flexible unit, and a cheap one with a 25 MW floor.

    Unit 2 costs 200 to start and 8/MWh, so its schedule set is {off} and 25..50 MW at
    200 + 8p. Its hull slope from off to 50 MW is 12, and L(lam) = 50 lam for lam <= 12,
    600 for 12 <= lam <= 60: the convex hull price the payment rule selects is 12.
    """
    return ck([U(0.0, 50.0, 60.0), U(25.0, 50.0, 8.0, su=200.0)], [50.0])[:2]


def test_an_optimal_master_value_is_not_a_price():
    """The restricted master reaches the hull value exactly and still prices at 8, not 12.

    Columns: unit 1 off; unit 2 at 50 MW (600) and at 25 MW (400). The master must run
    unit 2 at 50, so z = 600 = z_hull and there is no objective gap at all. Its dual face is
    pi_1 = 0, pi_2 = 600 - 50 lam, lam >= 8, the last from the 25 MW column; the payment
    rule selects lam = 8. Unit 2's omitted off schedule has reduced cost -pi_2 = -200 there,
    and BT's bound is 600 - 200 = 400 = L(8). The face also holds 12, which passes; the
    rule does not choose it. Only pricing the selected vector tells the two apart.
    """
    g, d = _hand()
    net = ck(g, d)[2]
    K = [[W._in(net, 0, 1, W._col(g[0], 1, [0.0], [0.0]))],
         [W._in(net, 1, 1, W._col(g[1], 1, [q], [1.0])) for q in (50.0, 25.0)]]
    z, _y, lam, pi, _st = W._rm(g, d, net, K, 1)
    assert z == pytest.approx(hc(g, d).z) == pytest.approx(600.0)
    assert lam == pytest.approx([8.0], abs=1e-6)
    (_p, u, _k), v = W._oc(g[1], 1, lam)
    assert u.tolist() == [0.0] and v - pi[1] == pytest.approx(-200.0, abs=1e-5)
    assert z + v - pi[1] == pytest.approx(qd(g, d, lam), abs=1e-5) == pytest.approx(400.0)
    for q, r in ((8.0, [0.0, 200.0]), (12.0, [0.0, 0.0])):
        assert all(k - q * a[0] - r[i] >= -1e-9 for i in range(2) for a, k, _ in K[i])
        assert 50.0 * q + sum(r) == pytest.approx(z)
    b = W.cg(g, d, K=[[([0.0], [0.0])], [([50.0], [1.0]), ([25.0], [1.0])]])
    assert b.s.pi.ravel() == pytest.approx([12.0], abs=1e-6)
    assert b.s.lb == pytest.approx(600.0, abs=1e-6)


def test_a_restricted_oracle_certifies_nothing(monkeypatch):
    """Priced only over unit 2's cleared and off schedules, the loop stops at 146.33.

    That oracle is what a heuristic pricing step is: every schedule it returns is feasible,
    so every column is valid, and its own reduced costs all vanish at the end. The loop
    therefore reports lb = z = 7,340, the hull value to within the AIC's own 1e-7 ceiling.
    The exact oracle at that price finds a start in period 3 the restricted one cannot
    see, and the Lagrangian value there is 6,202.5: the price leaves 1,137.5 of the bound
    uncertified. With exact pricing the same loop reaches 422, the price hl gives.
    """
    g, d = ex3()
    s = uc(g, d)
    cap = pc(g, d, s, 1e-7)
    f = W._oc

    def oc(x, T, lam, c=None):
        if x.su < 1.0:
            return f(x, T, lam, c)
        best = None
        for u in (np.ones(T), np.zeros(T)):
            q = M._pl(x, T, u, *M._vw(x, u), c)
            y = linprog(x.c - lam, A_ub=q[0], b_ub=q[1], bounds=(None, None), method="highs-ds")
            col = W._col(x, T, y.x, u, c)
            if best is None or col[2] - lam @ col[0] < best[1]:
                best = (col, col[2] - lam @ col[0])
        return best

    monkeypatch.setattr(W, "_oc", oc)
    b = W.cg(g, d, cap, s=s)
    monkeypatch.setattr(W, "_oc", f)
    assert b.s.pi.ravel() == pytest.approx([10.0, 10.0, AIC3], abs=1e-3)
    assert b.s.lb == pytest.approx(b.s.z, abs=1e-4) and b.s.z == pytest.approx(7340.0, abs=1e-3)
    assert hl(g, d, cap).z == pytest.approx(b.s.z, abs=1e-3)
    (_p, u, _k), _v = f(ck(g, d)[0][1], 3, b.s.pi[0], cap[1])
    assert u.tolist() == [0.0, 0.0, 1.0]
    assert qd(g, d, b.s.pi, cap) == pytest.approx(6202.5, abs=1e-3)
    e = W.cg(g, d, cap, s=s)
    assert e.s.pi.ravel() == pytest.approx([10.0, 10.0, 422.0], abs=1e-3)
    _br(hl(g, d, cap), e)


def test_a_seed_outside_the_unit_is_refused():
    """A column is a schedule of the unit it belongs to, or it is not a column."""
    g, d = ex1()
    with pytest.raises(ValueError, match="breaks a unit's own limits"):
        W.cg(g, d, K=[[([60.0], [1.0])], [([0.0], [0.0])]])


def _pg(g, d):
    """uc_price's units as pglib records: one start-up tier and a two-point cost line.

    pglib carries output above the minimum and prices the minimum through the first curve
    point, so a unit costing nl u + c p becomes the line through (lo, nl + c lo) and
    (hi, nl + c hi). pglib's ramp rows (19) and (20) also bind at a start and a stop; ex1
    and ex2 have ramps no tighter than their start-up and shut-down limits, so there the
    two feasible sets coincide. ex3's do not, and it is not used.
    """
    g, d, _ = ck(g, d)
    th = []
    for i, x in enumerate(g):
        pw = [{"mw": x.lo, "cost": x.nl + x.c * x.lo}]
        pw += [{"mw": x.hi, "cost": x.nl + x.c * x.hi}] if x.hi > x.lo else []
        th.append({"must_run": 0, "power_output_minimum": x.lo, "power_output_maximum": x.hi,
                   "ramp_up_limit": x.ru, "ramp_down_limit": x.rd, "ramp_startup_limit": x.sr,
                   "ramp_shutdown_limit": x.dr, "time_up_minimum": x.mu,
                   "time_down_minimum": x.md, "power_output_t0": x.p0, "unit_on_t0": x.u0,
                   "time_down_t0": 0 if x.u0 else x.e0, "time_up_t0": x.e0 if x.u0 else 0,
                   "startup": [{"lag": 1, "cost": x.su}], "piecewise_production": pw,
                   "name": f"u{i}"})
    T = d.shape[1]
    return {"T": T, "demand": d.ravel(), "reserves": np.zeros(T), "th": th, "re": []}


@pytest.mark.parametrize("q", [ex1, ex2])
def test_pglib_rows_reach_the_same_hull(q):
    """The pglib master, on pglib's own rows, reaches the hull hc writes from uc_price's.

    pglib_uc writes (4) to (23) without any of uc_price's row builders, so agreement here
    checks the decomposition and both unit formulations at once: CHP 12 on ex1, and
    (60, 60, 65.6) on ex2, each with value and certificate.
    """
    g, d = q()
    a, b = hc(g, d), W.cgp(_pg(g, d))
    assert b.lb - 1e-8 * abs(a.z) <= a.z <= b.z + 1e-8 * abs(a.z)
    assert b.pe == pytest.approx(a.pi.ravel(), abs=1e-4)
    assert (b.rho >= -b.tau).all()


def test_pglib_hull_prices_reserve():
    """With a reserve requirement the hull prices reserve where the held-commitment LMP does not.

    Reserve carries no cost of its own, so pglib_uc.px, which holds the cleared commitment,
    prices it at zero wherever the committed headroom covers it. The hull also charges for
    commitment: on the two-unit case with 10 MW required in period 2 the reserve price
    there is 9.375, the energy price 54.375. The hull value lies between pglib's own LP
    relaxation and its clearing, which is the bracket any Lagrangian dual must respect;
    here it meets the relaxation.
    """
    from tests.test_pglib_uc import two
    from models.pglib_uc import _sy, cl, px
    D = two(res=10.0)
    c, A, b, Ae, be, lb, ub, _it = _sy(D)
    lp = linprog(c, A_ub=A, b_ub=b, A_eq=Ae, b_eq=be, bounds=list(zip(lb, ub))).fun
    r = W.cgp(D)
    assert lp <= r.z + 1e-6 and r.lb <= cl(D).z + 1e-6
    assert r.z - r.lb <= len(r.rho) * r.tau + 1e-9 * r.z
    assert r.z == pytest.approx(lp, abs=1e-5)
    assert (r.pr >= 0.0).all()
    assert r.pr == pytest.approx([0.0, 9.375], abs=1e-4)
    assert r.pe == pytest.approx([20.0, 54.375], abs=1e-4)
    assert px(D).pr == pytest.approx([0.0, 0.0], abs=1e-9)


def test_pglib_bound_carries_the_renewables():
    """A renewable is a master column, so lb carries min over [lo, hi] of -lam'pw.

    Wind of 2..10 then 3..15 MW on the reserve case: the hull meets pglib's relaxation, and
    without that term lb would exceed it by about 1,016.
    """
    from tests.test_pglib_uc import two
    from models.pglib_uc import _sy
    D = two(res=10.0)
    D["re"] = [{"name": "wind", "power_output_minimum": [2.0, 3.0],
                "power_output_maximum": [10.0, 15.0]}]
    c, A, b, Ae, be, lb, ub, _it = _sy(D)
    lp = linprog(c, A_ub=A, b_ub=b, A_eq=Ae, b_eq=be, bounds=list(zip(lb, ub))).fun
    r = W.cgp(D)
    assert r.lb - 1e-8 * lp <= lp <= r.z + 1e-8 * lp
    assert r.z == pytest.approx(lp, rel=1e-9)


def test_no_thermal_unit():
    """Renewables alone leave no block to price: the master is the whole program.

    One period, demand 1, costless wind of 0..2 MW. The value is 0, and so is the price,
    because the wind column lies strictly inside its bounds; _ce holds the selected price
    to 1e-9.
    """
    D = {"T": 1, "th": [], "demand": np.array([1.0]), "reserves": np.array([0.0]),
         "re": [{"name": "wind", "power_output_minimum": [0.0], "power_output_maximum": [2.0]}]}
    r = W.cgp(D)
    assert r.z == pytest.approx(0.0, abs=1e-8) and r.lb == pytest.approx(0.0, abs=1e-8)
    assert r.pe == pytest.approx([0.0], abs=1e-8)
