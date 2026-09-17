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

### The source

A generator cannot be switched on for an hour at a time: it carries a start-up cost, a
minimum output once running, and a minimum number of hours it must then stay on. Those
integer decisions make the market's cost function nonconvex. The consequence is a theorem,
not an inconvenience: in general **no single price per megawatt-hour supports the schedule
the market just selected.** Somebody is always instructed to do what loses money at that
price, and the market covers the difference with a side payment: uplift, or make-whole.

How much uplift is paid depends on which price is posted, and more than one answer is
defensible. Locational marginal pricing holds the commitment and prices the dispatch that
remains. Convex hull pricing replaces each generator by the hull of everything it could have
done, and provably minimizes uplift. Average incremental cost prices that hull after
restricting the blocks that failed to cover their own cost.

### The task

Compute all three exactly on small systems, and measure what each leaves behind.

Exactness is the point and also the difficulty. Production markets approximate the hull
because computing it is expensive: MISO's Extended LMP relaxes the binary on a narrow set of
fast-start units and, from Phase III, drops ramp-down from the pricing run. An approximation
cannot measure its own error; built exactly, these rules become the instrument it is held
against.

### The method

Formulations come from the literature, never from invention: Gribik, Hogan and Pope for the
rule, Hua–Baldick and the Chen–O'Neill–Whitman FERC talk for worked cases, Balas and
Yu–Guan–Chen for the two hulls, Beck for the duality that settles what a dual must minimize
over. Data is public — NYISO zonal archives, pglib-uc's RTS-GMLC instance.

One unit's feasible set is written once and every route reads that copy; a separate pglib-uc
model writes its own rows and exists in order to disagree. Prices are duals, and a dual
optimum can be a face rather than a point, so the price is chosen by a stated rule, not by
whichever vertex the solver reached. Any claim of exactness asks for a zero gap and reads
back the gap achieved. SciPy and HiGHS do the solving; no commercial licence is required.

### The result

The two hull constructions agree on all 104 feasible markets among 141 seeds, to 2.55e-16
relative. Case `ex3`'s exact average incremental cost is $422; the talk's $146.33 is
recovered only by deleting a feasible schedule the source does not exclude. Both are pinned.
On a network the Lagrangian dual needs a transmission term, identically zero on one bus and
decisive on several; omitting it reported a dual of 4,500 against a clearing of 2,100, which
weak duality forbids. A 1 MW, 4 MWh battery replayed against 2025 NYISO prices nets $33,131
risk-neutral, against a $190,720 perfect-foresight ceiling it cannot reach.

### The context

A research and verification instrument, not a clearing engine: no contingencies, no losses,
no ISO-scale network, no ancillary co-optimization. Where it departs from a production
market, the documentation names which of the two is right.

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
