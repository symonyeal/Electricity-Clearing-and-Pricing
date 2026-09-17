# Historical storage replay

One 1 MW, 4 MWh battery is replayed chronologically against published N.Y.C. zonal prices.
The battery follows the model of [Storage trading](TRADING.md). The replay does not
reproduce NYISO bid acceptance, dispatch, or settlement rules.

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

Let $q_h$ be the hourly day-ahead position, $\lambda_h^{DA}$ and $\lambda_i^{RT}$ the
day-ahead and real-time prices, $c_i$ and $d_i$ grid-side charge and discharge, and
$k_{\rm deg}$ and $k_{\rm fee}$ the degradation and transaction costs. Settlement in
five-minute interval $i$ of hour $h$ is

$$
R_i=q_h\lambda_h^{DA}\Delta
+(g_i-q_h)\lambda_i^{RT}\Delta
-(k_{\rm deg}+k_{\rm fee})(c_i+d_i)\Delta,
\qquad g_i=d_i-c_i,\quad \Delta=1/12.
$$

This is the two-settlement form of [Storage trading](TRADING.md), per interval.

The hourly position is chosen at the configured 05:00 decision time on the preceding day.
It uses complete days through $D-2$. Dispatch is recomputed every fifteen minutes and uses
real-time prices ending at least ten minutes earlier. A leakage test perturbs later prices
and requires every earlier action to remain unchanged.

Scenarios are complete historical days of the same weekday class within a lookback window.
Quantile spacing selects $S$ paths by mean real-time price. Each path retains its joint
day-ahead and real-time curves. One persistence coefficient shifts the intraday ensemble
from the latest observed residual. Information nodes partition the ensemble; a node is
split only while both children contain at least two paths.

An analog day is put on the target day's **local clock hours**, not on its elapsed offsets
from midnight. The two agree on every pair of ordinary days and differ on the two days a
year whose lengths differ, where a target of 23 or 25 hours must be filled from an analog
of 24. What an analog supplies is a shape that belongs to the clock — the morning ramp and
the evening peak happen at a local hour — so the analog's 18:00 is used as the target's
18:00 whichever side of a transition it falls on. Concretely:

| Target | Local hours it settles | What a 24-hour analog supplies |
| --- | --- | --- |
| Spring, 23 hours | `00, 01, 03, …, 23` | its own hours, less local `02`, which the day does not have |
| Autumn, 25 hours | `00, 01, 01, 02, …, 23` | its own hours, with local `01` serving both passes |

The two passes of the autumn `01` differ in their offset from UTC and not in where they
sit in the local day, so one observation of that hour answers for both. An analog that is
itself a transition day, and so lacks an hour the target asks for, supplies its nearest.
The labels are read from `America/New_York` rather than assumed, so a change to the rule
carries into them.

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

364 of the 365 days in 2025 are complete. Each trading policy ran 35,308 solves. All
reached the requested $10^{-4}$ gap; no step used the fallback. The largest energy-balance
error in these runs is $2.1\times10^{-15}$ MWh. For the deterministic, risk-neutral, and
perfect-foresight policies, settlement rebuilt from the exported intervals differs by at
most $0.0013; CVaR was not reconciled from exports. The
[audit record](results/delivery/nyc/2025/audit.json) carries those checks.

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

## Delivery sensitivity

The settlement above assumes the day-ahead position is accepted in full and that the
participant self-dispatches around it. Relaxing that assumption imposes the band

$$
-\delta\le(d_{st}-c_{st})-q_t\le\delta,
\qquad \delta\in\{\infty,1,0.25,0\}\ \text{MW},
$$

on the same year. At $\delta=0$ the position is delivered exactly; $\delta=\infty$ is the
unbounded replay. Net settlement, in dollars:

| Policy | $\delta=\infty$ | $\delta=1$ | $\delta=0.25$ | $\delta=0$ |
| --- | ---: | ---: | ---: | ---: |
| Deterministic | 41,178 | 33,006 | 27,396 | 30,153 |
| Risk neutral | 33,131 | 26,727 | infeasible | 30,131 |
| Perfect foresight | 190,720 | 134,831 | 63,161 | 36,536 |

Delivery is the binding assumption: enforcing it removes 27% of the deterministic result and
81% of the perfect-foresight reference. The response is not monotone in $\delta$, because the
band also changes the position chosen against it. The risk-neutral run at $\delta=0.25$
stopped on 2025-12-15 with an infeasible capped dispatch, the specified outcome for a fixed
position under a finite band. CVaR was not run.

The band reuses the evaluation year, so it is a sensitivity and not a second held-out result.
Eleven completed runs passed independent settlement, energy, and band checks. A capped run can
report a large raw relative gap, because the contract's constant profit leaves a near-zero
variable objective; the audit re-solves those days and requires the full score to lie within
$10^{-7}$ of its certified bound. Results and the audit record are in
[`docs/results/delivery/`](results/delivery/README.md).

## Market interface

The replay above assumes the day-ahead position is accepted in full, at no charge, by a
resource the market admits. `market/bid.py` replaces each of those with a rule:

| Rule | Parameter | Default |
| --- | --- | --- |
| Offer the position as a curve and accept what the cleared price supports | `bk`, `bs` | `bk = 0`, full acceptance |
| Charge metered energy in both directions | `tar` | 0 |
| Admit only a resource above a rated power and a duration | `qmin`, `qdur` | 0, everything admitted |

The defaults reproduce the study above exactly, which is asserted in the tests. The curve
shape, the rate and the thresholds are parameters; they are not NYISO's, and fitting them
to a published tariff and qualification manual is not done here.

The curve is offered around the price the position was chosen at: the probability-weighted
day-ahead price of the scenario set. Under `fore` that reference is the realized price
itself, so the cleared price lands exactly at the centre of the curve and the accepted
share is $\lceil bk/2 \rceil / bk$ whatever the spread, one half for even `bk`. A
perfect-foresight run with `bk > 1` is therefore no longer an upper reference on what the
policies could earn; it is foresight bidding into its own price. Read the `fore` row with
`bk = 0`, which is how the study above is run.

### The tariff is charged after the decision, not inside it

`tar` is a post-hoc charge. The optimizing battery is built with throughput cost
`kd + fee`; both the day-ahead offer and the real-time dispatch read that record, and
settlement then charges `tar` on metered charge and discharge on top of it. **A run with
`tar > 0` therefore takes the same schedule it would have taken at `tar = 0` and subtracts
the charge afterwards.** That is an ex-post stress test of an existing policy, not a policy
that has been told what the energy costs.

The consequence is that a large enough tariff makes the selected trade lose money. Two
five-minute periods, $E=C=D=1$ MWh/MW, unit efficiencies, zero endpoints, `kd = fee = 0`,
`tar = 2` and prices $[10, 12]$:

| Quantity | Value |
| --- | ---: |
| Chosen schedule | charge $[1,0]$, discharge $[0,1]$ |
| Profit the model optimized | $+0.166667$ |
| Tariff settled | $0.333333$ |
| Net actually settled | $-0.166667$ |
| What pricing the tariff would choose | no trade, net $0$ |

The reported decomposition inherits the same boundary. `arb` in `market/report.py` is
defined against `kd + fee` only, so `arb + spread - net` reconciles at `tar = 0` and misses
by exactly the metered tariff otherwise — on the committed three-day fixture at `tar = 5`,
both sides are $149.143047259$.

None of this moves a published result: every committed run uses `tar = 0`, which is the
default, and the tests assert that the defaults reproduce the baseline to the cent. Pricing
the tariff into the objective is a separate piece of work and is recorded as such in
[Decisions](DECISIONS.md); it is not a bug being left unfixed but a scope line being drawn,
and this section is the disclosure that it was drawn here.

## Reproduction

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

`run_delivery.py` replays the delivery band and rebuilds its audit record. Only `fetch`
uses the network. Tests use committed fixtures.

## Limits

- Published prices are outputs of the market, not proof that modeled positions would clear.
- `tar` is charged in settlement and not priced into the policy; see the section above.
- The configured bid time, information lag, and settlement convention are study assumptions.
- The daily terminal target excludes multi-day arbitrage.
- Corrected archive prices may differ from prices available to a participant in real time.
- Results cover one zone, one battery, and one evaluation year.
