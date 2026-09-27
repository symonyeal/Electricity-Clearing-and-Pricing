# Verification for storage cleared inside the market, models/settle.py.
#
# Three kinds of check. Identities that hold at any price and any balanced dispatch: the
# settlement identity, and the congestion rent recomputed from line flows that are solved
# from the nodal injections alone. Theorems about the resource: X is inside conv(X) inside
# the cut relaxation R, so the three clearings nest; at a held-integer price the resource's
# schedule is its best over its held-mode polytope, so its profit is never negative; and
# R's best profit equals X's at any price above -k(1 + eta^2)/(1 - eta^2). Then each case's
# own numbers, which are arithmetic in its docstring. The baseline is models/joint.py's
# clearing with no resource, which is uc_price's program.
#
# LEGEND
#   X          : the module under test          J : models/joint.py
#   CS         : the seven case constructors    f : one of them
#   g,st,d,net : units, resources, demand, network
#   s,b        : a clearing with and without the resource
#   pi,t       : a price and the settlement at it
#   x,T,m      : one resource, its horizon, a mode pattern
#   a          : a seeded generator             q,y : scratch
#   CENT       : money tolerance, a tenth of a cent, as in test_uc_price

import numpy as np
import pytest

import models.joint as J
import models.settle as X
from models.joint import S
from models.uc_price import ptol
from tests.test_uc_price import CENT

CS = [X.s1, X.s2, X.s3, X.s4, X.s5, X.s6, X.s7]


def _run(f, how="X"):
    g, st, d, net = f()
    s = X.cl(g, st, d, net, how)
    pi, obj, _ = X.px(g, st, d, s, net, how)
    return g, st, d, net, s, pi, obj, X.stl(g, st, d, s, pi, net)


@pytest.mark.parametrize("f", CS)
def test_no_resource_is_joint(f):
    """With the resource removed, the clearing and its price are joint's, to the cent."""
    g, _st, d, net = f()
    a, b = J.cl(g, [], d, net), X.cl(g, [], d, net)
    assert b.z == pytest.approx(a.z, rel=1e-9) and b.obj == pytest.approx(a.z, rel=1e-9)
    assert X.px(g, [], d, b, net)[0] == pytest.approx(J.lmp(g, [], d, a, net).pi, abs=1e-4)


@pytest.mark.parametrize("how", ["X", "H", "R"])
@pytest.mark.parametrize("f", CS)
def test_settlement_identity(f, how):
    """L - z = units' profit + resources' profit + congestion rent, and rent = rf.

    The first is accounting: load pays for every MWh at its bus, each resource is paid for
    its injection at its own bus, and the difference is the rent. The second is the same
    rent from the flows that the injections imply on the dc network, solved without the
    clearing's angle columns. Both hold at any price, so they hold at this one.
    """
    _g, _st, _d, _net, s, _pi, obj, t = _run(f, how)
    assert t.L - t.z == pytest.approx(t.r.sum() + t.rs.sum() + t.rent, abs=CENT)
    assert t.rent == pytest.approx(t.rf, abs=CENT)
    assert obj == pytest.approx(s.obj, rel=1e-9)


def _inj(g, st, d, net, s):
    """Net injection per bus and period: output and discharge less demand and charge."""
    q = -d.copy()
    for i in range(len(g)):
        q[net.bus[i]] += s.p[i]
    for j, x in enumerate(st):
        q[x.bus] += s.sd[j] - s.sc[j]
    return q


@pytest.mark.parametrize("how", ["X", "H", "R"])
@pytest.mark.parametrize("f", CS)
def test_congestion_is_priced_only_on_a_full_line(f, how):
    """A price difference across a line requires that line at its limit, flowing uphill.

    Every case's network is a tree, so the nodal balance fixes each flow and _fl recovers
    it exactly. There the limit's multiplier on line (a, q) is pi_q - pi_a, and
    complementary slackness (BT Theorem 4.5) allows pi_q > pi_a only at f_aq = lim and
    pi_q < pi_a only at f_aq = -lim. Unlike rent = rf, this fails at an arbitrary price.
    """
    g, st, d, net, s, pi, _obj, _t = _run(f, how)
    fl = X._fl(net, _inj(g, st, d, net, s))
    for q, (a, b, _x, lim) in enumerate(net.ln):
        mu = pi[b] - pi[a]
        h = np.abs(mu) > 1e-6
        assert (np.sign(mu[h]) * fl[q][h] == pytest.approx(lim, abs=1e-6))


@pytest.mark.parametrize("f", CS)
def test_the_load_price_lies_on_the_optimal_face(f):
    """At the load bus each price lies in [v(d) - v(d - h e), v(d + h e) - v(d)] / h.

    An LP's optimal duals are the subgradients of its value in the right-hand side (BT
    Theorem 5.2), so the interval is the price's range over the optimal face; h = 0.01 MW
    lies below every breakpoint here, and ptol absorbs the value's own accuracy. The
    interval is a point in every case but s1, whose first and third periods admit any price
    in [10, 80]: there the payment rule of _px chooses 10.
    """
    g, st, d, net, s, pi, v, _t = _run(f)
    h = 1e-2
    for t in range(d.shape[1]):
        e = np.zeros(d.shape)
        e[1, t] = h
        lo = (v - X.px(g, st, d - e, s, net)[1]) / h
        hi = (X.px(g, st, d + e, s, net)[1] - v) / h
        assert lo - ptol <= pi[1, t] <= hi + ptol
        assert hi - lo <= ptol or (f is X.s1 and t in (0, 2))


@pytest.mark.parametrize("f", CS)
def test_conservation(f):
    """Every period balances, stored energy follows its recursion, and every line holds."""
    g, st, d, net, s, _pi, _obj, _t = _run(f)
    x = st[0]
    inj = _inj(g, st, d, net, s)
    assert inj.sum(0) == pytest.approx(0.0, abs=1e-9)
    e = x.e0 + np.cumsum(x.ec * s.sc[0] - s.sd[0] / x.ed)
    assert s.se[0] == pytest.approx(e, abs=1e-9)
    assert (s.sc[0] * s.sd[0] == pytest.approx(0.0, abs=1e-9))
    f = X._fl(net, inj)
    assert (np.abs(f) <= np.array([q[3] for q in net.ln])[:, None] + 1e-6).all()


@pytest.mark.parametrize("f", CS)
def test_three_descriptions_nest(f):
    """X is inside conv(X) inside R, so z_X >= z_H >= z_R, and no resource costs nothing.

    The resource may always idle, so none of the three can cost more than the baseline.
    """
    g, st, d, net = f()
    z = [X.cl(g, st, d, net, how).z for how in ("X", "H", "R")]
    assert z[0] + 1e-6 >= z[1] >= z[2] - 1e-6
    assert z[0] <= X.cl(g, [], d, net).z + 1e-6


def test_the_cut_is_exact_while_the_store_can_absorb():
    """s6 starts empty: A's 5 MW surplus is charged, and X, H and R clear at 2,470."""
    g, st, d, net = X.s6()
    for how in ("X", "H", "R"):
        assert X.cl(g, st, d, net, how).z == pytest.approx(2470.0, abs=1e-6)


def test_the_cut_overstates_a_full_store():
    """s7 starts full. X and H stop A and restart it at 6,000; R clears at 2,270.

    R charges and discharges in the same period at a full store: 0.8 c - d / 0.8 = 0
    keeps the energy at 20 while c - d = 5 MW is absorbed, c = 13.889 and d = 8.889. No
    schedule does that, and a mixture of schedules that each start full cannot absorb
    either, which is why H stays with X. The 3,730 is the cut's overstatement, all of it
    due to the energy bound the cut ignores.
    """
    g, st, d, net = X.s7()
    a, h, r = (X.cl(g, st, d, net, how) for how in ("X", "H", "R"))
    assert a.z == pytest.approx(6000.0, abs=1e-6) and h.z == pytest.approx(6000.0, abs=1e-6)
    assert r.z == pytest.approx(2270.0, abs=1e-6)
    assert a.u[0].tolist() == [0.0, 1.0] and r.u[0].tolist() == [1.0, 1.0]
    assert r.sc[0, 0] == pytest.approx(125.0 / 9.0, abs=1e-6)
    assert r.sd[0, 0] == pytest.approx(80.0 / 9.0, abs=1e-6)
    assert r.se[0, 0] == pytest.approx(20.0, abs=1e-6)


@pytest.mark.parametrize("sd", range(6))
def test_the_cut_is_exact_for_profit_above_its_threshold(sd):
    """max over R of p'(d - c) - k(c + d) equals the max over X when p >= -k(1+h)/(1-h).

    h = ec ed. At a period with c, d > 0, lower c by delta and d by h delta: the energy
    path is unchanged, the bounds and the cut still hold, and profit moves by
    delta (p (1 - h) + k (1 + h)) >= 0. Repeating leaves a schedule of X no worse. Below
    the threshold, and with the store full, R destroys energy for money and X cannot.
    """
    a = np.random.default_rng(sd)
    x = S(float(a.uniform(5, 30)), float(a.uniform(5, 20)), float(a.uniform(5, 20)),
          float(a.uniform(0.7, 1.0)), float(a.uniform(0.7, 1.0)), k=float(a.uniform(0, 3)))
    T, h = 4, x.ec * x.ed
    lo = -x.k * (1 + h) / (1 - h)
    p = lo + a.uniform(0, 60, T)
    assert X._ub(x, T, p, "R") == pytest.approx(X._ub(x, T, p), abs=1e-6)
    y = x._replace(e0=x.e)
    p = np.full(T, lo - 10.0)
    assert X._ub(y, T, p, "R") > X._ub(y, T, p) + 1e-3


@pytest.mark.parametrize("f", CS)
def test_a_held_price_pays_the_resource_its_best(f):
    """At the held-integer price the resource's profit is its best over its held modes.

    The re-dispatch is a linear program; relaxing its balance rows at an optimal dual
    leaves each resource minimising its own cost less its revenue, and the cleared
    schedule is such a minimiser. Idling is feasible under any modes when e0 = ef or ef is
    free, so the profit is never negative: under this rule storage needs no make-whole.
    """
    _g, st, d, _net, s, pi, _obj, t = _run(f)
    x = st[0]
    q = X._ub(x, d.shape[1], pi[x.bus], "P", s.sm[0])
    assert t.rs[0] == pytest.approx(q, abs=CENT)
    assert t.rs[0] >= -CENT and t.ls[0] >= -CENT


def test_s1_lowers_cost_and_earns_nothing():
    """Cost falls by 1,800 and B's 600 make-whole disappears; every price is 10.

    In the first and third periods 10 is the payment rule's choice from [10, 80], and so is
    the load payment. The resource's zero profit holds on the whole face: it charges and
    discharges the same lossless 30 MWh at one price.
    """
    g, _st, d, net, s, pi, _obj, t = _run(X.s1)
    b = X.cl(g, [], d, net)
    q = X.stl(g, [], d, b, X.px(g, [], d, b, net)[0], net)
    assert (b.z, s.z) == pytest.approx((4000.0, 2200.0))
    assert q.mw.sum() == pytest.approx(600.0, abs=CENT)
    assert t.mw.sum() == pytest.approx(0.0, abs=CENT)
    assert pi == pytest.approx(np.full(pi.shape, 10.0), abs=1e-6)
    assert t.rs[0] == pytest.approx(0.0, abs=CENT)
    assert (q.L, t.L) == pytest.approx((6200.0, 2200.0), abs=CENT)


@pytest.mark.parametrize("f,z,rs,rent", [(X.s2, 3250.0, 0.0, 1050.0),
                                         (X.s3, 3250.0, 0.0, 5950.0),
                                         (X.s4, 2900.0, 1400.0, 0.0),
                                         (X.s5, 3250.0, 1050.0, 4900.0)])
def test_value_and_profit_part(f, z, rs, rent):
    """What the resource saves and what it earns are different numbers.

    s2 and s3 save 750 and earn nothing; the saving reappears as rent. s4 and s5 earn
    more than they save: without B the peak price is C's 80, not B's 50, and B would
    have earned 1,200 at it, its lost opportunity.
    """
    _g, _st, _d, _net, s, _pi, _obj, t = _run(f)
    assert s.z == pytest.approx(z, abs=1e-6)
    assert t.rs[0] == pytest.approx(rs, abs=CENT)
    assert t.rent == pytest.approx(rent, abs=CENT)
    assert t.loc[1] == pytest.approx(1200.0, abs=CENT)


def test_s3_moves_the_generator_s_profit_into_rent():
    """At A's bus the resource fills the line: A's 2,800 at a peak price of 50 becomes rent."""
    g, _st, d, net, _s, _pi, _obj, t = _run(X.s3)
    b = X.cl(g, [], d, net)
    q = X.stl(g, [], d, b, X.px(g, [], d, b, net)[0], net)
    assert (q.r[0], t.r[0]) == pytest.approx((2800.0, 0.0), abs=CENT)
    assert (q.rent, t.rent) == pytest.approx((0.0, 5950.0), abs=CENT)


def test_the_energy_congestion_split_moves_with_the_reference():
    """s5's 1,050 is congestion value against bus 0 and energy value against bus 1."""
    g, st, d, net, s, pi, _obj, t = _run(X.s5)
    u = X.stl(g, st, d, s, pi, net, ref=1)
    assert (t.en[0], t.cn[0]) == pytest.approx((0.0, 1050.0), abs=CENT)
    assert (u.en[0], u.cn[0]) == pytest.approx((1050.0, 0.0), abs=CENT)
    assert t.rs == pytest.approx(u.rs)


def test_a_price_taking_schedule_imposed_in_full_earns_nothing():
    """Against the no-storage price the s1 resource expects 1,200; cleared, it earns 0.

    The schedule is the co-optimised one, so cost is again 2,200; the spread it was built
    on is what its own injection removes.
    """
    g, st, d, net = X.s1()
    b = X.cl(g, [], d, net)
    p0 = X.px(g, [], d, b, net)[0][1]
    q = X.ps(st[0], 4, p0)
    assert p0 @ (q[1] - q[0]) == pytest.approx(1200.0, abs=CENT)
    s = X.cl(g, st, d, net, "fix", q=[q])
    pi = X.px(g, st, d, s, net, "fix", q=[q])[0]
    assert s.z == pytest.approx(2200.0, abs=1e-6)
    assert X.stl(g, st, d, s, pi, net).rs[0] == pytest.approx(0.0, abs=CENT)


@pytest.mark.parametrize("kk,sp,z,peak,rs", [(1, 0.0, 2200.0, 50.0, 1200.0),
                                             (3, 0.2, 2200.0, 62.0, 1560.0),
                                             (5, 1.0, 2620.0, 80.0, 1680.0)])
def test_a_curve_sets_the_price_it_is_paid(kk, sp, z, peak, rs):
    """Offered as market/bid.py's curve around the no-storage price, the same position
    clears the same energy at a price its own offer sets.

    One step at the reference: the peak prices at the 50 offered, and the resource earns
    1,200 where co-optimisation paid it 0. Three steps at 20%: the 60 slice is taken and
    the store's last charged slice, bid at 8, adds 2 through the energy row, so the peak
    prices at 62. Five steps at 100%: the slice offered at 100 is above C's 80 and is not
    taken, C runs 6 MW, cost rises 420 and the peak prices at 80.
    """
    g, st, d, net = X.s1()
    b = X.cl(g, [], d, net)
    ref = X.px(g, [], d, b, net)[0][1]
    q = X.ps(st[0], 4, ref)
    y = [q[1] - q[0]]
    s = X.cl(g, st, d, net, "bid", q=y, ref=[ref], kk=kk, sp=sp)
    pi = X.px(g, st, d, s, net, "bid", q=y, ref=[ref], kk=kk, sp=sp)[0]
    t = X.stl(g, st, d, s, pi, net)
    assert s.z == pytest.approx(z, abs=1e-6)
    assert pi[1, 2] == pytest.approx(peak, abs=1e-4)
    assert t.rs[0] == pytest.approx(rs, abs=CENT)
