# Validation

Validation is divided by formulation. Agreement between two calls to the same row builder
is not treated as an independent check.

| Component | Primary check | Independent check |
| --- | --- | --- |
| Unit commitment and prices | Published cases `ex1`–`ex3`; synthetic network cases | Joint commitment enumeration; schedule and interval hulls |
| pglib-uc | Equations (1)–(24), assembled independently | Official RTS-GMLC relaxation objective |
| Storage | Sparse MIP | Signed-flow enumeration and analytical cases |
| NYISO replay | Chronological fixture runs | Settlement and energy reconstructed from exports |

## Commands

Run from the repository root:

```text
python -m pytest -q
python -m ruff check .
python -m pip check
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
