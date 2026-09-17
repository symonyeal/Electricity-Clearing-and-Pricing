# Synthetic trading checks and timings. Optional DOVE comparison uses its own environment.
# b : battery; da,rt,pr,h : prices, probabilities, information; r : result; t : seconds.

import argparse
import platform
import time

import numpy as np
import scipy

from models.storage import B, _tree, en, st


def tm(f, *a, **kw):
    t = time.perf_counter()
    r = f(*a, **kw)
    return r, time.perf_counter() - t


def dove(p):
    """Unmodified DOVE price-taker storage, hourly, zero endpoints and 81% round-trip."""
    import dove.core as dc
    r = dc.Resource(name="power")
    buy = dc.Source(name="buy", produces=r, installed_capacity=1,
                    cashflows=[dc.Cost(name="buy", price_profile=p)])
    sell = dc.Sink(name="sell", consumes=r, installed_capacity=1,
                   cashflows=[dc.Revenue(name="sell", price_profile=p)])
    b = dc.Storage(name="battery", resource=r, installed_capacity=1, rte=0.81)
    s = dc.System(components=[buy, sell, b], resources=[r], dispatch_window=list(range(len(p))))
    v = s.solve("price_taker", solver="appsi_highs")
    return float(np.asarray(p) @ (-v["sell_power_consumes"] - v["buy_power_produces"])), v


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dove", action="store_true", help="compare with locally installed DOVE")
    args = p.parse_args()
    print(f"Python {platform.python_version()}, NumPy {np.__version__}, SciPy {scipy.__version__}")
    print(platform.platform())
    b, da, rt, pr = B(1, 1, 1, 1, 1), [10, 40], [[10, 100], [10, -100]], [0.8, 0.2]
    print("\nSynthetic hedge; no scenario information before dispatch.")
    print("| Risk weight | Mean | CVaR loss | Score | Upper bound | Gap | MIP s | Enum s |")
    print("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for w in (0.0, 0.5, 1.0):
        r, t = tm(st, b, da, rt, pr, a=0.8, w=w)
        e, te = tm(en, b, da, rt, pr, a=0.8, w=w)
        assert abs(r.z - e.z) < 1e-7
        print(f"| {w} | {r.mu:.2f} | {r.cv:.2f} | {r.z:.2f} | {r.ub:.2f} | "
              f"{r.gap:.3g} | {t:.4f} | {te:.4f} |")
    print("\nSynthetic 24-hour tree: eight paths, revealed at hour 13.")
    rng = np.random.default_rng(7)
    da = 40 + 30 * np.sin(np.arange(24) * np.pi / 12)
    rt = np.tile(da, (8, 1))
    rt[:, 12:] += rng.normal(0, 25, (8, 12))
    h = np.zeros((8, 24), dtype=int)
    h[:, 12:] = np.arange(8)[:, None]
    b = B(4, 1, 1, e0=2, ef=2, k=1)
    r, t = tm(st, b, da, rt, np.full(8, 1 / 8), h, w=0.25)
    print(f"{len(_tree(h)[1])} binary nodes, {t:.4f}s; mean {r.mu:.6f}, "
          f"CVaR loss {r.cv:.6f}, score {r.z:.6f}, upper bound {r.ub:.6f}, gap {r.gap:.3g}.")
    print("\nSynthetic duplicate paths: identical prices, same optimal objective.")
    print("| Paths | Shared nodes | Separate nodes | Shared s | Separate s | "
          "Objective difference |")
    print("| ---: | ---: | ---: | ---: | ---: | ---: |")
    # Warm HiGHS once before comparing median assembly + solve times.
    st(b, da, [da], [1])
    for S in (8, 32):
        pr, rt = np.full(S, 1 / S), np.tile(da, (S, 1))
        hs, hd = np.zeros((S, 24), dtype=int), np.tile(np.arange(S)[:, None], (1, 24))
        rs, rd, ts, td = None, None, [], []
        for _ in range(3):
            rs, t = tm(st, b, da, rt, pr, hs)
            ts.append(t)
            rd, t = tm(st, b, da, rt, pr, hd)
            td.append(t)
        dz = abs(rs.z - rd.z)
        assert dz < 1e-6
        print(f"| {S} | {len(_tree(hs)[1])} | {len(_tree(hd)[1])} | "
              f"{np.median(ts):.4f} | {np.median(td):.4f} | {dz:.3g} |")
    if args.dove:
        print("\nDOVE reference: positive-price agreement, negative-price cycling counterexample.")
        for p in ([10, 100], [-100]):
            (z, v), t = tm(dove, p)
            r, ts = tm(st, B(1, 1, 1, 0.9, 0.9), p, [p], [1])
            assert abs(z - (71 if len(p) == 2 else 19)) < 1e-6
            assert abs(r.mu - (71 if len(p) == 2 else 0)) < 1e-6
            print(f"Prices {p}: DOVE {z:.6f} ({t:.4f}s), MIP {r.mu:.6f} ({ts:.4f}s)")
            print(v.to_string(index=False))


if __name__ == "__main__":
    main()
