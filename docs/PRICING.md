# Unit commitment and pricing

The published-case and numerical-face results below are retained from baseline `8e4637e`.
Current regression checks are recorded in [Validation](VALIDATION.md); larger historical
timing and AIC sensitivity tables are in the [archive](../_archive/20260915-inl-review/benchmarks.md).

For generator $g$ and period $t$, let $p_{gt}$ be output, $u_{gt}$ commitment,
$v_{gt}$ start-up, and $w_{gt}$ shut-down. With feasible unit set $X_g$, clearing is

$$
\begin{aligned}
\min \quad & \sum_{g,t}(c_g p_{gt}+n_g u_{gt}+s_g v_{gt})\\
\text{s.t.}\quad & \sum_g p_{gt}=d_t && t=1,\ldots,T,\\
& (p_g,u_g,v_g,w_g)\in X_g && g=1,\ldots,G.
\end{aligned}
$$

`_rw`, `_eq`, and `_fx` define $X_g$: output bounds, ramps, start and stop limits,
minimum up/down times, and the initial state.

Those rows are the reference unit-commitment formulation of Knueven, Ostrowski and
Watson, published as `MODEL.pdf` in [pglib-uc](https://github.com/power-grid-lib/pglib-uc)
and implemented in [Egret](https://github.com/grid-parity-exchange/Egret). The minimum up
and down rows are the Rajan-Takriti pair. This model restricts that formulation to one
linear production cost, one start-up cost, and no reserve requirement, so it does not yet
clear a pglib-uc instance.

`_nw` and `_tr` replace the single balance by one balance per bus under direct current, or
per zone under transport.

### Price definitions

| Price | Priced problem |
| --- | --- |
| LMP | Fix the cleared commitment and price the balance equations |
| CHP | Replace each $X_g$ by its convex hull |
| AIC | Restrict losing commitment blocks to cleared output plus epsilon, then price the restricted hull |

Make-whole is computed by commitment block. Total uplift equals make-whole plus lost
opportunity.

### Solve routes

| Function | Method | Role |
| --- | --- | --- |
| `uc` | Mixed-integer rows | Clearing |
| `rx` | Continuous relaxation of the same rows | Lower bound and relaxed price |
| `en` | Enumerate joint commitments and dispatch each | Small exact check |
| `hc` | Interval-graph convex hull | Default CHP and AIC |
| `hl` | Schedule-wise disjunctive hull | Independent small-case check |
| `lmp` | Cleared commitment fixed | LMP |
| `qd` | One best self-schedule problem per unit | Lagrangian dual and lost opportunity |

`hl` applies Balas' union-of-polyhedra construction to complete schedules. `hc` represents
each on-interval by an arc in an acyclic graph. It requires $O(T^2)$ arcs instead of
$2^T$ schedules. The two formulations agree on every published case and all 104 feasible
markets among seeds 0 through 140: relative objective tolerance $10^{-9}$, price tolerance
$0.0001/MWh.

### Canonical price selection

`_px` selects one vector from the optimal dual face:

1. Minimize demand payment over the dual-optimal set.
2. Solve one no-crossover interior-point probe on the tolerance-relaxed face.
3. If the probe differs by at most $0.001/MWh, stop. Otherwise minimize each balance price
   lexicographically.

The probe is a screen, not a bound on face diameter. It is identical for capped and
uncapped models.

| Case | Payment and probe | Forced walk | Price change | Decision |
| --- | ---: | ---: | ---: | --- |
| 48 x 24 | 2.66s | 32.50s | $0.00000226/MWh | Skip |
| 96 x 24 | 6.48s | 94.82s | $0.15225/MWh | Retain |

A forced-walk scan covered 410 capped and uncapped `hc` and `hl` routes. The screen skipped
391; the largest omitted change was $0.00000444/MWh. `LIM[3]` remains the maximum number of
balance rows in the lexicographic walk. The seed-61 capped test still requires `hc` and
`hl` to return different prices while agreeing on objective and demand payment.

### Published cases

| Case | Reproduced result |
| --- | --- |
| Hua and Baldick (2017), Example 1 | Cost 1,850; LMP $50 with uplift (100, 1,900); CHP $12 with uplift (1,430, 0) |
| Hua and Baldick (2017), Example 2 | Published dispatch; LMP (60, 60, 60) with uplift (0, 560); CHP (60, 60, 65.6) with uplift (168, 0) |
| Chen, O'Neill, and Whitman (2020) | Dispatch; LMP (10, 10, 90); unit-2 profits (-1,830, -1,030, 1,170); make-whole and uplift 1,690 |

At the talk's AIC price $(10,10,146.33)$, the implementation gives profit 13,633, best
self-schedule profit 14,771, uplift 1,138, and zero make-whole. The exact restricted hull
instead gives $(10,10,422)$. Limiting unit 2 to the cleared and off schedules recovers
$146.33 exactly; the full hull also contains a start in period 2. Both `hc` and `hl` give
$422. The talk does not publish the rows needed to resolve this difference.

The talk also reports $1,161 for a three-binary relaxation without listing its valid
inequalities. This formulation gives $218.31; it is not presented as a replication.

The payment identities are tested directly:

$$
U(\pi)=z_{UC}-L(\pi), \qquad z_{CHP}=\max_\pi L(\pi).
$$

Hence CHP minimizes total uplift over uniform prices.
