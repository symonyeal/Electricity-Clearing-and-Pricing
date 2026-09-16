# Joint and stochastic clearing

`models/joint.py` clears generation and storage in one program on a network.
`models/stoch.py` clears one commitment against many demands. Both reuse the unit rows,
the network rows and the price selection of [Pricing](PRICING.md); neither rewrites them.

## Storage as a cleared resource

Let $c_{jt}$ and $d_{jt}$ be resource $j$'s grid-side charge and discharge, $e_{jt}$ its
stored energy and $m_{jt}\in\{0,1\}$ its charge mode. With period length $\Delta$,

$$
\begin{aligned}
e_{jt}&=e_{j,t-1}+\Delta(\eta_c c_{jt}-d_{jt}/\eta_d),\\
0&\le e_{jt}\le E_j,\qquad e_{j,-1}=E_{j0},\\
0&\le c_{jt}\le C_j m_{jt},\qquad 0\le d_{jt}\le D_j(1-m_{jt}).
\end{aligned}
$$

The net injection $d_{jt}-c_{jt}$ enters the balance row of the bus the resource sits at,
so the resource settles at a price its own flows helped set. That is the difference from
[Storage trading](TRADING.md), where the price is an input.

The two mode rows imply

$$
\frac{c_{jt}}{C_j}+\frac{d_{jt}}{D_j}\le 1,
$$

which is the convex hull of the mode restriction in one period and is carried as a row of
its own. It is not the convex hull of the resource's whole feasible set: the state-of-charge
rows couple the periods, and a convex combination of mode patterns can hold an average
energy inside the battery while the patterns themselves do not. Where $0\le e\le E$ is
slack the cut is exact; where it binds the relaxation is a relaxation.

Deliverability is the network's. A resource behind a congested line can inject only what
that line carries, and the price at its bus separates from the price at the load.

| Case | Cleared cost | Energy delivered | Price at the load bus | Price at the resource |
| --- | ---: | ---: | ---: | ---: |
| 40 MWh battery at the load bus | 2,300 | 40 MWh | 20 | 20 |
| The same battery behind a 5 MW line | 2,700 | 20 MWh | 20 | 0 |

The 400 is the cost of the energy that cannot be delivered. With no resource the joint
program is the program of [Pricing](PRICING.md): cost, dispatch and locational price agree
unit for unit on seeded markets, the price to $10^{-4}$/MWh.

## One commitment, many demands

`models/stoch.py` takes $S$ demands with probabilities $p_s$. The commitment $u,v,w$ is
chosen before the scenario is known and is common to every scenario; dispatch, storage and
flows answer each scenario separately. The objective is

$$
(1-w)\sum_s p_s C_s
+w\left[\zeta+\frac{1}{1-\alpha}\sum_s p_s\xi_s\right],
\qquad \xi_s\ge C_s-\zeta,\quad \xi_s\ge 0,
$$

with $C_s$ scenario $s$'s own cost. The bracket is the Rockafellar–Uryasev CVaR of cost;
$w=0$ minimises the expected cost.

Scenario $s$'s balance row enters the objective already multiplied by $p_s$, so its dual is
$p_s$ times that scenario's price. `lmp` divides the weight back out, and a zero probability
is refused rather than divided by.

## What the bounds say

Write SP for the stochastic optimum, WS for the value of solving each scenario knowing
which one it is, and EEV for the mean-value commitment evaluated against every scenario.
Then $\text{WS}\le\text{SP}\le\text{EEV}$. On the instance in `tests/test_stoch.py`,
demand is 20 MW nine times in ten and 120 MW once, against a mid-merit unit that costs
1,000 an hour merely to be on:

| Value | Cost |
| --- | ---: |
| WS, perfect information | 1,060 |
| SP, one commitment for all scenarios | 1,960 |
| EEV, the mean-value commitment | 4,640 |

The expected value of perfect information is 900 and the value of the stochastic solution
is 2,680: the mean demand of 30 MW does not justify committing the mid-merit unit, and the
spike does. Both bounds are computed by running `models/joint.py` once per scenario, which
shares no assembly with the module under test.

## Scope

The clearing is a single-stage commitment with per-scenario recourse, one branch deep. It
is not a multi-stage tree, and it carries no ramping restriction between scenarios. Prices
are the duals of the balance rows once the integers are pinned; no hull is taken over the
joint feasible set, so a nonconvexity is left as make-whole rather than priced away.
