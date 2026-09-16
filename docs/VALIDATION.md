# Validation

Validation is divided by formulation. Agreement between two calls to the same row builder
is not treated as an independent check.

| Component | Primary check | Independent check |
| --- | --- | --- |
| Unit commitment and prices | Published cases `ex1`–`ex3`; synthetic network cases | Joint commitment enumeration; trajectory and interval hulls |
| Hull formulation sizes | Deterministic `run_bench.py sizes` report | Variable-count and enumeration-ceiling tests |
| pglib-uc | Equations (1)–(24), assembled independently | Official RTS-GMLC relaxation objective |
| Storage | Sparse MIP | Signed-flow enumeration and analytical cases |
| NYISO replay | Chronological fixture runs | Settlement and energy reconstructed from exports |
| Joint clearing | Seeded markets and arithmetic cases | The same markets cleared by `uc_price` |
| Stochastic clearing | Seeded scenarios | The wait-and-see and mean-value bounds, from `joint` |
| Market interface | Curve arithmetic by hand | The baseline replay, which its defaults must reproduce |

## Commands

Run from the repository root:

```text
python -m pytest -q
python -m ruff check .
python -m pip check
python run_bench.py sizes
python run_storage.py
git diff --check
```

The pglib-uc MIP test is marked `slow`. Its acceptance criterion is the achieved bound and
gap, not the requested stopping tolerance.

## Pricing

The small unit-commitment model is checked against three published cases. The integer
program and joint enumeration agree on ten seeded markets. The compact interval hull and
the schedule hull agree on every feasible instance among seeds 0 through 140: relative
objective tolerance $10^{-9}$ and price tolerance $10^{-4}$/MWh. A capped case also checks
hull value and demand payment when the price coordinates are not uniquely determined.

`python run_bench.py sizes` reproduces the decomposition-size table from the seed-7
synthetic markets. It reports graph arcs and actual LP variables separately for `hc`, and
feasible commitment trajectories and actual LP variables for `hl`. Tests pin the counting
rule, the 100,000-variable `hl` boundary, and the loss of full-hull dual feasibility when a
restricted trajectory set happens to retain the same primal objective.

DC and directional-NTC cases check uncongested reduction, congestion, loop flow, exchange
direction, and malformed networks. The full pglib-uc formulation reproduces the official
RTS-GMLC relaxation objective to relative tolerance $10^{-9}$.

## Storage

The MIP and signed-flow formulation are compared on 24 seeded cases with chosen and fixed
positions. Twelve additional seeded cases impose a binding deviation band. Tests cover
unequal probabilities, shared and branching information nodes, three risk weights,
full-delivery feasibility, fixed-position infeasibility, and `cap=None` regression values.

Analytical cases check efficiency loss, negative prices, terminal energy, two-settlement
accounting, scenario-dependent day-ahead prices, nonanticipativity, and discrete CVaR.
Failure tests cover invalid inputs, infeasibility, enumeration limits, and solver status.

## Joint and stochastic clearing

With no resource the joint program reproduces `uc_price` on seeded markets: cost to
relative $10^{-9}$, dispatch to $10^{-6}$ MW, locational price to $10^{-4}$/MWh. A lossless
20 MW battery moving energy from a 20/MWh period to an 80/MWh period lowers the clearing by
exactly 1,200. A 40 MWh battery behind a 5 MW line delivers 20 MWh rather than 40, and the
clearing rises from 2,300 to 2,700. Charge and discharge never run together, and stored
energy follows its recursion to $10^{-9}$ MWh.

The stochastic clearing reproduces the joint clearing on one scenario of probability one,
cost and price. On seeded scenarios it satisfies $\text{WS}\le\text{SP}\le\text{EEV}$,
both bounds computed with `models/joint.py`; on the instance in the tests the expected value
of perfect information is 900 and the value of the stochastic solution is 2,680. The
reported CVaR is checked against an independently weighted tail of the scenario costs.

## Market interface

Offer curves, the metered charge and the qualification screens are checked against the
slices by hand. The load-bearing check is that the defaults change nothing: `bk = 0`,
`tar = 0`, `qmin = 0` and `qdur = 0` reproduce the baseline replay's positions and flows
exactly.

## Historical replay

Committed NYISO fixtures cover ordinary and daylight-saving days. Tests check timestamp
conversion, subhourly weighting, missing-data treatment, information cutoffs, fallback
rules, settlement, energy conservation, figures, exports, and three-policy report
generation. They run without network access.

The committed 2025 result bundles are evidence from the recorded revisions, not a result
of the local test command. Their metrics, daily rows, configurations, and coverage report
remain under [`docs/results/`](results/README.md). Interval exports and source archives are
not committed; a fresh checkout must reacquire the NYISO files to repeat the full annual
reconciliation.

The delivery band is replayed over the same year by `run_delivery.py`; its runs are checked
against their own interval exports and recorded in
[`docs/results/delivery/`](results/delivery/README.md).

The former benchmark tables and the completed local-code review are preserved in the
[dated archive](../_archive/20260916-focus-reset/README.md).
