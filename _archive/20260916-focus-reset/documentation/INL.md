# Local INL project assessment

Reviewed on 2026-09-15 in `/home/yeal/idaholab`. The table records the checked local
revisions, not a claim about the latest upstream release. READMEs, the workspace run notes,
and the relevant implementation files were read. Existing local modifications were retained.

The useful immediate combination is HydroBoost's physical storage formulation, LOGOS's
CVaR formulation and DOVE as an external dispatch check. `models/storage.py` implements
the restricted model directly in SciPy. No INL package became a runtime dependency.

| Project / local revision | Applicable work | Decision |
| --- | --- | --- |
| HydroBoost `a7bea5eb05ae` | Battery mode binaries, energy balance, hydro and ancillary service constraints, rolling horizons | Adopt the energy/mode equations for a single battery. Keep hydro, reservoirs and reserve products for a measured extension. Its Julia/JuMP workflow is not a drop-in speed improvement for this SciPy model. |
| DOVE `b9fd260bd0d0` | Multi-resource price-taking dispatch and storage | Use as an optional independent hourly check. Its storage relaxation permits simultaneous charging and discharging; the negative-price counterexample below prevents treating it as equivalent to the MIP. |
| LOGOS `5a09f888535a` | CVaR, stochastic and distributionally robust capital budgeting; scheduling | Adopt the published mean/CVaR construction. Knapsack and maintenance constraints serve different decisions; importing its PySP machinery is unnecessary for this small extensive formulation. |
| ORCA `409c415b53c4` | State-space model predictive control with a next-dispatch interface | Reuse the rolling-operation pattern when measured plant dynamics are supplied. Its LTI controller is not unit commitment or a storage market formulation. |
| HERON `6037659d9815` | Dispatch nested inside capacity and economic optimization | Useful later for battery sizing and integrated-energy portfolios. Its storage balance and periodic endpoint corroborate the physical convention. Keep the current exact pricing routes. |
| TEAL `463f1d4eef84` | Taxes, inflation, depreciation, NPV, IRR and project lifetimes | Useful after dispatch cash flows have been validated, for asset investment analysis. It does not accelerate clearing or compute market prices. |
| RAVEN `01216937967c` | Scenario generation, uncertainty propagation, sensitivity studies and external-model runs | A possible outer experiment runner. Correlated scenarios need timestamp and information-tree validation; sampled or fitted outputs are not exact optimization certificates. |
| FORCE `5c439957305a` | Integration of HERON, TEAL, plant models and datasets | Useful for a larger engineering study. Duplicate pinned frameworks and XML workflows add no measured benefit to the present models. |
| POEM `8784991fd3e4` | RAVEN experiment design, calibration and Bayesian optimization | Useful for expensive outer simulations. Its surrogate optimization does not replace the exact MIP, hull or minimum-cut routes. Separate environment required by its local Python pins. |
| EMRALD `22ce3cee5fbe` | Event-based reliability and outage sequences | Possible future outage-scenario source. No immediate model coupling; its UI and simulation engine do not solve electricity clearing. |
| CMIP `348516d5f935` | Charger siting and vehicle assignment IP in CPLEX Concert | Reference for a future facility-location problem. Different objective and asset model; no present reuse. |
| STEM `8b1ecb6e32f5` | Archived biomass logistics techno-economic workbook | No present use. A spreadsheet cost model supplies neither market clearing nor an independent trading oracle. |
| `starters/` | Small local run examples, including DOVE, ORCA and TEAL | Used to understand callable interfaces. The fixtures are demonstrations, not market data. |

## Code evidence

- HydroBoost: [`HydroBoost_Model_C.jl`](https://github.com/idaholab/HydroBoost/blob/a7bea5eb05ae/Core_Models/HydroBoost/src/model_structure/HydroBoost_Model_C.jl),
  `HydroBoost_constraint_ES_SOC_Balance_Inter_Hour_iht`,
  `HydroBoost_constraint_ES_power_Bounds_UP_iht` and
  `HydroBoost_constraint_ES_charge_Bounds_UP_iht`. The two power limits use opposite
  binary modes. This file has no local diff at the reviewed revision.
- DOVE: [`rulelib.py`](https://github.com/idaholab/DOVE/blob/b9fd260bd0d0/src/dove/models/price_taker/rulelib.py),
  `storage_balance_rule`, `charge_limit_rule`, `discharge_limit_rule`,
  `periodic_storage_rule`; and [`builder.py`](https://github.com/idaholab/DOVE/blob/b9fd260bd0d0/src/dove/models/price_taker/builder.py),
  `_add_variables`. Charge and discharge are separate nonnegative variables with no
  exclusive storage mode. Efficiencies are the square root of round-trip efficiency.
- LOGOS: [`CVaRSKP.py`](https://github.com/idaholab/LOGOS/blob/5a09f888535a/src/CapitalInvestments/PyomoModels/CVaRSKP.py),
  `computeFirstStageCost`, `computeSecondStageCost`, `cvarConstraint`. The weighted
  expected-profit/CVaR objective is transferable; its capital-budgeting rows are not.
- ORCA: [`LTIStateSpaceMPCPyomoOptimization.py`](https://github.com/idaholab/ORCA/blob/409c415b53c4/ORCA/Optimization/LTIStateSpaceMPCPyomoOptimization.py).
  HERON: [`PyomoRuleLibrary.py`](https://github.com/idaholab/HERON/blob/6037659d9815/src/dispatch/PyomoRuleLibrary.py),
  `level_rule` and `periodic_level_rule`.

The implementation was written from the mathematical relationships and these references;
no upstream implementation was vendored. This preserves the local register: Python,
short mathematical names with a legend, small functions, sparse rows and independent checks.

## What makes it better or faster

The storage MIP gives physical decisions under negative prices, a specified information
structure and an auditable downside-risk objective. An independent cumulative-energy
formulation checks its optimum. Results include the achieved gap and objective bound.

Sharing variables by information node avoids duplicate scenario decisions and equality
rows. In the measured synthetic 32-path, 24-period duplication check, 48 binaries replace
792 and yield the same objective. [Validation](VALIDATION.md) records timings and scope.
No evidence here establishes a speed benefit from replacing HiGHS with another solver or
from importing a full INL framework.

DOVE agrees at 71 on an hourly 1 MW / 1 MWh battery with prices `(10,100)`, round-trip
efficiency 0.81 and zero endpoints. At price `-100` for one cyclic period it earns 19 by
charging 1 and discharging 0.81 simultaneously. The physical MIP and enumeration both
return zero. `run_storage.py --dove` reproduces both using the local DOVE checkout.

## Path forward

1. Use the implemented storage formulation and its explicit bounds for scenario valuation.
   Select the actual market and asset before adding bid formats or settlement rules.
2. Validate timestamped price scenarios and information labels on held-out days; freeze
   offers before evaluating realized outcomes. ORCA supplies a useful execution pattern;
   RAVEN can supply outer scenario studies. Neither removes forecast error.
3. Extend to reserve products or hydro only with their energy-deliverability and operating
   constraints. HydroBoost is the strongest local reference for that work.
4. For endogenous prices, first add fixed-commitment energy/reserve pricing to the full
   pglib-uc model, then derive or decompose its unit hull for CHP. Its current benchmark
   retains piecewise costs and startup tiers, which the small pricing model omits.
5. Apply TEAL/HERON to asset sizing and project economics once operating cash flows have
   been validated. LOGOS becomes relevant for discrete portfolio investment choices.

The framework capabilities support these extensions, but there is no evidence that a
national-laboratory tool alone makes a model compliant with a particular market's rules.
