# Price scenarios drawn from realized days, and the one coefficient fitted to history.
# Nothing here optimizes; nothing here reads a price stamped at or after the decision.
# Method, information timeline and tuning protocol: docs/MARKET.md.
#
# LEGEND
#   fr,i       : local-day frame and the index of the day being decided
#   j0         : last analog day whose own data is complete before the decision
#   cd,ix      : candidate analog days, and the scenarios chosen from them
#   hrs        : the local clock hour and fold of each hour of one day, as 2*hour + fold
#   al,ag      : put an analog day on the target day's clock hours; average bins into steps
#   An         : per-day analog matrices: hourly day-ahead, hourly and step real time
#   Sc         : scenarios: da, rt, probabilities, information labels, analog days
#   h,br,mn    : information labels, branch offsets in periods, smallest node to split
#   rho,res    : fitted hourly persistence of the residual, and the observed residual
#   MRES       : bins of observed residual averaged before it is carried forward
#   Ft         : the fit record: coefficient, days used, window, and pair count

import datetime as dt
from typing import NamedTuple

import numpy as np

from market.nyiso import BIN, HR, TZ, full

MRES = 3


class An(NamedTuple):
    ix: np.ndarray
    da: np.ndarray
    rh: np.ndarray
    rs: np.ndarray
    bn: np.ndarray


class Sc(NamedTuple):
    da: np.ndarray
    rt: np.ndarray
    pr: np.ndarray
    h: np.ndarray
    ix: np.ndarray


class Ft(NamedTuple):
    rho: float
    days: int
    pairs: int
    lo: str
    hi: str


def hrs(d):
    """The local clock hour and fold of each hour of one day, as 2*hour + fold.

    On a normal day the local hour is the elapsed hour since midnight. On the two days a
    year that are not normal it is not: the spring day has no local 02, and the autumn day
    settles local 01 twice, once at each offset. The labels are read from the zone rather
    than assumed, so a change to the rule carries into them.
    """
    n = (d.t1 - d.t0) // HR
    if n == 24:
        return np.arange(24) * 2
    q = (dt.datetime.fromtimestamp(d.t0 + i * HR, TZ) for i in range(n))
    return np.array([x.hour * 2 + x.fold for x in q])


def al(x, s, t):
    """Put an analog day's prices on the target day's local clock hours.

    What an analog supplies is a shape that belongs to the clock: the morning ramp and the
    evening peak happen at a local hour, not at an elapsed offset from midnight. Aligning
    by array position agrees with that on every pair of ordinary days and parts from it on
    the two transition days, where it slides every hour after the transition by one and
    then drops or repeats an end the transition never touched. Matching the local label
    instead leaves each of the analog's hours on the hour it was observed at.

    The autumn target settles local 01 twice and an ordinary analog holds that hour once,
    so the one observation serves both passes; the two differ in their offset from UTC and
    not in where they sit in the local day. The spring target has no local 02 and does not
    ask for one. An analog that is itself a transition day may lack an hour the target
    wants, and then supplies its nearest, which is the adjacent hour.
    """
    hs, ht = hrs(s), hrs(t)
    k = len(x) // max(len(hs), 1)
    if len(hs) * k != len(x):
        raise ValueError("an analog day's periods must divide evenly into its hours")
    ix = {int(h): i for i, h in enumerate(hs)}
    hk = np.array(sorted(ix))
    j = []
    for h in ht:
        h = int(h)
        q = ix.get(h, ix.get(h ^ 1))
        j.append(ix[int(hk[np.argmin(np.abs(hk - h))])] if q is None else q)
    return np.asarray(x).reshape(len(hs), k)[j].ravel()


def ag(x, sp):
    """Mean price over each decision step. A step spans sp settlement bins."""
    if sp < 1 or 12 % sp:
        raise ValueError("a decision step must divide the hour into whole bins")
    return x.reshape(-1, sp).mean(axis=1)


def cand(fr, i, L, j0):
    """Complete days of the same type inside the lookback window, published by then."""
    return [j for j in range(max(0, i - L), min(j0, i - 1) + 1)
            if full(fr[j]) and (fr[j].d.weekday() < 5) == (fr[i].d.weekday() < 5)]


def pick(fr, cd, S):
    """Span the level distribution: quantile-spaced days by mean real-time price."""
    if S < 1:
        raise ValueError("at least one scenario is required")
    if len(cd) <= S:
        return np.array(sorted(cd), dtype=int)
    m = np.array([fr[j].rt.mean() for j in cd])
    o = np.array(sorted(cd), dtype=int)[np.argsort(m, kind="stable")]
    return np.array(sorted(set(o[np.round(np.linspace(0, len(o) - 1, S)).astype(int)])))


def analog(fr, i, cf, j0):
    """The scenario days for day i, with their prices on day i's grid."""
    ix = pick(fr, cand(fr, i, cf.L, j0), cf.S)
    if not len(ix):
        return None
    da = np.array([al(fr[j].da, fr[j], fr[i]) for j in ix])
    bn = np.array([al(fr[j].rt, fr[j], fr[i]) for j in ix])
    return An(ix, da, np.array([ag(x, 12) for x in bn]),
              np.array([ag(x, cf.sp) for x in bn]), bn)


def _split(x, g, mn):
    """Halve a node at the median of its members' mean price over the coming segment."""
    if len(g) < 2 * mn:
        return [g]
    o = g[np.argsort(x[g].mean(axis=1), kind="stable")]
    return [np.sort(o[:len(g) // 2]), np.sort(o[len(g) // 2:])]


def tree(rt, br, mn):
    """Label the information a decision may use: a node is a group of paths, not a path.

    Before the first branch every path shares one node. At each branch the node splits
    at the median of its members' mean price over the segment that follows, so a node
    names the set of paths still indistinguishable from each other, and never merges.
    """
    S, T = np.shape(rt)
    h = np.zeros((S, T), dtype=int)
    cut = [0] + sorted({int(b) for b in br if 0 < b < T}) + [T]
    g, n = [np.arange(S)], 0
    for k in range(len(cut) - 1):
        a, b = cut[k], cut[k + 1]
        if k:
            g = [y for x in g for y in _split(rt[:, a:b], x, mn)]
        for x in g:
            h[x, a:b] = n
            n += 1
    return h


def _adj(an, obs, k, cf):
    """Decay the latest observed residual against the analog mean over the horizon."""
    n = an.rs.shape[1]
    b = k * cf.sp - cf.lag - 1
    if b < 0 or not cf.rho:
        return np.zeros(n)
    m = min(MRES, b + 1)
    res = float(np.mean(obs[b - m + 1:b + 1] - an.bn[:, b - m + 1:b + 1].mean(axis=0)))
    hrs = (np.arange(n) * cf.sp - b) * BIN / 3600
    return np.where(hrs > 0, cf.rho ** np.maximum(hrs, 0), 0.0) * res


def rt_scen(fr, i, k, an, obs, cf, det=False):
    """Scenarios for the remaining steps of day i, decided at the start of step k.

    obs holds this day's realized bins; only bins settled before the decision are read.
    """
    a = _adj(an, obs, k, cf)[k:]
    rt = an.rs[:, k:] + a
    da = ag(np.repeat(fr[i].da, 12), cf.sp)[k:]
    if det:
        rt = rt.mean(axis=0, keepdims=True)
    S = len(rt)
    pr = np.full(S, 1 / S)
    return Sc(np.tile(da, (S, 1)), rt, pr, tree(rt, cf.bt, cf.mn), an.ix)


def da_scen(fr, i, an, cf, det=False):
    """Scenarios for the hourly offer decided at bid close on the day before day i.

    Both prices are unknown then: each scenario carries one realized day's day-ahead
    and real-time curves together, so their joint shape is the observed one.
    """
    da, rt = an.da, an.rh
    if det:
        da, rt = da.mean(axis=0, keepdims=True), rt.mean(axis=0, keepdims=True)
    S = len(rt)
    pr = np.full(S, 1 / S)
    return Sc(da, rt, pr, tree(rt, cf.bd, cf.mn), an.ix)


def fit(fr, a, b, cf):
    """Hourly persistence of the residual against the analog mean, on complete days.

    This is the only coefficient estimated from data. It is fitted on a closed window
    and then held fixed; docs/MARKET.md records the retraining schedule.
    """
    a, b = (dt.date.fromisoformat(x) for x in (a, b))
    num = den = 0.0
    n = p = 0
    for i, d in enumerate(fr):
        if not (a <= d.d <= b and full(d)):
            continue
        an = analog(fr, i, cf, i - 1)
        if an is None or len(an.ix) < 2:
            continue
        r = ag(d.rt, 12) - an.rh.mean(axis=0)
        num += float(r[:-1] @ r[1:])
        den += float(r[:-1] @ r[:-1])
        n, p = n + 1, p + len(r) - 1
    if den <= 0:
        raise ValueError("no residual variation to fit")
    return Ft(float(np.clip(num / den, 0.0, 0.99)), n, p, str(a), str(b))
