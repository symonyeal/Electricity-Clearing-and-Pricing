# Design decisions

## Standards

| Decision | Reason |
| --- | --- |
| Use a published formulation and state every restriction. | A solver result cannot validate an unstated model. |
| Retain an independent formulation or external benchmark. | Two solvers on one matrix share its errors. |
| Compare objective values when optima are nonunique. | A dual-optimal face need not determine one price vector. |
| Report achieved gaps and bounds. | A requested tolerance is not a result. |
| Ask the reference clearings for a zero gap and read back the gap achieved. | HiGHS stops at 1e-4 by default, so "opt" without a read-back reports a tolerance nobody checked. |
| Build a dual bound from the solver's bound, never from its incumbent. | An incumbent can understate a subproblem optimum and carry the reported dual past the primal. |
| Name a failed solve by the solver's own status. | Bad data and an infeasible program both end in a failure; calling both infeasible is right once. |
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

## Joint and stochastic clearing

| Decision | Reason |
| --- | --- |
| Clear storage in the balance rather than replay it against a price. | A resource large enough to matter moves the price it settles at. |
| Import uc_price's unit, network and price-selection routines. | A market with no storage must clear exactly as it did. |
| Carry the mode hull cut $c/C+d/D\le1$ as its own row. | It is what the mode rows leave when the binary is relaxed. |
| Do not claim the cut is the hull of the whole resource. | The state-of-charge rows couple periods the cut treats separately. |
| Make the commitment common and the dispatch per scenario. | That is the decision the day-ahead market takes. |
| Divide the scenario probability out of the balance dual. | A weighted row has a weighted dual, which is not a price. |
| Check the stochastic optimum against WS and EEV. | Both bounds are theorems, and both are computed by another module. |

## Market interface

| Decision | Reason |
| --- | --- |
| Default to full acceptance at no charge with every resource admitted. | It is the replay's own assumption, and the baseline must not move. |
| Supply the curve, the charge and the screens as parameters. | Calibrating them needs a tariff, which is a different kind of work. |
| Screen qualification before the first solve. | An ineligible resource has no result worth computing. |
| Charge `tar` in settlement and leave it out of the optimizing objective. | The charge is an ex-post stress test of a policy chosen without it; pricing it in is a calibration question, not a correction, and is open work. |
| Require a whole, finite step count, spread, rate and screen threshold. | A nan passes a sign test, turns a screen into one that cannot refuse, and fails later somewhere that does not name the configuration. |

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
| Align an analog day to its target by local clock hour and fold. | A price shape belongs to the clock; by array position every hour past a transition slides by one. |
| Skip and record incomplete days; do not fill prices. | Imputation would add an untested data model. |
| Apply a two-bin real-time information lag. | A decision must not read its settlement interval. |
| Fit on training data, select on 2024, and evaluate the frozen policies on 2025. | This separates estimation, selection, and evaluation. |
| Reconstruct settlement from exported interval rows. | The audit does not share the replay arithmetic. |
| Permit a zero-power fallback only when `cap=None`. | Zero power can violate a finite delivery band. |
| Report the delivery band as a sensitivity, not a second evaluation. | It reuses 2025; only the assumption changes. |

## Open work

1. Calibrate `market/bid.py` to one market's published tariff and qualification manual.
   The mechanism is implemented; the parameters are not anyone's.
2. Price `tar` inside the policy rather than after it. Today the optimizing battery carries
   throughput cost `kd + fee`, so a run at `tar > 0` takes the schedule it would have taken
   at `tar = 0` and pays the charge afterwards; a large enough rate therefore makes the
   selected trade lose money, and `arb` in `market/report.py` reconciles only at `tar = 0`.
   The work is to put `tar` into `_bat(...).k`, give the report identity its own tariff
   component, and add a high-rate no-trade regression. It is deliberately not bundled with
   item 1: moving a cost into the objective changes which trades a policy takes, so it
   changes every result it touches and belongs with the calibration that gives the rate a
   number, not before it. [Market interface](MARKET.md) states the current boundary.
3. A convex hull price for the joint feasible set. Today the joint and stochastic clearings
   pin the integers, so the nonconvexity is left as make-whole.
4. A multi-stage scenario tree. The stochastic clearing branches once.
5. Ramping and reserve carried between scenarios, and a reserve product in `uc_price`.

Superseded decisions and the out-of-scope pit model are in the
[dated archive](../_archive/20260916-focus-reset/README.md).
