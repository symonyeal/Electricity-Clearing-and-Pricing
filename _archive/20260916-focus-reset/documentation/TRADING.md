# Storage trading

`models/storage.py` implements a price-taking storage offer with day-ahead and real-time
settlement, an explicit information tree, and Rockafellar-Uryasev CVaR. It uses the storage
balance and binary operating modes represented in HydroBoost, restricted to one battery
and energy trading. [INL assessment](INL.md) records the local code reviewed.

## Formulation

Let $c_{st},d_{st}$ be grid-side charge and discharge in MW, $e_{st}$ stored MWh, and
$u_{st}$ a charge-mode binary. With interval duration $\Delta$, every path satisfies

$$
\begin{aligned}
e_{st}&=e_{s,t-1}+\Delta(\eta_c c_{st}-d_{st}/\eta_d),\\
0&\le e_{st}\le E,\quad e_{s0}=E_0,\quad e_{sT}=E_f,\\
0&\le c_{st}\le C u_{st},\quad
0\le d_{st}\le D(1-u_{st}),\quad u_{st}\in\{0,1\}.
\end{aligned}
$$

$E$ is usable energy above the physical SOC floor. The implementation tightens $C$ to
$\min(C,E/(\Delta\eta_c))$ and $D$ to $\min(D,E\eta_d/\Delta)$. These are valid physical
bounds. Simultaneous charging and discharging is excluded even at negative prices.

Path 0 defines the common forward position $q_t$. In scenario $s$, profit is

$$
R_s=\Delta\sum_t\left[\lambda_{st}^{DA}q_t+
\lambda_{st}^{RT}(d_{st}-c_{st}-q_t)-k(c_{st}+d_{st})\right].
$$

The day-ahead price may be one common curve $\lambda_t^{DA}$ or one curve per scenario.
A position decided before the day-ahead market clears faces an unknown clearing price,
and a scenario then carries a day-ahead and a real-time curve together.

$k$ is a linear cost per grid MWh charged or discharged. The nominal schedule incurs no
physical throughput cost: actual operation incurs it once. The deviation term avoids
counting the forward sale twice. Both settlements use the same time grid; an hourly
day-ahead price and MW schedule must be repeated over its real-time intervals.

## An offer and an obligation are different objects

A position being chosen must be deliverable. With `q=None` the nominal path is a physical
schedule: it obeys the same limits, balance and endpoints as any other path, so the model
cannot offer energy the battery cannot produce from the energy it is assumed to hold.

A position already contracted is financial. Passing `q` fixes it, and the model then
builds no nominal path at all: the fixed terms enter the scenario profit as a constant,
physical rows exist only for the scenario paths, and dispatch and imbalance settlement
adapt around the obligation. This matters after real-time deviations. The energy a
schedule was planned from is not the energy the battery now holds, and requiring an
existing obligation to be physically reproducible from the current energy would report a
false infeasibility for a position that in fact simply settles. `Sol.e[0]` is `nan` for a
fixed position, because a contract has no physical trajectory, and `Sol.c[0]`, `Sol.d[0]`
carry the position split into its buying and selling parts.

An optional delivery rule bounds deviations on every scenario information node:

$$
-\delta \le (d_{st}-c_{st})-q_t \le \delta,\qquad \delta\ge0.
$$

`cap=delta` supplies this limit in MW; `cap=None` omits these rows and preserves the
unbounded model. `cap=0` forces actual dispatch to deliver the hourly position. The rule
applies both while choosing an offer and after contracting it. A supplied `q` still adds
no nominal physical path: the band constrains the actual scenario paths instead. A fixed
position can consequently be infeasible under a finite cap. The MIP adds one two-sided
sparse row per period and information node; the independent enumeration adds the two
halfspaces in signed flow, without using charge/discharge columns or SOC variables.

For probabilities $p_s>0$ summing to one, confidence $0\le\alpha<1$, and weight
$0\le w\le1$, maximize

$$
(1-w)\sum_s p_s R_s-w\left[\zeta+\frac{1}{1-\alpha}\sum_s p_s\xi_s\right],
\qquad \xi_s\ge -R_s-\zeta,\quad \xi_s\ge0,\quad\zeta\in\mathbb R.
$$

This is the Rockafellar-Uryasev epigraph for CVaR of **loss**, $-R_s$. A negative CVaR
means the worst tail still earns money. `cvar` independently computes the weighted tail,
splitting probability mass at the quantile; it remains valid when $w=0$ and the solver's
risk variables are not minimized. The score equals mean profit at $w=0$ and negative
CVaR at $w=1$.

## Information and exactness

`h[s,t]` names the information available when action $t$ is chosen. Scenarios with the
same label in a period share charge, discharge, energy and mode columns. Nodes may branch
but cannot merge after distinct histories. A label has meaning only within its period.
`h=None` shares every real-time decision across all scenarios: no uncertainty is revealed.
Distinct labels from the first period mean the whole path is revealed at that point.
That is a perfect-information recourse assumption and is usually optimistic.

The caller must define labels from information actually available at the decision time.
Current prices may distinguish nodes only if they are observed before dispatch. The
optimizer cannot verify when an input price became known. The 24-hour example deliberately
reveals the remaining price path at hour 13; it tests a tree, not a live trading policy.

| Route | Formulation | Limit |
| --- | --- | --- |
| `st` | Sparse MIP with one binary per information node, and per nominal period when an offer is chosen | HiGHS branch and bound; default requested relative gap zero, optional time limit |
| `en` | Enumerate charge/export signs, then solve signed-flow LPs with cumulative energy bounds | At most 12 nodes, including the nominal path |

The independent route has no SOC variables or separate charge/discharge columns and does
not call the MIP row builder. Both share input validation, the information-tree mapping
and result accounting. Analytical tests separately check physics, settlement and information.

`Sol.z` is the achieved risk score; `ub` is its certified upper bound and `gap` the
achieved relative solver gap. `mu`, `cv`, and `r` give mean profit, loss CVaR and scenario
profits. `q` is the forward MW schedule. Arrays `c,d,e` have shape `(S+1,T)`, nominal
path first. Only a solve reaching its requested tolerance is returned. Exact refers to
the finite MILP formulation and its certificate within solver tolerances, not exact
arithmetic or an exact representation of uncertain future prices.

`gap` retains the solver's raw relative ratio for its variable objective, which excludes
the fixed position's profit constant. Near a zero variable objective that ratio can be
large even when the full profit and its bound agree to rounding. Inspect `ub-z` as well;
the delivery experiment records targeted replays of these numerical cases rather than
replacing the reported ratios or claiming that every raw relative gap met the target.

## Use

```python
from models.storage import B, st

b = B(e=1, c=1, d=1, ec=1, ed=1)
r = st(b, da=[10, 40], rt=[[10, 100], [10, -100]], pr=[0.8, 0.2], a=0.8, w=0.5)
print(r.q, r.r, r.mu, r.cv, r.ub, r.gap)
# [-1, 1], [30, 30], 30, -30, 30, 0 (up to numerical tolerance)
```

Pass `q=r.q` on a subsequent solve to settle an existing obligation. For rolling
operation, pass the measured initial energy in `B.e0`, the remaining contracted position,
and scenarios conditioned only on available information; implement the first action and
repeat. `ef` is a hard terminal requirement, so choose it for the remaining horizon, and
choose one it can reach. `lim` bounds solver seconds; a solve that does not reach the
requested gap raises rather than returning its incumbent.

[The historical study](MARKET.md) runs exactly this loop against published New York ISO
prices, and reports what it measured.

The published mathematical precedents are the energy/mode rows in HydroBoost and the
Rockafellar-Uryasev risk formulation, also used by LOGOS. The combined model here is a
restricted adaptation, not a replication of either project's full application. Its worked
examples are synthetic. `run_storage.py` reproduces them and the timings in
[Validation](VALIDATION.md).

## Scope

Prices are exogenous. `da` may be one curve or one per scenario; either way the model
takes the clearing price as given and assumes the position is accepted in full, which
omits bid acceptance. The model produces a
quantity schedule, not a price-dependent bid curve or an exchange submission. It includes
single-price real-time imbalance settlement and an optional absolute deviation cap within
battery limits. The cap is a hypothetical market rule, not a NYISO participation model.
It omits reserve products, network constraints, nonlinear degradation, fees,
collateral, market-specific qualification, imbalance penalties and market impact.

Use this for formulation research, schedule valuation and scenario hedging. Real trading
requires the target market's rules and time-stamped out-of-sample inputs. An exact optimum
for supplied scenarios does not establish forecast skill or realized trading profit.
[The historical study](MARKET.md) supplies time-stamped out-of-sample inputs and states
which market execution assumptions remain unvalidated.

The existing UC and CHP models provide structural prices and uplift diagnostics. Feeding
their prices here is meaningful only under the price-taker assumption; including a large
battery in clearing would require a joint formulation. CHP and AIC outputs are not assumed
to be the target market's settlement prices.
