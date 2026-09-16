# NYISO zonal price archives: download, parse, align to UTC and validate coverage.
# The published files are the only price source; nothing here models or fills a price.
# Provenance and market rules: docs/MARKET.md.
#
# LEGEND
#   k        : "damlbmp" hourly day-ahead, "realtime" five-minute real-time LBMP
#   zone     : published zone name, e.g. "N.Y.C."      root : archive directory
#   Px       : t interval-beginning UTC seconds, p $/MWh, cv posted seconds in interval
#   BIN,HR   : real-time settlement bin and hour, in seconds
#   TZ       : eastern prevailing time, the time zone the files are stamped in
#   a,b      : inclusive first and last local date, "YYYY-MM-DD"
#   fold     : second pass of a repeated local hour on the autumn transition day
#   cov      : coverage report; expected, present, missing and partial intervals
#   gaps     : postings whose interval ran longer than a bin, with the seconds involved
#   Day      : one local day; hourly day-ahead, binned real-time, hour index per bin
#   frame    : the local-day dataset every policy and every statistic reads

import csv
import datetime as dt
import io
import urllib.request
import zipfile
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo

import numpy as np

URL = "http://mis.nyiso.com/public/csv/{k}/{m}{k}_zone_csv.zip"
TZ = ZoneInfo("America/New_York")
BIN, HR = 300, 3600
STEP = {"damlbmp": HR, "realtime": BIN}
FMT = {"damlbmp": "%m/%d/%Y %H:%M", "realtime": "%m/%d/%Y %H:%M:%S"}


class Px(NamedTuple):
    t: np.ndarray
    p: np.ndarray
    cv: np.ndarray


class Day(NamedTuple):
    d: dt.date
    t0: int
    t1: int
    da: np.ndarray
    rt: np.ndarray
    cv: np.ndarray
    hr: np.ndarray


def days(a, b):
    """Local dates from a to b inclusive."""
    a, b = (dt.date.fromisoformat(x) for x in (a, b))
    if b < a:
        raise ValueError("the last date precedes the first")
    return [a + dt.timedelta(days=i) for i in range((b - a).days + 1)]


def months(a, b):
    """Archive month keys, "YYYYMM01", covering the date range."""
    return sorted({d.strftime("%Y%m01") for d in days(a, b)})


def fetch(k, m, root):
    """Download one monthly archive unless it is already present and readable."""
    f = Path(root) / k / f"{m}{k}_zone_csv.zip"
    if f.exists() and f.stat().st_size:
        try:
            with zipfile.ZipFile(f) as z:
                if z.testzip() is None:
                    return f
        except zipfile.BadZipFile:
            pass
    f.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL.format(k=k, m=m), timeout=180) as r:
        raw = r.read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:      # refuse a truncated or HTML reply
        if z.testzip() is not None or not z.namelist():
            raise ValueError(f"{k} {m} archive did not unpack")
    f.write_bytes(raw)
    return f


def _utc(s, k, last):
    """Local stamp to UTC seconds. A repeated hour is the second pass; a gap is refused."""
    d = dt.datetime.strptime(s, FMT[k]).replace(tzinfo=TZ)
    u = int(d.timestamp())
    if last is not None and u <= last:
        u = int(d.replace(fold=1).timestamp())
    if dt.datetime.fromtimestamp(u, TZ).replace(tzinfo=None) != d.replace(tzinfo=None):
        raise ValueError(f"{s} is not a local time that exists")
    return u


def _day(z, n, k, zone):
    """One day file: interval-ending UTC seconds and prices for one zone, in file order."""
    with z.open(n) as f:
        rows = list(csv.reader(io.TextIOWrapper(f, "utf-8-sig")))
    t, p, last = [], [], None
    for r in rows[1:]:
        if len(r) < 4 or r[1].strip() != zone:
            continue
        last = _utc(r[0].strip(), k, last)
        t.append(last)
        p.append(float(r[3]))
    if not t:
        raise ValueError(f"{n} has no rows for {zone}")
    return np.array(t, dtype=np.int64), np.array(p, dtype=float)


def _bin(t, p, t0, t1):
    """Duration-weight postings into fixed bins. Real-time stamps end their interval."""
    n = (t1 - t0) // BIN
    w = np.zeros(n)
    s = np.zeros(n)
    a = np.r_[t0, t[:-1]]
    for i in range(len(t)):
        x, y = max(a[i], t0), min(t[i], t1)
        while x < y:
            j = (x - t0) // BIN
            e = min(y, t0 + (j + 1) * BIN)
            w[j] += e - x
            s[j] += (e - x) * p[i]
            x = e
    return np.where(w > 0, s / np.maximum(w, 1), np.nan), w


def _month(k, zone, m, root, cache):
    """One archive month on its published grid, cached as arrays after the first parse."""
    c = Path(root) / "cache" / f"{zone.replace(' ', '_')}_{k}_{m}.npz"
    if cache and c.exists():
        with np.load(c) as f:
            return Px(f["t"], f["p"], f["cv"])
    f = Path(root) / k / f"{m}{k}_zone_csv.zip"
    z = zipfile.ZipFile(f) if f.exists() else None
    n0 = z.namelist() if z else []
    t, p, cv = [], [], []
    d = dt.date.fromisoformat(f"{m[:4]}-{m[4:6]}-01")
    while d.strftime("%Y%m01") == m:
        n = d.strftime(f"%Y%m%d{k}_zone.csv")
        t0 = int(dt.datetime.combine(d, dt.time(), TZ).timestamp())
        t1 = int(dt.datetime.combine(d + dt.timedelta(days=1), dt.time(), TZ).timestamp())
        g = np.arange(t0, t1, STEP[k], dtype=np.int64)
        if n in n0:
            u, v = _day(z, n, k, zone)
            if k == "realtime":
                x, w = _bin(u, v, t0, t1)
            else:
                x, w = np.full(len(g), np.nan), np.zeros(len(g))
                j = np.searchsorted(g, u)             # hourly stamps begin their interval
                ok = (j < len(g)) & (g[np.minimum(j, len(g) - 1)] == u)
                x[j[ok]], w[j[ok]] = v[ok], HR
        else:
            x, w = np.full(len(g), np.nan), np.zeros(len(g))
        t.append(g)
        p.append(x)
        cv.append(w)
        d += dt.timedelta(days=1)
    if z:
        z.close()
    r = Px(np.concatenate(t), np.concatenate(p), np.concatenate(cv))
    if cache:
        c.parent.mkdir(parents=True, exist_ok=True)
        np.savez(c, t=r.t, p=r.p, cv=r.cv)
    return r


def load(k, zone, a, b, root="data/nyiso", cache=True):
    """Prices for a local date range on the published time grid, aligned to UTC.

    Day-ahead rows are hourly and interval-beginning. Real-time postings end their
    interval, are irregular when the dispatch reruns, and are weighted by the seconds
    each covers inside its bin. Missing intervals stay nan and are reported by cov.
    """
    if k not in STEP:
        raise ValueError(f"unknown report {k}")
    d = days(a, b)
    t0 = int(dt.datetime.combine(d[0], dt.time(), TZ).timestamp())
    t1 = int(dt.datetime.combine(d[-1] + dt.timedelta(days=1), dt.time(), TZ).timestamp())
    r = [_month(k, zone, m, root, cache) for m in months(a, b)]
    t = np.concatenate([x.t for x in r])
    i = (t >= t0) & (t < t1)
    return Px(t[i], np.concatenate([x.p for x in r])[i],
              np.concatenate([x.cv for x in r])[i])


def gaps(zone, a, b, root="data/nyiso", tol=60):
    """Postings whose interval ran longer than a bin, read from the published files.

    A real-time price applies from the previous posting to its own stamp, so a longer
    interval is a longer-lived price, not a filled one. This reports where that happened
    and for how long, because the binned grid cannot show it.
    """
    root = Path(root)
    out, tot = [], 0.0
    for m in months(a, b):
        f = root / "realtime" / f"{m}realtime_zone_csv.zip"
        if not f.exists():
            continue
        with zipfile.ZipFile(f) as z:
            names = set(z.namelist())
            for d in days(a, b):
                n = d.strftime("%Y%m%drealtime_zone.csv")
                if d.strftime("%Y%m01") != m or n not in names:
                    continue
                t0 = int(dt.datetime.combine(d, dt.time(), TZ).timestamp())
                u, _ = _day(z, n, "realtime", zone)
                w = np.diff(np.r_[t0, u])
                i = np.flatnonzero(w > BIN + tol)
                if len(i):
                    out.append({"date": str(d), "postings": len(i),
                                "longest": int(w[i].max()),
                                "seconds": float((w[i] - BIN).sum())})
                    tot += out[-1]["seconds"]
    return {"tolerance": tol, "days": len(out), "seconds": tot, "worst": out[:40]}


def cov(px, k):
    """Coverage of the loaded grid: what the archive supplied and what it did not."""
    n = len(px.t)
    full = float(STEP[k])
    miss = int(np.sum(px.cv <= 0))
    part = int(np.sum((px.cv > 0) & (px.cv < full - 1e-9)))
    fin = np.isfinite(px.p)
    return {"report": k, "intervals": n, "present": n - miss, "missing": miss,
            "partial": part, "seconds": float(px.cv.sum()),
            "min": float(px.p[fin].min()) if fin.any() else float("nan"),
            "max": float(px.p[fin].max()) if fin.any() else float("nan"),
            "first": int(px.t[0]), "last": int(px.t[-1])}


def frame(zone, a, b, root="data/nyiso", cache=True):
    """The local-day dataset. A transition day carries 23 or 25 hours, as published."""
    da, rt = (load(k, zone, a, b, root, cache) for k in ("damlbmp", "realtime"))
    out = []
    for d in days(a, b):
        t0 = int(dt.datetime.combine(d, dt.time(), TZ).timestamp())
        t1 = int(dt.datetime.combine(d + dt.timedelta(days=1), dt.time(), TZ).timestamp())
        i, j = (da.t >= t0) & (da.t < t1), (rt.t >= t0) & (rt.t < t1)
        out.append(Day(d, t0, t1, da.p[i], rt.p[j], rt.cv[j], (rt.t[j] - t0) // HR))
    return out


def full(d):
    """A day is tradable only if every published interval it needs is present."""
    return bool(np.isfinite(d.da).all() and np.isfinite(d.rt).all()
                and np.all(d.cv >= BIN - 1e-9) and len(d.da) == (d.t1 - d.t0) // HR
                and len(d.rt) == (d.t1 - d.t0) // BIN)
