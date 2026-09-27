# Prices under a risk-averse commitment

`stoch.cl` chooses one commitment against $S$ demands by minimising
$\rho(C)=(1-w)\,\mathbb E[C]+w\,\mathrm{CVaR}_\alpha(C)$. `stoch.lmp` prices that commitment
by re-dispatching it at expected cost. This note names every dual by the program it comes
from, derives how they relate, and states which of them is a price. `stoch.cvd` computes the
duals of the risk-averse program itself; `models/risk.py` holds five examples and the
settlement under each candidate. `python run_risk.py` regenerates every table.

## Two programs

Hold the clearing's integers: commitment $u$ and, where present, storage modes. Two linear
programs remain.

**The expected-cost re-dispatch** (`lmp`):

$$
\min_{x}\ \sum_s p_s\,c^\top x_s\quad\text{s.t.}\quad A_sx_s=d_s\ \ (\text{dual } y^E_s),\qquad x_s\in P_s(u).
$$

**The risk-averse program** (`cl` with its integers held; `cvd`):

$$
\min_{x,\zeta,\xi}\ (1-w)\sum_s p_s\,c^\top x_s+w\Big[\zeta+\tfrac1{1-\alpha}\sum_s p_s\xi_s\Big]
\quad\text{s.t.}\quad
\begin{aligned}
&A_sx_s=d_s &&(y_s)\\
&c^\top x_s-\zeta-\xi_s\le0 &&(\mu_s\ge0)\\
&\xi_s\ge0,\ x_s\in P_s(u).
\end{aligned}
$$

$A_sx_s=d_s$ is scenario $s$'s balance, one row per bus and period, and $P_s(u)$ the rest
of its rows with the integers held. `cvd` writes each epigraph row as an equality with a
surplus column, so $\mu$ leaves `_px` in the same selected dual vector as $y$.

## What their duals are

Stationarity of the risk-averse program (Beck, Theorem 10.7; BT §4.3) gives three facts.

1. In $\zeta$: $\sum_s\mu_s=w$. In $\xi_s$: $0\le\mu_s\le wp_s/(1-\alpha)$. Hence
   $\omega_s=(1-w)p_s+\mu_s\ge0$ and $\sum_s\omega_s=1$: $\omega$ is a probability. The
   $\mu$ are the dual of the Rockafellar–Uryasev minimisation over $\zeta$,
   $\mathrm{CVaR}_\alpha(C)=\max\{\theta^\top C:0\le\theta_s\le p_s/(1-\alpha),\ \sum\theta_s=1\}$,
   so $\mu/w$ maximises $\theta^\top C$ over that envelope. `_te` computes one maximiser
   from the scenario costs alone, filling the envelope from the dearest scenario down. With
   distinct costs it is the only one and $\mu=w\theta$; at a tie only $\theta^\top C$ is
   determined.
2. In scenario $s$'s dispatch, the objective's weight on $c^\top x_s$ is $\omega_s$. The
   stationarity conditions of block $s$ are those of $\min c^\top x_s$ over $P_s(u)$,
   multiplied by $\omega_s$. So wherever $\omega_s>0$,
   $$y_s=\omega_s\lambda_s,$$
   with $\lambda_s$ a dual of scenario $s$'s own cost-minimising re-dispatch. The same
   holds for the expected-cost program with $p_s$ in place of $\omega_s$: $y^E_s=p_s\lambda_s$.
3. Where $\omega_s>0$, both programs minimise scenario $s$'s own cost, so $y_s/\omega_s$ and
   $y^E_s/p_s$ lie on one scenario dual face. They are equal wherever that face is a
   point, and `_px`'s payment-minimising rule treats both programs alike, face by face.

Each candidate price is then one of these objects:

| Name | Object | Program | Is it a price? |
| --- | --- | --- | --- |
| expected-cost | $y^E_s/p_s=\lambda_s$ | expected-cost re-dispatch | Yes: scenario $s$'s marginal cost, given the commitment |
| raw | $y_s$ | risk-averse program | As a spot price, no. It is $\partial\rho^*/\partial d_s$: the ex-ante value, in the objective's units, of 1 MWh delivered in scenario $s$, a state price under $\omega$ |
| raw over $p$ | $y_s/p_s=(\omega_s/p_s)\lambda_s$ | risk-averse program | No: the scenario price times the likelihood ratio $\omega_s/p_s\in[1-w,\ 1-w+w/(1-\alpha)]$ |
| normalised | $y_s/\omega_s=\lambda_s$ | risk-averse program | Yes, where $\omega_s>0$: a point of the expected-cost program's scenario dual face. Where $\omega_s=0$ there is no price at all; `cvd` reads $\omega_s\le10^{-9}$ as 0 |

The normalisation asked for exists, and it is by $\omega_s$, not by $p_s$. It returns
nothing new: with the integers held, the risk-averse program's scenario prices lie on the
expected-cost program's scenario dual faces, and equal its prices where those faces are
points, as they are on every example below. Risk aversion reaches prices only through the
commitment it chooses. [Validation](VALIDATION.md#risk-averse-prices) lists what the tests
assert.

## Five examples

Three units at one bus: C, 40 MW at 20/MWh; M, mid-merit at 40/MWh, costing 1,000 a
period merely to be on; P, 200 MW at 500/MWh. No example has storage or a network.

| Example | Demand by scenario | Probabilities | $w$ | $\alpha$ | Commitment of M, $w=0$ | Commitment of M, risk averse |
| --- | --- | --- | ---: | ---: | --- | --- |
| r1 | (10, 20) / (10, 120) | 0.9, 0.1 | 0.5 | 0 | off, on | off, on |
| r2 | (10, 20) / (10, 120) | 0.9, 0.1 | 0.5 | 0.5 | off, on | off, on |
| r3 | 20 / 120, M holds 50 MW | 0.98, 0.02 | 0.5 | 0.95 | off | on |
| r4 | (10, 20) / (10, 120) | 0.9, 0.1 | 1 | 0.95 | off, on | off, on |
| r5 | 20 / 120 | 0.98, 0.02 | 0.5 | 0.95 | off | on |

r1, r2 and r4 are the instance of `tests/test_stoch.py`.

### The risk-averse program, integers held

| Example | Objective | $\mathbb E[C]$ | CVaR | $\zeta$ | $\xi$ | Scenario cost | $\mu$ | $w\theta(C)$ | $\omega$ |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| r1 | 1,960 | 1,960 | 1,960 | 1,600 | 0, 3,600 | 1,600, 5,200 | 0.45, 0.05 | 0.45, 0.05 | 0.90, 0.10 |
| r2 | 2,140 | 1,960 | 2,320 | 1,600 | 0, 3,600 | 1,600, 5,200 | 0.40, 0.10 | 0.40, 0.10 | 0.85, 0.15 |
| r3 | 5,054 | 1,748 | 8,360 | 1,400 | 0, 17,400 | 1,400, 18,800 | 0.30, 0.20 | 0.30, 0.20 | 0.79, 0.21 |
| r4 | 5,200 | 1,960 | 5,200 | 5,200 | 0, 0 | **5,200**, 5,200 | 0, 1 | 1, 0 | 0, 1 |
| r5 | 2,156 | 1,472 | 2,840 | 1,400 | 0, 3,600 | 1,400, 5,000 | 0.30, 0.20 | 0.30, 0.20 | 0.79, 0.21 |

### Candidate prices

| Example | Scenario | Expected-cost, $w=0$ commitment | Expected-cost | Raw $y$ | $y/p$ | $y/\omega$ |
| --- | ---: | --- | --- | --- | --- | --- |
| r1 | 1 | 20, 20 | 20, 20 | 18, 18 | 20, 20 | 20, 20 |
| r1 | 2 | 20, 40 | 20, 40 | 2, 4 | 20, 40 | 20, 40 |
| r2 | 1 | 20, 20 | 20, 20 | 17, 17 | 18.889, 18.889 | 20, 20 |
| r2 | 2 | 20, 40 | 20, 40 | 3, 6 | 30, 60 | 20, 40 |
| r3 | 1 | 20 | 20 | 15.8 | 16.122 | 20 |
| r3 | 2 | 500 | 500 | 105 | 5,250 | 500 |
| r4 | 1 | 20, 20 | 20, 20 | 0, 0 | 0, 0 | none |
| r4 | 2 | 20, 40 | 20, 40 | 20, 40 | 200, 400 | 20, 40 |
| r5 | 1 | 20 | 20 | 15.8 | 16.122 | 20 |
| r5 | 2 | 500 | 40 | 8.4 | 420 | 40 |

**r1: the views agree.** At $\alpha=0$ CVaR is the mean, $\mu=wp$, $\omega=p$, and every
column is the same price.

**r2: they part.** The commitment and the scenario prices are the risk-neutral ones.
$y/p$ is not: it prices the base scenario at 18.889, below C's own 20, and the spike's
first period at 30, which no unit's cost supports. $y/\omega$ recovers the prices exactly.

**r3: risk changes the commitment and no price.** M is committed only under risk, and M
holds 50 MW, too little to be marginal in the spike. So the spike still prices at P's 500
and the base at C's 20, under either commitment.

**r4: a scenario without a price.** At $w=1$ the 0.05 tail lies inside the spike's 0.1, so
the base scenario is wholly below the quantile: $\mu_1=0$, $\omega_1=0$, and $y_1=0$. The
program puts no weight on that scenario's cost, so its dual carries no price and no
normalisation recovers one. The failure is kept as a result, not patched. Nothing in the
program determines scenario 1's dispatch below the level $\zeta=5{,}200$. The held LP
returned a scenario-1 cost of 5,200; the integer clearing, a solve of the same program,
returned 1,600. Both are optimal. So at $w=1$, $\mathbb E[C]$ as `cl` reports it is not a
property of the program. `cvd` reports $\lambda_1$ as nan by construction.

**r5: risk changes the commitment and the price.** M covers the spike, so committing it
moves the spike's marginal unit from P at 500 to M at 40.

### Settlement under each candidate, in expectation over $p$

| Example | Commitment | Price | Load pays | Units' profit | Make-whole | Lost opportunity | Scenarios priced |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| r2 | risk averse | expected-cost | 1,040 | −920 | 1,000 | 0 | 2 of 2 |
| r2 | risk averse | $y/p$ | 1,260 | −700 | 930 | 70 | 2 of 2 |
| r3 | $w=0$ | expected-cost | 1,592 | 384 | 0 | 440 | 2 of 2 |
| r3 | risk averse | expected-cost | 1,592 | −156 | 980 | 0 | 2 of 2 |
| r3 | risk averse | $y/p$ | 12,916 | 11,168 | 1,056 | 16,150 | 2 of 2 |
| r4 | risk averse | $y/p$ | 5,000 | −200 | 4,680 | 2,760 | 2 of 2 |
| r4 | risk averse | $y/\omega$ | 500 | −20 | 100 | 0 | 1 of 2 |
| r5 | $w=0$ | expected-cost | 1,592 | 384 | 0 | 900 | 2 of 2 |
| r5 | risk averse | expected-cost | 488 | −984 | 1,000 | 0 | 2 of 2 |

`run_risk.py` prints every row; these are the ones the text reads. $y/\omega$ settles
exactly as the expected-cost price wherever it exists, and in r4 it prices only one
scenario of two.

**The raw dual as a settlement.** Settled ex post as $y_s/p_s$, the raw dual has expected
payment $\sum_sy_s^\top d_s$, which is what paying the state prices $y_s$ ex ante would
collect. In r3 that is 12,916, against 1,592 at scenario marginal cost. It supports the
hedge, but under $\omega$: at the expected-cost prices M loses 540 in expectation under
$p$ and gains 3,830 under $\omega$. The raw dual is a settlement under the planner's
risk-adjusted measure. As a spot price under the scenarios' own probabilities it
underpays inframarginal units in ordinary scenarios. In r2 it pays C 18.889 for energy
that costs 20, a make-whole of 33.33 for a unit that is never marginal.

## Settling a risk-averse commitment at expected-cost prices

With the integers held, the expected-cost price is each scenario's marginal cost. It
therefore carries none of the cost of committing for risk, and that cost reaches the
units instead.

- r3: load pays 1,592 in expectation under either commitment. The hedge raises expected
  cost by 540, and the units' expected profit falls by exactly 540. Make-whole rises
  from 0 to 980 in expectation, M's 1,000 in the base scenario; in the spike M earns
  22,000.
- r5: the hedge moves the spike's price from 500 to 40. Expected load payment falls from
  1,592 to 488 and expected make-whole rises from 0 to 1,000.

The rule this needs is the one the repository already applies, taken scenario by
scenario. Pay each unit its block make-whole in the realized scenario at the
expected-cost price, and fund it as uplift charged to load, as BPCG or RSG are funded.
Report expected uplift beside the price, since it is where the risk premium is paid.
A settlement that puts the premium into the energy price instead is the ex-ante
state-price settlement above, under $\omega$. It is internally consistent, it moves money
from load in ordinary scenarios toward the tail, and it is a different market design.
Nothing here implements it.

## Value of information

For the expectation these are Birge and Louveaux's WS, SP (their RP), EEV, EVPI and VSS.
Under $\rho$ apply $\rho$ to the same scenario cost vectors: $\mathrm{WS}_\rho=\rho(z^*_s)$,
$\mathrm{SP}_\rho=\min_u\rho(C(u))$, $\mathrm{EEV}_\rho=\rho(C(\bar u))$, each scenario at its
cheapest recourse. Cheapest recourse is optimal under any monotone $\rho$, and $\rho$ is
monotone. So $\mathrm{WS}_\rho\le\mathrm{SP}_\rho\le\mathrm{EEV}_\rho$ holds for the same
reason the expected chain does.

| Example | WS | SP | EEV | EVPI | VSS | WS, $\rho$ | SP, $\rho$ | EEV, $\rho$ | EVPI, $\rho$ | VSS, $\rho$ | $\mathbb E[C]$ at the $\rho$ commitment |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| r1 | 1,060 | 1,960 | 4,640 | 900 | 2,680 | 1,060 | 1,960 | 4,640 | 900 | 2,680 | 1,960 |
| r2 | 1,060 | 1,960 | 4,640 | 900 | 2,680 | 1,290 | 2,140 | 6,660 | 850 | 4,520 | 1,960 |
| r3 | 768 | 1,208 | 1,208 | 440 | 0 | 4,264 | 5,054 | 8,884 | 790 | 3,830 | 1,748 |
| r4 | 1,060 | 1,960 | 4,640 | 900 | 2,680 | 5,200 | 5,200 | 41,000 | 0 | 35,800 | 1,960 |
| r5 | 492 | 1,208 | 1,208 | 716 | 0 | 1,366 | 2,156 | 8,884 | 790 | 6,728 | 1,472 |

Both chains hold on every example, and each is valid in its own units. They do not mix.
$\mathrm{SP}_\rho-\mathrm{WS}$ is not an EVPI: it adds the risk premium to the value of
information. The two measures can disagree about both quantities. In r4 perfect
information is worth 900 in expectation and nothing under $\rho$, since knowing the
scenario does not lower the spike's cost, which is all $\rho$ sees. In r3 the mean-value
commitment is the stochastic one in expectation (VSS 0) and is 3,830 worse under $\rho$.
The last column is the cost of risk aversion in expectation: 540 in r3 and 264 in r5.

## Recommendation

Report the expected-cost re-dispatch price by default, as the repository does. With the
integers held it equals the risk-averse program's own dual normalised by $\omega_s$,
wherever that normalisation exists, so it is the price of both programs and not a
convention imposed on one. Beside it belongs this warning:

> Scenario prices are marginal costs given a commitment chosen under
> $(1-w)\mathbb E+w\,\mathrm{CVaR}_\alpha$. They carry no part of the cost of committing
> for risk, which is paid as make-whole; expected make-whole is reported beside them. The
> risk-averse program's raw balance duals are state prices under its risk-adjusted
> probabilities $\omega$, not scenario prices. Where $\omega_s=0$, which requires $w=1$,
> the program prices scenario $s$ not at all and does not determine its dispatch.

## Sources

Rockafellar and Uryasev (2000, 2002), in [Sources](SOURCES.md), give the epigraph and the
tail with atoms. The dual $\theta$ is the LP dual of that epigraph's minimisation over
$\zeta$, derived above from BT §4.3. Birge and Louveaux give WS, RP, EEV, EVPI and VSS.
