# Benchmarks for unit commitment, prices and networks.
#
# LEGEND
#   MKT,HUL,SIZ : market, priced-hull and size-report dimensions
#   SD          : fixed synthetic-market seed for the size report
#   LIN         : three-bus line limits
#   EPS,EPS10   : AIC output relaxations
#   tm,time     : timer and clock module
#   mkt,hul,sz  : one market, priced-hull or deterministic size row
#   sizes,_kp   : size table and path count through one unit's interval graph
#   aic,aseed   : AIC sweep and seeded check
#   net,zon     : nodal and zonal network rows
#   f,a,y,t     : timed function, arguments, result and seconds
#   G,T         : unit and period counts
#   g,d         : units and demand
#   s,R         : integer clearing and relaxation
#   L,H,A,E     : LMP, CHP, AIC and trajectory-wise hull solutions
#   P           : payments at one price
#   q,K         : hull columns and commitment-trajectory count
#   C,V,N       : interval arcs, actual hc variables and actual hl variables
#   cap,ep      : AIC output ceilings and relaxation
#   cm,pm       : cleared cost and weighted price per MWh
#   h           : spare MW in the peak-price period
#   mw          : units requiring make-whole
#   pi          : price vector
#   nw          : three-bus network
#   lim         : line limit
#   e           : hl comparison or exchange flow
#   rent        : demand payment less generator revenue
#   tag         : market label

import argparse
import time

import numpy as np

from models.uc_price import (LIM, _ar, _cl, ck, ex3, ex4, ex5, hc, hl, lmp, mk_g, pay, pc,
                             rx, uc)

MKT = [(12, 8), (24, 16), (48, 24), (96, 24)]
HUL = [(6, 4), (8, 6), (10, 8), (12, 10), (8, 14)]
SIZ = HUL[:-1] + [(8, 14), (10, 16), (24, 16), (48, 24), (96, 24)]
SD = 7
LIN = [100.0, 60.0, 40.0, 20.0]
EPS = (1e-6, 1e-4, 1e-3, 0.1, 1.0, 10.0)
EPS10 = (1e-6, 1e-5, 1e-4, 1e-3, 0.0025, 0.00275, 0.005, 0.1, 1.0, 10.0)


def tm(f, *a):
    """Return one result and its elapsed seconds."""
    t = time.perf_counter()
    y = f(*a)
    return y, time.perf_counter() - t


def _kp(C, T):
    """Count commitment trajectories as source-to-sink paths in one unit's interval graph."""
    E = [[] for _ in range(T + 2)]
    for a in C:
        E[a[0]].append(a[1])
    p = [0] * (T + 2)
    p[T + 1] = 1
    for t in [T + 1, *range(T)]:
        for j in E[t]:
            p[j] += p[t]
    return p[T]


def sz(G, T):
    """Return hc arcs/variables and hl trajectories/variables without enumeration."""
    g, d = mk_g(G, T, SD)
    C = [_ar(x, T) for x in ck(g, d)[0]]
    a = sum(len(x) for x in C)
    V = sum(sum((q[3] - q[2] + 1 if q[4] is not None else 0) + 1 for q in x) for x in C)
    K = sum(_kp(x, T) for x in C)
    return a, V, K, K * (T + 1)


def sizes():
    """Print the deterministic formulation sizes used by the decomposition note."""
    print("## Convex-hull formulation sizes\n")
    print(f"Synthetic `mk_g` markets, seed {SD}. Trajectories are counted as graph paths.\n")
    print("| Units x periods | hc arcs | hc variables | hl trajectories | "
          "hl variables | hl guard |")
    print("| --- | ---: | ---: | ---: | ---: | --- |")
    for G, T in SIZ:
        a, V, K, N = sz(G, T)
        if T > LIM[0]:
            q = f"over {LIM[0]}-period limit"
        elif N > LIM[1]:
            q = f"over {LIM[1]:,}-variable limit"
        else:
            q = "within limits"
        print(f"| {G} x {T} | {a:,} | {V:,} | {K:,} | {N:,} | {q} |")


def mkt(G, T):
    g, d = mk_g(G, T)
    s, t1 = tm(uc, g, d)
    R, t2 = tm(rx, g, d)
    L = lmp(g, d, s)
    P, t3 = tm(pay, g, s, L.pi)
    mw = int((P.mw > 1e-6).sum())
    print(
        f"| {G} x {T} | {4 * G * T:,} | {s.z:,.0f} | {t1:.2f}s | {t2:.2f}s | {t3:.2f}s | "
        f"{100 * (s.z - R.z) / s.z:.3f}% | {mw} | {P.up.sum():,.0f} |"
    )
    assert mw >= 1
    assert R.z <= s.z + 1e-6
    assert P.up.sum() >= P.mw.sum() - 1e-6


def hul(G, T):
    g, d = mk_g(G, T)
    q = ck(g, d)[0]
    s = uc(g, d)
    H, t1 = tm(hc, g, d)
    A, t2 = tm(hc, g, d, pc(g, d, s, 1e-6))
    try:
        E, t3 = tm(hl, g, d)
        e = f"{t3:.2f}s | {np.abs(E.pi - H.pi).max():.0e}"
        K = f"{sum(len(_cl(x, T)) for x in q):,}"
        assert abs(E.z - H.z) <= 1e-9 * max(1.0, abs(H.z))
    except ValueError:
        e, K = "refused | n/a", "over the ceiling"
    P = [pay(g, s, x.pi) for x in (lmp(g, d, s), H, A)]
    print(
        f"| {G} x {T} | {sum(len(_ar(x, T)) for x in q):,} | {K} | {t1:.2f}s | {t2:.2f}s | "
        f"{e} | {P[0].up.sum():,.0f} | {P[1].up.sum():,.0f} | {P[2].up.sum():,.0f} | "
        f"{P[2].mw.sum():.2f} |"
    )
    assert H.z <= s.z + 1e-6
    assert P[1].up.sum() <= P[0].up.sum() + 1e-3
    assert P[2].mw.sum() < 1e-3


def aic(tag, g, d, eps):
    """Print AIC prices and payments over an epsilon sweep."""
    s = uc(g, d)
    L = lmp(g, d, s)
    d = np.asarray(d, dtype=float)
    cm = s.z / d.sum()
    for ep in eps:
        cap = pc(g, d, s, ep, L)
        A = hc(g, d, cap)
        P = pay(g, s, A.pi)
        pi = A.pi.ravel()
        pm = float(pi @ d / d.sum())
        t = int(np.argmax(pi))
        h = float(cap[:, t].sum() - d[t])
        q = ", ".join(f"{x:,.3f}" for x in pi)
        print(
            f"| {tag} | {ep:g} | {q} | {P.up.sum():,.2f} | {P.mw.sum():,.2f} | "
            f"{cm:,.2f} | {pm - cm:,.2f} | {t + 1} / {h:,.6f} |"
        )


def aseed():
    """Measure the default epsilon on fifteen seeded 10 x 8 markets."""
    up, mw, peak, scarce = [], [], [], 0
    for sd in range(15):
        g, d = mk_g(10, 8, sd)
        s = uc(g, d)
        L = lmp(g, d, s)
        cap = pc(g, d, s, 1e-6, L)
        A = hc(g, d, cap)
        P = pay(g, s, A.pi)
        t = int(np.argmax(A.pi))
        up.append(float(P.up.sum()))
        mw.append(float(P.mw.sum()))
        peak.append(float(A.pi.max()))
        scarce += bool(cap[:, t].sum() - d[t] <= 1.1e-6)
    a = [x for x, p in zip(up, peak) if p <= 1000.0]
    b = [x for x, p in zip(up, peak) if p > 1000.0]
    print(
        f"| 15 | {len(b)} ({min(b):,.2f}-{max(b):,.2f}) | {len(a)} "
        f"({min(a):,.2f}-{max(a):,.2f}) | {scarce} | "
        f"{sum(x < 1e-3 for x in mw)} | {max(mw):,.2f} |"
    )


def net(lim):
    """Solve the three-bus loop at one line limit."""
    g, d, nw = ex4(lim)
    s = uc(g, d, net=nw)
    L = lmp(g, d, s, net=nw)
    pi, q = L.pi.ravel(), ck(g, d, nw)[2]
    rent = float((pi * np.atleast_2d(d).ravel()).sum()
                 - sum(pi[q.bus[i]] * s.p[i, 0] for i in range(len(g))))
    print(
        f"| {lim:,.0f} MW | {s.p[0, 0]:,.0f} | {s.p[1, 0]:,.0f} | {s.z:,.0f} | "
        f"{pi[0]:,.2f} | {pi[1]:,.2f} | {pi[2]:,.2f} | {rent:,.0f} |"
    )
    assert abs(2.0 * s.p[0, 0] / 3.0 - min(lim, 60.0)) < 1e-6
    assert rent > -1e-6


def zon():
    """Solve the two-zone market."""
    g, d, q = ex5()
    s = uc(g, d, net=q)
    pi, d = lmp(g, d, s, net=q).pi, np.atleast_2d(d)
    for t in range(d.shape[1]):
        e = float(sum(s.p[i, t] for i in range(len(g)) if q.bus[i] == 0) - d[0, t])
        rent = float((pi[:, t] * d[:, t]).sum()
                     - sum(pi[q.bus[i], t] * s.p[i, t] for i in range(len(g))))
        print(f"| {t + 1} | {pi[0, t]:,.2f} | {pi[1, t]:,.2f} | {e:,.0f} | {rent:,.0f} |")
        assert min(abs(e - y) for y in q.ln[0][2]) < 1e-6
        assert rent > -1e-6


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("table", nargs="?", choices=("sizes",), help="print one reproducible table")
    args = p.parse_args()
    if args.table == "sizes":
        sizes()
        raise SystemExit
    print("## Market clearing and locational prices\n")
    print(
        "| Units x periods | Variables | Cleared cost | uc | rx | pay | Relaxation gap | "
        "Units needing make-whole | LMP uplift |"
    )
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for d in MKT:
        mkt(*d)
    print("\n## Exact convex hull prices\n")
    print(
        "| Units x periods | Arcs | Trajectories | CHP | AIC | hl solve | Price gap | "
        "LMP uplift | CHP uplift | AIC uplift | AIC make-whole |"
    )
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for d in HUL:
        hul(*d)
    print("\n## AIC sensitivity to epsilon\n")
    print(
        "| Market | epsilon MW | Prices ($/MWh) | Uplift ($) | Make-whole ($) | "
        "Cost ($/MWh) | Weighted premium ($/MWh) | Peak period / spare MW |"
    )
    print("| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |")
    aic("ex3", *ex3(), EPS)
    aic("8 x 6, seed 7", *mk_g(8, 6), EPS)
    aic("10 x 8, seed 7", *mk_g(10, 8), EPS10)
    print("\n## AIC across 10 x 8 seeds\n")
    print(
        "| Seeds | Peak >$1,000/MWh: markets (uplift range, $) | "
        "Peak <=$1,000/MWh: markets (uplift range, $) | Peak at epsilon headroom | "
        "Make-whole <$0.001 | Maximum make-whole ($) |"
    )
    print("| ---: | --- | --- | ---: | ---: | ---: |")
    aseed()
    print("\n## A congested network\n")
    print(
        "| Line 0-2 limit | Bus 0 output | Bus 2 output | Cost | Price at 0 | Price at 1 | "
        "Price at 2 | Congestion rent |"
    )
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for d in LIN:
        net(d)
    print("\n## Two coupled bidding zones\n")
    print(
        "| Period | NO-NO1 price | NO-NO2 price | Flow NO-NO1 to NO-NO2 | Congestion rent |"
    )
    print("| ---: | ---: | ---: | ---: | ---: |")
    zon()
