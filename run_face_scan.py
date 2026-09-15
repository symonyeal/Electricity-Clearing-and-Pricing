# Forced-walk scan of the price face. Source of the screen tables in README.md.
#
# LEGEND
#   SEED,BIG : the seeded market family and the two large timing markets
#   EP       : the AIC output relaxation
#   _rand    : the seeded market generator, shared with the parity test
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

import time
from contextlib import contextmanager

import numpy as np

import models.uc_price as m
from models.uc_price import hc, hl, mk_g, pc, ptol, uc
from tests.test_uc_price import _rand

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
        g, d = _rand(sd)
        try:
            s = uc(g, d)
        except ValueError:
            continue
        cap = pc(g, d, s, EP)
        for f in (hl, hc):
            for c in (None, cap):
                try:
                    v, dv = rt(f, g, d, c)
                except ValueError:
                    continue
                R.append((sd, f.__name__, c is not None, v, dv))
    return R


def bg(G, T):
    """One large market: screened seconds, forced seconds, and the price change."""
    g, d = mk_g(G, T)
    a, t1 = tm(lambda: hc(g, d).pi)
    with fw():
        b, t2 = tm(lambda: hc(g, d).pi)
    return t1, t2, float(np.abs(a - b).max())


if __name__ == "__main__":
    R = sc()
    sk = [r for r in R if r[3] is not None and r[3] <= ptol]
    wk = [r for r in R if r[3] is not None and r[3] > ptol]
    print("## Price-face screen\n")
    print("| Routes | Screen skipped | Screen walked | Probe not reached |")
    print("| ---: | ---: | ---: | ---: |")
    print("| %d | %d | %d | %d |" % (len(R), len(sk), len(wk), len(R) - len(sk) - len(wk)))
    print("\nLargest omitted change: $%.8f/MWh" % max((r[4] for r in sk), default=0.0))
    print("Largest kept change: $%.8f/MWh" % max((r[4] for r in wk), default=0.0))
    print("\n## Large markets\n")
    print("| Case | Payment and probe | Forced walk | Price change | Decision |")
    print("| --- | ---: | ---: | ---: | --- |")
    for G, T in BIG:
        t1, t2, dv = bg(G, T)
        print("| %d x %d | %.2fs | %.2fs | $%.8f/MWh | %s |"
              % (G, T, t1, t2, dv, "Skip" if dv <= ptol else "Retain"))
