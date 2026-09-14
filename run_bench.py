# Scale bench for the Lerchs-Grossmann pit model. Prints the table in README.md.
#
# LEGEND
#   z1,t1 : pit value and elapsed seconds from the minimum cut
#   z2,t2 : pit value and elapsed seconds from the linear program
#   fr    : count of fractional entries in the linear program's solution
#   o     : ore blocks inside the pit          w : waste blocks inside the pit
#   lost  : ore blocks left outside the pit

import time

from models.lg_pit import lp, mc, mk_E, mk_v

DIMS = [(30, 30, 12), (60, 60, 20), (90, 90, 30)]


def row(nx_, ny_, nz_):
    v, E = mk_v(nx_, ny_, nz_), mk_E(nx_, ny_, nz_)
    t = time.time()
    z1, C = mc(v, E)
    t1 = time.time() - t
    t = time.time()
    z2, x = lp(v, E)
    t2 = time.time() - t
    fr = int(((x > 1e-6) & (x < 1 - 1e-6)).sum())
    o = sum(1 for b in C if v[b] > 0)
    w = len(C) - o
    lost = int((v > 0).sum()) - o
    print(f"| {nx_}x{ny_}x{nz_} | {len(v):,} | {len(E):,} | {z1:,.2f} | {t1:.2f}s | "
          f"{t2:.2f}s | {fr} | {w / o:.2f} | {lost} |")
    assert abs(z1 - z2) < 1e-6


if __name__ == "__main__":
    print("| Model | Blocks | Arcs | Pit value | Min cut | LP | Fractional | Strip ratio | Ore left out |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for d in DIMS:
        row(*d)
