# Electricity Market Model

Unit commitment, the prices dual to it, and the uplift each price leaves. A second exact
model, the ultimate pit limit, is kept here as the maximum-closure case. Each model has
independent checks.

| Model | Formulation | Default solver |
| --- | --- | --- |
| Unit commitment and pricing | Mixed-integer clearing followed by linear pricing | SciPy with HiGHS |
| Ultimate pit limit | Maximum-weight closure | OR-Tools maximum flow |

[Decisions](docs/DECISIONS.md) records modeling choices. [Sources](docs/SOURCES.md) records
references and data provenance.

## 1. Unit commitment and pricing

For generator $g$ and period $t$, let $p_{gt}$ be output, $u_{gt}$ commitment,
$v_{gt}$ start-up, and $w_{gt}$ shut-down. With feasible unit set $X_g$, clearing is

$$
\begin{aligned}
\min \quad & \sum_{g,t}(c_g p_{gt}+n_g u_{gt}+s_g v_{gt})\\
\text{s.t.}\quad & \sum_g p_{gt}=d_t && t=1,\ldots,T,\\
& (p_g,u_g,v_g,w_g)\in X_g && g=1,\ldots,G.
\end{aligned}
$$

`_rw`, `_eq`, and `_fx` define $X_g$: output bounds, ramps, start and stop limits,
minimum up/down times, and the initial state.

`_nw` and `_tr` replace the single balance by one balance per bus, under the direct-current
and transport line models respectively.

### Price definitions

| Price | Priced problem |
| --- | --- |
| LMP | Fix the cleared commitment and price the balance equations |
| CHP | Replace each $X_g$ by its convex hull |
| AIC | Restrict losing commitment blocks to cleared output plus epsilon, then price the restricted hull |

Make-whole is computed by commitment block. Total uplift equals make-whole plus lost
opportunity.

### Solve routes

| Function | Method | Role |
| --- | --- | --- |
| `uc` | Mixed-integer rows | Clearing |
| `rx` | Continuous relaxation of the same rows | Lower bound and relaxed price |
| `en` | Enumerate joint commitments and dispatch each | Small exact check |
| `hc` | Interval-graph convex hull | Default CHP and AIC |
| `hl` | Schedule-wise disjunctive hull | Independent small-case check |
| `lmp` | Cleared commitment fixed | LMP |
| `qd` | One best self-schedule problem per unit | Lagrangian dual and lost opportunity |

`hl` applies Balas' union-of-polyhedra construction to complete schedules. `hc` represents
each on-interval by an arc in an acyclic graph. It requires $O(T^2)$ arcs instead of
$2^T$ schedules. The two formulations agree on every published case and all 104 feasible
markets among seeds 0 through 140: relative objective tolerance $10^{-9}$, price tolerance
$0.0001/MWh.

### Canonical price selection

`_px` selects one vector from the optimal dual face:

1. Minimize demand payment over the dual-optimal set.
2. Solve one no-crossover interior-point probe on the tolerance-relaxed face.
3. If the probe differs by at most $0.001/MWh, stop. Otherwise minimize each balance price
   lexicographically.

The probe is a screen, not a bound on face diameter. It is identical for capped and
uncapped models.

| Case | Payment and probe | Forced walk | Price change | Decision |
| --- | ---: | ---: | ---: | --- |
| 48 x 24 | 2.66s | 32.50s | $0.00000226/MWh | Skip |
| 96 x 24 | 6.48s | 94.82s | $0.15225/MWh | Retain |

A forced-walk scan covered 410 capped and uncapped `hc` and `hl` routes. The screen skipped
391; the largest omitted change was $0.00000444/MWh. `LIM[3]` remains the maximum number of
balance rows in the lexicographic walk. The seed-61 capped test still requires `hc` and
`hl` to return different prices while agreeing on objective and demand payment.

### Published cases

| Case | Reproduced result |
| --- | --- |
| Hua and Baldick (2017), Example 1 | Cost 1,850; LMP $50 with uplift (100, 1,900); CHP $12 with uplift (1,430, 0) |
| Hua and Baldick (2017), Example 2 | Published dispatch; LMP (60, 60, 60) with uplift (0, 560); CHP (60, 60, 65.6) with uplift (168, 0) |
| Chen, O'Neill, and Whitman (2020) | Dispatch; LMP (10, 10, 90); unit-2 profits (-1,830, -1,030, 1,170); make-whole and uplift 1,690 |

At the talk's AIC price $(10,10,146.33)$, the implementation gives profit 13,633, best
self-schedule profit 14,771, uplift 1,138, and zero make-whole. The exact restricted hull
instead gives $(10,10,422)$. Limiting unit 2 to the cleared and off schedules recovers
$146.33 exactly; the full hull also contains a start in period 2. Both `hc` and `hl` give
$422. The talk does not publish the rows needed to resolve this difference.

The talk also reports $1,161 for a three-binary relaxation without listing its valid
inequalities. This formulation gives $218.31; it is not presented as a replication.

The payment identities are tested directly:

$$
U(\pi)=z_{UC}-L(\pi), \qquad z_{CHP}=\max_\pi L(\pi).
$$

Hence CHP minimizes total uplift over uniform prices.

## 2. Ultimate pit limit

Let $B$ be the blocks, $v_b$ the net value of block $b$, and $P(b)$ the blocks that
must be removed before $b$. The model is

$$
\begin{aligned}
\max_x \quad & \sum_{b\in B} v_b x_b \\
\text{s.t.}\quad & x_b \le x_p && b\in B,\ p\in P(b),\\
& x_b\in\{0,1\} && b\in B.
\end{aligned}
$$

This is a maximum-closure problem. Picard's reduction solves it by one minimum cut.

| Function | Method | Role |
| --- | --- | --- |
| `mc` | OR-Tools maximum flow; exact integer capacities | Default |
| `mc_nx` | NetworkX minimum cut | Independent implementation of the reduction |
| `lp` | Linear programming relaxation | Independent formulation |
| `bf` | Enumeration of closed sets | Exact check for at most 20 blocks |

All routes use the same precedence array. Separate tests check arc direction, boundary
counts, closure, and economic nontriviality.

### External validation

The MineLib Newman1 fixture has 1,060 blocks and 3,922 precedence arcs. The model returns
26,086,899.025970 and the same 1,059 selected block IDs as the official solution. Its
rounded value is MineLib's 26,086,899. OR-Tools, NetworkX, and the LP agree. File hashes are
in [Sources](docs/SOURCES.md#minelib-benchmark).

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
$-\bar f_{ij}\le f_{ij}\le\bar f_{ij}$. Transport (`ntc`) imposes the limit alone, so a
flow is any vector the nodal balances admit.

| Line model | Line 0-2 limit | Bus 0 output | Bus 2 output | Cost | Price at 0 | Price at 1 | Price at 2 | Congestion rent |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dc | 100 MW | 90 | 0 | 900 | 10.00 | 10.00 | 10.00 | 0 |
| dc | 60 MW | 90 | 0 | 900 | 10.00 | 10.00 | 10.00 | 0 |
| dc | 40 MW | 60 | 30 | 2,100 | 10.00 | 30.00 | 50.00 | 2,400 |
| dc | 20 MW | 30 | 60 | 3,300 | 10.00 | 30.00 | 50.00 | 1,200 |
| ntc | 100 MW | 90 | 0 | 900 | 10.00 | 10.00 | 10.00 | 0 |
| ntc | 60 MW | 90 | 0 | 900 | 10.00 | 10.00 | 10.00 | 0 |
| ntc | 40 MW | 90 | 0 | 900 | 10.00 | 10.00 | 10.00 | 0 |
| ntc | 20 MW | 90 | 0 | 900 | 10.00 | 10.00 | 10.00 | 0 |

With equal reactances, two thirds of bus-0 injection uses the direct line under `dc`. The
40 MW limit therefore caps bus-0 output at 60 MW, and the nodal prices are $(10,30,50)$.
Under `ntc` there is no loop-flow condition, so the cheap unit reaches 90 MW at every limit
tested by routing the balance through bus 1; the network does not congest and one price
clears every bus.

Transport is a relaxation of direct current on any network carrying a cycle, and the two
coincide on a tree, where the balances determine the flows. Zonal day-ahead coupling clears
on the transport model, so `ntc` is the mode whose prices are comparable with published
zonal prices.

### Ultimate pit

| Model | Blocks | Arcs | Pit value | OR-Tools | NetworkX | LP | Fractional | Strip ratio | Ore omitted |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30x30x12 | 10,800 | 85,184 | 2,552.23 | 0.009s | 0.83s | 0.23s | 0 | 2.64 | 73 |
| 60x60x20 | 72,000 | 601,996 | 20,102.47 | 0.085s | 8.14s | 2.06s | 0 | 2.06 | 230 |
| 90x90x30 | 243,000 | 2,082,896 | 68,454.46 | 0.420s | 41.69s | 10.83s | 0 | 2.03 | 602 |

The 90x90x30 arc array uses 15.90 MiB and took 0.410s to build. The former tuple list used
270.51 MiB and took 4.454s.

## Reproduce

```text
python -m pip install -r requirements.txt
python -m pytest -q
python -m ruff check .
python -m pip check
python run_bench.py
```

Verification on 2026-09-15: 236 tests passed; Ruff and dependency checks passed; all
benchmark rows completed, including the 2,082,896-row LP.
