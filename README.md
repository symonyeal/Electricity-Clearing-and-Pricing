# Electricity Market Model

Exact formulations for electricity clearing, prices and storage trading, with independent
solve routes and explicit model limits. Python, mathematical names, sparse rows and small
functions are the coding register; [Decisions](docs/DECISIONS.md) records the rules.

| Model | Formulation | Independent check |
| --- | --- | --- |
| [Unit commitment and pricing](docs/PRICING.md) | MIP clearing; LMP, CHP and AIC from linear programs | Schedule enumeration, schedule hull, published examples |
| [pglib-uc commitment](docs/PGLIB.md) | Piecewise costs, startup tiers, reserves, thermal and renewable units | IEEE PES benchmark and reference LP objective |
| [Storage trading](docs/TRADING.md) | Deliverable offer or fixed obligation, real-time deviations, information tree, CVaR | Signed-flow enumeration, analytical cases, optional DOVE comparison |
| [Ultimate pit limit](docs/PIT.md) | Maximum-weight closure by minimum cut | NetworkX, LP, enumeration and MineLib |
| [Historical study](docs/MARKET.md) | Chronological replay of the storage model against published NYISO prices | Independent settlement reconciliation, leakage, transition-day and fallback checks |

SciPy/HiGHS solves the electricity models. OR-Tools solves maximum closure.
[Sources](docs/SOURCES.md) records formulations and data provenance.

## Local projects and implemented path

The [INL assessment](docs/INL.md) covers all twelve neighboring projects and the local
starters. HydroBoost's storage modes and energy balance, LOGOS's CVaR formulation, and
DOVE's dispatch checks have immediate value. Their relevant mathematics is implemented
in `models/storage.py`; runtime dependencies remain the existing stack.

The storage model excludes simultaneous charging and discharging, settles deviations once,
uses explicit interval duration and terminal energy, and shares decisions until scenarios
are distinguishable. It returns the achieved gap and an objective upper bound. The
pglib-uc result now reports its achieved gap and cost lower bound too.

HERON and TEAL fit later asset sizing and project economics; ORCA and RAVEN fit rolling
operation and scenario studies. The assessment gives the evidence and limits for each.

## Historical study

`market/` replays one price-taking battery against published New York ISO zonal prices,
in order, with every decision taken from information available at its own decision time.
Statistical estimation is separate from the exact optimization: scenarios are realized
days and one fitted persistence coefficient, chosen on training and validation periods
only, and the held-out year is replayed once. Five policies share one battery, one cost
model and one settlement: no trading, a deterministic forecast, risk-neutral stochastic
optimization, CVaR, and perfect foresight as an explicitly optimistic benchmark.

[The study](docs/MARKET.md) states the data provenance, the information timeline, the
protocol, the measured results and what remains unvalidated, and
[docs/results](docs/results/README.md) holds what the held-out year actually wrote. It is a price-taking
simulation against published prices, not evidence that these positions could have been
submitted, accepted or settled.

## Reproduce

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
python -m ruff check .
python -m pip check
python run_storage.py
```

`pytest -q` includes the full pglib-uc MIP. Use `-m 'not slow'` for the smaller suite or
`-m slow` for that benchmark alone. `run_bench.py` and `run_face_scan.py` reproduce the
larger pricing and pit experiments. [Validation](docs/VALIDATION.md) records current
checks, versions, measured timings and the optional local DOVE command.

The historical study has its own commands, and only the first uses the network:

```bash
python run_market.py fetch                       # published archives, about 46 MB
python run_market.py validate --out results/coverage.json
python run_market.py smoke                       # five policies over a transition day
python run_market.py tune --out results/tune     # validation search
python run_market.py select --dir results/tune   # the stated selection rule
python run_market.py run --period test --pol all --out results/test
python run_market.py report --dir results/test   # tables and figures
```

```python
from models.storage import B, st

b = B(e=1, c=1, d=1, ec=1, ed=1)
r = st(b, da=[10, 40], rt=[[10, 100], [10, -100]], pr=[0.8, 0.2], a=0.8, w=0.5)
print(r.q, r.r, r.ub, r.gap)
# forward MW [-1, 1]; scenario profits [30, 30]; score bound 30; gap 0
```

This example is synthetic. `h=None` reveals no scenario information before dispatch.
[Trading](docs/TRADING.md) defines the information tree, result fields and equations.

## Scope

Storage prices are supplied, and the model assumes a price-taking asset. It produces a
quantity schedule under specified scenarios; it does not submit bids or establish that a
position would clear. Out-of-sample evaluation now exists for one zone and one held-out
year, with its assumptions and omitted charges stated. Market-specific participation
rules, reserve products and joint clearing remain extensions.

The pglib-uc benchmark clears the full reference model but does not yet price it. The
smaller pricing model retains its stated restrictions and numerical AIC corner cases;
[Pricing](docs/PRICING.md) preserves the published-example discrepancies. Independent
models and fixtures remain active validation, including the pit model.

Older Windows measurements and the broader unimplemented optimization sequence are in
[the dated archive](_archive/20260915-inl-review/README.md).
