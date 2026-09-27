# Direct hull against generated master. Source of the tables in docs/DW.md.
#
# LEGEND
#   PUB,SIZ,BIG : published cases; synthetic sizes run by default; the two large sizes
#   tm          : timer
#   rp          : record, at every selected dual, the most negative certified reduced cost
#   pub,fam,sz  : the published table, the seeded family, one synthetic size
#   rts         : the pglib-uc RTS-GMLC instance through cgp
#   _mn,orc     : one oracle problem by enumeration; every oracle call against it
#   TE,SC       : the enumeration LPs' tolerances; the offer-cost scales measured
#   a,e         : one cost scale, and the oracle's bound errors at it
#   g,d,net,cap : units, demand, network, AIC ceilings     s : the clearing
#   a,b,h       : hc, cg and hl results                    P : payments at one price
#   o           : recorded selected-dual violations        R : one row per route
#   t0..t3      : seconds for uc, hc, cg, hl
#   dz,dp       : relative value difference and largest price difference against hc

import argparse
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

import models.dw as W
from models.pglib_uc import ld
from models.uc_price import _cl, ex1, ex2, ex3, ex4, ex5, hc, hl, mk_g, pay, pc, uc, vr
from run_bench import sz as hs
from tests.test_uc_price import _clear, _rand

TE = {"presolve": False, "primal_feasibility_tolerance": 1e-10,
      "dual_feasibility_tolerance": 1e-10}

PUB = [("ex1", ex1), ("ex2", ex2), ("ex3", ex3), ("ex4", ex4), ("ex5", ex5)]
SIZ = [(6, 4), (8, 6), (10, 8), (12, 10), (8, 14), (10, 16), (24, 16)]
BIG = [(48, 24), (96, 24)]
SC = (1e-3, 1.0, 10.0, 1e3)


def tm(f, *a, **k):
    """Return one result and its elapsed seconds."""
    t = time.perf_counter()
    y = f(*a, **k)
    return y, time.perf_counter() - t


@contextmanager
def rp(o):
    """Record the most negative certified reduced cost found at each selected dual."""
    f, h, st = W._rm, W._oc, {}

    def rm(g, d, net, K, nt):
        r = f(g, d, net, K, nt)
        st.update(nt=nt, pi=r[3], i=0)
        return r

    def oc(x, T, lam, cap=None):
        r = h(x, T, lam, cap)
        if st["nt"]:
            o.append(r[1] - st["pi"][st["i"]])
        st["i"] += 1
        return r

    W._rm, W._oc = rm, oc
    try:
        yield
    finally:
        W._rm, W._oc = f, h


def pub():
    """The published cases, convex hull and AIC, direct against generated."""
    print("| Case | Price | hc value | cg value | cg bound | Price, hc | Price, cg | Uplift at cg "
          "| Solves | Generated | Repriced | Final | Active | hc s | cg s |")
    print("| --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: "
          "| ---: | ---: |")
    for tag, f in PUB:
        q = f()
        g, d, net = (*q, None) if len(q) == 2 else q
        s = uc(g, d, net=net)
        for c in ([None] if net is not None else [None, pc(g, d, s, 1e-6)]):
            a, t1 = tm(hc, g, d, c, net)
            b, t2 = tm(W.cg, g, d, c, net, s)
            u = pay(g, s, b.s.pi, net).up.sum()
            print(f"| {tag} | {'AIC' if c is not None else 'CHP'} | {a.z:,.4f} | {b.s.z:,.4f} | "
                  f"{b.s.lb:,.4f} | {', '.join(f'{x:.3f}' for x in a.pi.ravel())} | "
                  f"{', '.join(f'{x:.3f}' for x in b.s.pi.ravel())} | {u:,.2f} | {b.k} | "
                  f"{b.ng} | {b.nr} | {b.nk} | {b.na} | {t1:.2f} | {t2:.2f} |")


def fam():
    """Every feasible market of the 141-seed family, uncapped and capped."""
    R = []
    for sd in range(141):
        q = _clear(sd)
        if q is None:
            continue
        g, d, s = q
        for c in (None, pc(g, d, s, 1e-6)):
            o = []
            a, t1 = tm(hc, g, d, c)
            with rp(o):
                b, t2 = tm(W.cg, g, d, c, None, s)
            dz = (b.s.z - a.z) / max(1.0, abs(a.z))
            ex = (b.s.lb - a.z) / max(1.0, abs(a.z))
            dp = float(np.abs(a.pi - b.s.pi).max())
            du = abs(pay(g, s, a.pi).up.sum() - pay(g, s, b.s.pi).up.sum())
            v = min(o, default=0.0)
            R.append((sd, c is not None, dz, ex, dp, du, b.nr, v, b.na <= len(d) + len(g),
                      t1, t2, b.s.st, b.tau))
    print(f"{len({r[0] for r in R})} feasible markets, {len(R)} routes.\n")
    print("| Price | Routes | Max value gap, cg - hc | Max bound excess, lb - hc | "
          "Max price difference | Max uplift difference | Routes repriced | "
          "Most negative selected rho | Support <= T+G | hc s | cg s |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |")
    for k in (False, True):
        q = [r for r in R if r[1] == k]
        print(f"| {'AIC' if k else 'CHP'} | {len(q)} | {max(r[2] for r in q):.2e} | "
              f"{max(r[3] for r in q):.2e} | {max(r[4] for r in q):.2e} | "
              f"{max(r[5] for r in q):.2e} | {sum(r[6] > 0 for r in q)} | "
              f"{min(r[7] for r in q):.4g} | {all(r[8] for r in q)} | "
              f"{sum(r[9] for r in q):.1f} | {sum(r[10] for r in q):.1f} |")
    w = [(r[0], r[4], r[5]) for r in R if r[1] and r[4] > 1e-4]
    print("\nAIC routes whose prices differ by more than 1e-4 $/MWh (seed, price, uplift): "
          + ", ".join(f"{a} ({b:.4f}, {c:.2f})" for a, b, c in w))
    x = sorted((r[7], r[0], r[1]) for r in R if r[6] > 0)
    print("Repriced routes (rho, seed, capped): "
          + ", ".join(f"{v:.3g} ({a}, {'AIC' if b else 'CHP'})" for v, a, b in x))
    print("Tags: " + ", ".join(sorted({r[11] for r in R})))


def _mn(x, T, lam, cap):
    """min c_g - lam'p over X_g by enumeration: every feasible trajectory's dispatch LP."""
    q = [(linprog(x.c - lam, A_ub=A, b_ub=h, bounds=(None, None), options=TE), k)
         for _u, _v, _w, A, h, k in _cl(x, T, cap)]
    return min(r.fun + k for r, k in q if r.success)


def orc():
    """Every oracle call of the seeded family, capped and uncapped, against enumeration.

    Offer costs are scaled by a; the markets' feasible sets are not. e is the oracle's
    bound less the enumerated minimum, positive where the bound is invalid.
    """
    f = W._oc
    print("| Cost scale | Oracle calls | Bound less minimum | Stalled routes | "
          "Routes with lb > z |")
    print("| ---: | ---: | --- | ---: | ---: |")
    for a in SC:
        e, R = [], []

        def oc(x, T, lam, cap=None, e=e):
            r = f(x, T, lam, cap)
            e.append(r[1] - _mn(x, T, lam, cap))
            return r

        W._oc = oc
        try:
            for sd in range(141):
                if _clear(sd) is None:
                    continue
                g, d = _rand(sd)
                g = [x._replace(c=a * x.c, nl=a * x.nl, su=a * x.su) for x in g]
                s = uc(g, d)
                R += [W.cg(g, d, c, None, s) for c in (None, pc(g, d, s, 1e-6))]
        finally:
            W._oc = f
        print(f"| {a:g} | {len(e):,} | [{min(e):.1e}, {max(e):.1e}] | "
              f"{sum(b.s.st == 'stall' for b in R)} | {sum(b.s.lb > b.s.z for b in R)} |")


def sz(G, T):
    """One synthetic market: direct formulations against the generated master."""
    g, d = mk_g(G, T)
    s, t0 = tm(uc, g, d)
    a, t1 = tm(hc, g, d)
    try:
        h, t3 = tm(hl, g, d)
        e = f"{t3:.2f}"
        assert abs(h.z - a.z) <= 1e-8 * abs(a.z)
    except ValueError as x:
        if not str(x).startswith("hl is limited"):
            raise
        e = "refused"
    b, t2 = tm(W.cg, g, d, None, None, s)
    n = hs(G, T)
    print(f"| {G} x {T} | {n[1]:,} | {t1:.2f} | {e} | {t0:.2f} | {t2:.2f} | {b.k} | {b.ng} | "
          f"{b.nr} | {b.nk} | {b.na} | {G + T} | {b.s.gap:.1e} | "
          f"{(b.s.z - a.z) / abs(a.z):.1e} | {np.abs(a.pi - b.s.pi).max():.1e} | {b.s.st} |")


def rts():
    """The pglib-uc RTS-GMLC instance: no direct hull exists, so the bracket is the check."""
    from scipy.optimize import linprog

    from models.pglib_uc import _sy
    D = ld(Path("data/pglib_uc/rts_gmlc_2020-03-05.json"))
    c, A, b, Ae, be, lb, ub, _ = _sy(D)
    lp = linprog(c, A_ub=A, b_ub=b, A_eq=Ae, b_eq=be, bounds=list(zip(lb, ub))).fun
    r, t = tm(W.cgp, D)
    print("| LP relaxation | Hull bound lb | Master z | Relative gap | Solves | Generated | "
          "Repriced | Final | Active | Energy price | Reserve price > 0 | Tag | Seconds |")
    print("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- "
          "| ---: |")
    print(f"| {lp:,.2f} | {r.lb:,.2f} | {r.z:,.2f} | {(r.z - r.lb) / abs(r.z):.1e} | {r.k} | "
          f"{r.ng} | {r.nr} | {r.nk} | {r.na} | {r.pe.min():.4f} to {r.pe.max():.4f} | "
          f"{int((r.pr > 1e-9).sum())} of {len(r.pr)} | {r.st} | {t:.0f} |")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("table", nargs="?", choices=("big", "rts", "oracle"),
                   help="big: the 48 x 24 and 96 x 24 markets; rts: the pglib-uc instance; "
                        "oracle: every oracle bound against enumeration")
    args = p.parse_args()
    print(", ".join(f"{k} {v}" for k, v in vr().items()) + "\n")
    if args.table in ("rts", "oracle"):
        (rts if args.table == "rts" else orc)()
        raise SystemExit
    print("| Units x periods | hc variables | hc s | hl s | uc seed s | cg s | Solves | "
          "Generated | Repriced | Final | Active | T+G | cg gap | Value, cg - hc | "
          "Price difference | Tag |")
    print("| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: "
          "| ---: | ---: | ---: | --- |")
    for G, T in (BIG if args.table == "big" else SIZ):
        sz(G, T)
    if args.table == "big":
        raise SystemExit
    print("\n## Published cases\n")
    pub()
    print("\n## Seeded family\n")
    fam()
