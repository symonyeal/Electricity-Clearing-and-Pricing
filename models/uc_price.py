# Unit commitment, the prices dual to it, and the uplift each price leaves.
#
# The market clears once as a mixed-integer program. Every price is the dual of a linear
# program built from that one clearing: LMP fixes the cleared commitment; CHP replaces each
# unit by the convex hull of its schedules; AIC prices that hull after restricting the
# blocks that failed to cover their cost at LMP. Citations: docs/SOURCES.md.
#
# LEGEND
#   U,Net        : one unit's offer and initial state; unit buses and lines
#   Sol          : one solved outcome
#   Mkt,Pay      : every price from one clearing, and the payment split
#   mk,ck        : fill one unit's optional fields, validate a whole market
#   _ix          : the whole number a discrete field names, refusing anything else
#   _dg,_mi      : name why a solve failed; solve an integer program to a proved optimum
#   _rw,_eq,_fx  : THE feasible set, written once: rows, equalities, bounds
#   _pl          : those same rows with the binaries fixed -> one dispatch polytope
#   _vw          : the start and stop flags an on/off row implies
#   _tj,_cl      : every on/off trajectory, and the feasible ones with their polytopes
#   _iv,_ar      : one on-interval's polytope, and every arc of a unit's interval graph
#   _nw,_tr      : THE network, written once: angles, nodal flows, line limits; and the
#                  transport form of the same lines, limits only
#   fm,zn        : the line model, "dc" or "ntc"; the zone keys
#   xc,fl,nf     : one exchange capacity pair, all of them, and how many columns they fill
#   _sy,_out     : assemble the algebraic system, and split a solved vector back up
#   _ce,_fp,_px  : a stage ceiling, an optimal-face probe, and one canonical price
#   _jt          : dispatch one chosen trajectory per unit against demand
#   _hold        : the columns that hold a given commitment fixed
#   _bk,_pf      : a unit's commitment blocks, and one block's profit
#   _om          : best profit each unit could earn by self-scheduling
#   _nq          : the network subproblem the same relaxation leaves behind
#   uc,rx        : integer clearing, and the same system relaxed
#   en           : joint trajectory enumeration, the independent optimum
#   hc,hl        : the convex hull from intervals, and the same hull from whole trajectories;
#                  the balance dual of either is the CHP or, with pc's ceilings, the AIC
#   lmp          : prices with the cleared commitment held fixed
#   qd           : the Lagrangian dual value at a price
#   pc           : the AIC output ceilings built from a cleared market
#   pay,run      : profit and uplift, and one clearing followed by every price
#   mk_g         : a labelled synthetic market for the bench
#   ex1,ex2,ex3  : the three published cases this model is checked against
#   ex4,ex5      : the textbook three-bus loop, and the two-zone coupled market
#   x            : one unit                        g : the units of a market
#   lo,hi        : minimum and maximum output      c : energy cost per MWh
#   nl,su        : no-load cost per period, start-up cost per start
#   ru,rd        : normal ramp up and down         sr,dr : start-up and shut-down ramp
#   mu,md        : minimum run and minimum down periods
#   u0,p0,e0     : initial on/off, initial output, periods already in that state
#   d            : demand per bus and period       T,G,B : period, unit and bus counts
#   bus,ln,nb    : each unit's bus, the lines, and how many buses there are
#   lim          : one line's MW limit             r0 : where the balance rows start
#   p,u,v,w      : output, on/off, start, stop     y : a right side, or scaled hull output
#   pi           : energy price per period         z : one block's profit, or a total cost
#   ep           : the AIC output relaxation       cap : per-period output ceilings
#   A,b          : inequality rows and right side  Ae,be : equality rows and right side
#   lb,ub        : variable bounds                 nt : how many trailing rows are balance rows
#   f,it         : integrality switch and flags    P,Q,V,W : the four column blocks of a row
#   C,K          : the columns of each unit, and one column count
#   k            : a column's fixed cost           m,e,n : row and column counters
#   r,mw,loc,up  : profit, make-whole, lost opportunity, total uplift
#   om           : best profit a unit could self-schedule at pi
#   s,L          : the clearing, and its LMP solution
#   res,best     : a solver result, and the best result found so far
#   i,j,t,q,a    : unit, column, period and scratch indices
#   ri,ci,va     : sparse row, column and value lists   ei,ec,ev : the same for equalities
#   o            : variable offsets                tol : feasibility tolerance
#   ptol         : smallest price difference retained by the lexicographic walk
#   st           : how far price selection got: dual, raw, pay, probe, part, walk
#   vr           : versions of the solvers behind a result
#   LIM          : ceilings: enumerated periods, hull variables, joint commitments,
#                  and balance rows the price refinement will walk one at a time

import sys
import warnings
from itertools import product
from typing import NamedTuple

import numpy as np
import scipy
from scipy.optimize import Bounds, LinearConstraint, OptimizeWarning, linprog, milp
from scipy.sparse import csc_array, hstack, vstack

LIM = (16, 100000, 20000, 24)
tol = 1e-7
ptol = 1e-3


class U(NamedTuple):
    """One unit's offer, physical limits and initial state. mk fills the optional fields."""

    lo: float
    hi: float
    c: float
    nl: float = 0.0
    su: float = 0.0
    ru: float | None = None
    rd: float | None = None
    sr: float | None = None
    dr: float | None = None
    mu: int = 1
    md: int = 1
    u0: int = 0
    p0: float = 0.0
    e0: int | None = None


class Net(NamedTuple):
    """Where each unit sits, and the lines or exchanges between those locations.

    fm selects the line model and with it the shape of a line. Bus 0 is the angle reference
    under "dc"; under "ntc" there are no angles.

    Under "dc" a line is (bus, bus, reactance, MW limit) and carries
    f_ij = (theta_i - theta_j) / x_ij as well as the limit.

    Under "ntc" the buses are bidding zones and a line is an exchange,
    (zone, zone, (min, max)), keyed by its two zones in ascending order and bounding the
    signed flow from the first to the second. That is the electricity maps exchange record:
    NO-NO1_NO-NO2 carries capacity [-3500, 2200], meaning up to 3500 MW into NO-NO1 and up
    to 2200 MW out of it. There is no reactance, and the capacity is not symmetric.

    zn names the zones, one key per zone, as NO-NO1 and NO-NO2 do. Given no network, ck
    supplies one bus and no lines; a single-zone market is this container, empty.
    """

    bus: np.ndarray
    ln: tuple
    nb: int
    fm: str = "dc"
    zn: tuple = ()


class Sol(NamedTuple):
    """Cost, output, commitment and price of one solve. u is fractional in relaxed solves.

    pi carries one price per bus per period, so it is (1, T) on a market with no network.

    st says how far price selection got, because a price this routine could not refine is
    not the same object as one it walked: dual, the solver's own vertex with no selection
    asked for; raw, the payment stage itself failed; pay, past LIM[3] so payment only and
    the probe never reached; probe, the probe closed the face; part, the walk stopped on a
    failed step; walk, the walk completed. Only the last two are canonical to the walk.

    A route that prices nothing has no such walk to report, so there st carries the
    certificate of its own solve instead: opt, the search closed its bound; gap, it stopped
    short of one and the value is an incumbent rather than a proved optimum; enum, the value
    came from enumeration and no bound was involved.
    """

    z: float
    p: np.ndarray
    u: np.ndarray
    pi: np.ndarray
    st: str = ""


class Mkt(NamedTuple):
    """One integer clearing, then LMP, exact and relaxed CHP, exact and relaxed AIC."""

    uc: Sol
    lmp: Sol
    chp: Sol
    chp_r: Sol
    aic: Sol
    aic_r: Sol


class Pay(NamedTuple):
    """Per unit: realised profit, make-whole, lost opportunity and total uplift."""

    r: np.ndarray
    mw: np.ndarray
    loc: np.ndarray
    up: np.ndarray


def _ix(y, what):
    """The whole number a discrete field names, refusing a value that is not one.

    int() truncates. A minimum run time given as 1.9 periods silently becomes 1, a bus
    given as 0.9 becomes bus 0, and the model then answers a question nobody asked while
    reporting it as the one that was put. A discrete field is a whole number or an error.
    """
    q = float(y)
    if not np.isfinite(q) or q != int(q):
        raise ValueError(f"{what} must be a whole number")
    return int(q)


def mk(x):
    """Return one unit with its ramp and initial-duration defaults filled in.

    The discrete fields are checked before they are converted, so a fractional minimum run
    time is refused rather than truncated into a different unit.
    """
    hi = float(x.hi)
    mu, md = _ix(x.mu, "a minimum run time"), _ix(x.md, "a minimum down time")
    return U(
        float(x.lo),
        hi,
        float(x.c),
        float(x.nl),
        float(x.su),
        hi if x.ru is None else float(x.ru),
        hi if x.rd is None else float(x.rd),
        hi if x.sr is None else float(x.sr),
        hi if x.dr is None else float(x.dr),
        mu,
        md,
        _ix(x.u0, "an initial commitment"),
        float(x.p0),
        max(mu, md) if x.e0 is None else _ix(x.e0, "an initial duration"),
    )


def ck(g, d, net=None):
    """Validate one market and return its filled units, its nodal demand, and its network."""
    d = np.atleast_2d(np.asarray(d, dtype=float))
    if d.ndim != 2 or not d.size:
        raise ValueError("demand must be a non-empty vector, one value per period")
    if not np.isfinite(d).all() or (d < 0).any():
        raise ValueError("demand must be finite and non-negative")
    g = [mk(x if isinstance(x, U) else U(*x)) for x in g]
    if not g:
        raise ValueError("a market needs at least one unit")
    for x in g:
        if not all(np.isfinite(y) for y in (x.lo, x.hi, x.c, x.nl, x.su, x.p0,
                                            x.ru, x.rd, x.sr, x.dr)):
            raise ValueError("unit offers, limits and ramps must be finite")
        if x.hi <= 0 or x.lo < 0 or x.lo > x.hi:
            raise ValueError("require 0 <= lo <= hi with hi > 0")
        if x.nl < 0 or x.su < 0:
            raise ValueError("no-load and start-up costs must be non-negative")
        if min(x.ru, x.rd, x.sr, x.dr) <= 0:
            raise ValueError("every ramp limit must be positive")
        if x.mu < 1 or x.md < 1 or x.e0 < 0:
            raise ValueError("minimum run and down times must be at least one period")
        if x.u0 not in (0, 1):
            raise ValueError("the initial commitment must be 0 or 1")
        if x.u0 == 0 and x.p0 != 0.0:
            raise ValueError("a unit that starts offline must start at zero output")
        if x.u0 == 1 and not (x.lo <= x.p0 <= x.hi):
            raise ValueError("initial output must lie inside a running unit's limits")
    if net is None:
        net = Net(np.zeros(len(g), dtype=int), (), 1)
    else:
        nb = _ix(net.nb, "a bus count")
        bus = np.asarray(net.bus, dtype=float).ravel()
        bus = np.array([_ix(y, "a unit's bus") for y in bus], dtype=int)
        if bus.shape != (len(g),) or bus.min() < 0 or bus.max() >= nb:
            raise ValueError("every unit must sit at a bus of the network")
        if net.fm not in ("dc", "ntc"):
            raise ValueError("the line model must be dc or ntc")
        ln = []
        # The shape is counted before anything is read out of it. Reading e[0] first left a
        # line too short to hold two endpoints raising IndexError, so a malformed offer
        # reached the caller as "tuple index out of range" rather than as its own shape.
        sh = ("an exchange is (zone, zone, (min, max))" if net.fm == "ntc"
              else "a line is (bus, bus, reactance, limit)")
        for e in net.ln:
            if len(e) != (3 if net.fm == "ntc" else 4):
                raise ValueError(sh)
            a = _ix(e[0], "a line endpoint")
            q = _ix(e[1], "a line endpoint")
            if not (0 <= a < nb and 0 <= q < nb) or a == q:
                raise ValueError("every line must join two different buses")
            if net.fm == "ntc":
                if np.ndim(e[2]) != 1 or np.size(e[2]) != 2:
                    raise ValueError(sh)
                if a > q:
                    raise ValueError("an exchange must name its zones in ascending order")
                if not np.isfinite(e[2]).all() or e[2][0] >= 0 or e[2][1] <= 0:
                    raise ValueError("an exchange capacity must run from negative to positive")
            else:
                if not np.isfinite(e[2:]).all() or e[2] <= 0 or e[3] <= 0:
                    raise ValueError("every line needs a positive reactance and limit")
            ln.append((a, q) + tuple(e[2:]))
        zn = tuple(net.zn)
        if zn and (len(zn) != nb or len(set(zn)) != len(zn)):
            raise ValueError("zone keys must be one per zone and distinct")
        net = Net(bus, tuple(ln), nb, net.fm, zn)
    if d.shape[0] != net.nb:
        raise ValueError("demand must have one row per bus and one column per period")
    if d.sum(0).max() > sum(x.hi for x in g):
        raise ValueError("demand exceeds total generating capacity")
    return g, d, net


def _rw(x, T, cap=None):
    """Every inequality defining one unit's feasible set, over the columns [p|u|v|w]."""
    A, b = [], []

    def add(y=0.0):
        A.append(np.zeros(4 * T))
        b.append(y)
        return A[-1]

    P, Q, V, W = 0, T, 2 * T, 3 * T
    for t in range(T):
        r = add()
        r[P + t], r[Q + t] = -1.0, x.lo
        r = add()
        r[P + t], r[Q + t] = 1.0, -x.hi
        r = add()
        r[P + t], r[Q + t], r[V + t] = 1.0, -x.hi, x.hi - x.sr
        if t + 1 < T:
            r = add()
            r[P + t], r[Q + t], r[W + t + 1] = 1.0, -x.hi, x.hi - x.dr
        if t:
            r = add()
            r[P + t], r[P + t - 1], r[Q + t - 1], r[V + t] = 1.0, -1.0, -x.ru, -x.sr
            r = add()
            r[P + t - 1], r[P + t], r[Q + t], r[W + t] = 1.0, -1.0, -x.rd, -x.dr
        else:
            r = add(x.p0 + x.ru * x.u0)
            r[P], r[V] = 1.0, -x.sr
            r = add(-x.p0)
            r[P], r[Q], r[W] = -1.0, -x.rd, -x.dr
        r = add(1.0)
        r[V + t], r[W + t] = 1.0, 1.0
        r = add()
        r[V + t], r[Q + t] = 1.0, -1.0
        r = add(1.0)
        r[W + t], r[Q + t] = 1.0, 1.0
        r = add()
        r[Q + t] = -1.0
        for q in range(max(0, t - x.mu + 1), t + 1):
            r[V + q] += 1.0
        r = add(1.0)
        r[Q + t] = 1.0
        for q in range(max(0, t - x.md + 1), t + 1):
            r[W + q] += 1.0
        if cap is not None:
            r = add(float(cap[t]))
            r[P + t] = 1.0
    return np.array(A), np.array(b)


def _eq(x, T):
    """The start and stop state equation v - w = u - u_prev, over the columns [p|u|v|w]."""
    A, b = np.zeros((T, 4 * T)), np.zeros(T)
    for t in range(T):
        A[t, 2 * T + t], A[t, 3 * T + t], A[t, T + t] = 1.0, -1.0, -1.0
        if t:
            A[t, T + t - 1] = 1.0
        else:
            b[t] = -float(x.u0)
    return A, b


def _fx(x, T):
    """Variable bounds, including the run or down time a unit carries in from before t=0."""
    lb, ub = np.zeros(4 * T), np.r_[np.full(T, x.hi), np.ones(3 * T)]
    if x.u0 == 1 and x.e0 < x.mu:
        lb[T : T + min(T, x.mu - x.e0)] = 1.0
    if x.u0 == 0 and x.e0 < x.md:
        ub[T : T + min(T, x.md - x.e0)] = 0.0
    return lb, ub


def _pl(x, T, u, v, w, cap=None):
    """Fix one trajectory in the rows above and return its dispatch polytope, or None."""
    y = np.r_[u, v, w]
    A, b = _rw(x, T, cap)
    b = b - A[:, T:] @ y
    A = A[:, :T]
    m = np.abs(A).sum(1) > 0
    if (b[~m] < -tol).any():
        return None
    Ae, be = _eq(x, T)
    if np.abs(Ae[:, T:] @ y - be).max() > tol:
        return None
    lb, ub = _fx(x, T)
    if (y < lb[T:] - tol).any() or (y > ub[T:] + tol).any():
        return None
    return A[m], b[m]


def _vw(x, u):
    """The start and stop flags one commitment row implies, given the unit's initial state."""
    a = np.r_[float(x.u0), u[:-1]]
    return np.maximum(u - a, 0.0), np.maximum(a - u, 0.0)


def _tj(x, T):
    """Every on/off pattern, with the start and stop flags the state equation implies."""
    if T > LIM[0]:
        raise ValueError(f"trajectory enumeration is limited to {LIM[0]} periods")
    for q in product((0, 1), repeat=T):
        u = np.array(q, dtype=float)
        yield (u, *_vw(x, u))


def _cl(x, T, cap=None):
    """One unit's feasible trajectories as disjuncts: pattern, polytope and fixed cost."""
    C = []
    for u, v, w in _tj(x, T):
        r = _pl(x, T, u, v, w, cap)
        if r is not None:
            C.append((u, v, w, r[0], r[1], x.nl * u.sum() + x.su * v.sum()))
    if not C:
        raise ValueError("a unit has no feasible trajectory")
    return C


def _tr(net, T, n, A, b, Ae, c, lb, ub, it):
    """Append one exchange flow per line and period, bounded by its capacity and nothing else.

    This is the transport model zonal day-ahead coupling clears on. A flow is any vector the
    nodal balances admit inside the capacity pair, so there is no loop-flow condition: on a
    network with a cycle this is a strict relaxation of _nw, and on a tree the balances
    determine the flows and the two coincide. The capacity is the (min, max) bound on the
    signed flow, not one symmetric limit, because published transfer capacity is directional.
    """
    ei, ec, ev, fl = [], [], [], []
    r0 = Ae.shape[0] - net.nb * T
    for i, (a, q, xc) in enumerate(net.ln):
        for t in range(T):
            e = i * T + t
            ei.extend([r0 + a * T + t, r0 + q * T + t])
            ec.extend([e, e])
            ev.extend([-1.0, 1.0])
            fl.append((float(xc[0]), float(xc[1])))
    nf, fl = len(net.ln) * T, np.array(fl)
    ub = np.full(n, np.inf) if ub is None else ub
    return (
        csc_array(hstack([csc_array(A), csc_array((A.shape[0], nf))])),
        b,
        csc_array(hstack([csc_array(Ae),
                          csc_array((ev, (ei, ec)), shape=(Ae.shape[0], nf))])),
        np.r_[c, np.zeros(nf)],
        np.r_[lb, fl[:, 0]],
        np.r_[ub, fl[:, 1]],
        None if it is None else np.r_[it, np.zeros(nf)],
    )


def _nw(net, T, n, A, b, Ae, c, lb, ub, it):
    """Append one voltage angle per bus and period, then the line flows and the line limits.

    The last nb*T equality rows are the nodal balance rows; the flow terms enter there.
    Flow is f_ij = (theta_i - theta_j) / x_ij with -lim <= f_ij <= lim, the direct-current
    reading. Only angle differences matter, so bus 0 is held at zero. Every solve route
    calls this, so all of them price the same network.
    """
    B = net.nb
    if not net.ln:
        return A, b, Ae, c, lb, np.full(n, np.inf) if ub is None else ub, it
    if net.fm == "ntc":
        return _tr(net, T, n, A, b, Ae, c, lb, ub, it)
    ri, ci, va, bb = [], [], [], []
    ei, ec, ev = [], [], []
    r0 = Ae.shape[0] - B * T
    for t in range(T):
        for a, q, x, lim in net.ln:
            j = (a * T + t, q * T + t)
            for r, y in ((a, -1.0), (q, 1.0)):
                ei.extend([r0 + r * T + t] * 2)
                ec.extend(j)
                ev.extend([y / x, -y / x])
            for y in (1.0, -1.0):
                ri.extend([len(bb)] * 2)
                ci.extend(j)
                va.extend([y / x, -y / x])
                bb.append(float(lim))
    m = A.shape[0]
    A = vstack([
        hstack([csc_array(A), csc_array((m, B * T))]),
        hstack([csc_array((len(bb), n)), csc_array((va, (ri, ci)), shape=(len(bb), B * T))]),
    ])
    Ae = hstack([csc_array(Ae),
                 csc_array((ev, (ei, ec)), shape=(Ae.shape[0], B * T))])
    lb = np.r_[lb, np.full(B * T, -np.inf)]
    ub = np.r_[np.full(n, np.inf) if ub is None else ub, np.full(B * T, np.inf)]
    lb[n : n + T] = ub[n : n + T] = 0.0
    return (csc_array(A), np.r_[b, bb], csc_array(Ae), np.r_[c, np.zeros(B * T)], lb, ub,
            None if it is None else np.r_[it, np.zeros(B * T)])


def _sy(g, d, net, cap, f):
    """Assemble the algebraic system once; f decides whether the commitment stays integer."""
    G, T, B = len(g), d.shape[1], net.nb
    o, n = [4 * T * i for i in range(G)], 4 * T * G
    c, lb, ub = np.zeros(n), np.zeros(n), np.zeros(n)
    ri, ci, va, b = [], [], [], []
    ei, ec, ev, be = [], [], [], []
    m = e = 0
    for i, x in enumerate(g):
        A, y = _rw(x, T, None if cap is None else cap[i])
        q, r = np.nonzero(A)
        ri.extend(m + q)
        ci.extend(o[i] + r)
        va.extend(A[q, r])
        b.extend(y)
        m += len(A)
        A, y = _eq(x, T)
        q, r = np.nonzero(A)
        ei.extend(e + q)
        ec.extend(o[i] + r)
        ev.extend(A[q, r])
        be.extend(y)
        e += T
        c[o[i] : o[i] + T] = x.c
        c[o[i] + T : o[i] + 2 * T] = x.nl
        c[o[i] + 2 * T : o[i] + 3 * T] = x.su
        lb[o[i] : o[i] + 4 * T], ub[o[i] : o[i] + 4 * T] = _fx(x, T)
    for i in range(G):
        for t in range(T):
            ei.append(e + net.bus[i] * T + t)
            ec.append(o[i] + t)
            ev.append(1.0)
    be.extend(d.ravel())
    it = np.zeros(n)
    if f:
        for i in range(G):
            it[o[i] + T : o[i] + 4 * T] = 1.0
    A, b, Ae, c, lb, ub, it = _nw(
        net, T, n, csc_array((va, (ri, ci)), shape=(m, n)), np.array(b),
        csc_array((ev, (ei, ec)), shape=(e + B * T, n)), c, lb, ub, it)
    return c, A, b, Ae, np.array(be), lb, ub, it, o


def _out(g, T, y, o):
    """Split a solved algebraic vector back into per-unit output and commitment."""
    p = np.array([y[o[i] : o[i] + T] for i in range(len(g))])
    u = np.array([y[o[i] + T : o[i] + 2 * T] for i in range(len(g))])
    return np.where(np.abs(p) < 1e-9, 0.0, p), u


def _dg(res):
    """Why a solve did not succeed, in the solver's own terms rather than "infeasible".

    A malformed ramp and a demand no commitment can serve both end in a failed solve, and
    calling either one infeasible names the second correctly and the first wrongly. The
    status separates a proved infeasibility from a limit, an unbounded objective and a
    numerical failure, and the message says which the solver reached.
    """
    k = {1: "limit", 2: "infeasible", 3: "unbounded", 4: "numerical"}
    return f"{k.get(int(res.status), 'other')}: {res.message}"


def _mi(c, it, lb, ub, A, b, Ae, be, why):
    """Solve one integer program to a proved optimum, and report what was proved.

    A requested tolerance is not a result. HiGHS stops at a relative gap of 1e-4 unless
    told otherwise, so a reference routine that asks for nothing and returns "opt" is
    reporting a tolerance it never read back. These routines carry claims of exactness, so
    the gap asked for is zero and the gap achieved is read: "opt" means the bound closed,
    "gap" means the search stopped at an incumbent, and the two are not the same object.
    """
    res = milp(
        c,
        integrality=it,
        bounds=Bounds(lb, ub),
        constraints=[LinearConstraint(A, -np.inf, b), LinearConstraint(Ae, be, be)],
        options={"mip_rel_gap": 0.0},
    )
    if not res.success:
        raise ValueError(f"{why} [{_dg(res)}]")
    ag = float(res.mip_gap) if np.any(it) else 0.0
    return res, ag, "opt" if ag == 0.0 else "gap"


def uc(g, d, cap=None, net=None):
    """Clear the market: unit commitment and economic dispatch as one integer program."""
    g, d, net = ck(g, d, net)
    c, A, b, Ae, be, lb, ub, it, o = _sy(g, d, net, cap, True)
    res, _ag, st = _mi(c, it, lb, ub, A, b, Ae, be, "this demand did not clear")
    p, u = _out(g, d.shape[1], res.x, o)
    return Sol(float(res.fun), p, np.rint(u), np.full(d.shape, np.nan), st)


def rx(g, d, cap=None, net=None):
    """Relax the same system's binaries; its balance dual is the relaxation's energy price."""
    g, d, net = ck(g, d, net)
    c, A, b, Ae, be, lb, ub, _, o = _sy(g, d, net, cap, False)
    why = []
    res = _px(c, A, b, Ae, be, lb, ub, d.size, why)
    if res is None:
        raise ValueError(f"the relaxed commitment did not solve [{why[0]}]")
    p, u = _out(g, d.shape[1], res[1], o)
    return Sol(res[0], p, u, res[2][-d.size :].reshape(d.shape), res[3])


def _ce(v):
    """A ceiling just above v, so an already-minimised stage is held without exact equality."""
    return v + 1e-9 * max(1.0, abs(v))


def _fp(D, c, R, rhs, bd, m, e, nt, pi):
    """Probe the payment-optimal price face from a tolerance-relaxed interior point.

    A zero-objective interior-point solve without crossover returns a relative-interior
    point of the face rather than a vertex. The face rows carry the solver's feasibility
    tolerance, so a thin but feasible face is not reported infeasible. If that point and the
    payment-minimising vertex agree within ptol, no price difference of settlement size
    remains for the lexicographic walk to resolve.
    """
    q = np.asarray(rhs, dtype=float)
    q = q + tol * np.maximum(1.0, np.abs(q))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", OptimizeWarning)
        z = linprog(
            np.zeros(m + e),
            A_ub=csc_array(np.array(R)),
            b_ub=q,
            A_eq=D,
            b_eq=c,
            bounds=bd,
            method="highs-ipm",
            options={"run_crossover": "off"},
        )
    if not z.success:
        return np.inf
    return float(np.max(np.abs(np.asarray(z.x[m + e - nt :], dtype=float) - pi[-nt:])))


def _px(c, A, b, Ae, be, lb=None, ub=None, nt=0, why=None):
    """Solve a priced program, then select one canonical vector from its optimal duals.

    A balance dual is a subgradient of cost in demand. At a kink, and wherever pc's ceilings
    have made the program integral, the optimal duals form a face and the solver returns
    whichever vertex its basis reaches. The last nt equality rows are the balance rows, so
    be[-nt:] is demand. Stage 1 minimises the demand payment over that face; this selects
    the lower slope, the marginal cost of what was served. The payment-optimal face may hold
    more than one point. Stage 2 probes it with one tolerance-relaxed interior-point solve.
    If the probe moves no price by ptol, stage 3 is skipped; otherwise stage 3 minimises each
    balance price in turn and holds it. LIM caps the number of rows walked; past the cap only
    the payment is minimised, and the price is canonical only to that.

    Each stage is held by an inequality just above its own optimum, not by an equality.
    Exact equalities accumulate rounding until a later stage reports infeasible and
    refinement stops silently, which made two routes disagree on one market.

    Dual feasibility is an equality. An inequality looks correct while every variable carries
    a bound row, whose multiplier absorbs the slack; a free variable such as a voltage angle
    has no such row, and the inequality then admits vectors that are not duals.

    None still means the program did not solve, because one caller probes trajectories and
    reads that as an ordinary answer. A caller that will raise passes why, a list this
    appends the solver's own diagnosis to, so the failure is reported as what it was rather
    than as infeasibility.
    """
    A = csc_array(A)
    Ae = csc_array(Ae)
    if lb is not None or ub is not None:
        n = A.shape[1]
        ri, ci, va, y = [], [], [], []
        for i in range(n):
            for q, e in ((lb, -1.0), (ub, 1.0)):
                if q is not None and np.isfinite(q[i]):
                    ri.append(len(y))
                    ci.append(i)
                    va.append(e)
                    y.append(e * float(q[i]))
        if y:
            A = csc_array(vstack([A, csc_array((va, (ri, ci)), shape=(len(y), n))]))
            b = np.r_[b, y]
    res = linprog(c, A_ub=A, b_ub=b, A_eq=Ae, b_eq=be, bounds=(None, None))
    if not res.success:
        if why is not None:
            why.append(_dg(res))
        return None
    m, e = A.shape[0], Ae.shape[0]
    if not nt:
        return float(res.fun), res.x, np.asarray(res.eqlin.marginals, dtype=float), "dual"
    D, bd = csc_array(hstack([A.T, Ae.T])), [(None, 0.0)] * m + [(None, None)] * e
    R, rhs = [-np.r_[b, be]], [_ce(-float(res.fun))]
    y, pi = np.zeros(m + e), np.asarray(res.eqlin.marginals, dtype=float)
    y[m + e - nt :] = be[e - nt :]
    q = linprog(y, A_ub=csc_array(np.array(R)), b_ub=rhs, A_eq=D, b_eq=c, bounds=bd)
    if not q.success:
        return float(res.fun), res.x, pi, "raw"
    pi = np.asarray(q.x[m:], dtype=float)
    R.append(y.copy())
    rhs.append(_ce(float(q.fun)))
    if nt > LIM[3]:
        return float(res.fun), res.x, pi, "pay"
    if _fp(D, c, R, rhs, bd, m, e, nt, pi) <= ptol:
        return float(res.fun), res.x, pi, "probe"
    for t in range(nt):
        y = np.zeros(m + e)
        y[m + e - nt + t] = 1.0
        q = linprog(y, A_ub=csc_array(np.array(R)), b_ub=rhs, A_eq=D, b_eq=c, bounds=bd)
        if not q.success:
            return float(res.fun), res.x, pi, "part"
        pi = np.asarray(q.x[m:], dtype=float)
        R.append(y.copy())
        rhs.append(_ce(float(q.fun)))
    return float(res.fun), res.x, np.asarray(pi, dtype=float), "walk"


def _jt(g, d, net, C, j, why=None):
    """Dispatch one chosen trajectory per unit against demand; return cost, output and duals."""
    G, T = len(g), d.shape[1]
    n = G * T
    A, b, c = [], [], np.zeros(n)
    for i in range(G):
        f = np.zeros((len(C[i][j[i]][3]), n))
        f[:, i * T : (i + 1) * T] = C[i][j[i]][3]
        A.append(f)
        b.append(C[i][j[i]][4])
        c[i * T : (i + 1) * T] = g[i].c
    Ae = np.zeros((net.nb * T, n))
    for i in range(G):
        Ae[net.bus[i] * T : net.bus[i] * T + T, i * T : i * T + T] += np.eye(T)
    q = _nw(net, T, n, np.vstack(A), np.concatenate(b), Ae, c, np.full(n, -np.inf), None, None)
    res = _px(q[3], q[0], q[1], q[2], d.ravel(), q[4], q[5], nt=d.size, why=why)
    if res is None:
        return None
    k = sum(C[i][j[i]][5] for i in range(G))
    return res[0] + k, res[1][:n].reshape(G, T), res[2].reshape(d.shape), res[3]


def en(g, d, cap=None, net=None):
    """Enumerate every joint commitment and dispatch each one; the independent optimum."""
    g, d, net = ck(g, d, net)
    T = d.shape[1]
    C = [_cl(x, T, None if cap is None else cap[i]) for i, x in enumerate(g)]
    n = int(np.prod([len(y) for y in C]))
    if n > LIM[2]:
        raise ValueError(f"en is limited to {LIM[2]} joint commitments; this market has {n}")
    best = None
    for j in product(*[range(len(y)) for y in C]):
        res = _jt(g, d, net, C, j)
        if res is None:
            continue
        if best is None or res[0] < best[0] - 1e-9:
            u = np.array([C[i][j[i]][0] for i in range(len(g))])
            best = (res[0], np.where(np.abs(res[1]) < 1e-9, 0.0, res[1]), u)
    if best is None:
        raise ValueError("this demand did not clear [infeasible: no trajectory serves it]")
    return Sol(best[0], best[1], best[2], np.full(d.shape, np.nan), "enum")


def _hold(g, T, u, cap=None):
    """One column per unit, holding the given commitment fixed."""
    C = []
    for i, x in enumerate(g):
        v, w = _vw(x, u[i])
        r = _pl(x, T, u[i], v, w, None if cap is None else cap[i])
        if r is None:
            raise ValueError("the fixed commitment breaks a unit's own limits")
        C.append([(u[i], v, w, r[0], r[1], x.nl * u[i].sum() + x.su * v.sum())])
    return C


def lmp(g, d, s, cap=None, net=None):
    """Hold the cleared commitment fixed, re-dispatch, and read the balance duals as LMP."""
    g, d, net = ck(g, d, net)
    T = d.shape[1]
    u = np.atleast_2d(np.asarray(s.u, dtype=float))
    if u.shape != (len(g), T) or not np.isin(u, [0.0, 1.0]).all():
        raise ValueError("the fixed commitment must be one binary value per unit and period")
    why = []
    res = _jt(g, d, net, _hold(g, T, u, cap), [0] * len(g), why)
    if res is None:
        raise ValueError(f"the fixed commitment did not re-dispatch [{why[0]}]")
    return Sol(res[0], np.where(np.abs(res[1]) < 1e-9, 0.0, res[1]), u, res[2], res[3])


def hl(g, d, cap=None, net=None):
    """Convex hull program: each unit becomes the convex hull of its trajectory polytopes.

    Balas' union-of-polyhedra form is exact, so the balance dual is the exact convex hull
    price of the set it is given. Given pc's ceilings, that price is the AIC.
    """
    g, d, net = ck(g, d, net)
    G, T = len(g), d.shape[1]
    C = [_cl(x, T, None if cap is None else cap[i]) for i, x in enumerate(g)]
    K = sum(len(y) for y in C)
    if K * (T + 1) > LIM[1]:
        raise ValueError(f"hl is limited to {LIM[1]} variables; this market needs {K * (T + 1)}")
    o, n = [], 0
    for i in range(G):
        o.append([])
        for _ in C[i]:
            o[i].append(n)
            n += T + 1
    c = np.zeros(n)
    ri, ci, va = [], [], []
    ei, ec, ev = [], [], []
    m = 0
    for i in range(G):
        for j, (_, _, _, A, y, k) in enumerate(C[i]):
            q, r = np.nonzero(A)
            ri.extend(m + q)
            ci.extend(o[i][j] + r)
            va.extend(A[q, r])
            ri.extend(m + np.arange(len(A)))
            ci.extend([o[i][j] + T] * len(A))
            va.extend(-y)
            m += len(A)
            c[o[i][j] : o[i][j] + T] = g[i].c
            c[o[i][j] + T] = k
            ei.append(i)
            ec.append(o[i][j] + T)
            ev.append(1.0)
            ei.extend(G + net.bus[i] * T + np.arange(T))
            ec.extend(o[i][j] + np.arange(T))
            ev.extend(np.ones(T))
    q = _nw(net, T, n, csc_array((va, (ri, ci)), shape=(m, n)), np.zeros(m),
            csc_array((ev, (ei, ec)), shape=(G + net.nb * T, n)), c, np.zeros(n), None, None)
    why = []
    res = _px(q[3], q[0], q[1], q[2], np.r_[np.ones(G), d.ravel()], q[4], q[5], d.size, why)
    if res is None:
        raise ValueError(f"the convex hull program did not solve [{why[0]}]")
    p, u = np.zeros((G, T)), np.zeros((G, T))
    for i in range(G):
        for j, (q, _, _, _, _, _) in enumerate(C[i]):
            p[i] += res[1][o[i][j] : o[i][j] + T]
            u[i] += res[1][o[i][j] + T] * q
    p = np.where(np.abs(p) < 1e-9, 0.0, p)
    return Sol(res[0], p, u, res[2][G:].reshape(d.shape), res[3])


def _iv(x, T, s, e, cap=None):
    """One on-interval's dispatch polytope over the periods s..e, or None if infeasible.

    Built by fixing the single-interval schedule in the rows every other route reads, then
    keeping the columns that interval owns. A row left with no column of its own is a
    constant the interval must satisfy; a violated constant proves the interval infeasible.
    """
    u = np.zeros(T)
    u[s : e + 1] = 1.0
    r = _pl(x, T, u, *_vw(x, u), cap)
    if r is None:
        return None
    A, b = r[0][:, s : e + 1], r[1]
    m = np.abs(A).sum(1) > 0
    if (b[~m] < -tol).any():
        return None
    return A[m], b[m]


def _ar(x, T, cap=None):
    """Every arc of one unit's on/off graph: a node it leaves, a node it enters, an interval.

    A commitment trajectory is one source-to-T path, so this graph's flow polytope, carrying one
    dispatch polytope on each run arc, is the exact convex hull of the unit. The graph has
    O(T^2) arcs where _cl examines 2^T binary trajectories. Node t means the unit is off and free to
    start in period t; a run arc over s..e enters node e+1+md, which enforces the minimum
    down time between consecutive intervals.
    """
    y = U(x.lo, x.hi, x.c, x.nl, x.su, x.ru, x.rd, x.sr, x.dr, x.mu, x.md, 0, 0.0,
          max(x.mu, x.md))
    out = [(t, t + 1, 0, -1, None, None, 0.0) for t in range(T)]
    if x.u0:
        for e in range(-1, T):
            r = _iv(x, T, 0, e, cap)
            if r is not None:
                out.append((T + 1, min(T, e + 1 + x.md), 0, e, r[0], r[1], x.nl * (e + 1)))
    else:
        out.append((T + 1, min(T, max(0, x.md - x.e0)), 0, -1, None, None, 0.0))
    for s in range(T):
        for e in range(s, T):
            r = _iv(y, T, s, e, cap)
            if r is not None:
                out.append((s, min(T, e + 1 + x.md), s, e, r[0], r[1],
                            x.nl * (e - s + 1) + x.su))
    if not any(a[4] is not None or a[0] == T + 1 for a in out):
        raise ValueError("a unit has no feasible schedule")
    return out


def hc(g, d, cap=None, net=None):
    """The same convex hull as hl, using O(T^2) arcs instead of up to 2^T trajectories.

    Yu, Guan and Chen prove this per-unit form exact with ramping and minimum run times
    present, by a dynamic-programming argument. `hl` is retained as the independent check on
    that claim; the tests hold the two against each other.
    """
    g, d, net = ck(g, d, net)
    G, T = len(g), d.shape[1]
    C = [_ar(x, T, None if cap is None else cap[i]) for i, x in enumerate(g)]
    o, n, w = [], 0, T + 2
    for i in range(G):
        o.append([])
        for a in C[i]:
            o[i].append(n)
            n += (a[3] - a[2] + 1 if a[4] is not None else 0) + 1
    c = np.zeros(n)
    ri, ci, va = [], [], []
    ei, ec, ev = [], [], []
    m = 0
    for i in range(G):
        for j, (t, h, s, e, A, y, k) in enumerate(C[i]):
            z = o[i][j] + (e - s + 1 if A is not None else 0)
            c[z] = k
            if A is not None:
                q, r = np.nonzero(A)
                ri.extend(m + q)
                ci.extend(o[i][j] + r)
                va.extend(A[q, r])
                ri.extend(m + np.arange(len(A)))
                ci.extend([z] * len(A))
                va.extend(-y)
                m += len(A)
                c[o[i][j] : z] = g[i].c
                ei.extend(G * w + net.bus[i] * T + np.arange(s, e + 1))
                ec.extend(o[i][j] + np.arange(e - s + 1))
                ev.extend(np.ones(e - s + 1))
            for q, r in ((t, 1.0), (h, -1.0)):
                if q != T:
                    ei.append(i * w + q)
                    ec.append(z)
                    ev.append(r)
    be = np.zeros(G * w + d.size)
    for i in range(G):
        be[i * w + T + 1] = 1.0
    be[G * w :] = d.ravel()
    q = _nw(net, T, n, csc_array((va, (ri, ci)), shape=(m, n)), np.zeros(m),
            csc_array((ev, (ei, ec)), shape=(G * w + d.size, n)), c, np.zeros(n), None, None)
    why = []
    res = _px(q[3], q[0], q[1], q[2], be, q[4], q[5], d.size, why)
    if res is None:
        raise ValueError(f"the convex hull program did not solve [{why[0]}]")
    p, u = np.zeros((G, T)), np.zeros((G, T))
    for i in range(G):
        for j, (_, _, s, e, A, _, _) in enumerate(C[i]):
            if A is not None:
                p[i, s : e + 1] += res[1][o[i][j] : o[i][j] + e - s + 1]
                u[i, s : e + 1] += res[1][o[i][j] + e - s + 1]
    return Sol(res[0], np.where(np.abs(p) < 1e-9, 0.0, p), u,
               res[2][G * w :].reshape(d.shape), res[3])


def _om(g, T, pi, net, cap=None):
    """Maximum profit each unit can earn by self-scheduling at the given prices.

    One integer program per unit over that unit's own rows. It reads the feasible set
    algebraically; hl reads it through the trajectory columns. The two agree only if both
    descriptions are correct.

    What is returned is the solver's certified bound on that profit, not its incumbent. An
    incumbent can understate the best profit available, and qd subtracts these values, so
    an understated profit raises the reported dual above the true one and can carry it past
    the primal, which is exactly the weak-duality bound of Beck's Theorem 12.3. The bound
    errs the other way and is therefore the value a bound may be built on. At a closed gap
    the two are the same number.
    """
    om = np.zeros(len(g))
    for i, x in enumerate(g):
        A, b = _rw(x, T, None if cap is None else cap[i])
        Ae, be = _eq(x, T)
        lb, ub = _fx(x, T)
        res, _ag, _st = _mi(
            np.r_[x.c - pi[net.bus[i]], np.full(T, x.nl), np.full(T, x.su), np.zeros(T)],
            np.r_[np.zeros(T), np.ones(3 * T)],
            lb, ub, A, b, Ae, be, "a unit has no self-schedule")
        om[i] = -float(res.mip_dual_bound)
    return om


def _nq(net, T, pi):
    """Value of the network subproblem in the Lagrangian dual at one price.

    Relaxing the nodal balance rows leaves the flow columns behind. They carry no cost of
    their own but they are part of the minimisation, so the dual value is not complete
    without them. Dropping them minimises over a subset of the feasible set and returns a
    value above the true dual, which is what Theorem 12.3 of Beck forbids: on a congested
    network the reported bound then exceeds the primal optimum.

    Under "ntc" each exchange separates and is read off its capacity pair. Under "dc" the
    angles couple through the loop-flow condition and one linear program answers for them;
    only angle differences enter, so bus 0 is held at zero as it is in _nw. At a
    dual-optimal price this term is minus the congestion rent.
    """
    if not net.ln:
        return 0.0
    if net.fm == "ntc":
        return float(sum(np.minimum((pi[a] - pi[q]) * xc[0], (pi[a] - pi[q]) * xc[1]).sum()
                         for a, q, xc in net.ln))
    B = net.nb
    c = np.zeros(B * T)
    ri, ci, va, b = [], [], [], []
    for t in range(T):
        for a, q, x, lim in net.ln:
            c[a * T + t] -= (pi[q][t] - pi[a][t]) / x
            c[q * T + t] -= (pi[a][t] - pi[q][t]) / x
            for y in (1.0, -1.0):
                ri.extend([len(b)] * 2)
                ci.extend((a * T + t, q * T + t))
                va.extend([y / x, -y / x])
                b.append(float(lim))
    lo, hi = np.full(B * T, -np.inf), np.full(B * T, np.inf)
    lo[:T] = hi[:T] = 0.0
    res = linprog(c, A_ub=csc_array((va, (ri, ci)), shape=(len(b), B * T)),
                  b_ub=np.array(b), bounds=np.column_stack((lo, hi)))
    if not res.success:
        raise ValueError("the network admits no flow at this price")
    return float(res.fun)


def qd(g, d, pi, cap=None, net=None):
    """The unit-commitment Lagrangian dual value at one price.

    One best self-schedule problem per unit, plus the network subproblem the same
    relaxation leaves behind. Both are needed for the value to bound the clearing.

    Each unit subproblem contributes its certified bound rather than its incumbent, so the
    value returned is a valid lower bound on the integer clearing whatever the solver was
    able to prove, and not merely when every subproblem closed.
    """
    g, d, net = ck(g, d, net)
    pi = np.atleast_2d(np.asarray(pi, dtype=float))
    if pi.shape != d.shape or not np.isfinite(pi).all():
        raise ValueError("pi must hold one finite price per bus and period")
    T = d.shape[1]
    return float((pi * d).sum() - _om(g, T, pi, net, cap).sum() + _nq(net, T, pi))


def _bk(x, u):
    """Split one commitment into blocks of consecutive on periods: (first, last, starts here)."""
    out, t, T = [], 0, len(u)
    while t < T:
        if u[t] < 0.5:
            t += 1
            continue
        q = t
        while q + 1 < T and u[q + 1] > 0.5:
            q += 1
        out.append((t, q, t > 0 or x.u0 == 0))
        t = q + 1
    return out


def _pf(x, pi, p, t, q, a):
    """Profit of one commitment block: energy margin less no-load and any start-up cost."""
    return float((pi[t : q + 1] - x.c) @ p[t : q + 1] - x.nl * (q - t + 1) - x.su * a)


def pay(g, s, pi, net=None):
    """Profit, make-whole, lost opportunity and uplift, at any price, for a cleared market."""
    pi = np.atleast_2d(np.asarray(pi, dtype=float))
    T = pi.shape[1]
    g, _, net = ck(g, np.zeros(pi.shape), net)
    p = np.atleast_2d(np.asarray(s.p, dtype=float))
    u = np.atleast_2d(np.asarray(s.u, dtype=float))
    if p.shape != (len(g), T) or u.shape != p.shape:
        raise ValueError("a cleared market gives one output and one flag per unit and period")
    if not np.isin(u, [0.0, 1.0]).all() or not np.isfinite(p).all() or not np.isfinite(pi).all():
        raise ValueError("pay needs an integer commitment, finite output and finite prices")
    C = _hold(g, T, u)
    for i in range(len(g)):
        if (C[i][0][3] @ p[i] > C[i][0][4] + 1e-6).any():
            raise ValueError("the cleared market breaks a unit's own limits")
    r, mw = np.zeros(len(g)), np.zeros(len(g))
    for i, x in enumerate(g):
        for t, q, a in _bk(x, u[i]):
            z = _pf(x, pi[net.bus[i]], p[i], t, q, a)
            r[i] += z
            mw[i] += max(0.0, -z)
    up = _om(g, T, pi, net) - r
    return Pay(r, mw, up - mw, up)


def pc(g, d, s, ep=1e-6, L=None, net=None):
    """Cap a unit near its cleared output on each block that failed to cover its cost at LMP.

    L is the clearing's LMP solution. run already holds it and passes it in; called alone,
    pc solves it.
    """
    g, d, net = ck(g, d, net)
    if ep <= 0 or not np.isfinite(ep):
        raise ValueError("ep must be positive and finite")
    T = d.shape[1]
    L = lmp(g, d, s, net=net) if L is None else L
    p, u = np.atleast_2d(np.asarray(s.p, dtype=float)), np.atleast_2d(np.asarray(s.u, dtype=float))
    cap = np.array([np.full(T, x.hi) for x in g])
    for i, x in enumerate(g):
        for t, q, a in _bk(x, u[i]):
            if _pf(x, L.pi[net.bus[i]], p[i], t, q, a) < 0:
                cap[i, t : q + 1] = np.minimum(x.hi, p[i, t : q + 1] + ep)
        cap[i] = np.where(p[i] > tol, cap[i], 0.0)
    return cap


def run(g, d, ep=1e-6, net=None):
    """Clear the market once, then take every price in this file from that one clearing."""
    s = uc(g, d, net=net)
    L = lmp(g, d, s, net=net)
    cap = pc(g, d, s, ep, L, net)
    return Mkt(s, L, hc(g, d, net=net), rx(g, d, net=net), hc(g, d, cap, net),
               rx(g, d, cap, net))


def vr():
    """The solver stack behind every result here. HiGHS ships inside SciPy."""
    return {"python": sys.version.split()[0], "numpy": np.__version__,
            "scipy": scipy.__version__}


def mk_g(G, T, sd=7):
    """Synthetic market: cheap slow baseload through costly fast peakers, over a daily shape.

    Labelled synthetic. The bench tests its economics, not only its size: some unit must
    require a make-whole payment under LMP, or the market poses no pricing question.
    """
    a = np.random.default_rng(sd)
    g = []
    for i in range(G):
        q = i / max(1, G - 1)
        hi = round(float(a.uniform(0.8, 1.2)) * (300.0 - 250.0 * q), 2)
        lo = round(0.35 * (1.0 - q) * hi, 2)
        r = round(max(lo, (0.3 + 0.6 * q) * hi), 2)
        g.append(U(lo, hi, round(float(a.uniform(0.9, 1.1)) * (12.0 + 78.0 * q), 2),
                   nl=round(2.5 * (1.0 - q) * hi, 2), su=round(1200.0 * (1.0 - q) + 80.0, 2),
                   ru=r, rd=r, sr=max(0.5 * hi, lo), dr=max(0.5 * hi, lo),
                   mu=1 + int(2 * (1.0 - q)), md=1 + int(2 * (1.0 - q))))
    q = (1.0 - np.cos(np.arange(T) * 2.0 * np.pi / max(T, 2))) / 2.0
    return g, np.round(sum(x.hi for x in g) * (0.45 + 0.33 * q), 2)


def ex1():
    """Hua-Baldick Example 1: two units, one period, 35 MW. LMP is $50, exact CHP is $12."""
    return [U(10.0, 50.0, 50.0, su=100.0), U(50.0, 50.0, 10.0, su=100.0)], [35.0]


def ex2():
    """Hua-Baldick Example 2: ramping over three periods. Exact CHP is (60, 60, 65.6)."""
    return (
        [
            U(0.0, 100.0, 60.0, ru=120.0, rd=120.0, sr=120.0, dr=120.0),
            U(0.0, 100.0, 56.0, nl=600.0, ru=60.0, rd=60.0, sr=60.0, dr=60.0),
        ],
        [70.0, 100.0, 170.0],
    )


def ex4(lim=40.0):
    """The symmetric three-bus loop, checkable by hand.

    Equal reactances, cheap unit at bus 0, costly unit at bus 2, all load at bus 2. Two
    thirds of any bus-0 injection takes the direct line, so a 40 MW limit on it holds that
    unit to 60 MW. Bus 1 lies electrically midway and prices midway. Raising lim removes the
    congestion and leaves one price at every bus.
    """
    return (
        [U(0.0, 100.0, 10.0), U(0.0, 100.0, 50.0)],
        [[0.0], [0.0], [90.0]],
        Net([0, 2], ((0, 1, 1.0, 100.0), (1, 2, 1.0, 100.0), (0, 2, 1.0, lim)), 3),
    )


def ex5():
    """Two Norwegian bidding zones coupled by one exchange, over two periods.

    The capacity pair is the record electricity maps keeps for NO-NO1_NO-NO2, [-3500, 2200]:
    up to 3500 MW into NO-NO1 and up to 2200 MW out of it. The offers and the demand are
    labelled synthetic; no market publishes the offers behind a cleared price. Both bounds
    bind, one in each period, and the zonal prices separate in both.
    """
    return (
        [U(0.0, 5000.0, 40.0), U(0.0, 6000.0, 10.0), U(0.0, 3000.0, 90.0)],
        [[4000.0, 0.0], [0.0, 9000.0]],
        Net([0, 1, 1], ((0, 1, (-3500.0, 2200.0)),), 2, "ntc", ("NO-NO1", "NO-NO2")),
    )


def ex3():
    """The FERC talk's two-generator case: a start-up cost recoverable only in period three."""
    return (
        [
            U(0.0, 100.0, 10.0, ru=100.0, rd=100.0, sr=100.0, dr=100.0),
            U(20.0, 35.0, 50.0, nl=30.0, su=1000.0, ru=5.0, rd=5.0, sr=22.5, dr=35.0),
        ],
        [95.0, 100.0, 130.0],
    )
