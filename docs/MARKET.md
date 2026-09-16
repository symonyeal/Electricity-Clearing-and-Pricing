# Historical price-taking storage study

A single battery is replayed against published New York ISO zonal prices, in order, with
every decision taken from information available at its own decision time. The study
measures what the formulations in this repository earn under stated assumptions; it does
not establish that the same positions could have been submitted, accepted or settled in
the market. [Trading](TRADING.md) defines the optimization; this document defines the
data, the information timeline, the protocol, the baselines and the limits.

## What is simulated and what is assumed

Simulated from published data: hourly day-ahead prices, five-minute real-time prices,
the physical battery, two-settlement cash flows, degradation and transaction costs.

Assumed, and not validated here:

- Price taking. The battery's own quantities never move a price.
- Certain acceptance. An hourly day-ahead position clears in full at the published zonal
  price, and a real-time deviation settles in full at the published five-minute price.
- Self-scheduling. Real-time dispatch is chosen by the participant. A New York energy
  storage resource is dispatched by the ISO under its own participation model; base
  points, bid parameters and state-of-charge management by the ISO are not modelled.
- One zone, no network position. No transmission congestion contract, no losses beyond
  those already inside the published locational price.

Charges and revenues that a real participant faces and this study omits: NYISO Rate
Schedule 1 cost recovery, ancillary service charges and credits, installed capacity
revenue, transmission congestion contracts, station power, taxes, market power
mitigation, uninstructed deviation treatment, metering and rebilling adjustments, credit
and collateral, and any capital or fixed operating cost. The configured transaction cost
is a single per-megawatt-hour stand-in for the first of these, not a tariff calculation.

## Data

| Report | Archive | Grid | Convention |
| --- | --- | --- | --- |
| Day-ahead zonal LBMP | `damlbmp` monthly zip of daily CSV | hourly | stamp begins the hour |
| Real-time zonal LBMP | `realtime` monthly zip of daily CSV | five minutes | stamp ends the interval |

`market/nyiso.py` downloads `http://mis.nyiso.com/public/csv/{report}/{YYYYMM01}{report}_zone_csv.zip`,
keeps the archive unmodified, and parses the zone requested by name. Stamps are eastern
prevailing time. The loader converts each to UTC, resolves the repeated hour of the
autumn transition by order of appearance, and refuses a local time that does not exist.
A local day therefore carries 23, 24 or 25 hours and 276, 288 or 300 five-minute bins.

Real-time postings are irregular whenever the real-time dispatch reruns inside a
five-minute clock interval. A posted price applies from the previous posting to its own
stamp, so each posting is weighted by the seconds it covers inside its bin, which is exact
when the battery holds one power level across the bin. Where the cadence itself lapses the
price simply lives longer, and `validate` reports every posting that ran more than a
minute past five so the reader can see how often that happened rather than infer it from a
grid that cannot show it. Over 2022-10-01 to 2025-12-31 in this zone it happened on 11
days and covers 4.8 hours of 28,513, the longest single interval being fifteen minutes.

`python run_market.py validate` writes the coverage report: intervals expected, present,
missing and partial, the price range, and every day the archive did not supply in full.
A day that is not complete is never traded and never used as a scenario; it is recorded
as skipped and the battery holds its energy through it.

## Physical and financial model

The battery is the `models/storage.py` model: usable energy, separate charge and
discharge limits, one-way efficiencies, exclusive charge and discharge modes, and a
linear cost per megawatt hour of grid energy in either direction. Configured here as a
1 MW, 4 MWh unit at 92% one way, 84.6% round trip, with a $2/MWh degradation cost and a
$0.50/MWh transaction cost.

An hourly day-ahead position $q_h$ is decided once, before the day-ahead market clears,
and then frozen. Settlement over a five-minute bin $i$ inside hour $h$, of length
$\Delta = 1/12$ hour, is

$$
\underbrace{q_h\lambda^{DA}_h\Delta}_{\text{day ahead}}
+\underbrace{(g_i-q_h)\lambda^{RT}_i\Delta}_{\text{imbalance}}
-\underbrace{(k_{\text{deg}}+k_{\text{fee}})(c_i+d_i)\Delta}_{\text{costs}},
\qquad g_i=d_i-c_i .
$$

Once a position is contracted it is financial: it settles whatever the battery does. The
optimization holds it fixed and imposes no physical schedule for it, so a real-time
deviation can never make an existing obligation infeasible. A position being *chosen*
is different: the offer route requires the nominal schedule to be a feasible battery
schedule from the energy assumed at the time of the offer.

Energy is carried across every day boundary and is never reset. Each trading day ends at
a common target, 2 MWh, which every trading policy must meet. When the target is not
reachable from the current energy within the day's remaining steps, the model uses the
reachable value nearest to it, which keeps every solve feasible and is recorded.

## Information timeline

| Decision | Taken at | May use |
| --- | --- | --- |
| Hourly position for day $D$ | 05:00 local on $D-1$ | every day whose own prices were complete before then, that is days up to $D-2$ |
| Dispatch for step $k$ of day $D$ | start of the step | day $D$'s published day-ahead prices, and real-time bins ending at least two bins earlier |

One scenario set is built per day, at bid close, so the intraday decisions reuse it and
never see day $D-1$ as a scenario even though it has since completed. That discards
information rather than borrowing it; what the intraday decisions do use from the current
day is the observed residual, through the level shift below.

The real-time lag is two five-minute bins. A decision for a fifteen-minute step therefore
sees prices up to ten minutes before the step begins, and never the interval it is about
to be settled in. `market/scen.py` is the only module that reads history, and it enforces
the lag in one place, which `tests/test_market.py::test_no_leakage` checks by perturbing
prices after a decision time and requiring every earlier decision to be unchanged.

## Scenarios, and what a tree node means

Scenarios are realized days, not simulated paths. For the day being decided, the
candidate set is the complete days of the same type, weekday or weekend, inside a
lookback window of $L$ days that ends before the decision. From those candidates the
model keeps $S$ days spaced by quantiles of their mean real-time price, so the ensemble
spans the level distribution while each member keeps one real day's shape, including its
own joint day-ahead and real-time curves. Weights are equal. A transition day is aligned
by repeating or dropping its last hour, which affects two days a year.

One coefficient is fitted: $\rho$, the hourly persistence of the residual between the
realized price and the analog ensemble mean, estimated by least squares through the
origin on training days only. At an intraday decision the ensemble is shifted by
$\rho^{\Delta t}$ times the latest observed residual, so a spike that is already under
way is carried forward with decay. The day-ahead decision applies no shift: its last
observation is at least nineteen hours away and $\rho^{19}$ is about 0.005.

The information tree is built on the scenario ensemble, not on single paths. Before the
first branch every scenario shares one node. At a branch the node splits at the median of
its members' mean price over the segment that follows. A node is therefore a **set** of
price paths that remain indistinguishable to the decision maker, never a single path, and
nodes refine but never merge. A node is only split when it has at least $2m$ members, so
no scenario is ever alone in a node and no decision is taken knowing one exact future
path. `models/storage.py` shares one charge, discharge, energy and mode column per node.

## Policies

| Policy | Position | Dispatch | Note |
| --- | --- | --- | --- |
| `idle` | zero | none | no trading; energy held |
| `det` | one forecast path | the same forecast, re-made each step | ensemble mean, one scenario |
| `neutral` | $S$ scenarios, tree | $S$ scenarios, tree | expected profit |
| `cvar` | $S$ scenarios, tree | $S$ scenarios, tree | $(1-w)\,\mathbb E[R]-w\,\mathrm{CVaR}_\alpha(-R)$ |
| `fore` | realized prices | realized prices | perfect foresight, optimistic benchmark |

All five share the same battery, costs, decision cadence, settlement, end-of-day target
and solver tolerances. Only the prices each policy is allowed to see differ. `fore` is
not a policy anyone could run: it is the upper reference for the information gap.

## Protocol

1. **Train**, 2022-10-01 to 2023-12-31: fit $\rho$. Nothing else is estimated.
2. **Validate**, 2024: choose hyperparameters by replaying the validation year.
   - `det`: the lookback $L$ with the highest validation net settlement.
   - `neutral`: the pair $(L,S)$ with the highest validation net settlement.
   - `cvar`: with $(L,S)$ fixed at the risk-neutral choice, the $(w,\alpha)$ with the
     highest validation net settlement among those whose validation tail loss, the 5%
     conditional value at risk of daily net settlement, is strictly smaller than the
     risk-neutral policy's. If none qualifies, the smallest tail loss is taken and the
     rule is reported as not binding.
3. **Freeze** the chosen settings, refit $\rho$ on everything before the held-out year,
   and replay 2025 once. Retraining is scheduled, not continuous: the coefficient is
   refitted before each evaluation period, on data that ends before that period starts.

The held-out year is replayed once per policy, with the settings written into each run's
`config.toml`. Adverse results are reported exactly as favourable ones.

## Reporting

Reported: gross settlement revenue split into day-ahead and imbalance, degradation and
transaction costs, net settlement, monthly net, the largest peak-to-trough fall of the
running total, the worst day, the 5% conditional value at risk of daily net, grid
throughput, equivalent full cycles, energy-bound violations, solve counts, solve seconds,
achieved gaps, held steps, skipped days and data coverage.

The interval uncertainty is a moving block bootstrap of the daily net settlement, with
block length $\lceil n^{1/3}\rceil$ days and 10,000 replications from a seeded generator,
which keeps the day-to-day dependence that an independent resample would destroy.

Return on investment and Sharpe ratios are not reported. This study has no defensible
capital base: it prices no installation, no capacity market position and no financing,
and a ratio built on an arbitrary denominator would be a decoration, not a measurement.

## Reproducing

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python run_market.py fetch                      # about 46 MB of published archives
python run_market.py validate --out results/coverage.json
python run_market.py smoke                      # three days, five policies, includes a
                                                # 25-hour transition day
python run_market.py tune --out results/tune    # the validation search
python run_market.py run --period test --out results/test --pol all
python run_market.py report --dir results/test
```

`fetch` is the only command that uses the network. Every test runs offline against the
committed fixtures in `tests/fixtures/nyiso`, which `tests/fixtures/build.py` rebuilds
from the archive. Each run writes `intervals.csv.gz`, `daily.csv`, `monthly.csv`,
`metrics.json` with its diagnostics, fit record and environment, and the `config.toml`
that produced it. `report` writes `tables.md` and four standalone SVG figures: the cumulative net
settlement of every policy, net settlement by month, the share of the year earned on its
best days, and one day's prices, stored energy and grid power.

## Limits

- The study is a price-taking simulation against published prices. It is not evidence
  that these positions would have been accepted, dispatched or settled as modelled.
- An exact optimum under a scenario set is not forecast skill. The scenario ensemble is
  a transparent baseline: realized analog days, one fitted persistence coefficient, and a
  quantile-spaced subsample. Better forecasts exist and are not implemented.
- The end-of-day energy target excludes multi-day arbitrage and shortens the effective
  horizon. It is applied identically to every policy, including perfect foresight.
- The day-ahead decision uses hourly averages of real-time prices; within-hour real-time
  shape enters only through the real-time stage.
- Results are dominated by a small number of scarcity days. The tail statistics, the
  monthly table and the bootstrap interval are reported for that reason.
- One zone, one battery size, one year held out. Nothing here is a general statement
  about storage profitability.
- The archive restates corrected prices. The study reads it as it stood on 2026-09-15, so
  where a price was later corrected the corrected value is used, while a participant
  deciding at the time saw the original. The difference is not measured.
