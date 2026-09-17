# Electricity Market Model

Exact models for nonconvex electricity clearing, price formation, and price-taking storage.
Each model has an independent formulation or external benchmark.

| Component | Model | Check |
| --- | --- | --- |
| [Pricing](docs/PRICING.md) | Unit commitment; LMP, CHP, and AIC | Enumeration, two exact hulls, published cases |
| [pglib-uc](docs/PGLIB.md) | Piecewise cost, start-up tiers, reserve, thermal and renewable units | Independent rows and the reference relaxation |
| [Storage](docs/TRADING.md) | Day-ahead position, real-time recourse, information tree, CVaR | Signed-flow enumeration and analytical cases |
| [NYISO replay](docs/MARKET.md) | Chronological storage valuation under published zonal prices | Leakage tests and independent settlement reconstruction |
| [Joint clearing](docs/JOINT.md) | Generation and storage in one program, on a network | The same market without storage, cleared by the pricing model |
| [Stochastic clearing](docs/JOINT.md) | One commitment against many demands, with a CVaR tail | The wait-and-see and mean-value bounds |

SciPy/HiGHS solves all live optimization models. [Sources](docs/SOURCES.md) records the
formulations and data. [Validation](docs/VALIDATION.md) records executed checks.
[Decomposition](docs/DW.md) compares the direct hull formulations with an extreme-point
master and states when column generation becomes a candidate.

## Background

### The problem: price formation

An ISO clears its day-ahead market with a security-constrained unit commitment — which
units start, when, and how much each produces — then posts a locational marginal price at
every node. If every resource were perfectly flexible, that LMP would settle the market and
nothing further would be needed.

Thermal units are not flexible in that way. A unit carries a start-up cost, an economic
minimum it cannot run below, and minimum run and down times. Those are on/off decisions, and
they break the result that one clearing price supports the schedule the ISO just issued. It
shows up on settlement statements: a unit held at EcoMin through an off-peak hour can lose
money at the posted LMP even though the ISO needed it committed.

So the ISO writes a side payment. MISO calls it Revenue Sufficiency Guarantee, day-ahead and
real-time; NYISO calls it Bid Production Cost Guarantee; PJM calls it operating reserve
credits. Whatever the name, it is out-of-market money — paid to named units, absent from the
price everyone else sees, and allocated back to load. FERC has worked the subject since
Docket AD14-14, price formation, opened in June 2014, and every independent market monitor
reports the annual total. [Sources](docs/SOURCES.md) records the tariff and staff documents
these names come from.

### What this computes

Uplift is not a fixed cost of doing business. It depends on which price the ISO posts, and
there is more than one defensible choice:

| Rule | What it prices | Standing |
| --- | --- | --- |
| LMP | the dispatch, commitment held as cleared | what markets settle on today |
| Convex hull | what each unit could have offered to do, not only what it was told to do | the benchmark that provably minimizes total uplift |
| Average incremental cost | that benchmark, after screening blocks that did not cover their own cost | the FERC staff variant |

Real markets approximate the benchmark, because computing it at ISO scale is expensive.
MISO's Extended LMP relaxes the on/off decision for a short list of fast-start resources and,
from Phase III, stops enforcing ramp-down in the pricing run. That is a defensible
engineering compromise, but an approximation cannot report its own error. This code computes
the benchmark exactly on small systems, so the approximations have something to be held
against.

The other half is the participant side: a 1 MW, 4 MWh battery offered into the day-ahead
market and settled two-settlement against its real-time deviations, replayed chronologically
on published NYISO N.Y.C. zonal prices.

### What it shows

Two independent constructions of the benchmark agree to machine precision — 2.551e-16
relative — on all 104 feasible systems in a 141-case randomized set. The FERC staff example
prices at $422; the $146.33 in the talk is recoverable only by deleting a schedule the unit
could genuinely have run, and both numbers are pinned. On a constrained network the benchmark
must carry a transmission term: omit it and it reports 4,500 against a clearing of 2,100,
which cannot happen. Across 2025 the battery nets $33,131 risk-neutral, against a $190,720
perfect-foresight ceiling no real policy reaches.

### Where it stops

Small systems. No contingencies, no losses, no ancillary co-optimization, no ISO-scale
network, no offer mitigation. It measures pricing rules. It does not clear a market.

## Run

```text
python -m pip install -r requirements.txt
python -m pytest -q
python -m ruff check .
python -m pip check
python run_storage.py
python run_bench.py
python run_face_scan.py
```

The pglib-uc MIP is marked `slow`. Use `pytest -m 'not slow'` for the smaller suite.

The historical replay requires one network fetch; all tests use committed fixtures.

```text
python run_market.py fetch
python run_market.py validate --out results/coverage.json
python run_market.py smoke
python run_market.py tune --out results/tune
python run_market.py select --dir results/tune
python run_market.py run --period test --pol all --out results/test
python run_market.py report --dir results/test
python run_delivery.py audit
```

## Scope

The clearing models determine schedules and structural prices. The storage model accepts
prices as inputs and assumes a price-taking participant. The NYISO replay values modeled
positions; it does not reproduce bid acceptance, ISO dispatch, tariffs, or market impact.

The small pricing model omits piecewise offers, start-up tiers, and reserve. The separate
pglib-uc model includes those features and prices energy and reserve, but takes no hull.
The joint and stochastic clearings price by pinning the integers, so a nonconvexity is
left as make-whole rather than priced away.

The market interface in `market/bid.py` supplies offer curves, a metered charge and
qualification screens as parameters. It is not any market's rule set, and its defaults
reproduce full acceptance at no charge.

Unrelated models, completed reviews, and superseded documents are preserved in
[`_archive/`](_archive/README.md).
