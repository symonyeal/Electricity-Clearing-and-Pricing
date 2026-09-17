# Chronological replay: decide, freeze, execute one action, settle, carry energy forward.
# No decision reads a price stamped at or after its own decision time, except foresight,
# which is labelled optimistic. Protocol and market assumptions: docs/MARKET.md.
#
# LEGEND
#   pol        : idle, det, neutral, cvar or fore (perfect foresight, optimistic)
#   fr,i,lo,hi : local-day frame, the day index, and the replayed date range
#   q,qs       : frozen hourly position, and the same position per decision step
#   k,ns,sp    : decision step, steps in the day, settlement bins in a step
#   e,tg       : energy carried across days in MWh, and the reachable end-of-day target
#   rda,rrt    : day-ahead settlement and real-time imbalance settlement, currency
#   dg,dy,iv   : run diagnostics, one row per day, one row per settlement bin
#   why        : ok, gap, hold, skip, cold or fail; recorded, never silently dropped
#   fail       : why a solve missed its tolerance: limit, infeasible, unbounded, other
#   ref        : the ensemble price the position was chosen against, per hour
#   z,ub       : the offer solve's risk score and its certified upper bound

import time
from typing import NamedTuple

import numpy as np

from market.bid import accept, charge, qual
from market.nyiso import BIN, full
from market.scen import Sc, ag, analog, da_scen, rt_scen
from models.storage import B, st

POL = ("idle", "det", "neutral", "cvar", "fore")
DTB = BIN / 3600


class Rn(NamedTuple):
    iv: dict
    dy: list
    dg: dict


def _w(cf, pol):
    return float(cf.w) if pol == "cvar" else 0.0


def _bat(cf, e0, ef, dt):
    """The battery the policy optimizes against.

    Throughput cost is kd + fee and deliberately not cf.tar. The tariff is charged in
    settle, after the schedule has been chosen, so a run at tar > 0 takes the schedule it
    would have taken at tar = 0 and pays the charge afterwards: an ex-post stress test of
    an existing policy rather than a policy that was told the rate. A large enough rate can
    therefore make the selected trade lose money. That boundary is deliberate and is stated
    in docs/MARKET.md; pricing the tariff into the objective is open work, item 2 of
    docs/DECISIONS.md, because it changes which trades a policy takes and so changes every
    result it touches.
    """
    return B(cf.e, cf.c, cf.d, cf.ec, cf.ed, e0, ef, cf.kd + cf.fee, dt)


def _tg(cf, e, n, dt):
    """The reachable end-of-day energy nearest the common target, so a solve exists."""
    hi = min(cf.e, e + n * dt * cf.c * cf.ec)
    lo = max(0.0, e - n * dt * cf.d / cf.ed)
    return float(np.clip(cf.ef, lo, hi))


def _one(x):
    """A single-scenario set: one path, one node, everything shared."""
    da, rt = np.atleast_2d(x[0]), np.atleast_2d(x[1])
    return Sc(da, rt, np.ones(1), np.zeros(rt.shape, dtype=int), np.zeros(0, dtype=int))


def _sc_da(fr, i, an, cf, pol):
    if pol == "fore":
        return _one((fr[i].da, ag(fr[i].rt, 12)))
    return da_scen(fr, i, an, cf, det=pol == "det")


def _sc_rt(fr, i, k, an, cf, pol):
    d = fr[i]
    if pol == "fore":
        return _one((ag(np.repeat(d.da, 12), cf.sp)[k:], ag(d.rt, cf.sp)[k:]))
    return rt_scen(fr, i, k, an, d.rt, cf, det=pol == "det")


def _tag(msg):
    """Name why a solve did not reach its tolerance, briefly enough for a table."""
    if not msg:
        return ""
    m = msg.lower()
    return ("limit" if "limit" in m else
            "infeasible" if "infeasible" in m else
            "unbounded" if "unbounded" in m else "other")


def _solve(b, s, cf, q, w):
    """The requested solve, then a coarse retry, then hold. Every outcome is recorded."""
    t, msg = time.perf_counter(), ""
    for g, lim, why in ((cf.gap, cf.lim, "ok"), (max(cf.gap, 1e-2), 2 * cf.lim, "gap")):
        try:
            r = st(b, s.da, s.rt, s.pr, s.h, cf.al, w, q, g, lim, cap=cf.cap)
            return r, why, time.perf_counter() - t, msg
        except ValueError as err:
            msg = str(err)
    return None, "hold", time.perf_counter() - t, msg


def _offer(fr, i, an, cf, pol):
    """The hourly position chosen at bid close on the day before, then frozen."""
    n = len(fr[i].da)
    if pol == "idle":
        return np.zeros(n), "ok", 0.0, 0.0, 0.0, 0.0
    if an is None and pol != "fore":
        return np.zeros(n), "cold", 0.0, 0.0, 0.0, 0.0
    s = _sc_da(fr, i, an, cf, pol)
    b = _bat(cf, cf.ef, cf.ef, 1.0)
    r, why, sec, _ = _solve(b, s, cf, None, _w(cf, pol))
    if r is None:
        return np.zeros(n), "fail", sec, 0.0, 0.0, 0.0
    q = r.q
    if cf.bk > 0:
        da = np.atleast_2d(np.asarray(s.da, dtype=float))
        w = np.asarray(s.pr, dtype=float)
        ref = np.average(da, axis=0, weights=w) if da.shape[0] > 1 else da.ravel()
        q = accept(q, ref, np.asarray(fr[i].da, dtype=float), cf.bk, cf.bs)
    return q, why, sec, r.gap, r.z, r.ub


def day(fr, i, cf, pol, e):
    """Replay one local day from energy e. Returns the day's rows and closing energy."""
    d = fr[i]
    nb, nh = len(d.rt), len(d.da)
    ns = nb // cf.sp
    z = np.zeros(nb)
    row = {"date": str(d.d), "hours": nh, "bins": nb, "e0": e, "why": "ok",
           "solves": 0, "sec": 0.0, "gap": 0.0, "hold": 0, "coarse": 0, "viol": 0.0,
           "analogs": 0, "cold": 0, "z": 0.0, "ub": 0.0, "fail": ""}
    iv = {"t": d.t0 + BIN * np.arange(nb), "pda": np.repeat(d.da, 12), "prt": d.rt,
          "q": z.copy(), "c": z.copy(), "d": z.copy(), "e": z.copy()}
    if not full(d):
        row["why"] = "skip"
        iv["e"][:] = e
        return iv, row, e
    an = analog(fr, i, cf, i - 2) if pol not in ("idle", "fore") else None
    row["analogs"] = 0 if an is None else len(an.ix)
    q, why, sec, gp, z, ub = _offer(fr, i, an, cf, pol)
    row["why"], row["sec"], row["gap"], row["solves"] = why, sec, gp, 1
    row["z"], row["ub"] = z, ub
    row["cold"] = int(why in ("cold", "fail"))
    qs, iv["q"] = ag(np.repeat(q, 12), cf.sp), np.repeat(q, 12)
    if pol == "idle" or (an is None and pol != "fore"):
        iv["e"][:] = e                       # no position and no dispatch; energy holds
        return iv, row, e
    for k in range(ns):
        tg = _tg(cf, e, ns - k, cf.sp * DTB)
        b = _bat(cf, min(max(e, 0.0), cf.e), tg, cf.sp * DTB)
        r, w, sec, msg = _solve(b, _sc_rt(fr, i, k, an, cf, pol), cf, qs[k:], _w(cf, pol))
        if r is None and cf.cap is not None:
            raise ValueError(f"{d.d} step {k}: capped dispatch failed; hold may violate "
                             f"delivery: {msg}")
        row["fail"] = row["fail"] or _tag(msg)
        row["solves"] += 1
        row["sec"] += sec
        row["hold"] += w == "hold"
        row["coarse"] += w == "gap"
        c, dc = (0.0, 0.0) if r is None else (float(r.c[1, 0]), float(r.d[1, 0]))
        row["gap"] = max(row["gap"], 0.0 if r is None else r.gap)
        for j in range(k * cf.sp, (k + 1) * cf.sp):
            e += DTB * (cf.ec * c - dc / cf.ed)
            row["viol"] = max(row["viol"], -e, e - cf.e)
            iv["c"][j], iv["d"][j], iv["e"][j] = c, dc, e
            e = min(max(e, 0.0), cf.e)
    return iv, row, e


def settle(iv, cf):
    """Interval cash flows. The hourly position settles day ahead; the rest is imbalance.

    An interval the archive did not supply settles nothing, and carrying a position or a
    dispatch into one is refused rather than priced at an invented number.
    """
    g = iv["d"] - iv["c"]
    ok = np.isfinite(iv["pda"]) & np.isfinite(iv["prt"])
    if np.any(~ok & ((g != 0) | (iv["q"] != 0))):
        raise ValueError("a position fell in an interval the archive did not supply")
    da, rt = np.nan_to_num(iv["pda"]), np.nan_to_num(iv["prt"])
    return {"rda": iv["q"] * da * DTB, "rrt": (g - iv["q"]) * rt * DTB,
            "deg": cf.kd * (iv["c"] + iv["d"]) * DTB,
            "fee": (cf.fee * (iv["c"] + iv["d"]) + charge(iv["c"], iv["d"], cf.tar)) * DTB}


def run(fr, cf, pol, lo, hi, log=None):
    """Replay a date range in order. Energy is never reset at a day boundary.

    The market-interface parameters are checked here rather than where they are first
    used. A negative spread or tariff would otherwise raise inside the first day's offer
    or its settlement, after a solve that can run for seconds, and a negative step count
    would not raise at all: accept reads any k below one as "take the position in full",
    which silently turns the curve off instead of refusing the configuration.

    A step count is a count, so it is required to be a whole finite number. A nan compares
    false against every threshold and passes a bare sign test, then turns the curve off or
    fails deep inside curve's own array construction, neither of which names what was
    wrong with the configuration.
    """
    if not float(cf.bk).is_integer() or cf.bk < 0:
        raise ValueError("an offer curve needs a whole, non-negative number of steps")
    if not np.isfinite(cf.bs) or cf.bs < 0:
        raise ValueError("the bid spread must be finite and non-negative")
    if not np.isfinite(cf.tar) or cf.tar < 0:
        raise ValueError("a tariff rate must be finite and non-negative")
    ok, msg = qual(max(cf.c, cf.d), cf.e, cf.qmin, cf.qdur)
    if not ok:
        raise ValueError(f"this resource does not qualify: {msg}")
    if cf.cap is not None and (not np.isfinite(cf.cap) or cf.cap < 0):
        raise ValueError("deviation cap must be finite and nonnegative, or None")
    if pol not in POL:
        raise ValueError(f"unknown policy {pol}")
    if pol == "cvar" and not cf.w:
        raise ValueError("the CVaR policy needs a positive risk weight")
    ix = [i for i, d in enumerate(fr) if lo <= str(d.d) <= hi]
    if not ix:
        raise ValueError("no days in the replay range")
    e, iv, dy = float(cf.e0), [], []
    t0 = time.perf_counter()
    for i in ix:
        a, row, e = day(fr, i, cf, pol, e)
        s = settle(a, cf)
        a |= s
        row |= {k: float(v.sum()) for k, v in s.items()}
        row |= {"e1": e, "ch": float(a["c"].sum() * DTB), "dis": float(a["d"].sum() * DTB),
                "net": row["rda"] + row["rrt"] - row["deg"] - row["fee"]}
        iv.append(a)
        dy.append(row)
        if log and (row["date"][8:10] == "01" or i == ix[-1]):
            log(f"{pol} {row['date']} e={e:.2f} net={sum(r['net'] for r in dy):.0f}")
    iv = {k: np.concatenate([a[k] for a in iv]) for k in iv[0]}
    dg = {"policy": pol, "days": len(dy), "first": dy[0]["date"], "last": dy[-1]["date"],
          "failures": {t: sum(r["fail"] == t for r in dy)
                       for t in sorted({r["fail"] for r in dy} - {""})},
          "skipped": sum(r["why"] == "skip" for r in dy),
          "cold": sum(r["cold"] for r in dy),
          "solves": sum(r["solves"] for r in dy),
          "holds": sum(r["hold"] for r in dy),
          "coarse": sum(r["coarse"] for r in dy),
          "solve_seconds": sum(r["sec"] for r in dy),
          "max_gap": max(r["gap"] for r in dy),
          "max_violation": max(r["viol"] for r in dy),
          "wall_seconds": time.perf_counter() - t0}
    return Rn(iv, dy, dg)
