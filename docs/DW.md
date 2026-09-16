# Dantzig–Wolfe decomposition

This repository computes exact convex hull prices without Dantzig–Wolfe decomposition.
That is a choice, not an oversight, and this note records the reasoning and the measurements
behind it.

## The reformulation

Let $X_g$ be unit $g$'s feasible set and $N_g$ its feasible schedules. Writing
$z_g^{n}\ge0$ for the weight on schedule $n$ and $\hat x_{g,t}^{n}$ for its output,

$$
\begin{aligned}
\min\ &\sum_{g}\sum_{n\in N_g}\hat c_g^{n}z_g^{n}\\
\text{s.t.}\ &\sum_{g}\sum_{n\in N_g}\hat x_{g,t}^{n}z_g^{n}=D_t,\qquad t\in T,\\
&\sum_{n\in N_g}z_g^{n}=1,\qquad g.
\end{aligned}
$$

The first rows couple the units; the second are the convexity rows, one per unit. This is
the Dantzig–Wolfe reformulation of the clearing problem, and its linear relaxation solves
the Lagrangian dual, so its balance duals are exact convex hull prices. Andrianesis,
Bertsimas, Caramanis and Hogan set that out for unit commitment; Wolsey gives the general
construction.

Column generation solves it without writing $N_g$ down. A restricted master holds a subset
of schedules and returns duals $\lambda$ on the balance rows and $\pi_g$ on the convexity
rows. Schedule $n$ has reduced cost

$$
\hat c_g^{n}-\sum_t\lambda_t\hat x_{g,t}^{n}-\pi_g,
$$

so the column to add is the one minimising it, which is unit $g$'s most profitable
self-schedule at prices $\lambda$. A negative reduced cost means the unit would rather
self-schedule than follow the master; no negative reduced cost anywhere means lost
opportunity is minimised and the prices are the convex hull prices. Termination is finite
because each $X_g$ is a bounded polyhedron with finitely many extreme points.

## When the structure fits

Dantzig–Wolfe is the right tool when all four hold.

| Condition | In unit commitment |
| --- | --- |
| The matrix is block-angular: few coupling rows, many independent blocks | The balance rows couple; each unit's ramps, run times and bounds are its own block |
| The block subproblem is easy | One unit's cheapest schedule at a price is a shortest path over its interval graph |
| The blocks have far more extreme points than the master can hold | A unit over $T$ periods has up to $2^T$ schedules |
| The linear relaxation, not an integer solution, is what is wanted | The convex hull price is the relaxation's dual |

The third condition is the one that makes the method pay, and the reason is a basic fact
about linear programs rather than anything about electricity. The master has one balance
row per period, or one per bus and period on a network, and one convexity row per unit,
so a basic optimum has at most $|T|+G$ nonzero columns. At 96 units over 24 periods
that is at most 120 schedules out of the $96\times2^{24}=1{,}610{,}612{,}736$ the
units admit between them. Column generation finds those columns without enumerating the
rest.

## Why this repository does not use it

Because a compact exact alternative exists for this unit class. `hc` implements the
interval formulation of Yu, Guan and Chen: an extended formulation whose projection is the
same convex hull, of size $O(T^2)$ per unit rather than $O(2^T)$. It is solved once, by one
linear program, with no iteration and no convergence criterion.

The two routes are measured side by side. Arcs are `hc`'s columns; schedules are `hl`'s,
the explicit union-of-polyhedra form that is the master with every column present.

| Units × periods | `hc` arcs | `hl` schedules | `hl` columns | Enumeration |
| --- | ---: | ---: | ---: | ---: |
| 6 × 4 | 79 | 70 | 350 | 0.02 s |
| 8 × 6 | 200 | 332 | 2,324 | 0.10 s |
| 10 × 8 | 409 | 1,528 | 13,752 | 0.66 s |
| 12 × 10 | 730 | 6,924 | 76,164 | 4.42 s |
| 8 × 14 | 896 | 68,774 | 1,031,610 | 41.09 s |
| 10 × 16 | 1,441 | 338,611 | 5,756,387 | 177.32 s |
| 24 × 16 | 3,478 | beyond reach | n/a | n/a |
| 48 × 24 | 15,026 | beyond reach | n/a | n/a |
| 96 × 24 | 30,074 | beyond reach | n/a | n/a |

`hl` passes `LIM[1]`, its 100,000-variable ceiling, between 12 × 10 and 8 × 14 and is
refused past it. `hc` grows quadratically in the horizon and is still 30,074 columns at
96 × 24, which one solve handles. Enumeration is what fails at scale; the hull is not.

The two agree where both run: equal objective to relative $10^{-9}$ and equal price to
$10^{-4}$/MWh on every feasible instance among seeds 0 through 140. That agreement is the
evidence that the compact route returns what the master would have returned.

So the rule is narrower than "decompose large problems". **Dantzig–Wolfe earns its place
when the block has no compact exact extended formulation.** Where one is known and small,
solving it directly is shorter, exact in one step, and leaves no stopping rule to justify.

## Where it would earn its place here

Two places, both concrete.

**The pglib-uc unit class.** [pglib-uc](PGLIB.md) carries convex piecewise production costs,
off-time-dependent start-up tiers and a reserve requirement. The interval hull `hc` is
proved exact for the smaller class in [Pricing](PRICING.md), not for this one, and no
compact hull for the richer class is implemented here. Its prices are therefore locational
marginal prices with the integers pinned, and they leave 370,817.15 of make-whole over 30
units. A convex hull price for that formulation is open work, and column generation is the
route that does not require finding a compact hull first: the subproblem stays one unit's
own problem however rich its rows become.

**The joint feasible set.** [Joint clearing](JOINT.md) adds storage to the balance. The
per-period cut $c/C+d/D\le1$ is the hull of the mode restriction alone, not of the resource
coupled to its state of charge. A resource block is a natural Dantzig–Wolfe block, and its
subproblem is a small dynamic program over stored energy.

## What it would cost

Wolsey's computational issues are the ones to weigh, and one of them is load-bearing here.

| Cost | Consequence |
| --- | --- |
| Slow start: many early iterations before the duals mean anything | Initial columns must be seeded, usually from a heuristic schedule |
| Tailing-off: the last iterations move the objective very little | The stopping rule decides the last digits of the price |
| Degenerate and unstable duals | Stabilisation by dual bounds or penalty functions, which is another parameter to justify |
| Master infeasibility before enough columns exist | Slack columns with a penalty, whose penalty is a parameter |

Tailing-off is the one that matters most in this repository, because what is wanted is the
dual and not the objective. [Pricing](PRICING.md) selects one price from the optimal dual
face by minimising demand payment and then walking each balance price, and `_px` imposes
dual feasibility as an **equality**: an inequality admits vectors that are not duals
whenever a variable is free of a bound row. A column-generation master stopped early
returns duals of a restricted hull, not of the hull. The prices would be feasible for a
smaller set and wrong for the real one, and the failure is quiet: the number looks like a
price. Any Dantzig–Wolfe route added here has to reach zero reduced cost on every unit
before its duals may be read, not merely reach a small optimality gap.

## What already exists

Adding column generation here would be adding the loop, not the parts.

| Piece | Where it already is |
| --- | --- |
| The master with every column present | `hl`, the union-of-polyhedra form |
| The subproblem, a unit's best self-schedule at a price | `_om` in `models/uc_price.py` |
| The reduced-cost test, profit against the convexity dual | `pay`, which reports lost opportunity per unit |
| A price-selection rule for a degenerate optimal face | `_px` |

`_om` is the Dantzig–Wolfe subproblem under another name: it solves one integer program per
unit over that unit's own rows and returns the best profit the unit could earn by
self-scheduling. What is missing is the restricted master and the loop between them.

## Sources

| Source | Use |
| --- | --- |
| Andrianesis, P., Bertsimas, D., Caramanis, M. C. and Hogan, W. W. (2020), [“Computation of Convex Hull Prices in Electricity Markets with Non-Convexities using Dantzig-Wolfe Decomposition”](https://arxiv.org/abs/2012.13331) | The reformulation, the reduced cost, and the self-scheduling reading of the subproblem |
| Wolsey, L. A. (2021), *Integer Programming*, 2nd ed., Wiley, ch. 10–11 | Lagrangian duality; the Dantzig–Wolfe reformulation, column generation, branch-and-price, and the computational issues above |
| Dantzig, G. B. and Wolfe, P. (1960), “Decomposition Principle for Linear Programs”, *Operations Research* 8(1), 101–111 | The original decomposition |

The formulations this note compares against are in [Sources](SOURCES.md).
