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

In the original, unbounded experiment a contracted position is financial: it settles
whatever the battery does. The optimization holds it fixed and imposes no nominal
physical schedule for it. A position being *chosen* has a nominal schedule that must be
feasible from the energy assumed at the time of the offer. The delivery experiment below
adds an absolute deviation cap to the actual scenario dispatch in both stages; a supplied
position still builds no nominal path. A finite cap can make an obligation infeasible.

Energy is carried across every day boundary and is never reset. Each trading day ends at
a common target, 2 MWh, which every trading policy must meet. When the target is not
reachable from the current energy within the day's remaining steps, the model uses the
reachable value nearest to it. This ensures physical reachability in the unbounded model;
under a finite cap the remaining contracted position must also be feasible.

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
that produced it. The exported evidence for the run reported below is kept in
[`docs/results/`](results/README.md). `report` writes `tables.md` and four standalone SVG
figures: the cumulative net settlement of every policy, net settlement by month, the share
of the year earned on its best days, and one day's prices, stored energy and grid power.

## The validation search

Fifteen configurations were replayed over 2024. Only the two policies without
hyperparameters, no trading and perfect foresight, had been replayed on the held-out year
when this search ran, and neither has a lookback, a scenario count or a risk parameter to
choose, so nothing about a tuned policy's held-out performance entered it.

| Policy | Lookback | Scenarios | Risk weight | Confidence | Net | Tail loss 5% | Drawdown | Worst day | Cycles |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| deterministic forecast | 30 | 16 | 0.0 | 0.95 | 13,569 | 188 | 806 | -663 | 328 |
| deterministic forecast | 15 | 16 | 0.0 | 0.95 | 12,898 | 176 | 921 | -544 | 335 |
| deterministic forecast | 60 | 16 | 0.0 | 0.95 | 8,772 | 226 | 1,015 | -743 | 320 |
| deterministic forecast | 120 | 16 | 0.0 | 0.95 | 6,470 | 230 | 1,323 | -704 | 319 |
| risk neutral | 30 | 8 | 0.0 | 0.95 | 14,180 | 223 | 987 | -615 | 338 |
| risk neutral | 30 | 16 | 0.0 | 0.95 | 13,079 | 195 | 958 | -606 | 329 |
| risk neutral | 15 | 8 | 0.0 | 0.95 | 12,558 | 177 | 977 | -596 | 340 |
| risk neutral | 15 | 16 | 0.0 | 0.95 | 11,930 | 162 | 917 | -397 | 336 |
| risk neutral | 60 | 16 | 0.0 | 0.95 | 7,753 | 235 | 1,017 | -740 | 323 |
| risk neutral | 60 | 8 | 0.0 | 0.95 | 6,370 | 266 | 1,656 | -858 | 347 |
| risk neutral | 120 | 16 | 0.0 | 0.95 | 5,912 | 233 | 1,384 | -695 | 322 |
| risk neutral | 120 | 8 | 0.0 | 0.95 | 258 | 289 | 2,619 | -685 | 341 |
| CVaR | 30 | 8 | 0.25 | 0.95 | 12,737 | 199 | 1,041 | -478 | 326 |
| CVaR | 30 | 8 | 0.5 | 0.9 | 10,586 | 161 | 687 | -413 | 321 |
| CVaR | 30 | 8 | 0.5 | 0.95 | 10,586 | 161 | 687 | -413 | 321 |

The lookback window dominates everything else in the grid. Both policies earn between one
and a half and two and a quarter times as much at thirty days as at sixty, and the
risk-neutral policy at a hundred and twenty days with eight scenarios earns almost nothing
at all. The scenario count matters far less: at thirty days the two counts differ by 8%
for the risk-neutral policy, while
lengthening the window from thirty to a hundred and twenty days costs it 98%. The grid
first ran 30, 60 and 120 days and its best value was its own boundary, so it was extended
to fifteen days before any tuned policy was replayed on the held-out year. Fifteen came in
below thirty for both policies, which leaves the chosen window inside the searched range
rather than at its edge.

A shorter window is not simply worse. The fifteen-day configurations carry the smallest
tail losses in the grid, and the risk-neutral policy at fifteen days with sixteen
scenarios has both the smallest tail loss, 162, and the smallest worst day, -397. The
rule selects on net settlement, so it did not choose them.

The two CVaR confidences are one configuration, not two. With eight equally likely
scenarios any confidence above 0.875 puts the whole tail weight on the single worst
scenario, so 0.90 and 0.95 are the same objective and returned the same year to the cent.
All three risk configurations met the rule's condition of a smaller validation tail loss
than the risk-neutral policy's 223, and the rule took the largest net among them.

Frozen: a thirty-day lookback with sixteen scenarios for the deterministic forecast,
thirty days with eight scenarios for the risk-neutral policy, and the same with a risk
weight of 0.25 at 0.95 confidence for CVaR. The persistence coefficient was refitted on
everything before the held-out year, 819 days and 18,838 hourly pairs, and held: 0.731 to
0.739 depending on the ensemble each policy uses.

## Measured results

The held-out year is 2025, replayed once per policy from 2 MWh, carrying energy across
every day boundary and ending each day at the same 2 MWh target. The archive supplied 364
of its 365 days in full; 2025-05-27 is recorded as skipped and the battery holds its
energy through it. Nothing was re-tuned, and no day was dropped.

| Policy | Day ahead | Imbalance | Gross | Costs | Net | 2.5% | 97.5% | Worst day | Drawdown | Tail loss 5% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no trading | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| deterministic forecast | -36,419 | 84,861 | 48,441 | 7,263 | 41,178 | 17,571 | 73,907 | -917 | 1,362 | 299 |
| risk neutral | -34,823 | 75,431 | 40,608 | 7,477 | 33,131 | 9,182 | 65,272 | -2,955 | 4,304 | 507 |
| CVaR | -28,584 | 67,827 | 39,243 | 7,259 | 31,983 | 6,365 | 64,947 | -4,274 | 5,981 | 585 |
| perfect foresight | -22,830 | 222,424 | 199,595 | 8,875 | 190,720 | 138,858 | 256,192 | 0 | 0 | -75 |

| Policy | Day-ahead MWh | Imbalance MWh | Grid MWh | Discharged MWh | Cycles | Delivered energy | Spread |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no trading | 0 | 0 | 0 | 0 | 0.0 | 0 | 0 |
| deterministic forecast | 7,203 | 8,014 | 2,905 | 1,332 | 361.9 | 28,357 | 12,821 |
| risk neutral | 7,210 | 8,032 | 2,991 | 1,371 | 372.6 | 26,573 | 6,558 |
| CVaR | 7,045 | 7,651 | 2,904 | 1,331 | 361.7 | 26,180 | 5,803 |
| perfect foresight | 6,982 | 9,177 | 3,550 | 1,627 | 442.2 | 89,522 | 101,198 |

| Policy | Solves | Seconds | ms per solve | Max gap | Holds | Skipped | Cold | Max SOC error MWh |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no trading | 364 | 0 | 0.0 | 0 | 0 | 1 | 0 | 0 |
| deterministic forecast | 35,308 | 725 | 20.5 | 0.0001 | 0 | 1 | 0 | 2.1e-15 |
| risk neutral | 35,308 | 1,919 | 54.4 | 0.0001 | 0 | 1 | 0 | 1.2e-15 |
| CVaR | 35,308 | 1,686 | 47.7 | 0.0001 | 0 | 1 | 0 | 3.1e-16 |
| perfect foresight | 35,308 | 475 | 13.5 | 9.9e-05 | 0 | 1 | 0 | 2.1e-15 |

The deterministic forecast earned the most of the three implementable policies, $41,178,
which is 21.6% of what perfect foresight earned on the same days. The risk-neutral policy
earned $33,131 and CVaR $31,983. The bootstrap intervals overlap almost completely, so
this ordering is not a measured difference between the policies: a year is not enough data
to separate them when ten days carry two thirds of the result.

The accounting split values physical energy at real time, less costs, and puts the
contracted position's day-ahead minus real-time basis in the spread column. The first
term is 69–82% of each implementable policy's net; the second is 18–31%. For perfect
foresight the spread is $101,198 of $190,720, 53%. These percentages describe an
accounting identity, not the causal contribution of non-delivery: the spread can remain
nonzero even when actual dispatch equals the position everywhere. The unbounded model
does permit convergence trading that a physical resource cannot freely take. The
delivery-cap experiment below measures how much net changes when that freedom is removed.

The year is a handful of days. For the deterministic policy the best day is 22% of the
year, the best ten days are 68%, and the best fifty are 100.2%, so the remaining 315 days
lose money in aggregate. July alone is 53% of its year, 65% of the risk-neutral policy's
and 67% of CVaR's, almost all of it on 2025-07-01, when the zone's real-time price stayed
above $1,000/MWh for two and a quarter hours and peaked at $3,807.52. Perfect foresight is
far less concentrated, 30% in its best ten days, because it collects the ordinary spread
every day as well.

The scenario ensemble is not a forecast. The day-ahead solve's expected score averaged
$285 a day for the deterministic policy against $113 realized, and $380 against $91 for
the risk-neutral one; the correlation between what a day was expected to earn and what it
earned is 0.16 and 0.19. The optimizer is exact given its scenarios, and the scenarios are
optimistic by a factor of two and a half to four.

CVaR did not deliver the tail it was selected for. On the validation year its tail loss
was 199 against the risk-neutral policy's 223, which is why the rule chose it; on the
held-out year its tail loss is 585 against 507, its worst day is -$4,274 against -$2,955,
and its drawdown is $5,981 against $4,304. Tuning a risk measure on one year did not
reduce it in the next. The reported ordering follows the pre-registered rule, and this is
what it produced.

Every solve reached its tolerance. Each trading policy ran 35,308 solves, between 475 and
1,919 seconds in total and 13 to 54 milliseconds each, at an achieved gap no larger than
the requested 1e-4, with no held step, no coarse retry and no cold start. The largest
energy-bound violation across 105,120 settlement intervals is 3e-15 MWh, and every policy
ended the year at the 2 MWh target. `tests/test_market.py` rebuilds each run's settlement
from its own interval rows by a path that shares nothing with the replay's arithmetic; on
these five runs the two agree to the cent.

## Requiring delivery of the day-ahead position

This sensitivity changes one market rule, in MW:

$$
|(d_{st}-c_{st})-q_t|\le\delta,
\qquad\delta\in\{\text{unbounded},1,0.25,0\}.
$$

There is one band per period and information node, both when the hourly position is
chosen and when dispatch is re-solved. The position is still frozen at bid close. A
1 MW cap permits deviation up to the battery's rated power; 0.25 MW permits a quarter of
it; zero requires the position to be delivered in every five-minute settlement bin.
`cap=None` adds no rows and retains the original behavior. All other physical limits,
costs, timestamps, scenario rules, solver tolerances and the end-of-day target stay fixed.
The MILP is checked against independently enumerated signed-flow LPs on seeded binding
cases, plus an analytical case where zero cap forces the entire day-ahead cycle.

The twelve settings pair `det`, `neutral` and `fore` with the four caps, using the frozen
values in [`selected.json`](results/selected.json). Eleven replayed the year; the twelfth
stopped on an infeasible capped dispatch and is reported as such below rather than
dropped. Persistence is refitted through 2024-12-31 by the original schedule and is
identical across caps for a given policy. There is no selection on the capped outcomes and
no re-tuning. Runs execute concurrently as detached
processes; completion is checked from each child's recorded exit status and its exported
result files, never from a log tail or a process search. Commands, configuration, source
hashes and independent interval audits are in
[`results/delivery/`](results/delivery/README.md), and `run_delivery.py` rebuilds them.

The reported delivered/spread columns keep the original identity:

$$
N=\underbrace{\sum_i[g_i\lambda_i^{RT}-k(c_i+d_i)]\Delta}_{A}
 +\underbrace{\sum_i q_i(\lambda_i^{DA}-\lambda_i^{RT})\Delta}_{S}.
$$

Here $A$ is delivered energy valued at real time less costs, and $S$ is the day-ahead
basis term. Even when $g_i=q_i$, $S$ need not vanish: it changes the valuation from real
time to day ahead. At zero cap, imbalance revenue and imbalance volume vanish, and net
is entirely the delivered day-ahead schedule less costs. The causal comparison for this
specified replay is the net change under the rule, $N_{\rm None}-N_0$, not the original
spread column. It includes the policy's response in both its offer and its dispatch.
Zero cap also removes all intraday redispatch flexibility; the net difference is the
effect of that specified delivery rule, not an estimate of virtual-bid revenue alone.

| Policy | Cap MW | Net | Change | Change % | 2.5% | 97.5% | Worst day | Drawdown | Tail loss 5% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| deterministic forecast | unbounded | 41,178 | 0 | 0.0 | 17,571 | 73,907 | -917 | 1,362 | 299 |
| deterministic forecast | 1 | 33,006 | -8,172 | -19.8 | 16,901 | 53,854 | -1,397 | 2,698 | 306 |
| deterministic forecast | 0.25 | 27,396 | -13,782 | -33.5 | 18,930 | 37,875 | -1,333 | 1,732 | 136 |
| deterministic forecast | 0 | 30,153 | -11,025 | -26.8 | 23,482 | 38,935 | -54 | 54 | 15 |
| risk neutral | unbounded | 33,131 | 0 | 0.0 | 9,182 | 65,272 | -2,955 | 4,304 | 507 |
| risk neutral | 1 | 26,727 | -6,403 | -19.3 | 7,072 | 47,523 | -4,401 | 6,046 | 519 |
| risk neutral | 0.25 | infeasible 2025-12-15 | — | — | — | — | — | — | — |
| risk neutral | 0 | 30,131 | -2,999 | -9.1 | 23,432 | 38,924 | -54 | 54 | 15 |
| perfect foresight | unbounded | 190,720 | 0 | 0.0 | 138,858 | 256,192 | 0 | 0 | -75 |
| perfect foresight | 1 | 134,831 | -55,889 | -29.3 | 101,627 | 175,875 | 0 | 0 | -67 |
| perfect foresight | 0.25 | 63,161 | -127,559 | -66.9 | 49,534 | 79,494 | 0 | 0 | -34 |
| perfect foresight | 0 | 36,536 | -154,184 | -80.8 | 29,241 | 45,393 | 0 | 0 | -11 |

| Policy | Cap MW | Day-ahead MWh | Imbalance MWh | Max deviation MW | Grid MWh | Cycles | Delivered energy | Spread |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| deterministic forecast | unbounded | 7,203 | 8,014 | 2 | 2,905 | 361.9 | 28,357 | 12,821 |
| deterministic forecast | 1 | 5,961 | 6,190 | 1 | 2,369 | 295.0 | 26,369 | 6,637 |
| deterministic forecast | 0.25 | 3,815 | 1,862 | 0.25 | 2,918 | 363.4 | 34,171 | -6,775 |
| deterministic forecast | 0 | 3,010 | 0 | 1.1e-16 | 3,010 | 374.9 | 41,777 | -11,624 |
| risk neutral | unbounded | 7,210 | 8,032 | 2 | 2,991 | 372.6 | 26,573 | 6,558 |
| risk neutral | 1 | 5,701 | 6,016 | 1 | 2,506 | 312.2 | 28,040 | -1,313 |
| risk neutral | 0.25 | — | — | — | — | — | — | — |
| risk neutral | 0 | 2,983 | 0 | 1.1e-16 | 2,983 | 371.5 | 42,554 | -12,423 |
| perfect foresight | unbounded | 6,982 | 9,177 | 2 | 3,550 | 442.2 | 89,522 | 101,198 |
| perfect foresight | 1 | 5,917 | 6,811 | 1 | 2,437 | 303.6 | 68,774 | 66,057 |
| perfect foresight | 0.25 | 3,758 | 1,881 | 0.25 | 2,779 | 346.2 | 55,037 | 8,124 |
| perfect foresight | 0 | 2,988 | 0 | 1.1e-16 | 2,988 | 372.2 | 50,301 | -13,765 |

| Policy | Cap MW | Solves | Seconds | Max raw gap | Holds | Coarse | Max SOC error MWh | Max cap excess MW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| deterministic forecast | unbounded | 35,308 | 1,068 | 0.0001 | 0 | 0 | 2.1e-15 | 0 |
| deterministic forecast | 1 | 35,308 | 1,178 | 0.23 | 0 | 0 | 2.7e-15 | 1.4e-14 |
| deterministic forecast | 0.25 | 35,308 | 1,208 | 0.0001 | 0 | 0 | 1.8e-15 | 2.2e-13 |
| deterministic forecast | 0 | 35,308 | 665 | 1.4e-16 | 0 | 0 | 3.5e-15 | 1.1e-16 |
| risk neutral | unbounded | 35,308 | 1,686 | 0.0001 | 0 | 0 | 1.2e-15 | 0 |
| risk neutral | 1 | 35,308 | 2,060 | 0.22 | 0 | 0 | 1.8e-15 | 6.3e-14 |
| risk neutral | 0.25 | — | — | — | — | — | — | — |
| risk neutral | 0 | 35,308 | 1,617 | 2e-16 | 0 | 0 | 3.5e-15 | 1.1e-16 |
| perfect foresight | unbounded | 35,308 | 1,051 | 9.9e-05 | 0 | 0 | 2.1e-15 | 0 |
| perfect foresight | 1 | 35,308 | 1,156 | 0.091 | 0 | 0 | 3.6e-15 | 2.3e-14 |
| perfect foresight | 0.25 | 35,308 | 1,192 | 0.05 | 0 | 0 | 2.5e-15 | 3.6e-13 |
| perfect foresight | 0 | 35,308 | 653 | 4.9e-16 | 0 | 0 | 1.4e-14 | 1.1e-16 |

Every implementable policy earns less when it must deliver, and the accounting spread is
not the size of the loss in either direction. At full delivery the deterministic forecast
falls from $41,178 to $30,153, 26.8%, against a spread of $12,821 that is 31.1% of its
unbounded net. The risk-neutral policy falls from $33,131 to $30,131, 9.1%, against a
spread of 19.8%. Perfect foresight falls from $190,720 to $36,536, 80.8%, against a spread
of 53.1%. The spread overstates what the two implementable policies take from the
deviation and understates foresight's by half. It is an accounting identity; the replay
under the rule is the measurement.

The effect is not monotone in the cap for either implementable policy. The deterministic
forecast earns less at 0.25 MW, $27,396, than at either 1 MW or full delivery, and the
risk-neutral policy earns less at 1 MW, $26,727, than at full delivery. A band is not a
weaker obligation: it still leaves the policy free to act on its forecast in real time
while removing part of the position it would have acted against. Full delivery removes
that freedom outright, which for an ensemble optimistic by a factor of two and a half to
four is worth more than the flexibility it costs. These are three points from one year and
the bootstrap intervals overlap, so the ordering between adjacent caps is not a measured
difference between them.

What full delivery does measure cleanly is how much of the year came from deviating.
Imbalance volume falls from about 8,000 MWh to zero and the largest absolute deviation to
1e-16 MW, day-ahead volume falls from about 7,200 MWh to about 3,000, and cycles are
unchanged: 362 against 375 for the deterministic policy. The battery moves the same
energy. It commits it a day ahead instead of trading around it.

Concentration falls with it. July is 52.7% of the deterministic year unbounded and 24.8%
under full delivery, and its best ten days fall from 67.5% to 23.5%, the risk-neutral
policy's from 83.3% to 23.6%. The dependence on a handful of scarcity days reported above
is largely a property of unbounded real-time deviation rather than of delivered energy.
Daily risk falls with it: the risk-neutral worst day is -$54 under full delivery against
-$2,955 unbounded, and its drawdown $54 against $4,304. At the 1 MW band both are worse
than unbounded, -$4,401 and $6,046. Under full delivery the three policies nearly
converge, at $30,153, $30,131 and $36,536, and foresight's advantage over the
deterministic forecast falls from 4.6 times to 1.2.

One of the twelve settings has no result. The risk-neutral policy at a 0.25 MW cap stopped
on 2025-12-15 at 12:00. It had sold 1 MW for the 17:00 and 18:00 hours, held 0.40 MWh at
noon, and the band forces at least 0.75 MW of discharge through both of those hours, so
the store reaches zero at 18:45 even when charging as hard as the band allows. The
end-of-day target was not the binding constraint: 2.46 MWh was reachable against a 2 MWh
target. The position itself was undeliverable, the coarse retry returned infeasible rather
than slow, and decision 52 stops the replay instead of holding at zero power and breaching
the obligation. An offer that is a feasible hourly schedule from the 2 MWh assumed at bid
close is not necessarily deliverable at fifteen-minute resolution from the energy the
battery actually holds. That is a property of this rule and this policy, reported rather
than removed.

The eleven completed replays each ran 35,308 solves with no held step, no coarse retry and
no cold start, and no dispatch exceeds its cap by more than 4e-13 MW. Settlement rebuilt
from each run's own interval rows agrees with its reported total to within $0.006 over the
year, and stored energy recomputed from the dispatch to 4.2e-5 MWh over 105,120 intervals.
The three unbounded replays reproduce the original study exactly: every metric differs from
`results/<policy>/metrics.json` by zero. Thirteen days report a raw relative gap above the
requested 1e-4, all at the 1 and 0.25 MW caps and the largest 0.226; on the twelve solves
behind them the full score and its certified bound differ by at most 1.2e-14, which is the
numerical case described above and not an unconverged solve.

The cap is a hypothetical delivery requirement. It does not establish that the resulting
schedules obey NYISO bid parameters or ISO dispatch. Under a finite cap the original
zero-power fallback can violate an obligation, so after the usual coarse retry a failed
dispatch stops the replay and produces no completed result; the unbounded fallback is
unchanged. A target reachable under battery limits alone is not a guarantee that an
arbitrary contracted position is feasible under the cap, and on one of these twelve
settings it was not.

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
  monthly table and the bootstrap interval are reported for that reason, and the
  difference between the three implementable policies is inside those intervals.
- The unbounded model permits a day-ahead position to settle back in real time rather
  than be delivered. Imbalance volume measures the deviation; the accounting spread alone
  does not measure its profit contribution. The delivery-cap experiment measures the
  change under a hypothetical obligation to deliver. It still does not implement NYISO
  registration, ISO dispatch or the charges for a physical resource or a virtual bid.
- Tuning a risk measure on one year did not reduce it in the next. CVaR was selected for
  the smaller validation tail and produced a larger held-out tail than the risk-neutral
  policy. One year of selection data is thin for a tail statistic.
- One zone, one battery size, one year held out. Nothing here is a general statement
  about storage profitability.
- The archive restates corrected prices. The study reads it as it stood on 2026-09-15, so
  where a price was later corrected the corrected value is used, while a participant
  deciding at the time saw the original. The difference is not measured.
