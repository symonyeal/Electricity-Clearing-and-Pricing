# Scale bench for both models. Prints the tables in README.md.
#
# LEGEND
#   DIMS,MKT,HUL : the measured pit sizes, market sizes and convex-hull sizes
#   tm,time      : timer helper and the clock module
#   pit,mkt,hul  : one row of each of the three tables
#   z1,t1 : pit value and seconds from OR-Tools
#   z2,t2 : pit value and seconds from NetworkX
#   z3,t3 : pit value and seconds from the linear program
#   fr    : count of fractional entries in the linear program's solution
#   o     : ore blocks inside the pit          w : waste blocks inside the pit
#   sr    : waste-to-ore strip ratio           lost : ore blocks left outside the pit
#   v,E   : block values and precedence arcs   C : blocks inside the pit
#   b     : one block index                    x : linear-program block choices
#   nx_,ny_,nz_ : model dimensions             d : one model size, or market demand
#   f,a   : timed function and its arguments   y : timed function result
#   t     : timer reading
#   G,T   : unit and period counts             g : the units of a market
#   s,R   : integer clearing and relaxed solve L,H,A : LMP, CHP and AIC solutions
#   P     : payments at one price              K : hull columns, q : hull variables
#   cap   : the AIC output ceilings            mw : units needing a make-whole payment
#   net   : one row of the network table       lim : one line limit
#   nw,pi : the three-bus network and its nodal prices
#   rent  : what the congested network collects and pays to nobody
#   e,K   : the schedule-wise column, and the schedule count

import time

import numpy as np

from models.lg_pit import lp, mc, mc_nx, mk_E, mk_v
from models.uc_price import _ar, _cl, ck, ex4, hc, hl, lmp, mk_g, pay, pc, rx, uc

DIMS = [(30, 30, 12), (60, 60, 20), (90, 90, 30)]
MKT = [(12, 8), (24, 16), (48, 24), (96, 24)]
HUL = [(6, 4), (8, 6), (10, 8), (12, 10), (8, 14)]
LIN = [100.0, 60.0, 40.0, 20.0]


def tm(f, *a):
    """Return one function result and its elapsed seconds."""
    t = time.perf_counter()
    y = f(*a)
    return y, time.perf_counter() - t


def pit(nx_, ny_, nz_):
    v, E = mk_v(nx_, ny_, nz_), mk_E(nx_, ny_, nz_)
    (z1, C), t1 = tm(mc, v, E)
    (z2, _), t2 = tm(mc_nx, v, E)
    (z3, x), t3 = tm(lp, v, E)
    fr = int(((x > 1e-6) & (x < 1 - 1e-6)).sum())
    o = sum(1 for b in C if v[b] > 0)
    w = len(C) - o
    sr = w / o
    lost = int((v > 0).sum()) - o
    print(
        f"| {nx_}x{ny_}x{nz_} | {len(v):,} | {len(E):,} | {z1:,.2f} | {t1:.3f}s | "
        f"{t2:.2f}s | {t3:.2f}s | {fr} | {sr:.2f} | {lost} |"
    )
    assert abs(z1 - z2) < 1e-6
    assert abs(z1 - z3) < 1e-6
    assert 1.5 <= sr <= 3.0


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


def net(lim):
    """The three-bus loop at one line limit: dispatch, nodal prices and congestion rent."""
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


if __name__ == "__main__":
    print("## Ultimate pit limit\n")
    print(
        "| Model | Blocks | Arcs | Pit value | OR-Tools | NetworkX | LP | Fractional | "
        "Strip ratio | Ore left out |"
    )
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for d in DIMS:
        pit(*d)
    print("\n## Market clearing and locational prices\n")
    print(
        "| Units x periods | Variables | Cleared cost | uc | rx | pay | Relaxation gap | "
        "Units needing make-whole | LMP uplift |"
    )
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for d in MKT:
        mkt(*d)
    print("\n## Exact convex hull prices\n")
    print(
        "| Units x periods | Arcs | Schedules | CHP | AIC | Schedule-wise | Price gap | "
        "LMP uplift | CHP uplift | AIC uplift | AIC make-whole |"
    )
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for d in HUL:
        hul(*d)
    print("\n## A congested network\n")
    print(
        "| Line 0-2 limit | Bus 0 output | Bus 2 output | Cost | Price at 0 | Price at 1 | "
        "Price at 2 | Congestion rent |"
    )
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for d in LIN:
        net(d)
