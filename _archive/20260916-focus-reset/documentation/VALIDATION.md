# Validation

Local checks on 2026-09-16, Linux 6.17.0-42, AMD Ryzen 7 PRO 6850U (16 logical CPUs).
Python 3.13.12, NumPy 2.5.3, SciPy 1.18.1, NetworkX 3.6.1, OR-Tools 9.15.6755,
pytest 9.1.1 and Ruff 0.16.7. All commands ran from the repository root.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m pip check
.venv/bin/python run_storage.py
git diff --check
```

Result after the delivery-cap change: **370 passed in 47.20 seconds** on an idle machine,
and 74.73 seconds with three annual replays running concurrently; Ruff, dependency and
diff checks passed. The required offline smoke command also passed, as did the same smoke
at `--set cap=0.25` and at `--set cap=0.0`.

The full suite includes the pglib-uc MIP at a requested 1% gap, the reference LP objective,
published pricing cases, network checks, MineLib, the independent pit routes and storage.
CI partitions ordinary and slow tests so it does not solve the full MIP twice, and runs
the study's smoke command against the committed price fixtures.

The original storage suite has 65 checks: two formulations over twenty-four seeded cases,
half of them against a fixed position the battery cannot deliver, and analytical efficiency,
duration, terminal-state, settlement, offer-versus-obligation, scenario-day-ahead-price,
information and risk cases; invalid-input, infeasibility, enumeration-limit and
solver-failure checks. The historical study has 23 more, listed below. The pglib-uc
checks now verify achieved gap and lower bound, including a renewable-only continuous case.

The delivery rule adds 21 storage checks: twelve seeded cases with a binding cap, covering
chosen and fixed positions, shared and branching nodes, unequal scenario probabilities
and three risk weights; two analytical full-delivery and infeasibility checks; four
unbounded regression checks against objectives recorded before the change; and three
invalid-cap cases. Both formulations independently enforce and audit the cap. Eight new
historical checks cover all four caps through export and a 25-hour day, refusal of a
zero-power fallback under a cap, and future-price perturbations under each finite cap.
The original `test_no_leakage` is unchanged and passes.

## Synthetic storage results

The two-period hedge has real-time curves `(10,100)` and `(10,-100)` with probabilities
`(0.8,0.2)` and day-ahead curve `(10,40)`. Neither scenario is revealed before dispatch.
The 1 MW / 1 MWh battery has unit efficiencies, no throughput cost and zero endpoints.
CVaR confidence is 0.8. Both exact routes give:

| Risk weight | Mean profit | Loss CVaR | Score | Certified score upper bound | Achieved gap |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 50 | 110 | 50 | 50 | 0 |
| 0.5 | 30 | -30 | 30 | 30 | 0 |
| 1 | 30 | -30 | 30 | 30 | 0 |

The 24-hour, eight-scenario example reveals the remaining price path at hour 13. It has
132 binary nodes and solved in 0.061 seconds: mean 344.761101, loss CVaR -316.803404,
score and upper bound 337.771677, achieved gap zero. This is an assumed information
experiment, not an out-of-sample profit measurement.

The duplication experiment uses identical prices on every path. Shared and separately
represented paths therefore have the same optimal objective. Median assembly-plus-solve
times over three warm runs, from `/tmp/emm-storage-bench.log`:

| Paths x periods | Shared binaries | Separate binaries | Shared seconds | Separate seconds | Objective difference |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8 x 24 | 48 | 216 | 0.0222 | 0.0530 | 0 |
| 32 x 24 | 48 | 792 | 0.0324 | 0.1600 | 2.84e-14 |

This demonstrates removal of duplicated decisions. It is not a general speed comparison
with DOVE, HydroBoost or an industrial trading system. Times depend on the machine and
solver version; `run_storage.py` regenerates the cases and assertions.

## Historical study

The NYISO archive was downloaded on 2026-09-15 and parsed for the N.Y.C. zone from
2022-10-01 to 2025-12-31: 28,513 day-ahead hours, all present, and 342,156 five-minute
real-time bins, of which 342,123 are present. The 33 missing bins all fall on 2025-05-27,
the one day of 1,188 the archive did not supply in full; the replay records it as skipped
and the battery holds its energy through it. Day lengths of 23, 24 and 25 hours and 276,
288 and 300 bins all occur, and prices run from -153.35 to 5,527.35 $/MWh. Eleven days
carry a real-time posting that ran more than a minute past five, 4.8 hours in total and
fifteen minutes at the longest; `run_market.py validate` lists them.

One coefficient is fitted. On 2022-10-01 to 2023-12-31, 453 days and 10,420 hourly pairs,
the hourly persistence of the residual against the analog ensemble is 0.76; refitted
through 2024-12-31, 819 days and 18,838 pairs, it is 0.73. Nineteen hours of decay leaves
0.004 of it, which is why the day-ahead decision applies no level shift.

Fifteen configurations were replayed over the validation year and the held-out year was
then replayed once per policy. Each trading policy ran 35,308 solves, every one reaching
the requested 1e-4 gap, with no held step, no coarse retry and no cold start; the largest
energy-bound violation over 105,120 settlement intervals is 3e-15 MWh and every policy
ended the year at its 2 MWh target.

| Policy | Net | 2.5% | 97.5% | Delivered energy | Spread | Worst day | Cycles | Solver seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No trading | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Deterministic forecast | 41,178 | 17,571 | 73,907 | 28,357 | 12,821 | -917 | 362 | 725 |
| Risk neutral | 33,131 | 9,182 | 65,272 | 26,573 | 6,558 | -2,955 | 373 | 1,919 |
| CVaR | 31,983 | 6,365 | 64,947 | 26,180 | 5,803 | -4,274 | 362 | 1,686 |
| Perfect foresight | 190,720 | 138,858 | 256,192 | 89,522 | 101,198 | 0 | 442 | 475 |

Settlement was rebuilt from each run's own interval rows, by a path that shares nothing
with the replay's arithmetic: metrics, daily rows and intervals agree to the cent on all
five runs, and stored energy recomputed from the dispatch matches the exported trajectory
to 2e-5 MWh over 105,120 intervals. [The study](MARKET.md) reports the search, the tails,
the concentration and what the numbers do not establish; `docs/results/` holds the
exported evidence.

The delivery-cap sensitivity replayed twelve settings, three policies at four caps.
Eleven completed; `neutral` at a 0.25 MW cap stopped on 2025-12-15 with an infeasible
capped dispatch, which is the outcome decision 52 specifies and is reported rather than
dropped. `run_delivery.py audit` reruns the checks: on the eleven completed runs
settlement rebuilt from the interval export agrees with the reported total to $0.006,
stored energy to 4.2e-5 MWh, and no dispatch exceeds its cap. The three unbounded replays
reproduce the original study exactly, every metric differing by zero, which is the
regression check that `cap=None` adds no rows. Thirteen days report a raw relative MIP gap
above the requested 1e-4, the largest 0.226; those days were re-solved and on the twelve
solves concerned the full score and its certified bound differ by at most 1.2e-14, the
near-zero variable objective described in [trading](TRADING.md) rather than an unconverged
solve. No solver setting was changed and no reported ratio was replaced.

## Optional DOVE comparison

The reviewed DOVE checkout is `b9fd260bd0d0`. Only this comparison needs Pyomo and highspy;
they are not in runtime requirements. It ran with Pyomo 6.10.1 and highspy 1.15.1.

```bash
.venv/bin/pip install pyomo highspy
PYTHONPATH=/home/yeal/idaholab/DOVE/src .venv/bin/python run_storage.py --dove
```

| Hourly prices | DOVE profit | Storage MIP profit | Check |
| --- | ---: | ---: | --- |
| `(10,100)` | 71 | 71 | 1 MW / 1 MWh, 0.81 round-trip efficiency, zero endpoints |
| `(-100)` | 19 | 0 | DOVE charges 1 MW and discharges 0.81 MW simultaneously; MIP excludes it |

These results use DOVE's unchanged rows. HydroBoost was inspected as a formulation
reference, not run end to end for this review. Existing INL workspace test
claims were not relabelled as new executions.

## Preserved evidence

The [earlier Windows tables](../_archive/20260915-inl-review/benchmarks.md) retain their
original solver versions and date. The larger `run_bench.py` and `run_face_scan.py` runs
were not repeated for this storage change; their underlying pricing regressions passed.
No benchmark timing or prediction result is inferred from the INL projects' reputations.
