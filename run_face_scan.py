# Forced-walk scan of the price face. Source of the screen tables in docs/PRICING.md, and,
# with the argument aic, of its AIC-ceiling table.
#
# LEGEND
#   SEED,BIG : the seeded market family and the two large timing markets
#   EP       : the AIC output relaxation
#   _clear   : one seeded market and its clearing, None where uc proves it infeasible
#   tm       : timer helper
#   rp,fw    : record the probe reading; force the walk by reporting movement
#   rt,sc,bg : one route, the whole seeded scan, one large market
#   sd       : one seed                 g,d : one market and its demand
#   s,cap    : integer clearing and the AIC output ceilings
#   f,c      : one hull route, and the ceilings it is given or None
#   a,b      : screened and forced price vectors
#   v        : the probe reading, None where the probe was never reached
#   dv       : the price difference the screen omitted, $/MWh
#   o,R      : the recorded readings, and one tuple per route
#   sk,wk    : the routes the screen skipped and the routes it walked
#   t1,t2    : screened and forced seconds
#   aic,E    : the AIC's sensitivity to its ceiling ep, and the ceilings tried

import sys
import time
from contextlib import contextmanager

import numpy as np

import models.uc_price as m
from models.uc_price import hc, hl, mk_g, pay, pc, ptol
from tests.test_uc_price import _clear

SEED, BIG, EP = range(141), [(48, 24), (96, 24)], 1e-6


@contextmanager
def rp(o):
    """Record what the probe returns, leaving the screen's decision alone."""
    f = m._fp

    def w(*a):
        v = f(*a)
        o.append(v)
        return v

    m._fp = w
    try:
        yield
    finally:
        m._fp = f


@contextmanager
def fw():
    """Report movement on every probe, so the per-period walk always runs."""
    f = m._fp
    m._fp = lambda *a: np.inf
    try:
        yield
    finally:
        m._fp = f


def tm(f, *a):
    """Return one function result and its elapsed seconds."""
    t = time.perf_counter()
    y = f(*a)
    return y, time.perf_counter() - t


def rt(f, g, d, c):
    """One route screened and forced: the probe reading and the omitted price change."""
    o = []
    with rp(o):
        a = f(g, d, c).pi
    with fw():
        b = f(g, d, c).pi
    return (o[0] if o else None), float(np.abs(a - b).max())


def sc():
    """Every capped and uncapped hl and hc route over the seeded family."""
    R = []
    for sd in SEED:
        q = _clear(sd)
        if q is None:
            continue
        g, d, s = q
        cap = pc(g, d, s, EP)
        for f in (hl, hc):
            for c in (None, cap):
                R.append((sd, f.__name__, c is not None, *rt(f, g, d, c)))
    return R


def aic():
    """Both hulls' AIC on every feasible market at four ceilings, against ep = 1e-6."""
    E, R = (1e-6, 1e-5, 1e-4, 1e-3), {}
    for sd in SEED:
        q = _clear(sd)
        if q is None:
            continue
        g, d, s = q
        for ep in E:
            cap = pc(g, d, s, ep)
            for f in (hc, hl):
                x = f(g, d, cap)
                R[sd, ep, f] = x.z, x.pi, float(pay(g, s, x.pi).up.sum())
    print("| ep | Routes | Largest value change | Largest price change, $/MWh | "
          "Largest uplift change | Routes whose price moves > 1e-4 |")
    print("| ---: | ---: | ---: | ---: | ---: | ---: |")
    for ep in E:
        k = [(sd, f) for sd, e, f in R if e == ep]
        dv = [[abs(R[sd, ep, f][0] - R[sd, E[0], f][0]),
               float(np.abs(R[sd, ep, f][1] - R[sd, E[0], f][1]).max()),
               abs(R[sd, ep, f][2] - R[sd, E[0], f][2])] for sd, f in k]
        m = np.max(dv, axis=0)
        print(f"| {ep:g} | {len(k)} | {m[0]:.4g} | {m[1]:.4g} | {m[2]:.4g} | "
              f"{sum(r[1] > 1e-4 for r in dv)} |")


def bg(G, T):
    """One large market: screened seconds, forced seconds, and the price change."""
    g, d = mk_g(G, T)
    a, t1 = tm(lambda: hc(g, d).pi)
    with fw():
        b, t2 = tm(lambda: hc(g, d).pi)
    return t1, t2, float(np.abs(a - b).max())


if __name__ == "__main__":
    if sys.argv[1:] == ["aic"]:
        aic()
        raise SystemExit
    R = sc()
    sk = [r for r in R if r[3] is not None and r[3] <= ptol]
    wk = [r for r in R if r[3] is not None and r[3] > ptol]
    print("## Price-face screen\n")
    print("| Routes | Screen skipped | Screen walked | Probe not reached |")
    print("| ---: | ---: | ---: | ---: |")
    print(f"| {len(R)} | {len(sk)} | {len(wk)} | {len(R) - len(sk) - len(wk)} |")
    print(f"\nLargest omitted change: ${max((r[4] for r in sk), default=0.0):.8f}/MWh")
    print(f"Largest kept change: ${max((r[4] for r in wk), default=0.0):.8f}/MWh")
    print("\n## Large markets\n")
    print("| Case | Payment and probe | Forced walk | Price change | Decision |")
    print("| --- | ---: | ---: | ---: | --- |")
    for G, T in BIG:
        t1, t2, dv = bg(G, T)
        print(f"| {G} x {T} | {t1:.2f}s | {t2:.2f}s | ${dv:.8f}/MWh | "
              f"{'Skip' if dv <= ptol else 'Retain'} |")
