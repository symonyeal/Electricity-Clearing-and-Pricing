# The historical experiment: fetch, validate, smoke, tune, select, run, report.
# Every command takes one configuration file and writes what it used beside its results.
#
# LEGEND
#   cf,ft      : configuration record and the fitted persistence coefficient
#   per        : train, valid or test date range from the configuration
#   pol        : policy name, or "all" for every baseline in one command
#   out        : output directory; one subdirectory per policy
#   grid       : the validation search, run one configuration at a time

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from market import fig, replay, report
from market.cfg import Cf, read
from market.nyiso import cov, fetch, frame, full, load, months
from market.scen import fit

NAME = {"idle": "no trading", "det": "deterministic forecast", "neutral": "risk neutral",
        "cvar": "CVaR", "fore": "perfect foresight"}


def per(cf, p):
    return {"train": cf.tr, "valid": cf.va, "test": cf.te}[p]


def span(cf, p):
    """The frame a replay needs: the evaluated range plus the longest lookback."""
    import datetime as dt
    a = dt.date.fromisoformat(per(cf, p)[0]) - dt.timedelta(days=int(cf.L) + 7)
    return max(str(a), cf.tr[0]), per(cf, p)[1]


def _fit(cf, p, log):
    """Refit before the evaluated period, on data that ends before it starts."""
    import datetime as dt
    hi = str(dt.date.fromisoformat(per(cf, p)[0]) - dt.timedelta(days=1))
    fr = frame(cf.zone, cf.tr[0], hi, cf.root, cf.cache)
    ft = fit(fr, cf.tr[0], hi, cf)
    log(f"fit rho={ft.rho:.4f} on {ft.days} days, {ft.lo} to {ft.hi}")
    return cf.rep(rho=ft.rho), ft


def cmd_fetch(cf, a, log):
    for k in ("damlbmp", "realtime"):
        for m in months(*per(cf, "train")[:1] + per(cf, "test")[1:]):
            log(f"{k} {m} {fetch(k, m, cf.root)}")


def cmd_validate(cf, a, log):
    """Report coverage before any result is computed from the archive."""
    out = {"zone": cf.zone, "reports": []}
    lo, hi = per(cf, "train")[0], per(cf, "test")[1]
    for k in ("damlbmp", "realtime"):
        out["reports"].append(cov(load(k, cf.zone, lo, hi, cf.root, cf.cache), k))
    fr = frame(cf.zone, lo, hi, cf.root, cf.cache)
    bad = [str(d.d) for d in fr if not full(d)]
    out |= {"days": len(fr), "incomplete": bad,
            "hours_per_day": sorted({len(d.da) for d in fr}),
            "bins_per_day": sorted({len(d.rt) for d in fr})}
    log(json.dumps(out, indent=1))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(out, indent=1) + "\n")
    return out


def one(cf, ft, pol, p, out, log):
    """Replay one policy over one period and export it."""
    fr = frame(cf.zone, *span(cf, p), cf.root, cf.cache)
    rn = replay.run(fr, cf, pol, *per(cf, p), log=log)
    m = report.export(rn, cf, ft, Path(out) / pol, sys.argv)
    log(f"{pol}: net {m['net']:,.0f} over {m['days']} days, {m['solves']} solves, "
        f"{m['solve_seconds']:.0f}s, max gap {m['max_gap']:.2g}, holds {m['holds']}")
    return rn, m


def cmd_run(cf, a, log):
    cf, ft = (cf, None) if a.no_fit else _fit(cf, a.period, log)
    pols = replay.POL if a.pol == "all" else (a.pol,)
    for pol in pols:
        one(cf, ft, pol, a.period, a.out, log)


def cmd_smoke(cf, a, log):
    """A short replay that exercises every path, including a transition day."""
    cf = cf.rep(rho=0.75, w=cf.w or 0.5)
    fr = frame(cf.zone, a.lo, a.hi, cf.root, cf.cache)
    for pol in replay.POL:
        rn = replay.run(fr, cf, pol, a.smoke_lo or a.lo, a.hi)
        m = report.metrics(rn, cf, B=200)
        log(f"{pol:8s} net {m['net']:12,.2f} days {m['days']} solves {m['solves']:5d} "
            f"holds {m['holds']} viol {m['max_violation']:.2g} cycles {m['cycles']:.2f}")


def cmd_tune(cf, a, log):
    """The validation search. Selection is by the rule stated in docs/MARKET.md."""
    out = Path(a.out)
    res = []
    for pol, L, S, w, al in json.loads(Path(a.grid).read_text()):
        c = cf.rep(L=L, S=S, w=w, al=al)
        c, ft = _fit(c, "valid", log)
        tag = f"{pol}-L{L}-S{S}-w{w}-a{al}"
        m = one(c, ft, pol, "valid", out / tag, log)[1]
        r = {"tag": tag, "policy": pol, "L": L, "S": S, "w": w, "al": al} | m
        res.append(r)
        (out / f"{tag}.json").write_text(json.dumps(r, indent=1) + "\n")
    return res


def cmd_select(cf, a, log):
    """Apply the selection rule in docs/MARKET.md to the validation runs."""
    rows = [json.loads(f.read_text()) for f in sorted(Path(a.dir).glob("*.json"))]
    if not rows:
        raise ValueError(f"no validation runs under {a.dir}")
    best = {}
    for pol in ("det", "neutral"):
        r = [x for x in rows if x["policy"] == pol]
        if r:
            best[pol] = max(r, key=lambda x: x["net"])
    cv = [x for x in rows if x["policy"] == "cvar"]
    if cv and "neutral" in best:
        ok = [x for x in cv if x["cvar"] < best["neutral"]["cvar"]]
        best["cvar"] = (max(ok, key=lambda x: x["net"]) if ok
                        else min(cv, key=lambda x: x["cvar"]))
        best["cvar"]["rule"] = "net among smaller tail" if ok else "smallest tail, rule not binding"
    out = {p: {k: b[k] for k in ("tag", "L", "S", "w", "al", "net", "cvar", "drawdown")}
           for p, b in best.items()}
    log(json.dumps(out, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1) + "\n")
    return out


def cmd_report(cf, a, log):
    """Tables and figures from exported runs. Reads results only, never re-solves."""
    d = Path(a.dir)
    runs = {}
    for p in replay.POL:
        if (d / p / "metrics.json").exists():
            runs[p] = json.loads((d / p / "metrics.json").read_text())
    if not runs:
        raise ValueError(f"no exported runs under {d}")
    dy = {p: _daily(d / p / "daily.csv") for p in runs}
    txt = [f"# Held-out results: {cf.zone}, {runs[next(iter(runs))]['metrics']['days']} days",
           "", "## Settlement", "",
           report.tbl([{**runs[p]["metrics"], "policy": NAME[p]} for p in runs],
                      ["Policy", "Day ahead", "Imbalance", "Costs", "Net", "2.5%",
                       "97.5%", "Worst day", "Drawdown", "Tail loss 5%", "Cycles"],
                      ["policy", "rda", "rrt", "costs", "net", "net_lo", "net_hi",
                       "worst_day", "drawdown", "cvar", "cycles"], {"cycles": 1}),
           "", "## Solver and data", "",
           report.tbl([{**runs[p]["metrics"], "policy": NAME[p]} for p in runs],
                      ["Policy", "Solves", "Seconds", "ms per solve", "Max gap",
                       "Holds", "Skipped", "Cold", "Max SOC error MWh"],
                      ["policy", "solves", "solve_seconds", "ms_per_solve", "max_gap",
                       "holds", "skipped", "cold", "max_violation"],
                      {"ms_per_solve": 1, "max_gap": lambda v: f"{v:.2g}",
                       "max_violation": lambda v: f"{v:.2g}"})]
    mo = sorted({r["date"][:7] for r in next(iter(dy.values()))})
    txt += ["", "## Monthly net settlement", "",
            report.tbl([{"month": m, **{p: sum(r["net"] for r in dy[p]
                                               if r["date"][:7] == m) for p in runs}}
                        for m in mo], ["Month"] + [NAME[p] for p in runs],
                       ["month"] + list(runs))]
    (d / "tables.md").write_text("\n".join(txt) + "\n")
    x = np.arange(len(next(iter(dy.values()))))
    fig.lines(d / "cumulative.svg",
              [(NAME[p], x, np.cumsum([r["net"] for r in dy[p]])) for p in runs],
              f"Cumulative net settlement, {cf.zone}, {cf.te[0]} to {cf.te[1]}",
              "day of the held-out year", "currency")
    fig.bars(d / "monthly.svg", [m[5:] for m in mo],
             [(NAME[p], np.array([sum(r["net"] for r in dy[p] if r["date"][:7] == m)
                                  for m in mo])) for p in runs],
             "Net settlement by month", "month", "currency")
    fig.lines(d / "tail.svg",
              [(NAME[p], np.linspace(0, 100, len(dy[p])),
                np.sort([r["net"] for r in dy[p]])) for p in runs],
              "Daily net settlement, sorted", "percentile of days", "currency")
    pol = "neutral" if "neutral" in runs else next(iter(runs))
    day = max(dy[pol], key=lambda r: abs(r["net"]))["date"]
    iv = _intervals(d / pol / "intervals.csv.gz", day)
    fig.trace(d / "trace.svg", iv["t"], iv["prt"], iv["pda"], iv["e"],
              iv["d"] - iv["c"], f"{NAME[pol]}, {day}, {cf.zone}",
              f"largest absolute daily net settlement of the {NAME[pol]} policy: "
              f"{max(dy[pol], key=lambda r: abs(r['net']))['net']:,.0f}")
    log(f"wrote {d}/tables.md and four figures")
    return txt


def _intervals(p, day):
    """One local day of an exported interval file, as arrays."""
    import gzip
    with gzip.open(p, "rt") as f:
        rows = [r.split(",") for r in f.read().splitlines()]
    k = rows[0]
    out = [r for r in rows[1:] if r[1][:10] == day]
    if not out:
        raise ValueError(f"{day} is not in {p}")
    return {c: np.array([float(r[i]) for r in out])
            for i, c in enumerate(k) if c != "local"}


def _daily(p):
    rows = [x.split(",") for x in Path(p).read_text().splitlines()]
    k = rows[0]
    return [{a: (b if a in ("date", "why") else float(b)) for a, b in zip(k, r)}
            for r in rows[1:]]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cmd", choices=["fetch", "validate", "smoke", "tune", "select",
                                   "run", "report"])
    p.add_argument("--cfg", default="config/nyiso.toml")
    p.add_argument("--pol", default="all")
    p.add_argument("--period", default="test", choices=["train", "valid", "test"])
    p.add_argument("--out", default="")
    p.add_argument("--dir", default="")
    p.add_argument("--grid", default="config/grid.json")
    p.add_argument("--lo", default="2025-10-20")
    p.add_argument("--smoke-lo", default="2025-11-01")
    p.add_argument("--hi", default="2025-11-03")
    p.add_argument("--set", action="append", default=[])
    p.add_argument("--no-fit", action="store_true")
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args(argv)
    cf = read(a.cfg) if Path(a.cfg).exists() else Cf()
    for s in a.set:
        k, v = s.split("=", 1)
        cf = cf.rep(**{k: type(getattr(cf, k))(v) if not isinstance(getattr(cf, k), tuple)
                       else tuple(json.loads(v))})
    def log(m):
        if not a.quiet:
            print(m, flush=True)
    return {"fetch": cmd_fetch, "validate": cmd_validate, "smoke": cmd_smoke,
            "tune": cmd_tune, "select": cmd_select, "run": cmd_run,
            "report": cmd_report}[a.cmd](cf, a, log)


if __name__ == "__main__":
    main()
