# Storage cleared inside the market. Source of every table in docs/SETTLE.md.
#
# LEGEND
#   CS         : the seven cases             BID : the curve offers compared on s1
#   one        : clear, price and settle one case, with and without its resource
#   f,g,st,d   : one case, its units, resources and demand      net : its network
#   b,s        : the clearing without and with the resource
#   p0,pi      : their prices                q,t : their settlements
#   z          : X, H and R clearing costs   y : a position   ref : the reference price

import numpy as np

import models.settle as X
from models.uc_price import vr

CS = [X.s1, X.s2, X.s3, X.s4, X.s5, X.s6, X.s7]
BID = [(1, 0.0), (3, 0.2), (5, 1.0)]


def one(f, how="X"):
    """A case's baseline and cleared market, each priced with its integers held and settled."""
    g, st, d, net = f()
    b = X.cl(g, [], d, net)
    p0 = X.px(g, [], d, b, net)[0]
    s = X.cl(g, st, d, net, how)
    pi = X.px(g, st, d, s, net, how)[0]
    return g, st, d, net, b, p0, X.stl(g, [], d, b, p0, net), s, pi, X.stl(g, st, d, s, pi, net)


def fm(v):
    return ", ".join(f"{x:,.2f}" for x in np.ravel(v))


if __name__ == "__main__":
    print(", ".join(f"{k} {v}" for k, v in vr().items()) + "\n")
    R = {f.__name__: one(f) for f in CS}

    print("## Value and settlement\n")
    print("| Case | Cost without | Cost with | Saved | Storage profit | Load pays, without "
          "| Load pays, with | Make-whole, without | Make-whole, with | Lost opportunity, with "
          "| Rent, without | Rent, with |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for k, (g, st, d, net, b, p0, q, s, pi, t) in R.items():
        print(f"| {k} | {b.z:,.2f} | {s.z:,.2f} | {b.z - s.z:,.2f} | {t.rs.sum():,.2f} | "
              f"{q.L:,.2f} | {t.L:,.2f} | {q.mw.sum():,.2f} | {t.mw.sum():,.2f} | "
              f"{t.loc.sum() + t.ls.sum():,.2f} | {q.rent:,.2f} | {t.rent:,.2f} |")

    print("\n## Prices, held integers\n")
    print("| Case | Bus | Without | With |")
    print("| --- | ---: | --- | --- |")
    for k, (g, st, d, net, b, p0, q, s, pi, t) in R.items():
        for n in sorted({1, int(st[0].bus)}):
            print(f"| {k} | {n} | {fm(p0[n])} | {fm(pi[n])} |")

    print("\n## Dispatch of the resource\n")
    print("| Case | Charge | Discharge | Stored energy | Mode |")
    print("| --- | --- | --- | --- | --- |")
    for k, (g, st, d, net, b, p0, q, s, pi, t) in R.items():
        print(f"| {k} | {fm(s.sc)} | {fm(s.sd)} | {fm(s.se)} | {fm(s.sm)} |")

    print("\n## The settlement identity: L - z = units + storage + rent\n")
    print("| Case | L | z | Units' profit | Storage profit | Rent | Rent from flows | Residual |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for k, (g, st, d, net, b, p0, q, s, pi, t) in R.items():
        print(f"| {k} | {t.L:,.2f} | {t.z:,.2f} | {t.r.sum():,.2f} | {t.rs.sum():,.2f} | "
              f"{t.rent:,.2f} | {t.rf:,.2f} | {t.L - t.z - t.r.sum() - t.rs.sum() - t.rent:.1e} |")

    print("\n## Energy and congestion value of the resource, by reference bus\n")
    print("| Case | Resource bus | Energy, ref 0 | Congestion, ref 0 | Energy, ref 1 | "
          "Congestion, ref 1 |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |")
    for k, (g, st, d, net, b, p0, q, s, pi, t) in R.items():
        u = X.stl(g, st, d, s, pi, net, ref=1)
        print(f"| {k} | {st[0].bus} | {t.en[0]:,.2f} | {t.cn[0]:,.2f} | {u.en[0]:,.2f} | "
              f"{u.cn[0]:,.2f} |")

    print("\n## Three descriptions of the resource\n")
    print("| Case | z over X | z over H = conv(X) | z over R, the mode cut | X - H | H - R | "
          "Price over R |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for f in CS:
        g, st, d, net = f()
        z = [X.cl(g, st, d, net, how) for how in ("X", "H", "R")]
        pr = X.px(g, st, d, z[2], net, "R")[0][1]
        print(f"| {f.__name__} | {z[0].z:,.3f} | {z[1].z:,.3f} | {z[2].z:,.3f} | "
              f"{z[0].z - z[1].z:,.3f} | {z[1].z - z[2].z:,.3f} | {fm(pr)} |")

    print("\n## Market design on s1\n")
    g, st, d, net, b, p0, q, s, pi, t = R["s1"]
    ref = p0[1]
    y = X.ps(st[0], d.shape[1], ref)
    print(f"Price-taking schedule against the no-storage price: charge {fm(y[0])}, "
          f"discharge {fm(y[1])}; anticipated profit {ref @ (y[1] - y[0]):,.2f}.\n")
    print("| Design | Cost | Peak price | Storage profit | Load pays | Make-whole | "
          "Lost opportunity |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    print(f"| Co-optimised | {s.z:,.2f} | {pi[1, 2]:,.2f} | {t.rs[0]:,.2f} | {t.L:,.2f} | "
          f"{t.mw.sum():,.2f} | {t.loc.sum():,.2f} |")
    h = X.cl(g, st, d, net, "fix", q=[y])
    ph = X.px(g, st, d, h, net, "fix", q=[y])[0]
    th = X.stl(g, st, d, h, ph, net)
    print(f"| Price-taking schedule, imposed in full | {h.z:,.2f} | {ph[1, 2]:,.2f} | "
          f"{th.rs[0]:,.2f} | {th.L:,.2f} | {th.mw.sum():,.2f} | {th.loc.sum():,.2f} |")
    for kk, sp in BID:
        c = X.cl(g, st, d, net, "bid", q=[y[1] - y[0]], ref=[ref], kk=kk, sp=sp)
        pc = X.px(g, st, d, c, net, "bid", q=[y[1] - y[0]], ref=[ref], kk=kk, sp=sp)[0]
        tc = X.stl(g, st, d, c, pc, net)
        print(f"| Curve, {kk} step{'s' if kk > 1 else ''}, spread {sp:g} | {c.z:,.2f} | "
              f"{pc[1, 2]:,.2f} | {tc.rs[0]:,.2f} | {tc.L:,.2f} | {tc.mw.sum():,.2f} | "
              f"{tc.loc.sum():,.2f} |")
