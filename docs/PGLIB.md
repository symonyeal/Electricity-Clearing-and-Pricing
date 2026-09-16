# External unit-commitment benchmark

`models/pglib_uc.py` implements the pglib-uc reference formulation, equations (1) to (24)
of its `MODEL.pdf`, from its own rows. This is the IEEE PES Task Force benchmark: a global
demand and reserve requirement, thermal units with convex piecewise production costs,
off-time-dependent start-up costs, minimum run and down times, start-up and shut-down
ramps, and renewable units with per-period bounds.

The committed instance is `rts_gmlc/2020-03-05.json`, 73 thermal units, 81 renewable units
and 48 periods, giving 44,544 columns of which 16,128 are binary.

| Check | Value |
| --- | ---: |
| Reference `uc_model.py` relaxed, under HiGHS | 2,480,427.041110388 |
| This model, independent rows | 2,480,427.0411103913 |

The gate is the relaxation rather than the integer objective because the relaxation is
determined; at the reference script's 1% gap the incumbent is not. Clearing the instance at
that gap gives 2,520,108.89 in tens of seconds.

Dropping a cost category or a reserve restriction can lower the objective. Dropping
piecewise points can instead remove feasible output and make the model infeasible:

| Instance as read | Relaxation |
| --- | ---: |
| Every field | 2,480,427.04 |
| First piecewise point only | infeasible |
| First start-up category only | 2,474,234.88 |
| Reserve requirement dropped | 2,460,381.68 |
| Minimum run and down times dropped | 2,452,664.23 |

The first two are not hypothetical. `ConvexHullPricing.jl` reads
`piecewise_production[1]["cost"]` and `startup[1]["cost"]` and keeps nothing else.

`cl(d, gap=0.0)` returns cost `z`, status `st`, achieved relative gap `gap`, and the
solver's certified cost lower bound `lb`. A solve with positive achieved gap is marked
`gap`; only a zero achieved gap is marked `opt`. The requested tolerance is not echoed
as the achieved gap. This module still does not compute settlement prices.
