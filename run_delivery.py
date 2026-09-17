# The delivery-cap experiment's audit and its tables. Reads exported runs only, except
# for the targeted day probes, which re-solve one named day from its own exported
# configuration. Protocol and results: docs/results/delivery/README.md.
#
# LEGEND
#   cap,pol    : the deviation cap as it appears in a directory name, and the policy
#   d,cf,m     : one exported run, the configuration it used, its metrics
#   dy,v       : the daily export, and the interval export as arrays
#   off        : the contracted position's constant profit, removed from the raw ratio
#   seen       : every solve of one probed day, in order
#   SRC        : every source a replay's numbers depend on, fingerprinted beside them
#   KEEP       : the files published beside the study; interval files stay local
#   STOP       : the message a replay ends with when a capped dispatch is infeasible

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np

from market import replay
from market.cfg import read
from market.nyiso import frame
from market.replay import DTB
from market.report import tbl

SRC = ("models/storage.py", "market/bid.py", "market/cfg.py", "market/replay.py",
       "market/report.py", "market/scen.py", "market/nyiso.py", "run_market.py")
KEEP = ("metrics.json", "config.toml", "daily.csv", "monthly.csv")
STOP = re.compile(r"^ValueError: (\d{4}-\d{2}-\d{2}) step (\d+): (capped dispatch .*)$",
                  re.MULTILINE)
CAPS = (("None", "unbounded"), ("1.0", "1"), ("0.25", "0.25"), ("0.0", "0"))
POLS = (("det", "deterministic forecast"), ("neutral", "risk neutral"),
        ("fore", "perfect foresight"))
TIMING = {"policy", "solve_seconds", "ms_per_solve", "wall_seconds"}
RUNS = Path("results/delivery/nyc/2025")
DOCS = Path("docs/results/delivery/nyc/2025")
BASE = Path("docs/results")


def _cols(p):
    """The exported interval file as arrays, at the six decimals the export carries."""
    with gzip.open(p, "rt") as f:
        rows = list(csv.DictReader(f))
    return {k: np.array([float(r[k]) for r in rows])
            for k in ("pda", "prt", "q", "c", "d", "e")}


def _daily(d):
    return [{"date": r["date"], "net": float(r["net"]), "gap": float(r["gap"]),
             "e0": float(r["e0"])} for r in csv.DictReader((d / "daily.csv").open())]


def errors(d, cf, m):
    """Rebuild cash, stored energy and the cap from the interval export alone."""
    v = _cols(d / "intervals.csv.gz")
    pda, prt = np.nan_to_num(v["pda"]), np.nan_to_num(v["prt"])
    net = float((v["q"] * pda + (v["d"] - v["c"] - v["q"]) * prt
                 - (cf.kd + cf.fee) * (v["c"] + v["d"])).sum() * DTB)
    e, soc = float(cf.e0), 0.0
    for c, dc, x in zip(v["c"], v["d"], v["e"]):
        e = min(max(e + DTB * (cf.ec * c - dc / cf.ed), 0.0), cf.e)
        soc = max(soc, abs(e - x))
    dev = np.abs(v["d"] - v["c"] - v["q"])
    return {"cash_error_export_usd": abs(net - m["net"]),
            "soc_error_export_mwh": soc,
            "cap_error_export_mw": (0.0 if cf.cap is None
                                    else float(np.maximum(dev - cf.cap, 0).max()))}


def concentration(dy, m):
    """July, the year without it, and the ten best days, from the daily export."""
    jul = sum(r["net"] for r in dy if r["date"][:7] == "2025-07")
    return {"july_net": jul, "net_without_july": m["net"] - jul,
            "top10_net": sum(sorted((r["net"] for r in dy), reverse=True)[:10])}


def difference(m, pol):
    """An unbounded replay against the original study, metric by metric. Timing differs."""
    b = json.loads((BASE / pol / "metrics.json").read_text())["metrics"]
    return {k: m[k] - b[k] for k in sorted((set(m) & set(b)) - TIMING)
            if isinstance(b[k], (int, float)) and not isinstance(b[k], bool)}


def probe(cf, pol, day, e0):
    """Re-solve one day, recording every solve's raw ratio beside its absolute gap.

    The raw ratio is the solver's own relative gap on the variable objective, which
    excludes the contracted position's constant profit. Near a zero variable objective
    that ratio is large while the full score and its certified bound agree to rounding.
    """
    lo = max(cf.tr[0], str(dt.date.fromisoformat(day) - dt.timedelta(days=int(cf.L) + 7)))
    fr = frame(cf.zone, lo, day, cf.root, cf.cache)
    i = next(j for j, x in enumerate(fr) if str(x.d) == day)
    seen, real = [], replay.st

    def spy(b, da, rt, pr, h=None, a=0.95, w=0.0, q=None, gap=0.0, lim=None, cap=None):
        r = real(b, da, rt, pr, h, a, w, q, gap, lim, cap=cap)
        p, x = np.asarray(pr, float), np.asarray(rt, float)
        y = np.broadcast_to(np.atleast_2d(np.asarray(da, float)), x.shape)
        off = 0.0 if q is None else (1 - w) * float(
            p @ (b.dt * (y - x) @ np.asarray(q, float)))
        seen.append({"variable_score": r.z - off, "periods": x.shape[1], "z": r.z,
                     "ub": r.ub, "abs_gap": r.ub - r.z, "raw_gap": r.gap})
        return r

    replay.st = spy
    try:
        replay.day(fr, i, cf, pol, e0)
    finally:
        replay.st = real
    return {"cap": cf.cap, "policy": pol, "day": day,
            "worst_raw": max(seen, key=lambda s: s["raw_gap"]),
            "above_relative_target": [s for s in seen if s["raw_gap"] > cf.gap],
            "max_absolute_gap": max(abs(s["abs_gap"]) for s in seen)}


def exported(cap, pol):
    """One finished run: its directory, or why the replay stopped without one.

    A replay that a finite cap made infeasible has no result to read. That is the
    outcome decision 52 specifies, so it is recorded rather than treated as a
    missing file; any other nonzero exit is refused.
    """
    d, mark = RUNS / f"cap-{cap}" / pol, RUNS / f"cap-{cap}" / f"{pol}.exit"
    if not mark.exists():
        sys.exit(f"{d} has not finished: no exit status recorded")
    rc = mark.read_text().strip()
    if rc == "0":
        if not (d / "metrics.json").exists():
            sys.exit(f"{d} exited zero without exporting")
        return d, None
    m = STOP.search((RUNS / f"cap-{cap}" / f"{pol}.log").read_text())
    if not m:
        sys.exit(f"{d} exited {rc} for a reason that is not a delivery infeasibility")
    if (d / "metrics.json").exists():
        sys.exit(f"{d} exited {rc} but left an export behind")
    return d, {"exit": int(rc), "date": m[1], "step": int(m[2]), "reason": m[3]}


def cmd_audit(log):
    sha = {f: hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in SRC}
    out, probes = [], []
    for cap, _ in CAPS:
        for pol, _ in POLS:
            d, stop = exported(cap, pol)
            cmd = json.loads((RUNS / f"cap-{cap}" / f"{pol}.launch.json").read_text())
            if stop:
                out.append({"cap": None if cap == "None" else float(cap), "policy": pol,
                            "completed": False, "terminated": stop,
                            "source_sha256": sha, "command": cmd["command"]})
                log(f"cap {cap:>5} {pol:8} stopped on {stop['date']} step {stop['step']}: "
                    f"no completed result")
                continue
            cf = read(d / "config.toml")
            m = json.loads((d / "metrics.json").read_text())["metrics"]
            dy = _daily(d)
            e = {"cap": cf.cap, "policy": pol, "completed": True} | errors(d, cf, m)
            e["baseline_difference"] = difference(m, pol) if cf.cap is None else None
            e["gap_probes"] = [probe(cf, pol, r["date"], r["e0"])
                               for r in dy if r["gap"] > cf.gap]
            probes += e["gap_probes"]
            e |= concentration(dy, m)
            e |= {"source_sha256": sha, "command": cmd["command"]}
            out.append(e)
            pub = DOCS / f"cap-{cap}" / pol
            pub.mkdir(parents=True, exist_ok=True)
            for f in KEEP:
                shutil.copyfile(d / f, pub / f)
            log(f"cap {cap:>5} {pol:8} cash {e['cash_error_export_usd']:.1e} "
                f"soc {e['soc_error_export_mwh']:.1e} "
                f"cap {e['cap_error_export_mw']:.1e} probes {len(e['gap_probes'])}")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "audit.json").write_text(json.dumps(out, indent=1) + "\n")
    (RUNS / "gap-probes.json").write_text(json.dumps(probes, indent=1) + "\n")
    done = sum(e["completed"] for e in out)
    log(f"published {done} of {len(out)} settings under {DOCS}, with audit.json and "
        f"{RUNS}/gap-probes.json")
    return out


def rows(keys):
    """One row per policy and cap, with the change from that policy's unbounded net.

    A replay the cap made infeasible has no numbers. Its row is kept and marked, so a
    reader counts twelve settings rather than silently reading eleven.
    """
    stopped = {(e["policy"], e["cap"]): e["terminated"]
               for e in json.loads((DOCS / "audit.json").read_text())
               if not e.get("completed", True)}
    out = []
    for pol, name in POLS:
        base = None
        for cap, label in CAPS:
            s = stopped.get((pol, None if cap == "None" else float(cap)))
            if s:
                out.append({k: "\u2014" for k in keys}
                           | {"policy": name, "cap": label,
                              "net": f"infeasible {s['date']}"})
                continue
            m = json.loads((DOCS / f"cap-{cap}" / pol / "metrics.json").read_text())
            m = m["metrics"]
            base = m["net"] if base is None else base
            out.append(m | {"policy": name, "cap": label, "change": m["net"] - base,
                            "share": 100 * (m["net"] - base) / base})
    return out


def cmd_tables(log):
    g = lambda v: v if isinstance(v, str) else f"{v:.2g}"
    r = rows(["net", "change", "share", "net_lo", "net_hi", "worst_day", "drawdown",
              "cvar", "da_mwh", "imb_mwh", "max_deviation", "throughput", "cycles",
              "arb", "spread", "solves", "solve_seconds", "max_gap", "holds", "coarse",
              "max_violation", "max_cap_violation"])
    txt = [tbl(r, ["Policy", "Cap MW", "Net", "Change", "Change %", "2.5%", "97.5%",
                   "Worst day", "Drawdown", "Tail loss 5%"],
               ["policy", "cap", "net", "change", "share", "net_lo", "net_hi",
                "worst_day", "drawdown", "cvar"], {"share": 1}),
           "",
           tbl(r, ["Policy", "Cap MW", "Day-ahead MWh", "Imbalance MWh",
                   "Max deviation MW", "Grid MWh", "Cycles", "Delivered energy",
                   "Spread"],
               ["policy", "cap", "da_mwh", "imb_mwh", "max_deviation", "throughput",
                "cycles", "arb", "spread"], {"cycles": 1, "max_deviation": g}),
           "",
           tbl(r, ["Policy", "Cap MW", "Solves", "Seconds", "Max raw gap", "Holds",
                   "Coarse", "Max SOC error MWh", "Max cap excess MW"],
               ["policy", "cap", "solves", "solve_seconds", "max_gap", "holds", "coarse",
                "max_violation", "max_cap_violation"],
               {"max_gap": g, "max_violation": g, "max_cap_violation": g})]
    log("\n".join(txt))
    return txt


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cmd", choices=["audit", "tables"])
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args(argv)
    def log(m):
        if not a.quiet:
            print(m, flush=True)
    return {"audit": cmd_audit, "tables": cmd_tables}[a.cmd](log)


if __name__ == "__main__":
    main()
