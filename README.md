# Electricity Market Model

Exact formulations for electricity clearing, prices and storage trading, with independent
solve routes and explicit model limits. Python, mathematical names, sparse rows and small
functions are the coding register; [Decisions](docs/DECISIONS.md) records the rules.

| Model | Formulation | Independent check |
| --- | --- | --- |
| [Unit commitment and pricing](docs/PRICING.md) | MIP clearing; LMP, CHP and AIC from linear programs | Schedule enumeration, schedule hull, published examples |
| [pglib-uc commitment](docs/PGLIB.md) | Piecewise costs, startup tiers, reserves, thermal and renewable units | IEEE PES benchmark and reference LP objective |
| [Storage trading](docs/TRADING.md) | Physical forward schedule, real-time deviations, information tree, CVaR | Signed-flow enumeration, analytical cases, optional DOVE comparison |
| [Ultimate pit limit](docs/PIT.md) | Maximum-weight closure by minimum cut | NetworkX, LP, enumeration and MineLib |

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
quantity schedule under specified scenarios; it does not submit bids, predict prices or
establish trading profitability. Market-specific rules, fees, reserve products and
out-of-sample evaluation remain extensions.

The pglib-uc benchmark clears the full reference model but does not yet price it. The
smaller pricing model retains its stated restrictions and numerical AIC corner cases;
[Pricing](docs/PRICING.md) preserves the published-example discrepancies. Independent
models and fixtures remain active validation, including the pit model.

Older Windows measurements and the broader unimplemented optimization sequence are in
[the dated archive](_archive/20260915-inl-review/README.md).
