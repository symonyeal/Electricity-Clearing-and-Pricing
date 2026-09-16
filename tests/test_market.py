# Historical correctness: alignment, transition days, settlement arithmetic, energy,
# information, fallbacks and exports. Every check reads the committed price fixtures,
# so the suite runs offline. Fixtures are rebuilt by tests/fixtures/build.py.

import csv
import gzip
import io
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np
import pytest

from market import fig, replay, report, scen
from market.cfg import Cf, read
from market.nyiso import BIN, HR, _utc, cov, frame, full, load
from models.storage import B, st

FX = "tests/fixtures/nyiso"
CF = Cf(root=FX, L=7, S=4, sp=12, lag=2, bt=(2, 6), bd=(6, 12),
        te=("2025-11-01", "2025-11-03"), rho=0.5)
LO, HI = "2025-10-25", "2025-11-03"


@pytest.fixture(scope="module")
def fr():
    return frame(CF.zone, LO, HI, FX, cache=False)


def _raw(k, day, zone):
    """The published rows for one day, read here without the loader."""
    m = day[:7].replace("-", "") + "01"
    with zipfile.ZipFile(f"{FX}/{k}/{m}{k}_zone_csv.zip") as z:
        t = z.read(f"{day.replace('-', '')}{k}_zone.csv").decode("utf-8-sig")
    return [r for r in csv.reader(io.StringIO(t)) if r and r[1].strip() == zone]


def test_transition_days():
    """A spring day has 23 hours, an autumn day 25, and the grid is contiguous."""
    for day, nh in (("2025-03-09", 23), ("2025-11-02", 25)):
        d = frame(CF.zone, day, day, FX, cache=False)[0]
        assert len(d.da) == nh and len(d.rt) == 12 * nh
        assert d.t1 - d.t0 == nh * HR
        assert len(d.hr) == len(d.rt) and d.hr[0] == 0 and d.hr[-1] == nh - 1
        assert np.all(np.diff(d.hr) >= 0) and np.all(np.bincount(d.hr) == 12)
        assert full(d)
    n = frame(CF.zone, "2025-11-01", "2025-11-03", FX, cache=False)
    assert [len(x.da) for x in n] == [24, 25, 24]
    assert n[0].t1 == n[1].t0 and n[1].t1 == n[2].t0


def test_repeated_hour():
    """The repeated local hour is two distinct hours; a missing local hour is refused."""
    a = _utc("11/02/2025 01:00", "damlbmp", None)
    b = _utc("11/02/2025 01:00", "damlbmp", a)
    assert b - a == HR
    with pytest.raises(ValueError, match="not a local time"):
        _utc("03/09/2025 02:30", "damlbmp", None)
    d = frame(CF.zone, "2025-11-02", "2025-11-02", FX, cache=False)[0]
    raw = [r[0] for r in _raw("damlbmp", "2025-11-02", CF.zone)]
    assert sum(x.endswith("01:00") for x in raw) == 2      # one local hour, twice
    assert len(d.da) == 25 and d.da[1] != d.da[2]


def test_subhourly_settlement():
    """Bin prices are the published postings weighted by the seconds each covers."""
    day = "2025-06-01"
    d = frame(CF.zone, day, day, FX, cache=False)[0]
    rows = _raw("realtime", day, CF.zone)
    t, p, last = [], [], None
    for r in rows:
        last = _utc(r[0].strip(), "realtime", last)
        t.append(last)
        p.append(float(r[3]))
    t, p = np.array(t), np.array(p)
    assert np.any(np.diff(t) != BIN)                      # the day reruns its dispatch
    a = np.r_[d.t0, t[:-1]]
    for j in (0, 132, 133, 250, len(d.rt) - 1):           # bins around the reruns
        b0, b1 = d.t0 + j * BIN, d.t0 + (j + 1) * BIN
        w = np.maximum(0, np.minimum(t, b1) - np.maximum(a, b0))
        assert w.sum() == pytest.approx(BIN)
        assert d.rt[j] == pytest.approx(float(w @ p) / BIN)


def test_hourly_offer_over_bins(fr):
    """One hourly position settles day ahead once, spread over the hour's bins."""
    d = fr[-1]
    q = np.full(len(d.da), 0.4)
    iv = {"q": np.repeat(q, 12), "pda": np.repeat(d.da, 12), "prt": d.rt,
          "c": np.zeros(len(d.rt)), "d": np.zeros(len(d.rt))}
    s = replay.settle(iv, CF)
    assert s["rda"].sum() == pytest.approx(float(d.da @ q))
    assert s["rrt"].sum() == pytest.approx(float(-0.4 * d.rt.sum() * BIN / HR))
    for h in range(len(d.da)):
        i = slice(12 * h, 12 * h + 12)
        assert s["rda"][i].sum() == pytest.approx(0.4 * d.da[h])


def test_cash_reconciliation(tmp_path, fr):
    """Totals are rebuilt from the exported intervals without the replay's arithmetic."""
    rn = replay.run(fr, CF, "neutral", *CF.te)
    m = report.export(rn, CF, None, tmp_path, ["test"])
    with gzip.open(tmp_path / "intervals.csv.gz", "rt") as f:
        rows = list(csv.DictReader(f))
    dt = BIN / HR
    net = sum((float(r["q"]) * float(r["pda"])
               + (float(r["d"]) - float(r["c"]) - float(r["q"])) * float(r["prt"])
               - (CF.kd + CF.fee) * (float(r["c"]) + float(r["d"]))) * dt for r in rows)
    assert net == pytest.approx(m["net"], abs=1e-3)   # the export carries six decimals
    assert m["gross"] - m["costs"] == pytest.approx(m["net"])
    with open(tmp_path / "daily.csv") as f:
        day = list(csv.DictReader(f))
    assert sum(float(r["net"]) for r in day) == pytest.approx(m["net"], abs=1e-3)
    assert [r["date"] for r in day] == [x["date"] for x in rn.dy]
    assert read(tmp_path / "config.toml") == CF
    assert json.loads((tmp_path / "metrics.json").read_text())["metrics"]["net"] \
        == pytest.approx(m["net"])


def test_energy_conserved_across_days(fr):
    """Stored energy follows one recursion and never restarts at a day boundary."""
    rn = replay.run(fr, CF, "neutral", *CF.te)
    iv, dt = rn.iv, BIN / HR
    e = np.r_[CF.e0, iv["e"][:-1]] + dt * (CF.ec * iv["c"] - iv["d"] / CF.ed)
    assert iv["e"] == pytest.approx(e, abs=1e-9)
    assert np.all(iv["e"] >= -1e-9) and np.all(iv["e"] <= CF.e + 1e-9)
    for a, b in zip(rn.dy, rn.dy[1:]):
        assert a["e1"] == pytest.approx(b["e0"], abs=1e-12)
    assert rn.dy[0]["e0"] == pytest.approx(CF.e0)
    assert np.all(np.diff(iv["t"]) == BIN)


def test_exclusive_modes_and_negative_prices():
    """Published negative prices are dispatched, and no interval does both at once."""
    f = frame(CF.zone, "2025-09-19", "2025-09-20", FX, cache=False)
    assert f[1].rt.min() < 0
    cf = CF.rep(L=1, S=1, te=("2025-09-20", "2025-09-20"))
    rn = replay.run(f, cf, "fore", *cf.te)
    assert np.max(np.minimum(rn.iv["c"], rn.iv["d"])) < 1e-9
    assert rn.iv["c"][rn.iv["prt"] < 0].sum() > 0


def test_no_leakage(fr):
    """Changing prices after a decision cannot change the decision that preceded it."""
    a = replay.run(fr, CF, "neutral", *CF.te)
    cut = 24 * 12                                     # the boundary of the second day
    alt = []
    for d in fr:
        r = d.rt.copy()
        if str(d.d) >= CF.te[0]:
            k = max(0, cut - 12 * 24 * (int(str(d.d)[-2:]) - 1))
            r[k:] = r[k:] * 3 + 500
        alt.append(d._replace(rt=r))
    b = replay.run(alt, CF, "neutral", *CF.te)
    for k in ("q", "c", "d", "e"):
        assert a.iv[k][:cut] == pytest.approx(b.iv[k][:cut], abs=1e-9)
    assert not np.allclose(a.iv["c"][cut:], b.iv["c"][cut:])
    mid = cut + 144                                   # and again inside the second day
    alt = [d._replace(rt=np.r_[d.rt[:144], d.rt[144:] * 3 + 500])
           if str(d.d) == "2025-11-02" else d for d in fr]
    c = replay.run(alt, CF, "neutral", *CF.te)
    for k in ("c", "d", "e"):
        assert a.iv[k][:mid] == pytest.approx(c.iv[k][:mid], abs=1e-9)


def test_hold_fallback(fr, monkeypatch):
    """A solve that will not finish is held, counted, and does not stop the replay."""
    n = {"i": 0}

    def bad(*a, **k):
        n["i"] += 1
        if n["i"] % 3:
            raise ValueError("storage did not solve to the requested gap: time limit")
        return st(*a, **k)

    monkeypatch.setattr(replay, "st", bad)
    rn = replay.run(fr, CF, "det", *CF.te)
    assert rn.dg["holds"] > 0
    assert rn.dg["solves"] == sum(r["solves"] for r in rn.dy)
    assert np.all(np.isfinite(rn.iv["e"]))
    m = report.metrics(rn, CF, B=200)
    assert m["holds"] == rn.dg["holds"]


def test_position_survives_a_deviation(fr):
    """The offer is planned from the target energy; an empty battery still settles it."""
    cf = CF.rep(e0=0.0)
    rn = replay.run(fr, cf, "det", *cf.te)
    assert np.any(rn.iv["q"] != 0)
    assert rn.dy[0]["e0"] == 0 and rn.dg["holds"] == 0
    assert np.all(np.isfinite([r["net"] for r in rn.dy]))
    assert np.all(rn.iv["e"] >= -1e-9) and np.all(rn.iv["e"] <= cf.e + 1e-9)
    day = rn.dy[0]
    assert day["rrt"] != 0 and day["why"] == "ok"


def test_time_limit_is_not_an_optimum(fr):
    """A limit too short to prove optimality raises instead of returning an incumbent."""
    d = fr[-1]
    b = B(CF.e, CF.c, CF.d, CF.ec, CF.ed, 2.0, 2.0, CF.kd, 1.0)
    rt = np.tile(d.rt[:96].reshape(24, 4).mean(axis=1), (8, 1)) * np.linspace(0.5, 2, 8)[:, None]
    with pytest.raises(ValueError, match="did not solve"):
        st(b, d.da[:24], rt, np.full(8, 1 / 8), None, 0.95, 0.5, None, 0.0, 1e-9)


def test_incomplete_day_is_recorded():
    """A day the archive did not supply is skipped, recorded, and holds its energy."""
    f = frame(CF.zone, "2025-10-25", "2025-11-03", FX, cache=False)
    g = [x._replace(rt=x.rt.copy()) for x in f]
    g[-2].rt[10:20] = np.nan
    assert not full(g[-2])
    cf = CF.rep(te=("2025-11-01", "2025-11-03"))
    rn = replay.run(g, cf, "det", *cf.te)
    bad = [r for r in rn.dy if r["why"] == "skip"]
    assert len(bad) == 1 and bad[0]["date"] == "2025-11-02"
    assert bad[0]["e0"] == pytest.approx(bad[0]["e1"])
    assert rn.dg["skipped"] == 1
    c = cov(load("realtime", CF.zone, "2025-11-01", "2025-11-01", FX, cache=False),
            "realtime")
    assert c["missing"] == 0 and c["intervals"] == 288


def test_missing_prices_settle_nothing(fr):
    """A skipped day contributes no cash, and no position may be priced against nan."""
    g = [x._replace(rt=x.rt.copy()) for x in fr]
    g[-2].rt[10:20] = np.nan
    rn = replay.run(g, CF, "det", *CF.te)
    i = next(k for k, r in enumerate(rn.dy) if r["why"] == "skip")
    assert rn.dy[i]["net"] == 0 and rn.dy[i]["rrt"] == 0
    assert np.all(np.isfinite([r["net"] for r in rn.dy]))
    assert report.metrics(rn, CF, B=200)["net"] == pytest.approx(
        sum(r["net"] for r in rn.dy))
    bad = {"q": np.ones(2), "pda": np.array([1.0, np.nan]), "prt": np.ones(2),
           "c": np.zeros(2), "d": np.zeros(2)}
    with pytest.raises(ValueError, match="did not supply"):
        replay.settle(bad, CF)


def test_tree_branches_without_merging():
    """A node is a set of paths: labels refine, never merge, and never name one path."""
    rng = np.random.default_rng(3)
    rt = rng.normal(50, 20, (8, 24))
    h = scen.tree(rt, (4, 12), 2)
    for t in range(1, 24):
        for k in np.unique(h[:, t]):
            assert np.unique(h[h[:, t] == k, t - 1]).size == 1
    for t in range(24):
        assert min(np.bincount(h[:, t])[np.unique(h[:, t])]) >= 2
    assert len(np.unique(h[:, -1])) == 4
    b = B(1, 1, 1, 1, 1, 0.5, 0.5)
    assert st(b, np.full(24, 50.0), rt, np.full(8, 1 / 8), h).gap == 0


def test_fit_reads_only_its_window(fr):
    """The fitted coefficient cannot move when a day after the window changes."""
    a = scen.fit(fr, "2025-10-25", "2025-11-01", CF)
    alt = [d._replace(rt=d.rt * 5 + 100) if str(d.d) > "2025-11-01" else d for d in fr]
    b = scen.fit(alt, "2025-10-25", "2025-11-01", CF)
    assert a.rho == pytest.approx(b.rho)
    assert 0 <= a.rho < 1 and a.days > 0 and a.pairs > 0


def test_scenarios_use_published_days_only(fr):
    """Scenario days end before bid close, and each carries one realized day's curves."""
    i = len(fr) - 1
    an = scen.analog(fr, i, CF, i - 2)
    assert len(an.ix) and max(an.ix) <= i - 2
    assert an.da.shape[1] == len(fr[i].da)
    for r, j in zip(an.da, an.ix):
        assert r[:len(fr[j].da)] == pytest.approx(fr[j].da[:len(r)])
    with pytest.raises(ValueError, match="whole bins"):
        scen.ag(np.zeros(288), 5)
    assert len(scen.al(np.arange(24), 25)) == 25
    assert scen.al(np.arange(24), 25)[-1] == 23


def test_idle_and_metric_identities(fr):
    """Idle earns exactly nothing, and the reported aggregates are consistent."""
    rn = replay.run(fr, CF, "idle", *CF.te)
    m = report.metrics(rn, CF, B=200)
    assert m["net"] == 0 and m["throughput"] == 0 and m["cycles"] == 0
    assert np.all(rn.iv["e"] == CF.e0)
    r2 = replay.run(fr, CF.rep(w=0.5), "cvar", *CF.te)
    m2 = report.metrics(r2, CF, B=200)
    assert m2["gross"] - m2["costs"] == pytest.approx(m2["net"])
    assert m2["throughput"] == pytest.approx(
        float((r2.iv["c"] + r2.iv["d"]).sum() * BIN / HR))
    assert m2["cycles"] == pytest.approx(m2["discharged"] / CF.ed / CF.e)
    assert m2["max_violation"] < 1e-9


def test_bootstrap_is_seeded_and_ordered():
    x = np.random.default_rng(0).normal(10, 3, 200)
    a = report.boot(x, 8, 500, 0)
    assert a == report.boot(x, 8, 500, 0)
    assert a[0] < x.sum() < a[1]
    assert report.boot(x, 8, 500, 1) != a


def test_configuration_refuses_unknown_keys(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text(report.toml(CF))
    assert read(p) == CF
    p.write_text(report.toml(CF) + "\nsurprise = 1\n")
    with pytest.raises(ValueError, match="unknown configuration"):
        read(p)


def test_figures_are_well_formed(tmp_path, fr):
    x = np.arange(10)
    fig.lines(tmp_path / "a.svg", [("one", x, np.arange(10.0)),
                                   ("two", x, -np.arange(10.0))], "t", "x", "y")
    fig.bars(tmp_path / "b.svg", ["Jan", "Feb"], [("one", np.array([1.0, -2]))], "t")
    d = fr[-1]
    fig.trace(tmp_path / "c.svg", d.t0 + BIN * np.arange(len(d.rt)), d.rt,
              np.repeat(d.da, 12), np.full(len(d.rt), 2.0), np.zeros(len(d.rt)), "t", "c")
    for n in ("a.svg", "b.svg", "c.svg"):
        r = ET.parse(tmp_path / n).getroot()
        assert r.tag.endswith("svg") and len(r) > 5
    assert "one" in (tmp_path / "a.svg").read_text()


def test_local_time_of_export(tmp_path, fr):
    """Exported stamps are the market's local time, including the repeated hour."""
    rn = replay.run(fr, CF, "idle", "2025-11-02", "2025-11-02")
    report.export(rn, CF, None, tmp_path, ["test"])
    with gzip.open(tmp_path / "intervals.csv.gz", "rt") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 300
    off = [r["local"][-6:] for r in rows]
    assert off[0] == "-04:00" and off[-1] == "-05:00"
    assert sum(r["local"][11:16] == "01:00" for r in rows) == 2
    assert Path(tmp_path / "monthly.csv").read_text().count("\n") == 2
