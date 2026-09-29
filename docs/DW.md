# Dantzig–Wolfe decomposition

This study evaluates column generation as a route to convex-hull prices, including the
certificate required before a candidate price is reported to a market-design reader.

`models/dw.py` computes convex hull prices by column generation. `cg` prices the unit class
of [Pricing](PRICING.md), and `hc` and `hl` check it. `cgp` prices the
[pglib-uc](PGLIB.md) class, energy and reserve together; no direct hull of that class
exists here. Both run one loop, `_gen`, and neither reports a price until that exact
vector has been priced against every unit, or tags it `stall`. `python run_dw.py`
reproduces every table below except the RTS-GMLC row, `python run_dw.py rts`, and the
oracle's accuracy, `python run_dw.py oracle`.

## Reformulation

Let $X_g$ be the bounded mixed-integer feasible set of unit $g$, including output and
commitment variables, and let $V_g$ index the extreme points of
$\operatorname{conv}(X_g)$. For $k\in V_g$, let $\hat p_{g,t}^{k}$ and $\hat c_g^{k}$ be
the output and cost of the extreme point. The one-bus master is

$$
\begin{aligned}
\min\quad &\sum_g\sum_{k\in V_g}\hat c_g^{k}z_g^{k}\\
\text{s.t.}\quad
&\sum_g\sum_{k\in V_g}\hat p_{g,t}^{k}z_g^{k}=D_t,
&&t=1,\ldots,T,\\
&\sum_{k\in V_g}z_g^{k}=1,
&&g=1,\ldots,G,\\
&z_g^{k}\ge0.
\end{aligned}
$$

The first rows couple the units; the second are the convexity rows. This LP is the
Dantzig–Wolfe reformulation of the clearing problem. Its value is that of the Lagrangian
dual obtained by dualizing balance, and an optimal balance dual is a convex hull price.
Andrianesis et al. give the unit-commitment construction and interpretation in §III,
pp. 4–5; Wolsey gives the general construction in §11.2, p. 215. On a network `cg` keeps
the angle and line rows of `_nw` whole in the master, so only the unit columns are
generated. `cgp` keeps the renewables as bounded master columns, and writes reserve (3)
as an equality with a surplus column, as `pglib_uc.px` does.

## The certificate

Let $\lambda$ and $\pi_g$ be a dual of the restricted master. Unit $g$'s pricing
problem is

$$
v_g(\lambda)=\min_{x_g\in X_g}\left\{c_g(x_g)-\sum_t\lambda_t p_{g,t}\right\},
\qquad \rho_g=v_g(\lambda)-\pi_g ,
$$

its best self-schedule at $\lambda$, and $\rho_g$ its least reduced cost. `_oc` solves it as
an integer program over `_rw`, `_eq` and `_fx`, the rows every route reads, and takes
$v_g$ from `mip_dual_bound`, never from the incumbent. It is a bound route of `_mi`:
presolve off, feasibility tolerances $10^{-9}$. $v_g$ is exact only to those tolerances;
[Tolerances](#tolerances) measures how far. The Lagrangian value at $\lambda$ is

$$
L(\lambda)=\lambda^\top d+\sum_g v_g(\lambda)+W(\lambda)\le z_{\rm CHP}\le z ,
$$

where $W$ is the network subproblem `_nq` and $z$ the master value. The left inequality is
weak duality (Beck, Theorem 12.3), the right holds because the master is restricted.
`Dw.s.lb` is $L$ evaluated at the price reported, and `Dw.s.gap` is $(z-L)/\max(1,|z|)$.
BT Theorem 6.1 writes the same bound as $z+\sum_g\rho_g$; that form assumes the master's
dual cost equals $z$ exactly, which the selected dual below meets only within `_ce`, so
`lb` is computed from its definition. On one bus uplift is $U(\lambda)=z_{\rm UC}-L(\lambda)$
([Pricing](PRICING.md)), so

$$
U(\hat\lambda)-\min_\lambda U(\lambda)=z_{\rm CHP}-L(\hat\lambda)\le z-L(\hat\lambda):
$$

the uplift at the reported price exceeds the least uplift by no more than the certified
gap. That is the certificate a price needs. The master objective alone certifies nothing
about the price: it is the upper end of the bracket, and the bracket closes only at the
vector that was priced.

## The loop

    Input:          units, demand, network, ceilings; a feasible clearing s; eps
    Initialization: one column per unit, its schedule in s
    General step:   (a) solve the master; read the solver's own dual while generating
                    (b) price every unit exactly at lambda
                    (c) add each schedule whose reduced cost is below -tau
                    (d) when none is added: select the canonical dual on the master's
                        face with _px and price that vector; if it passes, stop;
                        otherwise add its violating columns and resume at (a)

The stopping rule is (d): the selected dual prices every unit to within $-\tau$. Then
$z-L(\hat\lambda)\le G\tau$ plus the selected dual's own shortfall against $z$. If the
selected dual fails and every column it violates is already in the master, the loop stops
with `st = stall`, and the vector it reports is not certified. Every
column is a vertex of a dispatch polytope fixed by its commitment, because `_oc` re-solves
the dispatch by simplex with the commitment held, and a column already in the master
never prices out by more than $r$ below. The column set is finite, so the loop
terminates. Seeding with a feasible clearing makes every master feasible without an
artificial penalty; the certificate does not depend on the seed.

## Tolerances

$$
\tau=\max\left(\varepsilon\max(1,|z|)/G,\;A_B+r\right),\qquad \varepsilon=10^{-9},\ A_B=10^{-5}.
$$

$r$ is the master's own dual residual: the most any column already in the master prices
out at $\lambda$. It is measured, not assumed. $A_B$ is the resolution the oracle's bound
supports: HiGHS closes its search to an absolute $10^{-6}$ and admits rows violated by its
feasibility tolerance, $10^{-9}$ in a bound route. Every oracle call of the seeded family,
against enumeration of every trajectory and its dispatch LP, with all offer costs scaled
by one factor (`python run_dw.py oracle`):

| Cost scale | Oracle calls | Bound less minimum | Stalled routes | Routes with $L>z$ |
| ---: | ---: | --- | ---: | ---: |
| $10^{-3}$ | 4,057 | $[-2.4\times10^{-7},\ 5.5\times10^{-9}]$ | 0 | 3 |
| 1 | 4,142 | $[-7.9\times10^{-8},\ 1.0\times10^{-11}]$ | 0 | 0 |
| 10 | 4,232 | $[-7.9\times10^{-7},\ 2.6\times10^{-10}]$ | 0 | 0 |
| $10^3$ | 4,321 | $[-7.3\times10^{-7},\ 3.7\times10^{-9}]$ | 0 | 0 |

The three routes with $L>z$ exceed by at most $4.3\times10^{-9}$, the master LP's own
accuracy. The $10^{-9}$ tolerances cost nothing measurable: measured 2026-09-26 in two runs
each, the 208 `cg` routes took 53.0 and 56.2 s against 55.2 and 57.0 s at the defaults, and
`qd` at 96 × 24 took 1.10–1.19 s against 0.95–1.13 s. With $A_B=10^{-6}$ one route
stalls at scale 1; with $10^{-5}$, none at any scale. Every tolerance here is absolute and
measured only over these scales; a route outside them that stalls says so in `st`. No
$\tau$ below $A_B+r$ can be certified: below it, a schedule already in the master reads as
a violation.

| Object | Tolerance | Measured on the 104-market family |
| --- | --- | --- |
| Reduced cost | $\tau$ above | Certified gap at most $9.3\times10^{-9}$ relative |
| Bracket $L\le z_{\rm hull}\le z$ | $10^{-8}$ relative | $L$ stayed below `hc`'s LP value on every CHP route and exceeded it by at most $1.3\times10^{-11}$ on the AIC: an LP value is exact only to the feasibility tolerance |
| Convex hull price | $10^{-4}$/MWh | Agrees with `hc` to $4.97\times10^{-6}$ on all 104 |
| AIC price | none: compare value and payment | The face is wide on 5 of 104 markets, 36, 61, 70, 85, 103; prices differ by up to 7.59/MWh, demand payment agrees |
| Convex hull uplift | a tenth of a cent | Agrees with `hc` to $6.5\times10^{-6}$ |
| AIC uplift | not determined | Up to 171.88 apart between two dual-optimal AIC prices |

The last row is a property of the AIC rule, not of either method. Uplift is measured
against each unit's unrestricted best self-schedule, while the AIC face is optimal for the
restricted one. Two points on that face have the same restricted Lagrangian value and
different unrestricted ones. The convex hull price has no such freedom, because
$U(\lambda)=z_{\rm UC}-L(\lambda)$ is constant on its face. An AIC uplift figure is
therefore a statement about the selection rule as well as the market.

## Failure modes

**An optimal master value is not a price.** One period, 50 MW; a flexible unit at 60/MWh,
and a unit with a 25 MW floor, 8/MWh and a 200 start-up. Seed unit 2 with 25 MW and
50 MW. The master must run it at 50, so $z=600=z_{\rm CHP}$ and the objective gap is zero.
Its dual face is $\lambda\ge8$, and the payment rule selects 8. Unit 2's omitted off
schedule then has reduced cost $-200$, and $L(8)=400$. The face also holds 12, the convex
hull price, which passes; only pricing the selected vector tells them apart.

**The selected dual must be repriced.** On 18 of the 208 routes of the seeded family, the
dual selected after generation had stopped violated a column the solver's own dual had not.
On 7 AIC routes this was structural, down to $-104.45$ on seed 111, because the restricted
face extended past the true one. On the rest it was at tolerance scale, at most
$3.8\times10^{-4}$. On ex2 the selected vector lay $2\times10^{-6}$/MWh from the face's
point and priced a zero-reduced-cost column at $-6.9\times10^{-5}$. One column closed each.

**A restricted oracle certifies nothing.** On ex3's AIC, pricing unit 2 only over its
cleared and off schedules, as a heuristic pricing step might, stops at $(10,10,146.33)$.
It certifies itself: every returned schedule is feasible and every reduced cost it can
see vanishes, so it reports $L=z=7{,}340$. The exact oracle at that price finds a start in
period 3, and $L=6{,}202.5$. With exact pricing the loop reaches 422. This is the loop's
form of the result [Pricing](PRICING.md) records for `hl`.

**Solver defects on thin programs.** [Pricing](PRICING.md#what-a-clearing-certifies)
records how HiGHS failed on the AIC's $10^{-6}$-wide ranges and how every route now guards
against it. In this loop the default tolerances put $L$ above $z$ on 6 of the 208 routes,
and on 61 with offer costs scaled by $10^{-3}$, where capped seed 88 reported a relative
gap of $-1.1\times10^{-7}$; with costs scaled by 10, seed 98 capped stalled on a bound
$5.9\times10^{-5}$ below its column. [Tolerances](#tolerances) measures the repair.

**Slow start.** With one seed column per unit every $\lambda$ is dual-optimal, and the
first raw dual on seed 41 capped was $2.2\times10^{10}$/MWh. The loop recovers; a
stabilised master would start closer.

## Results

### Published cases

| Case | Price | `hc` value | `cg` value | `cg` bound | Price | Uplift | Solves | Generated | Repriced | Final | Active | `hc` s | `cg` s |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ex1 | CHP | 420.0000 | 420.0000 | 420.0000 | 12 | 1,430.00 | 4 | 3 | 0 | 5 | 3 | 0.01 | 0.11 |
| ex1 | AIC | 1,850.0000 | 1,850.0000 | 1,850.0000 | 52.857 | 2,085.71 | 3 | 1 | 0 | 3 | 2 | 0.01 | 0.09 |
| ex2 | CHP | 20,792.0000 | 20,792.0000 | 20,792.0000 | 60, 60, 65.6 | 168.00 | 9 | 10 | 1 | 12 | 5 | 0.01 | 0.24 |
| ex2 | AIC | 20,960.0000 | 20,960.0000 | 20,960.0000 | 60, 66, 62 | 460.00 | 6 | 7 | 0 | 9 | 2 | 0.01 | 0.16 |
| ex3 | CHP | 6,975.0000 | 6,975.0000 | 6,975.0000 | 10, 10, 276 | 365.00 | 8 | 12 | 0 | 14 | 5 | 0.01 | 0.21 |
| ex3 | AIC | 7,339.9997 | 7,339.9997 | 7,339.9997 | 10, 10, 422 | 730.00 | 9 | 14 | 0 | 16 | 5 | 0.01 | 0.23 |
| ex4 | CHP | 2,100.0000 | 2,100.0000 | 2,100.0000 | 10, 30, 50 | 0.00 | 3 | 2 | 0 | 4 | 2 | 0.01 | 0.09 |
| ex5 | CHP | 275,000.0000 | 275,000.0000 | 274,999.9997 | 40, 40 / 10, 90 | 0.00 | 5 | 6 | 0 | 9 | 5 | 0.01 | 0.20 |

The prices agree with `hc` in every digit shown. The uplift is `pay`'s total at the `cg`
price; on ex1–ex3 it reproduces the published figures of [Pricing](PRICING.md).

### Seeded family

The 104 feasible markets of seeds 0 to 140, uncapped and capped:

| Price | Routes | Largest value gap, `cg` − `hc` | Largest price difference | Repriced routes | Active columns $\le T+G$ | `hc` s | `cg` s |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| CHP | 104 | $5.4\times10^{-16}$ | $4.97\times10^{-6}$ | 9 | all | 1.8 | 26.8 |
| AIC | 104 | $8.4\times10^{-9}$ | 7.59, on wide faces | 9 | all | 1.9 | 26.3 |

### Size and time

Synthetic `mk_g` markets, seed 7. `cg` s excludes the clearing that seeds it, reported
beside it. Every row agrees with `hc` in value to $1.2\times10^{-15}$ relative and in price
to $9.4\times10^{-5}$.

| Units × periods | `hc` variables | `hc` s | `hl` s | Seed s | `cg` s | Solves | Generated | Repriced | Final | Active | $T+G$ |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 6 × 4 | 186 | 0.04 | 0.05 | 0.02 | 0.66 | 9 | 23 | 0 | 29 | 10 | 10 |
| 8 × 6 | 620 | 0.14 | 0.41 | 0.05 | 1.32 | 13 | 55 | 0 | 63 | 14 | 14 |
| 10 × 8 | 1,562 | 0.40 | 3.82 | 0.06 | 2.51 | 19 | 99 | 0 | 109 | 18 | 18 |
| 12 × 10 | 3,300 | 3.55 | 122.26 | 0.10 | 3.58 | 22 | 149 | 0 | 161 | 22 | 22 |
| 8 × 14 | 5,300 | 2.68 | refused | 0.22 | 3.99 | 34 | 163 | 0 | 171 | 22 | 22 |
| 10 × 16 | 9,498 | 6.75 | refused | 0.11 | 6.27 | 46 | 281 | 0 | 291 | 26 | 26 |
| 24 × 16 | 22,854 | 28.00 | refused | 3.94 | 13.65 | 37 | 531 | 1 | 555 | 39 | 40 |
| 48 × 24 | 139,230 | > 2,579, stopped | refused | 3.83 | 51.82 | 60 | 1,890 | 0 | 1,938 | 68 | 72 |
| 96 × 24 | 278,526 | not run | refused | 12.34 | 96.35 | 54 | 3,338 | 0 | 3,434 | 117 | 120 |

At 48 × 24 and 96 × 24 no row is compared with `hc` in value; the certificate stands alone,
a relative gap of $10^{-9}$ on both (`python run_dw.py big`).

Measured 2026-09-24 on one laptop core, Python 3.14.7, SciPy 1.18.1, other benchmark
processes running on other cores.

The generated master is small: at 24 × 16 its final 555 columns, 39 of them active,
stand against `hc`'s 22,854 variables. Its time is not: every iteration solves $G$
integer programs. `hc` is faster up to 8 × 14; from 10 × 16 the generated master is
faster, and at 48 × 24 it certifies its price in 56 s, seed included, where `hc` had
not returned after 2,579 CPU-seconds and was stopped.

### pglib-uc

`cgp` reads pglib-uc's own rows, so it shares no row builder with `cg`. On ex1 and ex2,
written as pglib records, it reaches `hc`'s value and prices, 12 and (60, 60, 65.6). On
the two-unit instance of the pglib tests with 10 MW of reserve required in period 2, the
hull prices reserve at 9.375 and energy at 54.375 there. `pglib_uc.px`, which holds the
cleared commitment, prices that reserve at zero. The hull value equals pglib's own LP
relaxation on that instance.

On the committed RTS-GMLC day, 73 thermal units, 81 renewables and 48 periods, with energy
and reserve priced together (measured 2026-09-24):

| Quantity | Value |
| --- | ---: |
| LP relaxation | 2,480,427.04 |
| Hull value, bracket | [2,501,406.3307, 2,501,406.3332] |
| 1% incumbent, reference gap | 2,520,108.89 |
| Master solves; columns generated; of which by repricing | 106; 2,910; 19 |
| Final columns; active | 2,983; 131, against $T+|J_r|+G=169$ |
| Seconds, seed clearing included | 334 |
| Energy price | 0 to 115.37/MWh |
| Reserve price | positive in 3 of 48 periods: 41.41, 71.76, 81.42 |

The hull value is a lower bound on the clearing, so it certifies the 1% incumbent to within
0.74% of optimal, where the solver's own gap claimed 1%. The incumbent less $L$ at the hull
prices, 18,702.56, is the Lagrangian duality gap at that incumbent. The tag is `pay`: 96
priced rows exceed `LIM[3]`, so the prices are canonical to the payment only, as in
[pglib-uc](PGLIB.md).

## What the study answers

1. **Does the generated master reproduce the direct hulls?** Yes, in value on all 208
   routes and in price wherever the hull's price is unique: every convex hull price, and
   the AIC on 99 of 104 markets. On the other five the AIC face is wide, and both
   methods report points of it with equal value and payment.
2. **When does it win?** In size, always, since its support is at most $T+G$ columns. In
   time, from 10 × 16 on these markets, and it is the only exact method here for the
   pglib-uc class. Below that, `hc`'s single LP is faster than $G$ integer programs per
   iteration.
3. **What certifies a price?** The Lagrangian value at the reported vector, from exact
   pricing, against the master value, both to the solver's tolerances. The master
   objective, the gap at the solver's own dual, and a heuristic oracle's reduced costs
   each certify nothing about the reported price, and each failed on a case above.
4. **pglib-uc.** No direct hull is implemented for piecewise costs, start-up tiers and
   reserve, and the generated master needs none: its oracle is one unit's own integer
   program. The Benders form is Dantzig–Wolfe applied to the dual (BT §6.3 and p. 259).
   Kelley's cutting planes on $L$, with this oracle, generate this loop's columns as cuts,
   so there is no second computation to time. Knueven, Ostrowski, Castillo and Watson cut
   the same dual in a primal Benders form over a compact per-unit hull. That needs a
   compact hull for each unit, which `hc` supplies for the small class and nothing here
   supplies for pglib-uc. It is not implemented, and their order-of-magnitude figure is
   not measured here.
5. **Which tolerances?** Those in the table above, each tied to what the solver can
   certify. The reduced-cost tolerance cannot fall below the oracle's resolution plus the
   master's own residual. Prices compare only on a unique face, and AIC uplift does not
   compare at all. The AIC ceiling of $10^{-6}$ sits at the solver's resolution and is
   the source of the solver defects above.

## Structure and sparsity

For the displayed one-bus master, a basic solution has at most $T+G$ positive
extreme-point columns. Thus a 96-unit, 24-period basic solution uses at most 120 positive
columns. This is a support bound, not a bound on generated columns: degeneracy and
tailing-off make column generation add many columns that are zero in the final solution.
On a network the bound depends on the rank of all coupling rows and on the network
variables retained in the master; on pglib-uc it is $T+|J_r|+G$, with $J_r$ the periods
that require reserve. Every route measured above meets it.

The $96\times2^{24}=1{,}610{,}612{,}736$ figure is only an upper bound on binary
commitment trajectories across 96 unconstrained units. It is not the number of
Dantzig–Wolfe columns, because a column fixes continuous dispatch as well as commitment.

## Direct formulations in this repository

`hl` and `hc` are two direct extended formulations of the same unit hull.

`hl` enumerates feasible binary commitment trajectories. For each trajectory it retains a
continuous dispatch polytope and applies Balas' union-of-polyhedra construction. It is not
the extreme-point master above: one `hl` trajectory contributes $T$ dispatch variables and
one weight, whereas one master column is a fixed extreme point.

`hc` uses the interval formulation of Yu, Guan and Chen. It has $O(T^2)$ interval-graph
arcs. An on-interval of length $l$ also owns $l$ dispatch variables, so this implementation
has $O(T^3)$ LP variables in the worst case. It remains a polynomial-size exact extended
formulation assembled in full rather than generated iteratively.

The following counts use `mk_g` with its default seed 7. The `hc` variable count includes
the arc weights and their interval dispatch variables. The `hl` trajectory count is
obtained by path counting on the interval graph without enumerating the paths; its variable
count is the number of trajectories times $T+1$. Run `python run_bench.py sizes` to
reproduce the table.

| Units × periods | `hc` arcs | `hc` LP variables | `hl` trajectories | `hl` LP variables | `hl` guard |
| --- | ---: | ---: | ---: | ---: | --- |
| 6 × 4 | 79 | 186 | 70 | 350 | within limits |
| 8 × 6 | 200 | 620 | 332 | 2,324 | within limits |
| 10 × 8 | 409 | 1,562 | 1,528 | 13,752 | within limits |
| 12 × 10 | 730 | 3,300 | 6,924 | 76,164 | within limits |
| 8 × 14 | 896 | 5,300 | 68,774 | 1,031,610 | over 100,000-variable limit |
| 10 × 16 | 1,441 | 9,498 | 338,611 | 5,756,387 | over 100,000-variable limit |
| 24 × 16 | 3,478 | 22,854 | 815,451 | 13,862,667 | over 100,000-variable limit |
| 48 × 24 | 15,026 | 139,230 | 405,457,887 | 10,136,447,175 | over 16-period limit |
| 96 × 24 | 30,074 | 278,526 | 811,024,503 | 20,275,612,575 | over 16-period limit |

`hl` exceeds `LIM[1]`, its 100,000-variable ceiling, between 12 × 10 and 8 × 14; it also
refuses horizons beyond `LIM[0]=16`. The last three `hl` sizes are exact path counts, not
constructed LPs.

## Sources

| Source | Use |
| --- | --- |
| Andrianesis, P., Bertsimas, D., Caramanis, M. C. and Hogan, W. W. (2020), [“Computation of Convex Hull Prices in Electricity Markets with Non-Convexities using Dantzig-Wolfe Decomposition”](https://arxiv.org/abs/2012.13331), §II–III, pp. 3–5 | Lagrangian-dual price, extreme-point master, reduced cost, self-scheduling oracle, and finite convergence |
| Wolsey, L. A. (2021), *Integer Programming*, 2nd ed., Wiley, ch. 10, pp. 195–209; §§11.2–11.3, pp. 215–217; p. 226 | Lagrangian duality, Dantzig–Wolfe reformulation, column generation, initialization, stopping, and computational issues |
| Dantzig, G. B. and Wolfe, P. (1960), [“Decomposition Principle for Linear Programs”](https://doi.org/10.1287/opre.8.1.101), *Operations Research* 8(1), 101–111 | Original decomposition |
| Bertsimas, D. and Tsitsiklis, J. N. (1997), *Introduction to Linear Optimization*, Athena Scientific, §6.1, §6.3, §6.4 with Theorem 6.1, pp. 252–253, and §6.5, p. 259 | Delayed column generation, its cutting-plane dual, the decomposition bound, and Benders as Dantzig–Wolfe on the dual |
| Nemirovski, A. (2024), *Introduction to Linear Optimization*, World Scientific, §3.1.3, pp. 176–179 | Certificates of optimality in linear optimization |
| Knueven, B., Ostrowski, J., Castillo, A. and Watson, J.-P. (2022), [“A computationally efficient algorithm for computing convex hull prices”](https://doi.org/10.1016/j.cie.2021.107806), *Computers & Industrial Engineering* 163, 107806 | Benders alternative to column generation; the standing computational comparison |

The direct hull formulations and Beck's weak duality theorem are cited in
[Sources](SOURCES.md).
