# Validation

Local checks on 2026-09-15, Linux 6.17.0-42, AMD Ryzen 7 PRO 6850U (16 logical CPUs).
Python 3.13.12, NumPy 2.5.3, SciPy 1.18.1, NetworkX 3.6.1, OR-Tools 9.15.6755,
pytest 9.1.1 and Ruff 0.16.7. All commands ran from the repository root.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m pip check
.venv/bin/python run_storage.py
git diff --check
```

Result: **297 passed in 29.38 seconds**; Ruff, dependency and diff checks passed.

The full suite includes the pglib-uc MIP at a requested 1% gap, the reference LP objective,
published pricing cases, network checks, MineLib, the independent pit routes and storage.
CI now partitions ordinary and slow tests so it does not solve the full MIP twice.

Storage has 44 checks: two independent formulations over twelve seeded cases and
analytical efficiency, duration, terminal-state, settlement, information and risk cases;
invalid-input, infeasibility, enumeration-limit and solver-failure checks. The pglib-uc
checks now verify achieved gap and lower bound, including a renewable-only continuous case.

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
132 binary nodes and solved in 0.056 seconds: mean 344.761101, loss CVaR -316.803404,
score and upper bound 337.771677, achieved gap zero. This is an assumed information
experiment, not an out-of-sample profit measurement.

The duplication experiment uses identical prices on every path. Shared and separately
represented paths therefore have the same optimal objective. Median assembly-plus-solve
times over three warm runs, from `/tmp/emm-storage-bench.log`:

| Paths x periods | Shared binaries | Separate binaries | Shared seconds | Separate seconds | Objective difference |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8 x 24 | 48 | 216 | 0.0215 | 0.0512 | 0 |
| 32 x 24 | 48 | 792 | 0.0304 | 0.1561 | 2.84e-14 |

This demonstrates removal of duplicated decisions. It is not a general speed comparison
with DOVE, HydroBoost or an industrial trading system. Times depend on the machine and
solver version; `run_storage.py` regenerates the cases and assertions.

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
