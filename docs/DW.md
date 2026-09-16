# Dantzig–Wolfe decomposition

This repository uses direct extended formulations for the convex hull of its small unit
class. Dantzig–Wolfe decomposition is an alternative when the extreme-point master is too
large to write and no practical direct formulation is available.

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
Dantzig–Wolfe reformulation of the clearing problem. It has the value of the Lagrangian
dual obtained by dualizing balance, and an optimal balance dual is a convex hull price.
Andrianesis et al. give the unit-commitment construction and interpretation in §III,
pp. 4–5; Wolsey gives the general construction in §11.2, p. 215.

Let $\lambda_t$ and $\pi_g$ be the restricted master's balance and convexity duals. The
reduced cost of extreme point $k$ is

$$
\rho_g^k=\hat c_g^k-\sum_t\lambda_t\hat p_{g,t}^k-\pi_g.
$$

Pricing unit $g$ therefore solves

$$
\min_{x_g\in X_g}\left\{c_g(x_g)-\sum_t\lambda_t p_{g,t}\right\},
$$

equivalently its maximum-profit self-schedule at prices $\lambda$. The restricted-master
dual is feasible for the full master if every unit's minimum reduced cost is nonnegative.
At an exact optimum that minimum is zero for each unit because its convexity row has a
positive master variable. In computation, termination requires a stated reduced-cost
tolerance for every exactly solved pricing problem; a small master objective gap is not a
substitute.

Finite termination follows because $\operatorname{conv}(X_g)$ is a polytope with finitely
many extreme points. It does not follow from $X_g$ itself being a polyhedron: $X_g$ contains
integrality restrictions.

## Structure and sparsity

Column generation is applicable when the following structure is present.

| Condition | Unit-commitment interpretation |
| --- | --- |
| Few coupling rows and independent blocks | Balance and other system requirements couple otherwise independent units |
| A tractable pricing problem | Each unit can optimize its own schedule at a given price |
| An impractical number of block extreme points | Binary commitment trajectories alone number up to $2^T$, and each trajectory's dispatch polytope can have several extreme points |
| The master relaxation is the required object | Convex hull prices are duals of that relaxation |

For the displayed one-bus master, a basic solution has at most $T+G$ positive
extreme-point columns. Thus a 96-unit, 24-period basic solution uses at most 120 positive
columns. This is a support bound, not a bound on generated columns: degeneracy and
tailing-off can cause column generation to add many columns that are zero in the final
solution. On a network, the corresponding bound depends on the rank of all coupling rows
and on any explicit network variables retained in the master.

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
constructed LPs. At 96 × 24, `hc` has 30,074 arcs and 278,526 LP variables and is solved
as a full formulation by `run_face_scan.py`; no restricted-master iteration is used.

The formulations have equal objectives to relative tolerance $10^{-9}$ and equal selected
prices to $10^{-4}$/MWh on the published cases and all 104 feasible markets among seeds 0
through 140. This is an implementation check on sampled instances. Exactness follows from
the two formulations, not from the sample. The table compares the direct formulations; it
does not report a column-generation benchmark.

A practical compact exact formulation removes the present need for decomposition. Its
absence is a reason to evaluate Dantzig–Wolfe when the pricing problems remain tractable
and the coupling set remains small. It is neither a necessary nor a sufficient condition;
the generated-master size and measured solution time still decide between methods.

## Candidate extensions

Two model classes lack a complete direct hull in this repository.

**The pglib-uc unit class.** [pglib-uc](PGLIB.md) includes convex piecewise production
costs, off-time-dependent start-up tiers, and reserve. No compact exact formulation for
that complete class is implemented here. On the documented 1%-gap incumbent, its current
prices fix the integer decisions and leave $370{,}817.15$ of make-whole over 30 units.
Dantzig–Wolfe is a candidate because a column can include one unit's energy and reserve
schedule and the pricing problem remains separable by unit. No column-generation runtime
has been measured.

**The storage resource set.** [Joint clearing](JOINT.md) uses the per-period inequality
$c/C+d/D\le1$, which is the hull of the charge/discharge mode restriction for that period.
It is not the hull of the full resource set because state of charge couples periods. A
resource can form one Dantzig–Wolfe block if its self-scheduling MILP or dynamic
optimization is a practical pricing oracle. No such master or benchmark is implemented.

These are candidate applications, not evidence that column generation is faster than a
direct formulation not yet constructed.

## Computational requirements

Wolsey's implementation issues are directly relevant (p. 217 and p. 226).

| Requirement | Consequence |
| --- | --- |
| Restricted-master feasibility | Seed feasible unit schedules or use explicit artificial/slack columns with a documented penalty |
| Slow initial progress | Supply useful starting columns, commonly from a feasible clearing or a heuristic |
| Tailing-off | Expect more generated columns than the final basic support |
| Dual instability | If stabilization is used, document its bounds or penalties |
| Heuristic pricing | It may be used during early iterations, but every unit's final pricing problem must be solved exactly |

This repository requires the price, not only the master objective. `_px` first minimizes
demand payment on the optimal dual face, probes that face, and then applies a
lexicographic price rule. Its stationarity equation is an equality because finite primal
bounds are represented as rows and the remaining primal variables are free. Replacing the
equality by an inequality admits vectors that are not LP duals when a variable has no bound
row.

Column generation adds another condition. A dual returned by a converged restricted
master is certified only after pricing that particular vector. The restricted master has
fewer dual constraints than the full master, so `_px` can select a different vector on its
larger optimal dual face that violates an omitted column. The selected vector must itself
be priced against every unit. If any reduced cost is below tolerance, the column must be
added and the master, face selection, and pricing checks repeated. Prices may be reported
only after the selected vector passes this test.

## Existing and missing components

| Component | Present support | Required work |
| --- | --- | --- |
| Unit pricing objective | `_om` solves maximum-profit self-scheduling | Return the optimizing schedule and its cost, not only profit |
| Explicit exact comparator | `hl` represents the same hull by Balas' formulation | Do not treat its trajectory variables as extreme-point master columns |
| Price-face rule | `_px` selects a dual from a complete LP | Apply it inside a generate–select–reprice loop |
| Payment diagnostic | `pay` reports realized profit, make-whole, lost opportunity, and uplift | It is not a reduced-cost test because it has no convexity dual $\pi_g$ |

A column-generation implementation therefore still needs a restricted master, initial
columns or artificials, a column representation, convexity-dual extraction, a
schedule-returning pricing oracle, the generation loop, selected-dual repricing, and
documented numerical tolerances.

## Sources

| Source | Use |
| --- | --- |
| Andrianesis, P., Bertsimas, D., Caramanis, M. C. and Hogan, W. W. (2020), [“Computation of Convex Hull Prices in Electricity Markets with Non-Convexities using Dantzig-Wolfe Decomposition”](https://arxiv.org/abs/2012.13331), §II–III, pp. 3–5 | Lagrangian-dual price, extreme-point master, reduced cost, self-scheduling oracle, and finite convergence |
| Wolsey, L. A. (2021), *Integer Programming*, 2nd ed., Wiley, ch. 10, pp. 195–209; §§11.2–11.3, pp. 215–217; p. 226 | Lagrangian duality, Dantzig–Wolfe reformulation, column generation, initialization, stopping, and computational issues |
| Dantzig, G. B. and Wolfe, P. (1960), [“Decomposition Principle for Linear Programs”](https://doi.org/10.1287/opre.8.1.101), *Operations Research* 8(1), 101–111 | Original decomposition |

The direct hull formulations are cited in [Sources](SOURCES.md).
