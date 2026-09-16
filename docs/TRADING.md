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

Path 0 defines the common forward offer $q_t=d_{0t}-c_{0t}$. It obeys the same physical
limits and endpoints, so an offer must be deliverable as a complete battery schedule.
Actual paths may deviate. In scenario $s$, profit is

$$
R_s=\Delta\sum_t\left[\lambda_t^{DA}q_t+
\lambda_{st}^{RT}(d_{st}-c_{st}-q_t)-k(c_{st}+d_{st})\right].
$$

$k$ is a linear cost per grid MWh charged or discharged. The nominal schedule incurs no
physical throughput cost: actual operation incurs it once. The deviation term avoids
counting the forward sale twice. Both settlements use the same time grid; an hourly
day-ahead price and MW schedule must be repeated over its real-time intervals.

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
| `st` | Sparse MIP with one binary per information node and per nominal period | HiGHS branch and bound; default requested relative gap zero |
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

## Use

```python
from models.storage import B, st

b = B(e=1, c=1, d=1, ec=1, ed=1)
r = st(b, da=[10, 40], rt=[[10, 100], [10, -100]], pr=[0.8, 0.2], a=0.8, w=0.5)
print(r.q, r.r, r.mu, r.cv, r.ub, r.gap)
# [-1, 1], [30, 30], 30, -30, 30, 0 (up to numerical tolerance)
```

Pass `q=r.q` on a subsequent solve to hold an existing offer fixed. For rolling operation,
pass the measured initial energy in `B.e0`, the remaining fixed offer, and scenarios
conditioned only on available information; implement the first action and repeat.
`ef` is a hard terminal requirement, so choose it for the remaining horizon.

The published mathematical precedents are the energy/mode rows in HydroBoost and the
Rockafellar-Uryasev risk formulation, also used by LOGOS. The combined model here is a
restricted adaptation, not a replication of either project's full application. Its worked
examples are synthetic. `run_storage.py` reproduces them and the timings in
[Validation](VALIDATION.md).

## Scope

Prices are exogenous. `da` is one supplied day-ahead curve; before clearing, treating it
as fixed omits day-ahead price uncertainty and bid acceptance. The model produces a
quantity schedule, not a price-dependent bid curve or an exchange submission. It includes
single-price real-time imbalance settlement and unrestricted deviations within battery
limits. It omits reserve products, network constraints, nonlinear degradation, fees,
collateral, market-specific qualification, imbalance penalties and market impact.

Use this for formulation research, schedule valuation and scenario hedging. Real trading
requires the target market's rules and time-stamped out-of-sample inputs. An exact optimum
for supplied scenarios does not establish forecast skill or realized trading profit.

The existing UC and CHP models provide structural prices and uplift diagnostics. Feeding
their prices here is meaningful only under the price-taker assumption; including a large
battery in clearing would require a joint formulation. CHP and AIC outputs are not assumed
to be the target market's settlement prices.
