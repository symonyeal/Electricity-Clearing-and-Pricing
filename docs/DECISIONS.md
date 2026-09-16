# Design decisions

## Standards

| Decision | Reason |
| --- | --- |
| Use a published formulation and state every restriction. | A solver result cannot validate an unstated model. |
| Retain an independent formulation or external benchmark. | Two solvers on one matrix share its errors. |
| Compare objective values when optima are nonunique. | A dual-optimal face need not determine one price vector. |
| Report achieved gaps and bounds. | A requested tolerance is not a result. |
| Label synthetic data and its tested property. | A synthetic result has no empirical interpretation without one. |
| Add dependencies only after measurement. | The live models require no framework layer. |

## Unit commitment and pricing

| Decision | Reason |
| --- | --- |
| Keep the small pricing formulation in `uc_price.py`. | Its explicit hulls compute LMP, CHP, and AIC for the stated unit class. |
| Keep the full pglib-uc formulation in `pglib_uc.py`, with independent rows. | Piecewise costs, start-up tiers, and reserve change the formulation; separate rows also test the shared-row pricing model. |
| Reject unread pglib-uc fields. | Silent truncation can return a plausible value for a different instance. |
| Use the pglib-uc relaxation as the equality gate. | The LP optimum is determined; a 1% MIP incumbent depends on search order. |
| Use the interval hull `hc` by default and retain the schedule hull `hl`. | `hc` has $O(T^2)$ arcs; `hl` is an independent exact check on small cases. |
| Impose dual feasibility as equality. | An inequality admits false prices when a primal variable is free. |
| Minimize demand payment, probe the optimal face, then walk prices if needed. | The rule selects a reproducible point without walking a numerically closed face. |
| Compare hull value, demand payment, and uplift before price coordinates. | Distinct price vectors may lie on the same optimal face. |
| Retain the exact AIC value $422 for `ex3`. | Both exact hulls give $422; $146.33 follows only after removing a feasible schedule not excluded by the source. |
| Keep DC and NTC networks distinct. | DC flow uses reactance; zonal transport uses directional exchange bounds. |

## Storage

| Decision | Reason |
| --- | --- |
| Exclude simultaneous charge and discharge with binary modes. | A continuous relaxation can cycle at negative prices. |
| Count the forward position once and settle real-time deviations. | This is the two-settlement identity used by the model. |
| Require a chosen position to have a feasible nominal path. | The model may not offer energy outside the battery limits. |
| With fixed `q` and `cap=None`, treat `q` as a contract term only. | Current physical dispatch adapts around the obligation. |
| With finite `cap`, constrain dispatch around fixed `q`. | The contract may then be infeasible; `cap=0` requires delivery. |
| Share variables by information node. | This enforces nonanticipativity without duplicate equality rows. |
| Check the MIP with signed-flow enumeration. | The check has no state-of-charge variables or charge/discharge row builder. |
| Compute loss CVaR by the Rockafellar–Uryasev epigraph and an independent weighted tail. | Probability atoms and unequal scenario weights are explicit. |

## Historical replay

| Decision | Reason |
| --- | --- |
| Preserve NYISO archives and parse local timestamps to UTC. | Transition days contain 23 or 25 hours. |
| Skip and record incomplete days; do not fill prices. | Imputation would add an untested data model. |
| Apply a two-bin real-time information lag. | A decision must not read its settlement interval. |
| Fit on training data, select on 2024, and evaluate the frozen policies on 2025. | This separates estimation, selection, and evaluation. |
| Reconstruct settlement from exported interval rows. | The audit does not share the replay arithmetic. |
| Permit a zero-power fallback only when `cap=None`. | Zero power can violate a finite delivery band. |
| Report the delivery band as a sensitivity, not a second evaluation. | It reuses 2025; only the assumption changes. |

## Open work

1. Market-specific storage bids, ISO dispatch, tariffs, and qualification rules.
2. Energy and reserve prices for the full pglib-uc formulation.
3. Joint storage and unit-commitment clearing with network deliverability.
4. Stochastic or robust system clearing. Storage price scenarios are exogenous.

Superseded decisions and the out-of-scope pit model are in the
[dated archive](../_archive/20260916-focus-reset/README.md).
