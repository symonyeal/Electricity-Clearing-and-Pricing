# Scale bench for the Lerchs-Grossmann pit model. Prints the table in README.md.
#
# LEGEND
#   DIMS  : measured model sizes             tm,row : timer and one benchmark row
#   time  : clock module
#   z1,t1 : pit value and seconds from OR-Tools
#   z2,t2 : pit value and seconds from NetworkX
#   z3,t3 : pit value and seconds from the linear program
#   fr    : count of fractional entries in the linear program's solution
#   o     : ore blocks inside the pit          w : waste blocks inside the pit
#   sr    : waste-to-ore strip ratio           lost : ore blocks left outside the pit
#   v,E   : block values and precedence arcs   C : blocks inside the pit
#   b     : one block index
#   x     : linear-program block choices       nx_,ny_,nz_ : model dimensions
#   f,a   : timed function and its arguments   y : timed function result
#   t     : timer reading                      d : one model-size tuple

import time

from models.lg_pit import lp, mc, mc_nx, mk_E, mk_v

DIMS = [(30, 30, 12), (60, 60, 20), (90, 90, 30)]


def tm(f, *a):
    """Return one function result and its elapsed seconds."""
    t = time.perf_counter()
    y = f(*a)
    return y, time.perf_counter() - t


def row(nx_, ny_, nz_):
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


if __name__ == "__main__":
    print(
        "| Model | Blocks | Arcs | Pit value | OR-Tools | NetworkX | LP | Fractional | "
        "Strip ratio | Ore left out |"
    )
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for d in DIMS:
        row(*d)
