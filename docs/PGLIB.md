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
`startup[1]["cost"]`. The corresponding truncations are the second and third rows.

## Energy and reserve prices

`px(d, gap)` clears, pins every integer column, and reads the duals of (2) and (3) from the
linear program that remains. (3) carries a surplus column so that it is an equality and its
dual is nonnegative. The balance rows are moved last because `_px` reads them there; that
price selection rule is shared with [Pricing](PRICING.md) deliberately, so that two priced
programs cannot answer one degenerate face differently. No row builder is shared.

Measured on 2026-09-16 on the committed instance at the reference script's 1% gap:

| Quantity | Value |
| --- | ---: |
| Energy price | 0 to 55.5092/MWh, mean 17.4799 |
| Reserve price | 0 to 27.7546/MWh, positive in 4 of 48 periods |
| Demand payment | 3,111,148.57 |
| Reserve payment | 3,455.80 |
| Thermal revenue | 2,329,739.62 |
| Renewable revenue | 784,864.75 |
| Make-whole | 370,817.15 over 30 units |

Payment equals revenue to the cent. Reserve carries no cost of its own in this formulation
and competes only for capacity, so it prices only where capacity is scarce. The commitment
is a 1% incumbent, so the prices follow that incumbent; what the tests assert is the
accounting identity and the sign, not a value.

There are 96 balance rows against `LIM[3]` of 24, so price selection stops at the payment
stage and the tag is `pay`: these prices are canonical to the demand payment only.

## Result fields

`cl(d, gap=0.0)` returns cost `z`, status `st`, achieved relative gap `gap`, and the
solver's certified cost lower bound `lb`. A positive achieved gap gives status `gap`; a
zero gap gives `opt`. The reported gap is achieved, not requested. This module does not
compute settlement prices.
