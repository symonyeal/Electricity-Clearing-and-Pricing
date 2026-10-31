# Electricity Clearing and Pricing

This repository implements small-system models for nonconvex electricity-market clearing,
price formation, and price-taking storage.

## Model coverage

| Component | Model | Check |
| --- | --- | --- |
| [Pricing](docs/PRICING.md) | Base-case network-constrained unit commitment; LMP, CHP, and AIC price runs | Enumeration, two exact hulls, published cases |
| [pglib-uc](docs/PGLIB.md) | Thermal commitment and renewable dispatch with piecewise offers, start-up tiers, and reserve | Independent rows and the reference relaxation |
| [Storage](docs/TRADING.md) | Day-ahead position, real-time recourse, information tree, and loss CVaR | Signed-flow enumeration and analytical cases |
| [NYISO replay](docs/MARKET.md) | Chronological storage valuation against published zonal prices | Leakage tests and independent settlement reconstruction |
| [Joint clearing](docs/JOINT.md) | Generation and storage in one program, on a network | The same market without storage, cleared by the pricing model |
| [Stochastic clearing](docs/JOINT.md) | One commitment against many demands, with a CVaR tail | The wait-and-see and mean-value bounds |
| [Decomposition](docs/DW.md) | Convex hull prices by column generation, including pglib-uc energy and reserve | Both direct hulls on 208 routes; a Lagrangian bound at every reported price |
| [Storage in the clearing](docs/SETTLE.md) | Value, settlement, congestion and the mode cut, on seven small cases | Settlement identity, congestion priced only on full lines, the exact storage hull |
| [Risk-averse prices](docs/RISK.md) | Which dual of a CVaR clearing is a price | The expected-cost re-dispatch and CVaR's closed-form dual weights |

SciPy/HiGHS solves all live optimization models. [Sources](docs/SOURCES.md) records the
formulations and data. [Validation](docs/VALIDATION.md) records executed checks, and [Open issues](docs/ISSUES.md) what remains.
[Decomposition](docs/DW.md) generates the extreme-point master, brackets the hull value at
each price it reports, to the solver's tolerances, and measures it against the direct hull
formulations.

## Pricing rules

Day-ahead clearing produces two linked outputs: a least-cost commitment and dispatch, and
the nodal price used to settle energy. This repository examines where nonconvex resource
constraints separate those two outcomes.

An ISO clears its day-ahead market through security-constrained unit commitment, which
determines which units start and how much they produce, then posts a locational marginal
price at every node. If every resource were perfectly flexible, that LMP would settle the
market.

Thermal units are not flexible in that way. A unit carries a start-up cost, an economic
minimum it cannot run below, and minimum run and down times. Those are on/off decisions, and
they break the result that one clearing price supports the schedule the ISO just issued. It
shows up on settlement statements: a unit held at EcoMin through an off-peak hour can lose
money at the posted LMP even though the ISO needed it committed.

The ISO writes a side payment: Revenue Sufficiency Guarantee at MISO, Bid Production Cost
Guarantee at NYISO, or operating reserve credits at PJM. These are out-of-market payments to
named units. They are absent from the price other participants see and are allocated back to
load. FERC has addressed the subject since opening price-formation Docket AD14-14 in June 2014.
[Sources](docs/SOURCES.md) records the documents these names come from.

Uplift depends on the price rule. The models compare:

| Rule | What it prices | Standing |
| --- | --- | --- |
| LMP | the dispatch, commitment held as cleared | what markets settle on today |
| Convex hull | convex combinations of each unit's feasible schedules | minimizes total uplift over uniform linear prices for the fixed cleared allocation |
| Average incremental cost | that benchmark, after screening blocks that did not cover their own cost | the FERC staff variant |

Real markets approximate convex-hull pricing because computing it at ISO scale is expensive.
MISO's Extended LMP relaxes on/off decisions for selected fast-start resources and, from
Phase III, does not enforce ramp-down in the pricing run. This implementation computes the
convex-hull benchmark exactly on small systems.

## Results

The FERC staff case has two units over three periods: a cheap flexible unit and a costly
slow unit with a $1,000 start-up, serving 95, 100 and 130 MW.
Production cost is $7,340 under each pricing rule; the dispatch stays unchanged.

| Rule | Period-3 price, $/MWh | Make-whole, $ | Total uplift, $ |
| --- | ---: | ---: | ---: |
| LMP | 90 | 1,690 | 1,690 |
| Convex hull | 276 | 0 | 365 |
| Average incremental cost | 422 | 0 | 730 |

The convex-hull price reduces total uplift by 78% while keeping the dispatch unchanged. Its
$365 of remaining uplift is lost opportunity cost; the LMP case pays $1,690 in make-whole.

For AIC, the talk reports $146.33/MWh for the AIC
price above; the exact p-cut hull over this repository's full schedule set gives $422/MWh.
Restricting unit 2 to the cleared and off schedules gives $146.33. The talk later describes
binary cuts for its AIC34 variant that induce that same restriction on this case, but does
not say those cuts produced the earlier AIC row. The two numbers therefore belong to
different stated feasible sets, and both are pinned in the tests.

On a three-bus loop with 90 MW of load behind a 40 MW constraint, the $2,100 clearing dispatches
60 MW from the cheap unit and 30 MW from the expensive unit. Hull prices are $10, $30 and
$50/MWh at the three buses. Omitting the transmission term from the hull gives a $4,500 lower
bound on the $2,100 cost, so the bound is invalid and the resulting uplift is wrong.

The two hull constructions agreed to 2.551e-16 across 104 feasible systems in a 141-case
random set.

On the participant side, a 1 MW, 4 MWh battery offered into the day-ahead market and settled
two-settlement against its real-time deviations nets, through 2025 in N.Y.C., $41,178 on a
deterministic forecast and $33,131 risk-neutral. These are 22% and 17% of the $190,720 a
perfect-foresight trader would have captured.

Those are archived outputs from revision `88d244d`, taken before analog days were aligned
by local clock hour, and no full-year rerun has been measured. The committed
[provenance note](docs/results/README.md#provenance-note-analog-alignment) bounds the reach
at 18 of 365 days, of which only the two clock-transition days are certain to move.

## Run

```text
python -m pip install -r requirements.txt
python -m pytest -q
python -m ruff check .
python -m pip check
python run_storage.py
python run_bench.py
python run_face_scan.py
python run_dw.py
python run_settle.py
python run_risk.py
```

The pglib-uc MIP is marked `slow`. Use `pytest -m 'not slow'` for the smaller suite.

The historical replay needs the NYISO archives, which are not committed. Its fetch and the
seven commands after it are in [NYISO replay](docs/MARKET.md#reproduction). Every test
runs on committed fixtures.

## Scope

These are small systems. The pricing case omits contingencies, losses, ancillary
co-optimization, an ISO-scale network, and offer mitigation. The project compares pricing
rules; it does not operate a market.

The clearing models determine schedules and structural prices. The storage model accepts
prices as inputs and assumes a price-taking participant. The NYISO replay values modeled
positions; it does not reproduce bid acceptance, ISO dispatch, tariffs, or market impact.

The small pricing model omits piecewise offers, start-up tiers, and reserve. The separate
pglib-uc model includes those features and prices energy and reserve with its integers
held; `models/dw.py` takes its convex hull by column generation. The joint and stochastic
clearings price by pinning the integers, so a nonconvexity is left as make-whole rather
than priced away.

The market interface in `market/bid.py` supplies offer curves, a metered charge and
qualification screens as parameters. It is not any market's rule set, and its defaults
reproduce full acceptance at no charge.

Unrelated models, completed reviews, and superseded documents are preserved in
[`_archive/`](_archive/README.md).
