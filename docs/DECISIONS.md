# Decisions and remaining work

[Validation](VALIDATION.md) contains current checks. [Sources](SOURCES.md) contains
references and data provenance. [INL assessment](INL.md) records the local project review.

## Model standards

1. Use at least two exact solve routes.
2. Prefer independent formulations to multiple solvers on one formulation.
3. Compare objective values when optima are nonunique.
4. Test against published results and state every difference.
5. Label synthetic data and test its intended property.
6. Add a dependency only after measurement on the implemented model.
7. Implement a published formulation and name it. Where an open implementation of that
   formulation exists, cite it too, and state what this model restricts or omits.
8. Keep the existing Python register: mathematical names with a legend, small functions,
   direct sparse formulations, and no framework layer without a measured need.
9. Separate formulation exactness, the achieved solver gap and uncertainty in the inputs.

## Ultimate pit

| ID | Decision | Reason |
| ---: | --- | --- |
| 1 | Use Picard's maximum-closure reduction. Positive values connect from the source; negative values connect to the sink; precedence arcs point from a block to its required predecessor. | One minimum cut gives an exact solution. |
| 2 | Use OR-Tools 9.15.6755 in `mc`; retain NetworkX in `mc_nx` and SciPy in `lp`. | OR-Tools was fastest; the other routes remain checks. |
| 3 | Scale values exactly to signed 64-bit integer capacities. Set each precedence capacity to the sum of positive capacities plus one. | Scaling preserves the ordering of pits; no optimum can cut a precedence arc. |
| 4 | Set ore value to revenue minus processing and mining cost; set waste value to negative mining cost. | Every removed block incurs mining cost. |
| 5 | Store precedence arcs once in a two-column `int32` array. | All solvers use the same compact representation. |
| 6 | Limit `bf` to 20 blocks. | It enumerates closed sets and serves only as small-instance ground truth. |
| 7 | Test geometry directly. | Solver agreement cannot detect a shared error in the precedence array. |

## Unit commitment and pricing

| ID | Decision | Reason |
| ---: | --- | --- |
| 8 | Define unit feasibility once in `_rw`, `_eq`, and `_fx`. Read it algebraically in `uc`, `rx`, and `qd`; read schedule polytopes through `_pl` in `hl` and `en`. | The two representations provide an independent formulation check. |
| 9 | Impose separate start-up and shut-down output ceilings. | A combined row can exclude feasible one-period runs. |
| 10 | Build `hl` with Balas' union-of-polyhedra formulation. | It is the exact convex hull of the schedule polytopes. |
| 11 | Among dual-optimal prices, first minimize demand payment. | This selects the lower slope at a cost kink. |
| 12 | Compute each unit's best self-schedule with one integer program in `_om`. | Payments and dual values then have no schedule-enumeration limit. |
| 13 | Compute make-whole by commitment block; define lost opportunity as uplift minus make-whole. | The AIC restriction is block-specific. |
| 14 | Retain the exact AIC value $422 for `ex3`. Recover $146.33 only when unit 2 is limited to the cleared and off schedules. | The published talk omits the rows required to obtain its value from the full restricted hull. |
| 15 | Treat the $38.4 million AIC uplift as a corner case. | Only 3 of 15 seeded 10 x 8 markets have peak prices above $1,000/MWh. Depleted capped headroom occurs in 6 and is not sufficient. |
| 16 | Use the interval-graph hull `hc` by default; retain the schedule hull `hl`. | `hc` has $O(T^2)$ arcs; `hl` has $2^T$ schedules. They agree within stated tolerances on all 104 feasible markets among seeds 0 through 140. |
| 17 | Impose dual feasibility as an equality. | An inequality admits false prices when a primal variable, such as a voltage angle, is free. |
| 18 | After payment minimization, apply one no-crossover interior-point probe. Skip the lexicographic walk when its price distance is at most $0.001/MWh. Do not branch on output ceilings. | In 410 routes, 391 were skipped; the largest omitted change was $0.00000444/MWh. Materially wide faces retain the original walk. |
| 19 | Preserve the capped seed-61 disagreement between `hc` and `hl`. | Both prices are dual-optimal and have equal demand payment; the optimal face is not numerically resolved to one point. |
| 20 | Add network equations once in `_nw` and use them in every solve route. | A one-bus market is the same model with no lines. |
| 24 | Offer two line models on the same `Net`. `dc` keeps the reactance and imposes $f_{ij}=(\theta_i-\theta_j)/x_{ij}$ with a symmetric limit. `ntc` drops the reactance and gives each exchange a capacity pair keyed by its two zones in ascending order, bounding the signed flow from the first to the second. | A day-ahead market clears by zone. Without the zonal model no price this repository computes is comparable with a published one. |
| 25 | Take the exchange record from electricity maps unchanged: ascending zone key, one $[\underline c,\bar c]$ pair, zone keys carried on the network. | Published transfer capacity is directional and asymmetric; `NO-NO1_NO-NO2` is $[-3500, 2200]$. A single symmetric limit cannot express it, and would have priced the wrong market in one direction. |

Proposition 3 of Chen, O'Neill, and Whitman applies only to restricted commitment blocks as
epsilon tends to zero. It does not guarantee zero make-whole on unrestricted blocks.

Every price here is read off one clearing, solved to the solver's default optimality gap.
Yang, Knueven, Watson and Ostrowski report that the choice among near-optimal commitments
changes generator revenue across pricing schemes. That is a property of the primal, and it
is not measured here; decision 19 concerns the dual face of a fixed clearing, which is a
different thing.

## Shared decisions

| ID | Decision |
| ---: | --- |
| 21 | Keep `models/__init__.py`; do not rely on an implicit namespace package. |
| 22 | Declare Ruff in `requirements.txt`. |
| 23 | Record only checked sources. The source register was last checked on 2026-09-15. |
| 26 | Build the pglib-uc formulation in its own module, from its own rows, rather than widening `U` and the hull routes to carry piecewise costs and start-up tiers. The two formulations differ in what the output variable means, and `hl` and `hc` would each need their convex hull re-derived for a piecewise cost before they could price one. An independent route is also the clean-room oracle the shared-row structure lacks. |
| 27 | Gate the benchmark on the linear relaxation, not the integer objective. At the reference script's 1% gap the returned incumbent is not determined, so an equality there would assert the solver's search order. The relaxation is determined and every piecewise point, start-up category and row enters it. |
| 28 | Refuse an instance field the model does not read. A loader that keeps the first piecewise point and the first start-up category still solves and still reports a number; that number is not the benchmark's. |
| 29 | Report pglib-uc's achieved MIP gap and lower bound. Use status `gap` when the achieved gap is positive, `opt` when it is zero. The stopping tolerance is not a result. |

## Storage trading

| ID | Decision | Reason |
| ---: | --- | --- |
| 30 | Use the HydroBoost storage balance and exclusive binary modes, restricted to energy trading. | Negative prices can reward simultaneous cycling in a continuous relaxation. |
| 31 | Use one physically feasible forward schedule and scenario-dependent real-time deviations. | Settlement must count forward energy once and prevent unsupported forward positions. |
| 32 | Share columns by information node, with no revelation by default. | This enforces nonanticipativity and reduces duplicate variables. |
| 33 | Use Rockafellar-Uryasev CVaR of loss and independently compute the weighted tail. | Handles unequal probabilities and probability atoms; risk reporting remains valid at zero risk weight. |
| 34 | Check the MIP with enumerated signed-flow LPs and cumulative energy bounds. | Independent physical formulation, bounded to 12 nodes for tractability. |
| 35 | Keep the INL tools as formulation references and optional checks. | No measured benefit justifies adding their frameworks to runtime requirements. |

## Historical study

[The study](MARKET.md) states the protocol; these are the decisions behind it.

| ID | Decision | Reason |
| ---: | --- | --- |
| 36 | Separate a chosen offer from a contracted position. `q=None` builds a nominal physical path, so an offer must be deliverable. A supplied `q` builds none: its terms enter each scenario's profit as a constant and only the scenario paths carry physical rows. | After a real-time deviation the battery no longer holds the energy the schedule was planned from. Requiring an existing obligation to be reproducible from current energy reports a false infeasibility for a position that simply settles. |
| 37 | Accept one day-ahead curve per scenario. | The position is chosen before the day-ahead market clears, so its price is not known then. One curve per scenario also keeps each scenario's day-ahead and real-time curves the pair that actually occurred. |
| 38 | Take the NYISO archive unchanged. Resolve the repeated hour of the autumn transition by order of appearance, and refuse a local time that does not exist. | The files carry eastern prevailing time with no offset column. Order is the only information that separates the two passes, and a silent reinterpretation of a missing hour would move prices by an hour. |
| 39 | Weight each real-time posting by the seconds it covers inside its five-minute bin. | The dispatch reruns inside a clock interval and posts irregular stamps. Duration weighting is exact when the battery holds one power level across the bin, which the decision cadence guarantees. |
| 40 | Decide every fifteen minutes; settle every five. | A decision cadence coarser than settlement is a restriction on the policy, not an information advantage, so it cannot flatter the measured result. |
| 41 | Build scenarios from realized days and fit exactly one coefficient, the hourly persistence of the residual. | Realized days carry their own within-day shape and their own joint day-ahead and real-time curves. One fitted coefficient keeps the statistical layer inspectable and separate from the optimizer. Model standard 6. |
| 42 | A tree node is a set of paths, and a node is split only when it has at least twice the smallest node size. | A unique label would reveal an entire future path to a decision taken before it. |
| 43 | One end-of-day energy target for every trading policy, clipped to the interval reachable from current energy. | It makes the day-ahead offer deliverable from a known starting energy, keeps every real-time solve feasible, and is identical across policies, including perfect foresight. |
| 44 | A day the archive did not supply in full is skipped and recorded, never filled or dropped. | A filled price is a modelling assumption disguised as data; a dropped day is a silent selection. |
| 45 | Choose hyperparameters on the validation year only, refit the coefficient before each evaluation period, and replay the held-out year once. | Selection on the evaluated period is the leak that makes a backtest meaningless. |
| 46 | Report a moving block bootstrap interval; report no return on investment or Sharpe ratio. | Daily results are dependent, so an independent resample understates the interval. There is no defensible capital base here for a ratio. |
| 47 | Write figures directly as SVG. | No implemented result needs a plotting framework, and the figures stay reproducible byte for byte. Model standard 6. |
| 48 | Keep continuous integration offline against committed fixtures, rebuilt from the archive by a committed script. | A test that depends on a market website is a test of the website. |
| 49 | On a solve that does not reach its tolerance, retry once at a coarse gap, then hold power at zero for the step. Record every outcome. | Holding is always feasible and is an action the operator could take. A discarded difficult step would quietly remove the hardest days from the result. |

## Remaining work

1. Market-specific storage participation: the New York energy storage resource model,
   bid parameters, ISO dispatch and the charges listed in [the study](MARKET.md). The
   timestamped out-of-sample evaluation now exists for one zone and one held-out year;
   acceptance, dispatch and settlement under the real participation model do not.
2. Energy and reserve pricing for the full pglib-uc formulation, then exact hull pricing
   with piecewise costs and start-up tiers. Fixed-commitment pricing alone does not require
   a hull re-derivation. The current benchmark still clears without pricing.
3. Reserve deliverability and joint storage/UC clearing; losses and network contingencies.
4. Stochastic or robust clearing over demand and wind scenarios. The implemented storage
   scenarios are exogenous price scenarios, not stochastic system clearing.

The broader optimization sequence and former Windows tables are in the
[archive](../_archive/20260915-inl-review/README.md). Independent pit formulations remain
active checks; model differences and numerical pricing limitations remain documented.

## Rejected alternatives

| Alternative | Reason |
| --- | --- |
| One solve route | It cannot detect a wrong formulation. |
| Original 1965 pit graph procedure | Picard's reduction already has three independent checks. |
| Subgradient CHP search | Hua and Baldick report 0.88% suboptimality after 550 iterations; the LP is exact. |
| Pit metaheuristic | It cannot improve an exact minimum-cut solution. |
| Neural dependency | No implemented model requires it. |
| Fitted day-ahead price forecasting in the solver | Forecast fitting is a separate statistical task. It now lives in `market/scen.py`, is fitted only on data that precedes each decision, and is measured out of sample; the optimizer still receives scenarios as inputs. |
| Live price and generation feeds | An API key and a network dependency, with no implemented model measuring better for either. The study reads a published archive of settled prices, offline after one fetch, which is a different thing. |
| Filling a missing interval to keep a day tradable | A filled price is an assumption presented as a measurement. Incomplete days are skipped and counted. |
| Warm-started price walk | The prototype erased the required seed-61 price difference without proving closure of the face. |
| Unreviewed reading-list entries | A title is not evidence. |
| Synthetic inputs without a tested property | A benchmark must state what it is designed to exhibit. |
