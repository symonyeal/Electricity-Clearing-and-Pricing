# Prices under a risk-averse commitment. Source of every table in docs/RISK.md.
#
# LEGEND
#   EX         : the five examples              fm : format a vector
#   f,g,st,d   : one example, its units, resources and demand      pr,w,al : its risk data
#   s0,s       : the risk-neutral and the risk-averse clearing
#   L0,L       : lmp at each                    c : cvd at the risk-averse clearing
#   v          : value of information           e : one settlement
#   R          : the candidate prices, each with the dispatch and commitment it settles

import numpy as np

import models.risk as K
from models.stoch import _te, cl, cvd, lmp
from models.uc_price import vr

EX = [K.r1, K.r2, K.r3, K.r4, K.r5]


def fm(v):
    return ", ".join("nan" if np.isnan(x) else f"{round(float(x), 3) + 0.0:,.3f}"
                     for x in np.ravel(v))


if __name__ == "__main__":
    print(", ".join(f"{k} {v}" for k, v in vr().items()) + "\n")
    rows = []
    for f in EX:
        g, st, d, pr, w, al = f()
        s0, s = cl(g, st, d, pr), cl(g, st, d, pr, w=w, al=al)
        rows.append((f.__name__, g, d, pr, w, al, s0, s, lmp(g, st, d, s0, pr),
                     lmp(g, st, d, s, pr), cvd(g, st, d, s, pr, w=w, al=al),
                     K.vi(g, st, d, pr, None, w, al)))

    print("## The examples\n")
    print("| Example | Demand by scenario | Probabilities | w | al | Commitment, w = 0 | "
          "Commitment, risk averse |")
    print("| --- | --- | --- | ---: | ---: | --- | --- |")
    for k, g, d, pr, w, al, s0, s, *_ in rows:
        print(f"| {k} | {' / '.join(fm(x) for x in d[:, 0])} | {fm(pr)} | {w:g} | {al:g} | "
              f"{' / '.join(fm(x) for x in s0.u)} | {' / '.join(fm(x) for x in s.u)} |")

    print("\n## The risk-averse program, integers held\n")
    print("| Example | Objective | E[C] | CVaR | Level zt | Excess xi | Scenario cost | "
          "mu | w th(q) | om = (1 - w) p + mu |")
    print("| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |")
    for k, g, d, pr, w, al, s0, s, L0, L, c, v in rows:
        print(f"| {k} | {c.z:,.3f} | {s.mean:,.3f} | {s.cv:,.3f} | {c.zt:,.3f} | {fm(c.xi)} | "
              f"{fm(c.q)} | {fm(c.mu)} | {fm(w * _te(c.q, pr, al))} | {fm(c.om)} |")

    print("\n## Candidate prices, by scenario\n")
    print("| Example | Scenario | Expected-cost re-dispatch, w = 0 commitment | "
          "Expected-cost re-dispatch | Raw dual y | y / p | y / om |")
    print("| --- | ---: | --- | --- | --- | --- | --- |")
    for k, g, d, pr, w, al, s0, s, L0, L, c, v in rows:
        for j in range(len(pr)):
            print(f"| {k} | {j + 1} | {fm(L0.pi[j])} | {fm(L.pi[j])} | {fm(c.y[j])} | "
                  f"{fm(c.y[j] / pr[j])} | {fm(c.lam[j])} |")

    print("\n## Settlement under each candidate, in expectation over p\n")
    print("| Example | Commitment | Price | Load pays | Units' profit | Make-whole | "
          "Lost opportunity | Scenarios priced |")
    print("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for k, g, d, pr, w, al, s0, s, L0, L, c, v in rows:
        R = [("w = 0", "expected-cost", s0.u, L0.p, L0.pi),
             ("risk averse", "expected-cost", s.u, L.p, L.pi),
             ("risk averse", "y / p", s.u, c.p, c.y / pr[:, None, None]),
             ("risk averse", "y / om", s.u, c.p, c.lam)]
        for a, b, u, p, pi in R:
            e = K.se(g, d, pr, u, p, pi)
            print(f"| {k} | {a} | {b} | {e.EL:,.2f} | {e.Er:,.2f} | {e.Emw:,.2f} | "
                  f"{e.Eloc:,.2f} | {int((~np.isnan(e.L)).sum())} of {len(pr)} |")

    print("\n## Value of information, under E and under rho\n")
    print("| Example | WS | SP | EEV | EVPI | VSS | WS, rho | SP, rho | EEV, rho | EVPI, rho | "
          "VSS, rho | E[C] at the rho commitment |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for k, *_, v in rows:
        print(f"| {k} | {v.ws:,.2f} | {v.sp:,.2f} | {v.ee:,.2f} | {v.evpi:,.2f} | {v.vss:,.2f} "
              f"| {v.wsr:,.2f} | {v.spr:,.2f} | {v.eer:,.2f} | {v.evpir:,.2f} | {v.vssr:,.2f} | "
              f"{v.mr:,.2f} |")
