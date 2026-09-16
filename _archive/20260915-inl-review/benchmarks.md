# Historical benchmark snapshot

Moved from README at baseline `8e4637e` on 2026-09-15. These Windows results describe
the earlier code and solver stack; they are not measurements of the current Linux checkout.
`run_bench.py` and `run_face_scan.py` retain the reproductions. Current checks are in
[Validation](../../docs/VALIDATION.md).

## 3. Computational results

One run on 2026-09-15 used Python 3.14.3, OR-Tools 9.15.6755, NetworkX 3.6.1, SciPy
1.17.1, NumPy 2.4.4, Windows 11 build 26200, and an Intel64 family 6 model 186 processor.
Times are elapsed seconds.

### Market clearing

| Units x periods | Variables | Cost | `uc` | `rx` | Payments | Relaxation gap | Units with make-whole | LMP uplift |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 12 x 8 | 384 | 321,499 | 1.69s | 0.29s | 0.18s | 0.328% | 2 | 1,898 |
| 24 x 16 | 1,536 | 1,264,174 | 2.64s | 0.40s | 0.39s | 0.085% | 6 | 5,478 |
| 48 x 24 | 4,608 | 3,831,805 | 2.14s | 2.71s | 0.90s | 0.035% | 5 | 6,473 |
| 96 x 24 | 9,216 | 7,721,565 | 3.95s | 95.18s | 1.82s | 0.013% | 5 | 6,346 |

### Exact hull prices

| Units x periods | Arcs | Schedules | CHP | AIC | Schedule hull | Price gap | LMP uplift | CHP uplift | AIC uplift | AIC make-whole |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 6 x 4 | 79 | 70 | 0.05s | 0.04s | 0.06s | 3e-13 | 762 | 260 | 486 | 0.00 |
| 8 x 6 | 200 | 332 | 0.15s | 0.11s | 0.39s | 4e-12 | 1,698 | 363 | 686 | 0.00 |
| 10 x 8 | 409 | 1,528 | 0.51s | 0.87s | 4.60s | 7e-11 | 1,924 | 366 | 38,447,064 | 0.00 |
| 12 x 10 | 730 | 6,924 | 4.37s | 0.80s | 134.49s | 8e-11 | 1,855 | 752 | 3,651 | 0.00 |
| 8 x 14 | 896 | over limit | 2.84s | 6.26s | refused | n/a | 5,460 | 1,964 | 4,727 | 0.00 |

### AIC sensitivity to epsilon

Epsilon is the additional MW allowed above each restricted block's cleared output. Cleared
cost per MWh is $z_{UC}/\sum_t d_t$. Weighted premium is the demand-weighted price less that cost.
Spare MW is capped capacity less demand in the highest-price period.

| Market | epsilon MW | Prices ($/MWh) | Uplift ($) | Make-whole ($) | Cost ($/MWh) | Weighted premium ($/MWh) | Peak period / spare MW |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| ex3 | 1e-06 | 10.000, 10.000, 422.000 | 730.00 | 0.00 | 22.58 | 152.22 | 3 / 0.000001 |
| ex3 | 0.0001 | 10.000, 10.000, 421.988 | 729.97 | 0.00 | 22.58 | 152.21 | 3 / 0.000100 |
| ex3 | 0.001 | 10.000, 10.000, 421.883 | 729.71 | 0.00 | 22.58 | 152.17 | 3 / 0.001000 |
| ex3 | 0.1 | 10.000, 10.000, 410.769 | 701.92 | 0.00 | 22.58 | 147.72 | 3 / 0.100000 |
| ex3 | 1 | 10.000, 10.000, 338.571 | 521.43 | 0.00 | 22.58 | 118.84 | 3 / 1.000000 |
| ex3 | 10 | 10.000, 10.000, 276.000 | 365.00 | 0.00 | 22.58 | 93.82 | 3 / 5.000000 |
| 8 x 6, seed 7 | 1e-06 | 74.724, 36.850, 56.210, 65.113, 58.745, 36.850 | 686.11 | 0.00 | 30.40 | 24.84 | 1 / 486.715002 |
| 8 x 6, seed 7 | 0.0001 | 74.724, 36.850, 56.210, 65.113, 58.745, 36.850 | 686.11 | 0.00 | 30.40 | 24.84 | 1 / 486.715200 |
| 8 x 6, seed 7 | 0.001 | 74.724, 36.850, 56.210, 65.113, 58.745, 36.850 | 686.11 | 0.02 | 30.40 | 24.84 | 1 / 486.717000 |
| 8 x 6, seed 7 | 0.1 | 74.704, 36.850, 56.210, 65.113, 58.729, 36.850 | 685.75 | 2.14 | 30.40 | 24.84 | 1 / 486.915000 |
| 8 x 6, seed 7 | 1 | 74.529, 36.850, 56.210, 65.113, 58.589, 36.850 | 682.58 | 21.10 | 30.40 | 24.79 | 1 / 488.715000 |
| 8 x 6, seed 7 | 10 | 73.699, 36.850, 56.210, 65.113, 57.357, 36.850 | 658.72 | 151.97 | 30.40 | 24.45 | 1 / 506.715000 |
| 10 x 8, seed 7 | 1e-06 | 84.020, 40.440, 40.440, 52.880, 55.564, 82,085.019, 46.387, 31.520 | 38,447,063.94 | 0.00 | 30.53 | 12,219.15 | 6 / 0.000001 |
| 10 x 8, seed 7 | 1e-05 | 84.020, 40.440, 40.440, 52.880, 55.564, 82,221.562, 46.370, 31.520 | 38,511,081.04 | 0.00 | 30.53 | 12,239.46 | 6 / 0.000010 |
| 10 x 8, seed 7 | 0.0001 | 84.020, 40.440, 40.440, 52.880, 55.564, 57,979.259, 49.360, 31.520 | 27,145,243.51 | 0.00 | 30.53 | 8,634.66 | 6 / 0.000100 |
| 10 x 8, seed 7 | 0.001 | 84.020, 40.440, 40.440, 52.880, 55.564, 57,979.206, 49.360, 31.520 | 27,145,218.58 | 0.01 | 30.53 | 8,634.66 | 6 / 0.001000 |
| 10 x 8, seed 7 | 0.0025 | 84.019, 40.440, 40.440, 52.880, 55.564, 57,978.079, 49.360, 31.520 | 27,144,689.94 | 0.03 | 30.53 | 8,634.49 | 6 / 0.002500 |
| 10 x 8, seed 7 | 0.00275 | 84.019, 40.440, 40.440, 52.880, 55.664, 67.146, 52.692, 31.520 | 1,559.91 | 0.08 | 30.53 | 22.76 | 1 / 747.982750 |
| 10 x 8, seed 7 | 0.005 | 84.018, 40.440, 40.440, 52.880, 61.048, 52.880, 52.693, 31.520 | 416.91 | 0.09 | 30.53 | 21.49 | 1 / 747.985000 |
| 10 x 8, seed 7 | 0.1 | 83.992, 40.440, 40.440, 52.880, 61.043, 52.880, 52.693, 31.520 | 416.46 | 1.87 | 30.53 | 21.49 | 1 / 748.080000 |
| 10 x 8, seed 7 | 1 | 83.751, 40.440, 40.440, 52.880, 60.989, 52.880, 52.693, 31.520 | 412.25 | 18.42 | 30.53 | 21.46 | 1 / 748.980000 |
| 10 x 8, seed 7 | 10 | 81.830, 40.440, 40.440, 52.880, 60.488, 52.880, 52.693, 31.520 | 377.90 | 159.98 | 30.53 | 21.20 | 1 / 757.980000 |

Results:

- `ex3`: the peak price remains near $422 through epsilon 0.001, then decreases.
- 8 x 6: prices are stable; the peak period has at least 486.7 MW spare.
- 10 x 8: the period-6 price falls from $57,978.08 to $67.15 between epsilon 0.0025 and
  0.00275. The schedule set is unchanged; the output ceilings move the optimum to another
  hull face. At epsilon $10^{-6}$, `hc` and `hl` differ by $64.48/MWh because the face is
  numerically thin. At $10^{-5}$, they agree within $0.0002/MWh at about $82,221.56/MWh.

At epsilon $10^{-6}$, 15 independent 10 x 8 markets give:

| Peak price | Markets | Uplift range ($) |
| --- | ---: | ---: |
| Above $1,000/MWh | 3 | 32,759,768.79-38,447,063.94 |
| At most $1,000/MWh | 12 | 283.70-14,585.92 |

Six peak periods have at most $1.1\times10^{-6}$ MW spare, but only three have extreme
prices. Thus depleted headroom is not sufficient. Fourteen markets have make-whole below
$0.001. The remaining market has $10.38 on an unrestricted block. This is outside
Proposition 3, which applies to restricted blocks as epsilon tends to zero.

### Three-bus network

Nodal balances replace the single-system balance under both line models. Direct current
(`dc`) imposes $f_{ij}=(\theta_i-\theta_j)/x_{ij}$ and
$-\bar f_{ij}\le f_{ij}\le\bar f_{ij}$. This case is a meshed transmission network, so it
is priced under `dc`.

| Line 0-2 limit | Bus 0 output | Bus 2 output | Cost | Price at 0 | Price at 1 | Price at 2 | Congestion rent |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 MW | 90 | 0 | 900 | 10.00 | 10.00 | 10.00 | 0 |
| 60 MW | 90 | 0 | 900 | 10.00 | 10.00 | 10.00 | 0 |
| 40 MW | 60 | 30 | 2,100 | 10.00 | 30.00 | 50.00 | 2,400 |
| 20 MW | 30 | 60 | 3,300 | 10.00 | 30.00 | 50.00 | 1,200 |

With equal reactances, two thirds of bus-0 injection uses the direct line. The 40 MW limit
therefore caps bus-0 output at 60 MW. The computed nodal prices are $(10,30,50)$.

### Two coupled bidding zones

A day-ahead market clears by zone, not by node. Transport (`ntc`) drops the reactance and
gives each exchange a capacity pair: a line is $(z_1,z_2,(\underline c,\bar c))$, keyed by
its two zones in ascending order and bounding the signed flow from the first to the second.
Published transfer capacity is directional, so the pair is not symmetric.

`ex5` couples two Norwegian zones by the exchange electricity maps records as
`NO-NO1_NO-NO2`, capacity $[-3500, 2200]$. The capacity is that record. The offers and the
demand are labelled synthetic, because no market publishes the offers behind a cleared
price.

| Period | NO-NO1 price | NO-NO2 price | Flow NO-NO1 to NO-NO2 | Congestion rent |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 40.00 | 10.00 | -3,500 | 105,000 |
| 2 | 40.00 | 90.00 | 2,200 | 110,000 |

Each bound binds in one period, and the zones price apart in both. Total cost is 275,000.

Transport is a relaxation of direct current on any network carrying a cycle, and the two
coincide on a tree, where the balances determine the flows. Tests hold both halves.

### Ultimate pit

| Model | Blocks | Arcs | Pit value | OR-Tools | NetworkX | LP | Fractional | Strip ratio | Ore omitted |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30x30x12 | 10,800 | 85,184 | 2,552.23 | 0.009s | 0.83s | 0.23s | 0 | 2.64 | 73 |
| 60x60x20 | 72,000 | 601,996 | 20,102.47 | 0.085s | 8.14s | 2.06s | 0 | 2.06 | 230 |
| 90x90x30 | 243,000 | 2,082,896 | 68,454.46 | 0.420s | 41.69s | 10.83s | 0 | 2.03 | 602 |

The 90x90x30 arc array uses 15.90 MiB and took 0.410s to build. The former tuple list used
270.51 MiB and took 4.454s.
