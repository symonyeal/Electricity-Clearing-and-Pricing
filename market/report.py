# Measured results: settlement, costs, risk, diagnostics, exports and tables.
# Every number here is computed from the replay's own interval rows.
#
# LEGEND
#   rn,cf,ft   : a replay result, its configuration, the fitted coefficient record
#   net,cum    : daily net settlement and its running total
#   dd         : largest peak-to-trough fall of the running total
#   cvar,var   : tail loss of the daily net at confidence al
#   bl,B,seed  : moving block length, bootstrap replications, generator seed
#   cyc,thr    : equivalent full cycles and grid throughput in MWh
#   da_mwh     : day-ahead volume; imb_mwh : volume that settled as imbalance instead
#   arb,spread : the exact split of net into delivered energy and the position's
#                day-ahead minus real-time spread; the two sum to net by identity
#   iv,dy,mo   : interval, daily and monthly rows

import datetime as dt
import gzip
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import scipy

from market.nyiso import TZ
from market.replay import DTB
from models.storage import cvar

IVC = ("t", "pda", "prt", "q", "c", "d", "e", "rda", "rrt", "deg", "fee")
DYC = ("date", "why", "fail", "hours", "bins", "analogs", "e0", "e1", "ch", "dis",
       "rda", "rrt", "deg", "fee", "net", "z", "ub", "gap", "solves", "sec",
       "hold", "coarse", "cold", "viol")


def boot(x, bl, B, seed):
    """Moving block bootstrap of the total: blocks keep the day-to-day dependence."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 2:
        return float("nan"), float("nan")
    bl = int(min(max(1, bl), n))
    g = np.random.default_rng(seed)
    k = int(np.ceil(n / bl))
    s = g.integers(0, n - bl + 1, size=(B, k))
    ix = (s[:, :, None] + np.arange(bl)[None, None, :]).reshape(B, -1)[:, :n]
    tot = x[ix].sum(axis=1)
    return float(np.percentile(tot, 2.5)), float(np.percentile(tot, 97.5))


def metrics(rn, cf, seed=0, B=10000):
    """Settlement, costs, risk, throughput and solver diagnostics for one replay."""
    dy = rn.dy
    net = np.array([r["net"] for r in dy])
    cum = np.cumsum(net)
    al = 0.95
    n = len(net)
    bl = max(1, int(np.ceil(n ** (1 / 3))))
    lo, hi = boot(net, bl, B, seed)
    thr = float((rn.iv["c"] + rn.iv["d"]).sum() * DTB)
    dis = float(rn.iv["d"].sum() * DTB)
    g = rn.iv["d"] - rn.iv["c"]
    m = {"policy": rn.dg["policy"], "days": n,
         "traded": int(sum(r["why"] not in ("skip", "cold", "fail") for r in dy)),
         "skipped": rn.dg["skipped"], "cold": rn.dg["cold"],
         "rda": float(sum(r["rda"] for r in dy)), "rrt": float(sum(r["rrt"] for r in dy)),
         "deg": float(sum(r["deg"] for r in dy)), "fee": float(sum(r["fee"] for r in dy))}
    m["gross"] = m["rda"] + m["rrt"]
    m["costs"] = m["deg"] + m["fee"]
    m["net"] = m["gross"] - m["costs"]
    m |= {"net_lo": lo, "net_hi": hi, "block": bl, "reps": B, "seed": seed,
          "best_day": float(net.max()), "worst_day": float(net.min()),
          "top_day_share": float(net.max() / m["net"]) if m["net"] else float("nan"),
          "drawdown": float(np.max(np.maximum.accumulate(np.r_[0, cum]) - np.r_[0, cum])),
          "var": float(np.percentile(net, 100 * (1 - al))),
          "cvar": cvar(net, np.full(n, 1 / n), al) if n > 1 else float("nan"),
          "throughput": thr, "discharged": dis, "cycles": dis / cf.ed / cf.e,
          "da_mwh": float(np.abs(rn.iv["q"]).sum() * DTB),
          "imb_mwh": float(np.abs(g - rn.iv["q"]).sum() * DTB),
          "max_deviation": float(np.abs(g - rn.iv["q"]).max()),
          "max_cap_violation": (0.0 if cf.cap is None else
                                float(np.maximum(np.abs(g - rn.iv["q"]) - cf.cap, 0).max())),
          "arb": float((g * np.nan_to_num(rn.iv["prt"])
                        - (cf.kd + cf.fee) * (rn.iv["c"] + rn.iv["d"])).sum() * DTB),
          "spread": float((rn.iv["q"] * (np.nan_to_num(rn.iv["pda"])
                                         - np.nan_to_num(rn.iv["prt"]))).sum() * DTB),
          "e_open": dy[0]["e0"], "e_close": dy[-1]["e1"],
          "solves": rn.dg["solves"], "solve_seconds": rn.dg["solve_seconds"],
          "ms_per_solve": 1e3 * rn.dg["solve_seconds"] / max(rn.dg["solves"], 1),
          "max_gap": rn.dg["max_gap"], "holds": rn.dg["holds"],
          "coarse": rn.dg["coarse"], "max_violation": rn.dg["max_violation"],
          "wall_seconds": rn.dg["wall_seconds"]}
    return m


def monthly(rn):
    """Net settlement by calendar month, in the market's local time."""
    mo = {}
    for r in rn.dy:
        k = r["date"][:7]
        a = mo.setdefault(k, {"month": k, "days": 0, "rda": 0.0, "rrt": 0.0,
                              "deg": 0.0, "fee": 0.0, "net": 0.0})
        a["days"] += 1
        for f in ("rda", "rrt", "deg", "fee", "net"):
            a[f] += r[f]
    return [mo[k] for k in sorted(mo)]


def env(argv=None):
    """What produced the result: versions, revision, platform and command."""
    try:
        rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                                    text=True, check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        rev, dirty = "", False
    return {"utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "revision": rev, "dirty": dirty, "python": platform.python_version(),
            "numpy": np.__version__, "scipy": scipy.__version__,
            "platform": platform.platform(), "command": argv or []}


def toml(cf):
    """The configuration as it was used, in the format read back by market.cfg."""
    out = []
    for k, v in cf._asdict().items():
        if v is None:
            out.append(f"# {k} omitted: unbounded")
        elif isinstance(v, str):
            out.append(f'{k} = "{v}"')
        elif isinstance(v, tuple):
            out.append(f"{k} = [{', '.join(json.dumps(x) for x in v)}]")
        else:
            out.append(f"{k} = {json.dumps(v)}")
    return "\n".join(out) + "\n"


def export(rn, cf, ft, out, argv=None, seed=0):
    """Write one replay: intervals, days, months, metrics, configuration, environment."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    iv = rn.iv
    with gzip.open(out / "intervals.csv.gz", "wt", newline="") as f:
        f.write("t,local," + ",".join(IVC[1:]) + "\n")
        for i in range(len(iv["t"])):
            t = int(iv["t"][i])
            f.write(f"{t},{dt.datetime.fromtimestamp(t, TZ).isoformat()},"
                    + ",".join(f"{iv[c][i]:.6f}" for c in IVC[1:]) + "\n")
    with open(out / "daily.csv", "w", newline="") as f:
        f.write(",".join(DYC) + "\n")
        f.writelines(",".join(f"{r[c]:.6f}" if isinstance(r[c], float) else str(r[c])
                             for c in DYC) + "\n" for r in rn.dy)
    mo = monthly(rn)
    with open(out / "monthly.csv", "w", newline="") as f:
        f.write(",".join(mo[0]) + "\n")
        f.writelines(",".join(f"{v:.6f}" if isinstance(v, float) else str(v)
                             for v in r.values()) + "\n" for r in mo)
    m = metrics(rn, cf, seed)
    (out / "metrics.json").write_text(json.dumps(
        {"metrics": m, "diagnostics": rn.dg, "fit": ft._asdict() if ft else None,
         "environment": env(argv)}, indent=1) + "\n")
    (out / "config.toml").write_text(toml(cf))
    return m


def cell(v, f):
    """One table entry: a string as it stands, a number to the decimals this column wants."""
    if isinstance(v, str):
        return v
    return f(v) if callable(f) else f"{v:,.{f}f}"


def tbl(rows, head, keys, dec=None):
    """One markdown table; every number is formatted once, here."""
    dec = dec or {}
    out = ["| " + " | ".join(head) + " |",
           "| " + " | ".join("---" if i == 0 else "---:" for i in range(len(head))) + " |"]
    out += ["| " + " | ".join(cell(r[k], dec.get(k, 0)) for k in keys) + " |" for r in rows]
    return "\n".join(out)
