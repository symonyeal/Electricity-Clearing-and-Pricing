# Verification for unit commitment and the three wholesale pricing rules.
#
# Published cases: Hua & Baldick (2017) Tables 1-5, and the Chen-O'Neill-Whitman FERC talk.
#
# LEGEND
#   test_*    : one verification case            np,pytest : test support
#   M         : the model under test             U,Sol,ck : container, result, validator
#   uc,en,rx  : integer clearing, enumeration, relaxation
#   hl,lmp,pc : convex hull program, fixed-commitment prices, the AIC output ceilings
#   pay,qd,run : payments, the Lagrangian dual value, the whole workflow
#   ex1,ex2,ex3 : the published cases
#   g,d       : units and demand                 s,r : a clearing, a full market result
#   P,pi      : payments and prices              cap : the AIC output ceilings
#   x,y       : two results being compared       z,z1,z2 : objective values
#   t,i,j     : period, unit and scratch indices q : a case, a saved function, a scalar
#                                                    or a network
#   ln        : the lines of a network           fm : the line model, "dc" or "ntc"
#   sd        : random seed                      h : a demand perturbation
#   k         : the name of one price            a,b : a seeded generator, a best value
#   f,n       : saved linear-program function and its call count
#   sz,_kp    : deterministic hull-size report helper, and its path count
#   nw        : the network under test           rent : congestion rent of the cleared flows
#   AIC3,LMP3 : the talk's reported period-3 AIC and LMP prices

import numpy as np
import pytest
from scipy.optimize import linprog

import models.uc_price as M
from models.uc_price import (LIM, U, Net, Sol, ck, en, ex1, ex2, ex3, ex4, ex5, hc, hl, lmp, pay,
                             pc, qd, run, rx, uc)
from run_bench import _kp, sz

AIC3 = 4390.0 / 30.0
LMP3 = 90.0
# Prices are canonical to about 1e-9 of the program's own objective, so dollar figures
# derived from them carry sub-cent noise. Money is therefore compared to a tenth of a cent.
CENT = 1e-3


def test_ex1_clearing():
    """Hua-Baldick Example 1 has one feasible commitment; enumeration confirms it."""
    g, d = ex1()
    s, y = uc(g, d), en(g, d)
    assert s.z == pytest.approx(1850.0)
    assert s.p.ravel() == pytest.approx([35.0, 0.0])
    assert s.u.tolist() == [[1.0], [0.0]]
    assert y.z == pytest.approx(s.z)


def test_ex1_published_prices():
    """Table 2: LMP is $50 with uplift (100, 1900); exact CHP is $12 with uplift (1430, 0)."""
    g, d = ex1()
    r = run(g, d)
    assert r.lmp.pi.ravel() == pytest.approx([50.0])
    assert pay(g, r.uc, r.lmp.pi).up == pytest.approx([100.0, 1900.0], abs=1e-3)
    assert r.chp.pi.ravel() == pytest.approx([12.0])
    assert pay(g, r.uc, r.chp.pi).up == pytest.approx([1430.0, 0.0], abs=1e-3)
    assert r.chp.z == pytest.approx(420.0)


def test_ex1_aic_removes_make_whole():
    """The p-cut price is unit 1's average incremental cost, and it leaves no make-whole."""
    g, d = ex1()
    r = run(g, d, ep=1e-9)
    assert r.aic.pi.ravel() == pytest.approx([1850.0 / 35.0], abs=1e-5)
    assert pay(g, r.uc, r.aic.pi).mw.sum() == pytest.approx(0.0, abs=1e-3)


def test_ex2_clearing():
    """Table 4: ramping forces unit 2 on at t=2 so it can reach 100 MW at t=3."""
    g, d = ex2()
    s, y = uc(g, d), en(g, d)
    assert s.p.ravel() == pytest.approx([70.0, 40.0, 70.0, 0.0, 60.0, 100.0])
    assert s.u.tolist() == [[1.0, 1.0, 1.0], [0.0, 1.0, 1.0]]
    assert s.z == pytest.approx(20960.0)
    assert y.z == pytest.approx(s.z)


def test_ex2_published_prices():
    """Table 5: LMP is 60 flat with uplift (0, 560); exact CHP is (60, 60, 65.6), (168, 0)."""
    g, d = ex2()
    r = run(g, d)
    assert r.lmp.pi.ravel() == pytest.approx([60.0, 60.0, 60.0])
    assert pay(g, r.uc, r.lmp.pi).up == pytest.approx([0.0, 560.0], abs=1e-3)
    assert r.chp.pi.ravel() == pytest.approx([60.0, 60.0, 65.6])
    assert pay(g, r.uc, r.chp.pi).up == pytest.approx([168.0, 0.0], abs=1e-3)


def test_ex3_clearing_and_lmp():
    """The talk's case: its dispatch, its LMPs, and its period-by-period unit 2 profit."""
    g, d = ex3()
    s, y = uc(g, d), en(g, d)
    assert s.p.ravel() == pytest.approx([75.0, 75.0, 100.0, 20.0, 25.0, 30.0])
    assert y.z == pytest.approx(s.z) == pytest.approx(7340.0)
    L = lmp(g, d, s)
    assert L.pi.ravel() == pytest.approx([10.0, 10.0, LMP3])
    assert L.z == pytest.approx(s.z)
    q = [(L.pi[0, t] - 50.0) * s.p[1][t] - 30.0 - (1000.0 if t == 0 else 0.0) for t in range(3)]
    assert q == pytest.approx([-1830.0, -1030.0, 1170.0])
    P = pay(g, s, L.pi)
    assert P.r == pytest.approx([8000.0, -1690.0])
    assert (P.mw.sum(), P.up.sum()) == pytest.approx((1690.0, 1690.0))


def test_ex3_at_the_talks_aic_price():
    """At the talk's own AIC price this model reproduces its profit and uplift line exactly."""
    g, d = ex3()
    s = uc(g, d)
    P = pay(g, s, [10.0, 10.0, AIC3])
    assert P.r.sum() == pytest.approx(13633.333333, abs=1e-5)
    assert (P.r + P.up).sum() == pytest.approx(14770.833333, abs=1e-5)
    assert P.up.sum() == pytest.approx(1137.5)
    assert P.mw.sum() == pytest.approx(0.0, abs=1e-9)


def test_ex3_exact_aic_is_not_the_talks_price():
    """The exact hull prices the p-cut at 422, and 146.33 is one restricted mixture of it.

    The talk reports $146.33 for period 3. That is exactly the slope of mixing unit 2's
    cleared schedule with being off. The convex hull of the p-cut set also contains the
    'start at period 2' schedule, whose mixture is worth more, so the exact price is $422.
    Both leave zero make-whole for the restricted block, the scope of Proposition 3.
    """
    g, d = ex3()
    s = uc(g, d)
    cap = pc(g, d, s, 1e-7)
    assert cap.ravel() == pytest.approx([100.0, 100.0, 100.0, 20.0, 25.0, 30.0], abs=1e-6)
    a = hl(g, d, cap)
    assert a.pi.ravel() == pytest.approx([10.0, 10.0, 422.0], abs=1e-3)
    assert pay(g, s, a.pi).mw.sum() == pytest.approx(0.0, abs=1e-6)
    q = M._cl
    try:
        M._cl = lambda x, T, c=None: [
            y for y in q(x, T, c) if x.su < 1.0 or tuple(y[0]) in {(0, 0, 0), (1, 1, 1)}
        ]
        r = hl(g, d, cap)
    finally:
        M._cl = q
    assert r.pi.ravel() == pytest.approx([10.0, 10.0, AIC3], abs=1e-3)
    assert r.z == pytest.approx(7340.0, abs=1e-4)
    z = qd(g, d, r.pi, cap)
    assert z == pytest.approx(6202.5, abs=1e-4)
    assert r.z - z == pytest.approx(1137.5, abs=1e-4)


@pytest.mark.parametrize("q", [ex1, ex2, ex3])
def test_hull_value_is_the_dual_maximum(q):
    """Gribik-Hogan-Pope: the convex hull program's value is the Lagrangian dual maximum."""
    g, d = q()
    x = hl(g, d)
    assert qd(g, d, x.pi) == pytest.approx(x.z, rel=1e-8)
    a = np.random.default_rng(3)
    for _ in range(25):
        assert qd(g, d, x.pi + a.uniform(-40, 40, len(d))) <= x.z + 1e-6


@pytest.mark.parametrize("q", [ex1, ex2, ex3])
def test_uplift_is_the_duality_gap(q):
    """At any price at all, total uplift is the cleared cost less the dual value."""
    g, d = q()
    r = run(g, d)
    a = np.random.default_rng(11)
    pi = [getattr(r, k).pi for k in ("lmp", "chp", "chp_r", "aic", "aic_r")]
    pi += [a.uniform(-30, 300, len(d)) for _ in range(15)]
    for x in pi:
        assert pay(g, r.uc, x).up.sum() == pytest.approx(r.uc.z - qd(g, d, x), abs=1e-6)


@pytest.mark.parametrize("q", [ex1, ex2, ex3])
def test_convex_hull_price_minimises_uplift(q):
    """That gap is smallest at the convex hull price; no other price can beat it."""
    g, d = q()
    r = run(g, d)
    z = pay(g, r.uc, r.chp.pi).up.sum()
    for k in ("lmp", "chp_r", "aic", "aic_r"):
        assert pay(g, r.uc, getattr(r, k).pi).up.sum() >= z - 1e-3
    a = np.random.default_rng(5)
    for _ in range(25):
        assert pay(g, r.uc, a.uniform(-30, 300, len(d))).up.sum() >= z - 1e-3


@pytest.mark.parametrize("q", [ex1, ex2, ex3])
def test_bounds_between_the_three_programs(q):
    """The hull sits between the relaxed system and the integer clearing, as it must."""
    g, d = q()
    r = run(g, d)
    assert r.chp_r.z <= r.chp.z + 1e-6
    assert r.chp.z <= r.uc.z + 1e-6
    assert r.aic_r.z <= r.aic.z + 1e-6
    assert r.aic.z <= r.uc.z + 1e-6


@pytest.mark.parametrize("sd", range(8))
def test_two_feasible_set_descriptions_agree(sd):
    """The trajectory columns and the algebraic rows must describe the same unit.

    The best self-schedule is found by an integer program over the rows; the same figure
    is recomputed here by enumerating trajectories and solving each polytope. A wrong row,
    or a wrongly filtered trajectory, separates the two answers.
    """
    a = np.random.default_rng(sd)
    T = int(a.integers(1, 5))
    x = M.mk(U(float(a.integers(0, 20)), float(a.integers(20, 60)), float(a.integers(5, 60)),
               nl=float(a.integers(0, 50)), su=float(a.integers(0, 500)),
               ru=float(a.integers(5, 40)), rd=float(a.integers(5, 40)),
               sr=float(a.integers(5, 40)), dr=float(a.integers(5, 40)),
               mu=int(a.integers(1, 3)), md=int(a.integers(1, 3))))
    pi = a.uniform(-10, 120, T)
    b = -np.inf
    for _, _, _, A, y, k in M._cl(x, T):
        j = linprog(x.c - pi, A_ub=A, b_ub=y, bounds=(None, None))
        if j.success:
            b = max(b, -(float(j.fun) + k))
    assert b == pytest.approx(M._om([x], T, pi[None, :], M.Net(np.zeros(1, int), (), 1))[0],
                              abs=1e-6)


@pytest.mark.parametrize("sd", range(10))
def test_random_markets_clear_the_same_two_ways(sd):
    """The integer program and joint enumeration must agree on seeded random markets."""
    a = np.random.default_rng(100 + sd)
    T = int(a.integers(1, 4))
    g = [U(float(a.integers(0, 15)), float(a.integers(20, 50)), float(a.integers(5, 60)),
           nl=float(a.integers(0, 40)), su=float(a.integers(0, 300)),
           ru=float(a.integers(8, 40)), rd=float(a.integers(8, 40)),
           sr=float(a.integers(8, 40)), dr=float(a.integers(8, 40))) for _ in range(3)]
    d = a.uniform(0.2, 0.8, T) * sum(x.hi for x in g)
    try:
        x = uc(g, d)
    except ValueError:
        with pytest.raises(ValueError):
            en(g, d)
        return
    assert x.z == pytest.approx(en(g, d).z, abs=1e-6)
    assert lmp(g, d, x).z == pytest.approx(x.z, abs=1e-6)


@pytest.mark.parametrize("sd", range(6))
def test_p_cut_removes_make_whole(sd):
    """The talk's Proposition 3: under the exact hull, the p-cut price pays every block."""
    a = np.random.default_rng(200 + sd)
    T = int(a.integers(1, 4))
    g = [U(float(a.integers(0, 15)), float(a.integers(20, 50)), float(a.integers(5, 60)),
           nl=float(a.integers(0, 40)), su=float(a.integers(0, 400)),
           ru=float(a.integers(10, 40)), sr=float(a.integers(10, 40))) for _ in range(3)]
    d = a.uniform(0.3, 0.7, T) * sum(x.hi for x in g)
    try:
        s = uc(g, d)
    except ValueError:
        return
    x = hl(g, d, pc(g, d, s, 1e-9))
    assert pay(g, s, x.pi).mw.sum() == pytest.approx(0.0, abs=1e-5)


def test_price_is_a_left_hand_marginal_cost():
    """At a kink in the cost curve the returned price is the lower slope, not an arbitrary one."""
    g, d = ex3()
    s = uc(g, d)
    h = 1e-4
    z1 = lmp(g, [95.0, 100.0, 130.0 - h], s).z
    z2 = lmp(g, [95.0, 100.0, 130.0 + h], s).z
    assert (s.z - z1) / h == pytest.approx(LMP3, abs=1e-4)
    assert (z2 - s.z) / h > LMP3 + 1.0
    assert lmp(g, d, s).pi[0, 2] == pytest.approx(LMP3)


def test_minimum_run_and_initial_state():
    """Minimum run time, minimum down time and a carried-in commitment all bind."""
    d = [40.0, 10.0, 10.0]
    s = uc([U(10.0, 40.0, 1.0, nl=100.0), U(0.0, 100.0, 8.0)], d)
    assert s.u[0].tolist() == [1.0, 0.0, 0.0] and s.z == pytest.approx(300.0)
    s = uc([U(10.0, 40.0, 1.0, nl=100.0, mu=3), U(0.0, 100.0, 8.0)], d)
    assert s.u[0].tolist() == [1.0, 1.0, 1.0] and s.z == pytest.approx(360.0)
    d = [15.0, 15.0, 15.0]
    s = uc([U(10.0, 40.0, 1.0), U(0.0, 100.0, 8.0)], d)
    assert s.u[0].tolist() == [1.0, 1.0, 1.0] and s.z == pytest.approx(45.0)
    s = uc([U(10.0, 40.0, 1.0, md=3, e0=0), U(0.0, 100.0, 8.0)], d)
    assert s.u[0].tolist() == [0.0, 0.0, 0.0] and s.z == pytest.approx(360.0)
    s = uc([U(10.0, 40.0, 5.0, ru=5.0, rd=5.0, u0=1, p0=20.0), U(0.0, 100.0, 90.0)], [30.0] * 3)
    assert s.p[0] == pytest.approx([25.0, 30.0, 30.0])


def test_relaxation_is_the_hull_for_a_one_period_unit():
    """With one period and no ramp rows, the relaxation is already the convex hull."""
    g = [U(10.0, 50.0, 50.0, su=100.0), U(20.0, 60.0, 20.0, su=400.0)]
    for d in ([35.0], [60.0], [80.0]):
        assert rx(g, d).z == pytest.approx(hl(g, d).z, abs=1e-6)
        assert rx(g, d).pi.ravel() == pytest.approx(hl(g, d).pi.ravel(), abs=1e-5)


def test_no_fixed_cost_gives_marginal_cost():
    """With convex offers, every pricing rule collapses onto marginal cost."""
    g = [U(0.0, 50.0, 10.0), U(0.0, 50.0, 20.0)]
    r = run(g, [70.0])
    assert r.uc.z == pytest.approx(900.0)
    for k in ("lmp", "chp", "chp_r", "aic", "aic_r"):
        assert getattr(r, k).pi.ravel() == pytest.approx([20.0])


def test_thin_price_face_skips_the_period_walk(monkeypatch):
    """A face narrower than a tenth of a cent costs one probe, not one solve per period."""
    f, n = M.linprog, 0

    def lp(*a, **k):
        nonlocal n
        n += 1
        return f(*a, **k)

    monkeypatch.setattr(M, "linprog", lp)
    x = rx([U(0.0, 50.0, 10.0), U(0.0, 50.0, 20.0)], [70.0, 70.0, 70.0])
    assert x.pi.ravel() == pytest.approx([20.0, 20.0, 20.0])
    assert n == 3


def test_wide_price_face_keeps_the_period_walk(monkeypatch):
    """A measurably wide capped face still takes every lexicographic stage."""
    g, d = _rand(61)
    s = uc(g, d)
    cap = pc(g, d, s, 1e-6)
    f, n = M.linprog, 0

    def lp(*a, **k):
        nonlocal n
        n += 1
        return f(*a, **k)

    monkeypatch.setattr(M, "linprog", lp)
    hc(g, d, cap)
    assert n == len(d) + 3


def test_bad():
    """Malformed, infeasible and out-of-range inputs are rejected."""
    g, d = ex1()
    with pytest.raises(ValueError, match="non-empty vector"):
        uc(g, [])
    with pytest.raises(ValueError, match="at least one unit"):
        uc([], [1.0])
    with pytest.raises(ValueError, match="0 <= lo <= hi"):
        uc([U(30.0, 10.0, 5.0)], [1.0])
    with pytest.raises(ValueError, match="finite and non-negative"):
        uc(g, [np.nan])
    with pytest.raises(ValueError, match="ramp limit must be positive"):
        uc([U(0.0, 10.0, 5.0, ru=0.0)], [1.0])
    with pytest.raises(ValueError, match="minimum run and down"):
        uc([U(0.0, 10.0, 5.0, mu=0)], [1.0])
    with pytest.raises(ValueError, match="initial commitment must be 0 or 1"):
        uc([U(0.0, 10.0, 5.0, u0=2)], [1.0])
    with pytest.raises(ValueError, match="starts offline must start at zero"):
        uc([U(0.0, 10.0, 5.0, u0=0, p0=4.0)], [1.0])
    with pytest.raises(ValueError, match="inside a running unit"):
        uc([U(5.0, 10.0, 5.0, u0=1, p0=99.0)], [1.0])
    with pytest.raises(ValueError, match="exceeds total generating capacity"):
        uc(g, [500.0])
    with pytest.raises(ValueError, match="no feasible unit commitment"):
        uc([U(30.0, 40.0, 5.0)], [10.0])
    with pytest.raises(ValueError, match="one binary value"):
        lmp(g, d, Sol(0.0, np.zeros((2, 1)), np.full((2, 1), 0.5), np.zeros((1, 1))))
    with pytest.raises(ValueError, match="ep must be positive"):
        pc(g, d, uc(g, d), ep=0.0)
    with pytest.raises(ValueError, match="breaks a unit's own limits"):
        pay(g, Sol(0.0, np.array([[99.0], [0.0]]), np.array([[1.0], [0.0]]), None), [1.0])
    with pytest.raises(ValueError, match="limited to 16 periods"):
        hl([U(0.0, 10.0, 5.0)], np.ones(17))
    with pytest.raises(ValueError, match="joint commitments"):
        en([U(0.0, 10.0, 5.0)] * 6, np.ones(4))


def test_ck_fills_defaults():
    """An unspecified ramp is the unit's full range; a fresh unit carries no initial duration."""
    x = ck([U(10.0, 40.0, 5.0, mu=3, md=2)], [1.0])[0][0]
    assert (x.ru, x.rd, x.sr, x.dr) == (40.0, 40.0, 40.0, 40.0)
    assert x.e0 == 3


def _rand(sd, lo=0.15, hi=0.6):
    """One seeded random market with ramps, minimum run times and a carried-in state."""
    a = np.random.default_rng(sd)
    T, G, g = int(a.integers(1, 6)), int(a.integers(2, 4)), []
    for _ in range(G):
        q, y = float(a.integers(30, 80)), float(a.integers(0, 12))
        u0 = int(a.integers(0, 2))
        g.append(U(y, q, float(a.integers(5, 60)), nl=float(a.integers(0, 40)),
                   su=float(a.integers(0, 300)), ru=float(a.integers(15, 60)),
                   rd=float(a.integers(15, 60)), sr=float(a.integers(15, 60)),
                   dr=float(a.integers(15, 60)), mu=int(a.integers(1, 4)),
                   md=int(a.integers(1, 4)), u0=u0,
                   p0=float(a.integers(int(y), int(q))) if u0 else 0.0,
                   e0=int(a.integers(0, 4))))
    return g, a.uniform(lo, hi, T) * sum(x.hi for x in g)


def _hull(f, g, d):
    """Return one hull result, accepting only the model's explicit infeasibility result."""
    try:
        return f(g, d)
    except ValueError as e:
        assert str(e) == "this demand is infeasible for the convex hull program"
        return None


@pytest.mark.parametrize("q", [ex1, ex2, ex3])
def test_compact_hull_equals_enumerated_hull(q):
    """The O(T^2)-arc interval and trajectory-wise disjunctive formulations give one hull."""
    g, d = q()
    a, b = hl(g, d), hc(g, d)
    assert a.z == pytest.approx(b.z, rel=1e-9)
    assert a.pi.ravel() == pytest.approx(b.pi.ravel(), abs=1e-4)


@pytest.mark.parametrize("sd", range(141))
def test_compact_hull_equals_enumerated_hull_at_random(sd):
    """Same claim on seeded units with ramps, minimum run times and an initial state.

    This is the check on Yu, Guan and Chen's theorem as implemented here: the interval graph
    is only the convex hull if its arcs, its minimum-down jumps and its initial arcs are all
    right, and any error in them separates it from the schedule-by-schedule hull. Seeds 0
    through 140 cover 104 feasible markets; infeasible samples are ignored by both routes.
    """
    g, d = _rand(sd)
    a, b = _hull(hl, g, d), _hull(hc, g, d)
    assert (a is None) == (b is None)
    if a is None:
        return
    assert a.z == pytest.approx(b.z, rel=1e-9)
    assert a.pi.ravel() == pytest.approx(b.pi.ravel(), abs=1e-4)


def test_random_family_has_104_feasible_markets():
    """The documented seed range contains 104 feasible and 37 infeasible clearings."""
    n = 0
    for sd in range(141):
        g, d = _rand(sd)
        try:
            uc(g, d)
        except ValueError as e:
            assert str(e) == "this demand has no feasible unit commitment"
        else:
            n += 1
    assert n == 104


def test_hull_size_report_counts_actual_variables():
    """An interval arc carries its own weight and, when on, one dispatch variable per period."""
    a = sz(6, 4)
    g, d = M.mk_g(6, 4, 7)
    assert a == (79, 186, 70, 350)
    assert a[2] == sum(len(M._cl(x, 4)) for x in ck(g, d)[0])


@pytest.mark.parametrize("G,T", [(6, 4), (8, 6), (10, 8), (12, 10), (4, 12)])
def test_path_count_equals_enumeration(G, T):
    """Trajectories are counted as graph paths; enumeration confirms the rule.

    The 48 x 24 and 96 x 24 rows of the decomposition table are path counts of sets far too
    large to enumerate, so the counting rule itself is pinned on every horizon that can be
    enumerated, per unit and in total. A rule that over-counted would inflate the figure the
    note uses to argue that enumeration is out of reach.
    """
    g, d = M.mk_g(G, T, 7)
    q = ck(g, d)[0]
    assert sz(G, T)[2] == sum(len(M._cl(x, T)) for x in q)
    for x in q:
        assert _kp(M._ar(x, T), T) == len(M._cl(x, T))


def test_trajectory_hull_crosses_the_variable_ceiling():
    """The documented cases immediately around LIM[1] lie on opposite sides of the guard."""
    a, b = sz(12, 10), sz(8, 14)
    assert a[3] == 76_164 <= LIM[1]
    assert b[3] == 1_031_610 > LIM[1]
    assert 10 <= LIM[0] and 14 <= LIM[0]


def test_trajectory_hull_enforces_the_variable_ceiling(monkeypatch):
    """hl applies LIM[1] after constructing the unit trajectory lists."""
    T = 14
    K = LIM[1] // (T + 1) + 1
    monkeypatch.setattr(M, "_cl", lambda *a: [None] * K)
    with pytest.raises(ValueError, match="limited to 100000 variables"):
        hl([U(0.0, 10.0, 1.0)], np.zeros(T))


def test_capped_hull_agrees_on_what_the_data_determines():
    """With the AIC ceilings on, the two hulls can pick different prices from one flat face.

    Seed 61 is such a market. Both prices maximise the Lagrangian dual and both pay the
    same for demand, so the data does not determine one; the refinement in _px narrows the
    face but cannot close it to a point at solver tolerance. Cost and payment are
    determined, and those are what this asserts.
    """
    g, d = _rand(61)
    s = uc(g, d)
    cap = pc(g, d, s, 1e-6)
    a, b = hl(g, d, cap), hc(g, d, cap)
    assert a.z == pytest.approx(b.z, rel=1e-9)
    assert (a.pi * np.atleast_2d(d)).sum() == pytest.approx((b.pi * np.atleast_2d(d)).sum(),
                                                            rel=1e-9)
    assert qd(g, d, a.pi, cap) == pytest.approx(a.z, rel=1e-8)
    assert qd(g, d, b.pi, cap) == pytest.approx(b.z, rel=1e-8)
    assert np.abs(a.pi - b.pi).max() > 1e-4


def test_compact_hull_passes_the_enumeration_ceiling():
    """hc prices a horizon hl refuses. That is the purpose of the interval form."""
    g = [U(10.0, 80.0, 20.0, nl=30.0, su=200.0, ru=60.0, sr=60.0, mu=2, md=2)] * 2
    d = np.full(17, 90.0)
    with pytest.raises(ValueError, match="limited to 16 periods"):
        hl(g, d)
    assert hc(g, d).z > 0.0


def test_three_bus_loop():
    """A symmetric loop splits flow two thirds to one, and its prices follow the congestion.

    Unit 1 is cheap at bus 0, unit 2 costly at bus 2, and the load sits at bus 2. With
    equal reactances the direct line carries two thirds of any bus-0 injection, so a 40 MW
    limit on it caps that unit at 60 MW. Bus 1 lies electrically midway and prices midway.
    """
    g, d, nw = ex4(lim=100.0)
    s = uc(g, d, net=nw)
    assert s.p.ravel() == pytest.approx([90.0, 0.0])
    assert s.z == pytest.approx(900.0)
    assert lmp(g, d, s, net=nw).pi.ravel() == pytest.approx([10.0, 10.0, 10.0])
    g, d, nw = ex4()
    s = uc(g, d, net=nw)
    assert s.p.ravel() == pytest.approx([60.0, 30.0])
    assert s.z == pytest.approx(2100.0)
    assert lmp(g, d, s, net=nw).pi.ravel() == pytest.approx([10.0, 30.0, 50.0])
    assert en(g, d, net=nw).z == pytest.approx(s.z)
    assert hc(g, d, net=nw).z == pytest.approx(hl(g, d, net=nw).z, rel=1e-9)


def test_network_reduces_to_one_bus_when_nothing_binds():
    """With no binding line, every route returns the single-bus answer."""
    g, d = ex2()
    nw = Net([0, 1], ((0, 1, 0.1, 1000.0),), 2)
    q = np.zeros((2, 3))
    q[1] = d
    a, b = run(g, d), run(g, q, net=nw)
    assert a.uc.z == pytest.approx(b.uc.z)
    assert b.lmp.pi[0] == pytest.approx(b.lmp.pi[1])
    assert b.lmp.pi[0] == pytest.approx(a.lmp.pi[0])
    assert b.chp.pi[0] == pytest.approx(a.chp.pi[0])


def test_congestion_separates_prices_and_costs_money():
    """A binding line raises the cleared cost and splits one price into two."""
    g = [U(0.0, 100.0, 10.0), U(0.0, 100.0, 40.0)]
    d = [[0.0], [80.0]]
    free = Net([0, 1], ((0, 1, 1.0, 100.0),), 2)
    tight = Net([0, 1], ((0, 1, 1.0, 30.0),), 2)
    a = uc(g, d, net=free)
    b = uc(g, d, net=tight)
    assert a.p.ravel() == pytest.approx([80.0, 0.0])
    assert b.p.ravel() == pytest.approx([30.0, 50.0])
    assert b.z > a.z
    assert lmp(g, d, a, net=free).pi.ravel() == pytest.approx([10.0, 10.0])
    assert lmp(g, d, b, net=tight).pi.ravel() == pytest.approx([10.0, 40.0])


def test_network_bad():
    """A malformed network is rejected before anything is solved."""
    g = [U(0.0, 100.0, 10.0), U(0.0, 100.0, 50.0)]
    with pytest.raises(ValueError, match="sit at a bus"):
        uc(g, [[0.0], [10.0]], net=Net([0, 5], (), 2))
    with pytest.raises(ValueError, match="join two different buses"):
        uc(g, [[0.0], [10.0]], net=Net([0, 1], ((1, 1, 1.0, 5.0),), 2))
    with pytest.raises(ValueError, match="positive reactance and limit"):
        uc(g, [[0.0], [10.0]], net=Net([0, 1], ((0, 1, 0.0, 5.0),), 2))
    with pytest.raises(ValueError, match="one row per bus"):
        uc(g, [10.0], net=Net([0, 1], ((0, 1, 1.0, 5.0),), 2))
    with pytest.raises(ValueError, match="line model must be dc or ntc"):
        uc(g, [[0.0], [10.0]], net=Net([0, 1], ((0, 1, 1.0, 5.0),), 2, "flow"))


def test_ntc_matches_dc_on_a_tree():
    """A tree has no cycle, so the balances fix the flows and both line models agree."""
    g = [U(0.0, 100.0, 10.0), U(0.0, 100.0, 40.0)]
    d = [[0.0], [30.0], [50.0]]
    x = Net([0, 2], ((0, 1, 1.0, 100.0), (1, 2, 1.0, 100.0)), 3)
    y = Net([0, 2], ((0, 1, (-100.0, 100.0)), (1, 2, (-100.0, 100.0))), 3, "ntc")
    a, b = uc(g, d, net=x), uc(g, d, net=y)
    assert b.z == pytest.approx(a.z)
    assert b.p.ravel() == pytest.approx(a.p.ravel())
    assert lmp(g, d, b, net=y).pi.ravel() == pytest.approx(lmp(g, d, a, net=x).pi.ravel())


def test_ntc_relaxes_the_loop():
    """Around a cycle the transport model drops the loop-flow condition, so it costs less."""
    g, d, x = ex4(40.0)
    y = Net(x.bus, ((0, 1, (-100.0, 100.0)), (1, 2, (-100.0, 100.0)),
                    (0, 2, (-40.0, 40.0))), 3, "ntc")
    a, b = uc(g, d, net=x), uc(g, d, net=y)
    assert a.p.ravel() == pytest.approx([60.0, 30.0])
    assert a.z == pytest.approx(2100.0)
    assert b.p.ravel() == pytest.approx([90.0, 0.0])
    assert b.z == pytest.approx(900.0)
    assert b.z < a.z
    assert lmp(g, d, b, net=y).pi.ravel() == pytest.approx([10.0, 10.0, 10.0])


def test_ntc_capacity_is_directional():
    """ex5 binds -3500 in one period and +2200 in the other, on one exchange record."""
    g, d, q = ex5()
    a = uc(g, d, net=q)
    assert a.z == pytest.approx(275000.0)
    assert a.p[0] == pytest.approx([500.0, 2200.0])
    assert a.p[1] == pytest.approx([3500.0, 6000.0])
    assert a.p[2] == pytest.approx([0.0, 800.0])
    pi = lmp(g, d, a, net=q).pi
    assert pi[0] == pytest.approx([40.0, 40.0], abs=CENT)
    assert pi[1] == pytest.approx([10.0, 90.0], abs=CENT)


def test_ntc_capacity_is_not_symmetric():
    """Widening one direction of the pair alone changes only the period that direction binds."""
    g, d, q = ex5()
    a = uc(g, d, net=q)
    b = uc(g, d, net=Net(q.bus, ((0, 1, (-4000.0, 2200.0)),), q.nb, "ntc", q.zn))
    assert b.p[0, 0] == pytest.approx(0.0)
    assert b.p[0, 1] == pytest.approx(a.p[0, 1])
    assert b.z < a.z


def test_ntc_exchange_record_is_checked():
    """An exchange carries a capacity pair, in ascending zone order, straddling zero."""
    g = [U(0.0, 100.0, 10.0), U(0.0, 100.0, 50.0)]
    d = [[0.0], [10.0]]
    with pytest.raises(ValueError, match="an exchange is"):
        uc(g, d, net=Net([0, 1], ((0, 1, 1.0, 5.0),), 2, "ntc"))
    with pytest.raises(ValueError, match="ascending order"):
        uc(g, d, net=Net([0, 1], ((1, 0, (-5.0, 5.0)),), 2, "ntc"))
    with pytest.raises(ValueError, match="negative to positive"):
        uc(g, d, net=Net([0, 1], ((0, 1, (5.0, 10.0)),), 2, "ntc"))
    with pytest.raises(ValueError, match="one per zone and distinct"):
        uc(g, d, net=Net([0, 1], ((0, 1, (-5.0, 5.0)),), 2, "ntc", ("NO-NO1",)))
    with pytest.raises(ValueError, match="one per zone and distinct"):
        uc(g, d, net=Net([0, 1], ((0, 1, (-5.0, 5.0)),), 2, "ntc", ("NO-NO1", "NO-NO1")))
    with pytest.raises(ValueError, match="a line is"):
        uc(g, d, net=Net([0, 1], ((0, 1, (-5.0, 5.0)),), 2))


@pytest.mark.parametrize("q", [ex4, ex5])
def test_dual_bounds_the_clearing_on_a_network(q):
    """Beck Theorem 12.3: the dual value never exceeds the clearing, congestion or not.

    The flow columns are part of the relaxed program. Reading the dual from the unit
    subproblems alone minimises over a subset of the feasible set, and on both of these
    markets that returned a bound above the primal optimum.
    """
    g, d, nw = q()
    g, d, nw = ck(g, d, nw)
    s = uc(g, d, net=nw)
    for pi in (lmp(g, d, s, net=nw).pi, hc(g, d, net=nw).pi):
        assert qd(g, d, pi, net=nw) <= s.z + CENT
    a = np.random.default_rng(11)
    for _ in range(25):
        assert qd(g, d, a.uniform(-30, 300, d.shape), net=nw) <= s.z + CENT


@pytest.mark.parametrize("q", [ex4, ex5])
def test_hull_value_is_the_dual_maximum_on_a_network(q):
    """Gribik-Hogan-Pope holds with lines: the hull's value is still the dual maximum."""
    g, d, nw = q()
    x = hc(g, d, net=nw)
    assert qd(g, d, x.pi, net=nw) == pytest.approx(x.z, rel=1e-8)


@pytest.mark.parametrize("q", [ex4, ex5])
def test_uplift_is_the_duality_gap_on_a_network(q):
    """With lines the gap carries two more terms, and the identity is exact at any price.

    Uplift is measured at each unit's own bus, so what the load pays and what the units
    are paid differ by the congestion rent of the cleared flows. The dual's network
    subproblem is free to choose other flows, and does at a price that is not a dual, so
    both terms appear separately rather than cancelling.
    """
    g, d, nw = q()
    g, d, nw = ck(g, d, nw)
    s = uc(g, d, net=nw)
    a = np.random.default_rng(11)
    px = [lmp(g, d, s, net=nw).pi, hc(g, d, net=nw).pi]
    px += [a.uniform(-30, 300, d.shape) for _ in range(15)]
    for pi in px:
        rent = (pi * d).sum() - sum(pi[nw.bus[i]] @ s.p[i] for i in range(len(g)))
        assert pay(g, s, pi, net=nw).up.sum() == pytest.approx(
            s.z - qd(g, d, pi, net=nw) + M._nq(nw, d.shape[1], pi) + rent, abs=CENT)


def test_network_subproblem_is_minus_the_congestion_rent_at_a_dual_price():
    """At a price that is a dual, the cleared flows solve the network subproblem.

    That is why the two extra terms of the identity above cancel at LMP and at CHP, and
    why the single-bus form of the identity survived without them.
    """
    g, d, nw = ex4()
    g, d, nw = ck(g, d, nw)
    s = uc(g, d, net=nw)
    pi = lmp(g, d, s, net=nw).pi
    rent = (pi * d).sum() - sum(pi[nw.bus[i]] @ s.p[i] for i in range(len(g)))
    assert rent == pytest.approx(2400.0, abs=CENT)
    assert M._nq(nw, d.shape[1], pi) == pytest.approx(-rent, abs=CENT)
    assert qd(g, d, pi, net=nw) == pytest.approx(s.z, abs=CENT)
