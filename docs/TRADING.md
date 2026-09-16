# Storage trading

`models/storage.py` gives a price-taking battery with day-ahead settlement, real-time
recourse, nonanticipativity, and loss CVaR.

## Formulation

For scenario $s$ and period $t$, let $c_{st}$ and $d_{st}$ be grid-side charge and
discharge, $e_{st}$ stored energy, and $u_{st}$ the charge-mode binary. With period length
$\Delta$,

$$
\begin{aligned}
e_{st}&=e_{s,t-1}+\Delta(\eta_c c_{st}-d_{st}/\eta_d),\\
0&\le e_{st}\le E,\quad e_{s0}=E_0,\quad e_{sT}=E_f,\\
0&\le c_{st}\le C u_{st},\quad
0\le d_{st}\le D(1-u_{st}),\quad u_{st}\in\{0,1\}.
\end{aligned}
$$

Simultaneous charge and discharge is infeasible. The implementation tightens the power
bounds to the energy that can enter or leave in one period.

Let $q_t$ be the day-ahead position. Scenario profit is

$$
R_s=\Delta\sum_t\left[
\lambda^{DA}_{st}q_t+
\lambda^{RT}_{st}(d_{st}-c_{st}-q_t)-k(c_{st}+d_{st})
\right].
$$

The first term settles the position; the second settles its deviation. Physical throughput
cost is charged once. Day-ahead prices may be common or scenario-specific.

When `q=None`, path 0 is a feasible nominal battery schedule and defines the offer. When
`q` is supplied and `cap=None`, the position enters profit as a constant and has no nominal
physical path. Scenario dispatch then adapts around the contract.

An optional deviation band is

$$
-\delta\le(d_{st}-c_{st})-q_t\le\delta,
\qquad \delta\ge0.
$$

`cap=delta` applies the band to every information node. `cap=0` enforces delivery. A fixed
position may be infeasible under a finite band.

For probabilities $p_s>0$, confidence $0\le\alpha<1$, and risk weight $0\le w\le1$, the
objective is

$$
\max\ (1-w)\sum_s p_sR_s-w\left[
\zeta+\frac{1}{1-\alpha}\sum_s p_s\xi_s
\right],
\qquad \xi_s\ge-R_s-\zeta,\quad \xi_s\ge0.
$$

The bracketed term is CVaR of loss. `cvar` independently evaluates the weighted tail and
splits mass at the quantile.

## Information

`h[s,t]` labels the information node at which action $t$ is chosen. Equal labels within a
period share charge, discharge, energy, and mode variables. Nodes may branch but not merge.
`h=None` reveals no scenario before dispatch. Distinct initial labels give perfect
information and are optimistic unless justified by the data process.

The caller defines what is observable at each decision time. The optimizer cannot infer
when a price became available.

## Solution routes

| Function | Formulation | Limit |
| --- | --- | --- |
| `st` | Sparse MIP with one binary per information node | HiGHS branch and bound |
| `en` | Sign enumeration and cumulative-energy LP | At most 12 nodes |

`en` has no state-of-charge variables and does not call the MIP row builder. Both routes
share input checks, information-node construction, and result accounting.

`Sol.z` is the achieved risk score; `ub` is its certified upper bound; `gap` is the HiGHS
relative gap for the variable objective. With a fixed contract, that variable objective may
be near zero. In that case `ub-z` is the informative absolute certificate. `mu`, `cv`, and
`r` are mean profit, loss CVaR, and scenario profits.

## Scope

Prices are exogenous and positions are assumed accepted in full. The model omits bid
curves, market impact, reserve products, networks, nonlinear degradation, tariffs,
collateral, and qualification rules. It is a schedule-valuation model, not a market
submission system. The [NYISO replay](MARKET.md) supplies chronological inputs and states
its additional assumptions.
