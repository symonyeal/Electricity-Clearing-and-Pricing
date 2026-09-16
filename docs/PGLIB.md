# pglib-uc benchmark

`models/pglib_uc.py` implements equations (1)–(24) of the IEEE PES Task Force
[pglib-uc](https://github.com/power-grid-lib/pglib-uc) `MODEL.pdf` with an independent
row construction. The formulation has global demand and reserve requirements; convex
piecewise production costs; off-time-dependent start-up costs; minimum up- and down-times;
start-up and shut-down ramps; and renewable bounds.

The committed instance is `rts_gmlc/2020-03-05.json`, 73 thermal units, 81 renewable units
and 48 periods, giving 44,544 columns of which 16,128 are binary.

| Check | Value |
| --- | ---: |
| Reference `uc_model.py` relaxed, under HiGHS | 2,480,427.041110388 |
| This model, independent rows | 2,480,427.0411103913 |

The LP optimum is determined; the incumbent returned at a 1% MIP gap depends on search
order. The relaxation is therefore the regression gate. At a 1% gap, this implementation
returns cost 2,520,108.89.

## Parser checks

Dropping a cost category or a reserve restriction can lower the objective. Dropping
piecewise points can instead remove feasible output and make the model infeasible:

| Instance as read | Relaxation |
| --- | ---: |
| Every field | 2,480,427.04 |
| First piecewise point only | infeasible |
| First start-up category only | 2,474,234.88 |
| Reserve requirement dropped | 2,460,381.68 |
| Minimum run and down times dropped | 2,452,664.23 |

`ConvexHullPricing.jl` reads only `piecewise_production[1]["cost"]` and
`startup[1]["cost"]`. The corresponding truncations are shown above.

## Result fields

`cl(d, gap=0.0)` returns cost `z`, status `st`, achieved relative gap `gap`, and the
solver's certified cost lower bound `lb`. A positive achieved gap gives status `gap`; a
zero gap gives `opt`. The reported gap is achieved, not requested. This module does not
compute settlement prices.
