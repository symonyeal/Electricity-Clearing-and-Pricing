# Electricity Market Model

Exact models for nonconvex electricity clearing, price formation, and price-taking storage.
Each model has an independent formulation or external benchmark.

| Component | Model | Check |
| --- | --- | --- |
| [Pricing](docs/PRICING.md) | Unit commitment; LMP, CHP, and AIC | Enumeration, two exact hulls, published cases |
| [pglib-uc](docs/PGLIB.md) | Piecewise cost, start-up tiers, reserve, thermal and renewable units | Independent rows and the reference relaxation |
| [Storage](docs/TRADING.md) | Day-ahead position, real-time recourse, information tree, CVaR | Signed-flow enumeration and analytical cases |
| [NYISO replay](docs/MARKET.md) | Chronological storage valuation under published zonal prices | Leakage tests and independent settlement reconstruction |

SciPy/HiGHS solves all live optimization models. [Sources](docs/SOURCES.md) records the
formulations and data. [Validation](docs/VALIDATION.md) records executed checks.

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
pglib-uc model includes those features but does not compute settlement prices. Joint
storage and unit-commitment clearing is not implemented.

Unrelated models, completed reviews, and superseded documents are preserved in
[`_archive/`](_archive/README.md).
