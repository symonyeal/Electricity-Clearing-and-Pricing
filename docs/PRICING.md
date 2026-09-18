# Unit commitment and pricing

For generator $g$ and period $t$, let $p_{gt}$ be output, $u_{gt}$ commitment,
$v_{gt}$ start-up, and $w_{gt}$ shut-down. Let $X_g$ be the feasible set of unit $g$.
The clearing problem is

$$
\begin{aligned}
\min \quad & \sum_{g,t}(c_g p_{gt}+n_g u_{gt}+s_g v_{gt})\\
\text{s.t.}\quad & \sum_g p_{gt}=d_t && t=1,\ldots,T,\\
& (p_g,u_g,v_g,w_g)\in X_g && g=1,\ldots,G.
\end{aligned}
$$

`_rw`, `_eq`, and `_fx` define $X_g$: output bounds, ramps, start and stop limits,
minimum up/down times, and the initial state.

These rows follow the formulation of Knueven, Ostrowski, and Watson, published as
`MODEL.pdf` in [pglib-uc](https://github.com/power-grid-lib/pglib-uc) and implemented in
[Egret](https://github.com/grid-parity-exchange/Egret). The minimum up- and down-time rows
are the Rajan–Takriti inequalities. This formulation has one linear production cost, one
start-up cost, and no reserve requirement. The full formulation is implemented separately
in the [pglib-uc benchmark](PGLIB.md).

`_nw` and `_tr` replace the single balance by one balance per bus under direct current, or
per zone under transport.

## Price definitions

| Price | Priced problem |
| --- | --- |
| LMP | Fix the cleared commitment and price the balance equations |
| CHP | Replace each $X_g$ by its convex hull |
| AIC | Restrict losing commitment blocks to cleared output plus epsilon, then price the restricted hull |

Make-whole is computed by commitment block. Total uplift equals make-whole plus lost
opportunity. All three rules hold the allocation fixed and choose a price for it; Liberopoulos
and Andrianesis survey that family and the alternatives to it.

## Solve routes

| Function | Method | Role |
| --- | --- | --- |
| `uc` | Mixed-integer rows | Clearing |
| `rx` | Continuous relaxation of the same rows | Lower bound and relaxed price |
| `en` | Enumerate joint commitments and dispatch each | Small exact check |
| `hc` | Interval-graph convex hull | Default CHP and AIC |
| `hl` | Schedule-wise disjunctive hull | Independent small-case check |
| `lmp` | Cleared commitment fixed | LMP |
| `qd` | One best self-schedule problem per unit, plus the network subproblem | Lagrangian dual and lost opportunity |

`hl` applies Balas' union-of-polyhedra construction to feasible commitment trajectories and
their dispatch polyhedra. `hc` represents each on-interval by an arc in an acyclic graph.
It requires $O(T^2)$ arcs instead of up to $2^T$ commitment trajectories; its interval
dispatch variables make the implemented LP $O(T^3)$ in the worst case. The two formulations
agree on every published case and all 104 feasible markets among seeds 0 through 140:
relative objective tolerance $10^{-9}$, price tolerance $0.0001/MWh.

## What a clearing certifies

`uc` and the self-schedule subproblems inside `qd` carry claims of exactness, so they ask
the solver for a relative gap of zero and read back the gap it achieved. `Sol.st` is `opt`
only when the bound closed and `gap` when the search returned an incumbent, which is a
feasible cost and not a proved optimum. A requested tolerance is not a result: HiGHS stops
at $10^{-4}$ unless told otherwise, and on the 12-by-10 synthetic market that default
returns an incumbent 23.4 above its own certified bound.

`Sol.gap` is the achieved relative gap and `Sol.lb` is the solver's certified lower bound
on cost. On a linear or enumerated route the optimum is determined, so `gap` is zero and
`lb` equals `z`. The categorical tag and the numeric certificate therefore describe the
same solve rather than asking a reader to infer how far a search closed.

`qd` subtracts each unit's best self-schedule profit, so it takes the solver's certified
bound on that profit rather than its incumbent. An incumbent can understate the profit a
unit could take; understating it lifts the reported dual, and a dual above the primal is
what weak duality forbids. The bound errs the other way, so

$$q(\pi)\le z_{\rm UC}$$

holds whatever the search was able to prove, and not only when every subproblem closed. At
a closed gap the bound and the incumbent are the same number.

A solve that fails is named by the solver's own status — infeasible, limit, unbounded or
numerical — and not called infeasible by default. Malformed data and a demand no commitment
can serve both end in a failed solve, and only the second of them is an infeasibility.

## Price selection

`_px` selects one vector from the optimal dual face:

1. Minimize demand payment over the dual-optimal set.
2. Solve one no-crossover interior-point probe on the tolerance-relaxed face.
3. If the probe differs by at most $0.001/MWh, stop. Otherwise minimize each balance price
   lexicographically.

The probe screens the optimal face; it does not bound its diameter. The rule is identical
for capped and uncapped models.

| Case | Forced-walk price change | Decision |
| --- | ---: | --- |
| 48 x 24 | $0.00000226/MWh | Skip |
| 96 x 24 | $0.15225/MWh | Retain |

A forced-walk scan covered 410 capped and uncapped `hc` and `hl` routes. The screen
skipped 391; the largest omitted change was $0.00000444/MWh. `LIM[3]` bounds the number
of balance rows in the lexicographic walk. In the capped seed-61 case, `hc` and `hl`
return different prices but the same objective and demand payment.

## Decomposition

`hl` is a trajectory-wise Balas formulation of the same hull as the Dantzig–Wolfe
extreme-point master; it is not that master written in full. `hc` is a direct interval
extended formulation. Neither generates extreme-point columns. [Decomposition](DW.md)
compares their sizes with the master representation and states the pricing and termination
checks required by a column-generation implementation.

## Published cases

| Case | Reproduced result |
| --- | --- |
| Hua and Baldick (2017), Example 1 | Cost 1,850; LMP $50 with uplift (100, 1,900); CHP $12 with uplift (1,430, 0) |
| Hua and Baldick (2017), Example 2 | Published dispatch; LMP (60, 60, 60) with uplift (0, 560); CHP (60, 60, 65.6) with uplift (168, 0) |
| Chen, O'Neill, and Whitman (2020) | Dispatch; LMP (10, 10, 90); unit-2 profits (-1,830, -1,030, 1,170); make-whole and uplift 1,690 |

At the talk's AIC price $(10,10,146.33)$, unit 2 has profit 13,633, best self-schedule
profit 14,771, uplift 1,138, and zero make-whole. The full restricted hull gives
$(10,10,422)$. Restricting unit 2 to the cleared and off schedules gives $146.33$; the
full hull also permits a start in period 2. Both `hc` and `hl` give $422$. The talk does
not publish the rows needed to resolve the difference.

The talk also reports $1,161 for a three-binary relaxation without listing its valid
inequalities. This formulation gives $218.31; it is not presented as a replication.

On one bus the payment identities are tested directly:

$$
U(\pi)=z_{UC}-L(\pi), \qquad z_{CHP}=\max_\pi L(\pi).
$$

Hence CHP minimizes total uplift over uniform prices. The second identity holds with lines
as it stands; the first gains two terms, below.

### The dual on a network

$L$ relaxes the nodal balance rows. That leaves the flow columns in the minimization, so

$$
L(\pi)=\pi^\top d+\sum_g\min_{x_g\in X_g}\left[c_g(x_g)-\pi_{b(g)}^\top p_g\right]
       +\min_{v\in V}-\left(N^\top\pi\right)^\top v,
$$

where $N$ is the network block of the balance rows and $V$ the feasible flows. The third
term is zero on one bus. Omitting it minimizes over a subset of the feasible set, which
breaks the hypothesis of the weak duality theorem (Beck, Theorem 12.3): on `ex4` that
returned $4{,}500$ against a clearing of $2{,}100$, and on `ex5` $489{,}999.999$ against
$275{,}000$. With the term, both are bounds and both are tight.

The uplift identity carries two further terms with lines. Uplift is measured at each unit's
own bus, so the load payment and the unit revenue differ by the congestion rent
$R(\pi)=\pi^\top d-\sum_g\pi_{b(g)}^\top p_g$ of the cleared flows, and the network
subproblem is free to choose other flows. Writing $W(\pi)$ for its value,

$$
U(\pi)=z_{UC}-L(\pi)+W(\pi)+R(\pi),
$$

exact at every price to $9.3\times10^{-10}$ over 400 random prices on `ex4` and `ex5`. At a
price that is a dual the cleared flows solve the subproblem, so $W(\pi)=-R(\pi)$ and the
single-bus form returns. Both $W$ and $R$ vanish identically on one bus.

## What is settled in practice

No market settles an exact hull price. The base rule everywhere is LMP with the commitment
fixed, relaxed in some markets for fast-start resources only, and the residue is paid as
uplift in all of them: Chen and O'Neill put it as "all ISO/RTOs compensate for MWP", the
objection being transparency rather than existence. MISO's Extended LMP is the oldest
production rule of the relaxed family, and it is an approximation in two distinct senses.

| | Extended LMP, in production | `hc` and `hl` |
| --- | --- | --- |
| Integrality | A variable $\mathit{on}\in[0,1]$ replaces the binary, with cost $\mathit{on}\times(\text{start-up}+\text{no-load})$ and limits $\mathit{on}\times\underline{P}\le p\le \mathit{on}\times\overline{P}$ | The convex hull of $X_g$ |
| Ramp rows | Ramp-down is **not enforced** in the pricing run, so a unit held at its minimum can still set price | Retained inside $X_g$ |
| Who is eligible | Fast Start Resources only: start-up plus notification $\le 60$ min, minimum run $\le 1$ h, excluding storage, pumped storage, run-of-river hydro and wind | Every unit |

A relaxed binary with a deleted constraint is not a hull. The exact hull is therefore an
instrument for measuring that rule rather than a competitor to it, which is the use this
model is fit for.

| Measured, MISO | Value |
| --- | ---: |
| Market units, of which fast-start eligible (2014 parallel operation) | 1,391 / ~60 |
| Real-time intervals where ELMP equalled LMP | 94.3% |
| Revenue sufficiency guarantee make-whole reduction, Phase I / Phase II | ~1% / ~9% |
| Make-whole under an exact hull, relative to LMP, seven day-ahead cases | 1.64%–26.55% |

The last two rows are different metrics on different markets and do not divide into one
another. Their separation is the open question.

Two consequences of the network term above are recorded in the same study. Constraints not
binding in the clearing may bind under a hull price, so $R$ moves and the rent that funds
financial transmission rights moves with it; its measured FTR uplift is zero under LMP by
construction and 1.19%–5.76% of generator profit under the hull. And the convex hull of a
storage resource is named there as open research, which is the same limitation
[JOINT](JOINT.md) records for the mode cut.

Holding the allocation fixed and choosing a price for it is itself a choice. Ahunbay, Bichler,
Dobos and Knörr instead compute an approximate competitive equilibrium in polynomial time,
changing the schedule to obtain a price with no budget deficit. Nothing here implements that,
and it is the alternative worth knowing about.
