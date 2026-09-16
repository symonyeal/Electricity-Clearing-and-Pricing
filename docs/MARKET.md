# Historical storage replay

One 1 MW, 4 MWh battery is replayed chronologically against published N.Y.C. zonal prices.
The experiment values the model in [Storage trading](TRADING.md). It does not reproduce
NYISO bid acceptance, dispatch, or settlement rules.

## Data and assumptions

| Item | Specification |
| --- | --- |
| Day-ahead price | NYISO zonal LBMP, hourly |
| Real-time price | NYISO zonal LBMP, five-minute bins |
| Training | 2022-10-01 through 2023-12-31 |
| Validation | 2024 |
| Evaluation | 2025 |
| Battery | 1 MW, 4 MWh, 92% one-way efficiency |
| Costs | $2/MWh degradation and $0.50/MWh transaction cost |
| State | 2 MWh initial and daily terminal energy |

Monthly archives were downloaded on 2026-09-15 and retained without modification outside
the repository. Timestamps are interpreted in `America/New_York` and converted to UTC.
Transition days contain 23 or 25 hours. The full record has 28,513 day-ahead hours and
342,123 of 342,156 expected real-time bins. The 33 missing bins occur on 2025-05-27; that
day is recorded and excluded from trading. No price is imputed.

The real-time files may contain irregular postings within a five-minute bin. The parser
weights each posting by its inferred duration, from the preceding stamp to its own stamp.
This convention is derived from the files, not from a market manual.

The model assumes price taking, full acceptance of the day-ahead position, participant
self-dispatch, and single-price deviation settlement. It omits tariffs, ancillary services,
capacity revenue, transmission contracts, station power, taxes, mitigation, collateral,
metering adjustments, and fixed asset costs.

## Settlement and information

For five-minute interval $i$ in hour $h$,

$$
q_h\lambda_h^{DA}\Delta
+(g_i-q_h)\lambda_i^{RT}\Delta
-(k_{\rm deg}+k_{\rm fee})(c_i+d_i)\Delta,
\qquad g_i=d_i-c_i,\quad \Delta=1/12.
$$

The hourly position is chosen at the configured 05:00 decision time on the preceding day.
It uses complete days through $D-2$. Dispatch is recomputed every fifteen minutes and uses
real-time prices ending at least ten minutes earlier. A leakage test perturbs later prices
and requires every earlier action to remain unchanged.

Scenarios are complete historical days of the same weekday class within a lookback window.
Quantile spacing selects $S$ paths by mean real-time price. Each path retains its joint
day-ahead and real-time curves. One persistence coefficient shifts the intraday ensemble
from the latest observed residual. Information nodes partition the ensemble; a node is
split only while both children contain at least two paths.

| Policy | Price information | Objective |
| --- | --- | --- |
| `idle` | none | no trading |
| `det` | ensemble mean | expected profit on one path |
| `neutral` | scenario tree | expected profit |
| `cvar` | scenario tree | mean profit and loss CVaR |
| `fore` | realized path | perfect-foresight upper reference |

## Protocol

The persistence coefficient is fitted on training data. Hyperparameters are selected on
2024. The coefficient is then refitted through 2024, the selected settings are frozen, and
2025 is evaluated once for each policy. The selected settings are recorded in
[`results/selected.json`](results/selected.json); the validation grid is in
[`results/tune.md`](results/tune.md).

Annual uncertainty is a seeded moving-block bootstrap of daily net settlement with block
length $\lceil n^{1/3}\rceil$ and 10,000 replications. This is sampling uncertainty for the
observed daily series; it does not include model or market-rule uncertainty.

## Results

The archive supplied 364 complete days in 2025. Each trading policy ran 35,308 solves. All
reached the requested $10^{-4}$ gap; no step used the fallback. The largest energy-balance
error is $2.1\times10^{-15}$ MWh. For the deterministic, risk-neutral, and perfect-foresight
policies, settlement rebuilt from the exported intervals differs by at most $0.0013; CVaR
was not reconciled from exports. That check is recorded in the
[archived audit](../_archive/20260916-focus-reset/delivery/results/nyc/2025/audit.json).

| Policy | Net, $ | 95% block interval, $ | Worst day, $ | Cycles |
| --- | ---: | ---: | ---: | ---: |
| No trading | 0 | [0, 0] | 0 | 0.0 |
| Deterministic | 41,178 | [17,571, 73,907] | -917 | 361.9 |
| Risk neutral | 33,131 | [9,182, 65,272] | -2,955 | 372.6 |
| CVaR | 31,983 | [6,365, 64,947] | -4,274 | 361.7 |
| Perfect foresight | 190,720 | [138,858, 256,192] | 0 | 442.2 |

The forecast-based intervals overlap; the year does not separate their expected
performance. The deterministic policy obtains 67% of annual net settlement on its ten
best days and 53% in July. Its mean expected and realized daily scores are $285 and $113,
with correlation 0.16. The risk-neutral values are $380 and $91, with correlation 0.19.
The scenario model is therefore poorly calibrated for realized profit.

CVaR reduced validation tail loss from $223 to $199 but increased the evaluated tail loss
from $507 to $585 relative to the risk-neutral policy. Selection on one year did not
produce a smaller tail in the next.

Full tables, monthly values, run configurations, and figures are in
[`docs/results/`](results/README.md).

## Post-hoc delivery sensitivity

A later experiment reused 2025 with the deviation constraint

$$
|(d_{st}-c_{st})-q_t|\le\delta,
\qquad\delta\in\{\infty,1,0.25,0\}\ \text{MW}.
$$

It covered the deterministic, risk-neutral, and perfect-foresight policies; CVaR was not
run. It is a post-hoc sensitivity, not an independent held-out result. At $\delta=0$, net
settlement was 30,153 USD, 30,131 USD, and 36,536 USD, respectively. The risk-neutral run at
$\delta=0.25$ stopped on 2025-12-15 because its fixed position was infeasible. Eleven
completed runs passed independent settlement, energy, and cap checks. The program and
evidence are [archived](../_archive/20260916-focus-reset/delivery/results/README.md).

## Reproduction

```text
python run_market.py fetch
python run_market.py validate --out results/coverage.json
python run_market.py smoke
python run_market.py tune --out results/tune
python run_market.py select --dir results/tune
python run_market.py run --period test --pol all --out results/test
python run_market.py report --dir results/test
```

Only `fetch` uses the network. Tests use committed fixtures.

## Limits

- Published prices are outputs of the market, not proof that modeled positions would clear.
- The configured bid time, information lag, and settlement convention are study assumptions.
- The daily terminal target excludes multi-day arbitrage.
- Corrected archive prices may differ from prices available to a participant in real time.
- Results cover one zone, one battery, and one evaluation year.
