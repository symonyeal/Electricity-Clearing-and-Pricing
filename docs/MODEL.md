# Model

For unit i and period k, p is generation, u commitment, v start-up and w shut-down. The
offer has energy cost c, no-load cost nl and start-up cost su. The unit's feasible set X_i
contains minimum output, capacity, ramps, start-up and shut-down ramps, minimum up and
down times, state transitions and initial-state obligations. `unit::rows` defines X_i once;
every program below derives from it.

The clearing minimises Σ c p + nl u + su v over the product of the X_i, subject to nodal
balance and network limits. A DC line carries (θ_a − θ_b)/x within a symmetric limit, with
θ_0 = 0. A transfer limit carries a free flow between signed bounds, without a loop-flow
condition. One network may mix both. [Sources](SOURCES.md) records the formulations.

## Price rules

| Route | Priced feasible set |
| --- | --- |
| `lmp` | Dispatch with the integer clearing's commitment fixed |
| `chp` | Product of exact unit hulls, each the flow polytope of an interval graph |
| `aic` | The same hulls after capping the cleared blocks that lose money at LMP |
| `rx` | Continuous relaxation of the commitment rows (`chp_r`, `aic_r` in `all`) |

Each price is the dual of its program's balance equations. Commitment is cleared once,
so every rule settles the same schedule. LMP prices the dispatch-only program and adds
the commitment's fixed costs afterwards.

The hull of one unit is a path from source to sink through idle periods and on-intervals
[s, s + n); an on-interval arc carries the perspective of that interval's dispatch
polytope and is followed by md idle periods. A unit online before the horizon starts
with its initial run. The graph has O(T²) arcs and O(T³) dispatch columns per unit.

AIC starts every unit at full capacity. A cleared block that loses money at LMP is capped
at its dispatch plus 1e-6 MW; a period with cleared output at most 1e-7 MW is capped at
zero. The 1e-6 MW relaxation lowers case 3's peak AIC price by about 1.2e-4.

## Uplift and certificates

At price π a unit's realised profit is energy revenue less operating cost. Total uplift
is its best self-scheduled profit at π, from the certified MIP bound, less realised
profit. Make-whole is the sum of the losses of its cleared on-blocks, capped at total
uplift; lost opportunity is the remainder. The cap binds only when a unit's initial state
forces a loss on it: a unit that starts offline can always drop a losing block.

Relaxing nodal balance leaves unit and network subproblems. The Lagrangian value
q(π) = π·d + Σ_i min (cost_i − π·p_i) + W(π) bounds the clearing cost from below, where
W(π) is the minimum network term. Omitting W can put the purported bound above the
clearing cost on a congested network. `chp` reports q at its selected price as `lb`;
lb = z certifies a convex-hull price. At arbitrary π, uplift = clearing cost − q + W + R,
where R is the cleared congestion rent; W = −R only at an appropriate dual optimum.

## Solver boundary

`lp::Problem` holds sparse rows and plain values; HiGHS access lives only in `lp`. Integer
programs request zero relative gap and read back the achieved gap and objective bound.
Bound solves disable presolve and use 1e-9 feasibility tolerances. A presolve
infeasibility is retried without presolve; other failures keep the solver status.

`pricing::price` minimises demand payment over the optimal dual face, probes the face with an
interior-point solve without crossover, and otherwise walks the balance prices
lexicographically (one LP per row, so only up to 24 rows). Dual stationarity is an equality, including at free angle columns,
and the balance equalities must be the last rows. The output `price_selection` names the stage.

| `price_selection` | Meaning |
| --- | --- |
| `probe` | Interior point and vertex agree within 1e-3/MWh |
| `walk` | Lexicographic walk over the balance prices completed |
| `partial` | Walk stopped early; the last completed stage is returned |
| `payment` | More than 24 balance rows and the probe disagrees with the vertex; demand payment minimised only |
| `raw` | Face program failed; raw solver duals |

The face ceiling holds each stage within 1e-9 relative (scale at least 1); the probe
relaxes it by 1e-7 to avoid false infeasibility on thin faces.

## Input

`g` is a non-empty array of units; `d` a non-empty rectangular matrix indexed by bus,
then period, in MW. Each unit requires `lo`, `hi` and `c`. Costs `nl` and `su` default
to zero. Ramps `ru`, `rd`, `sr`, `dr` default to `hi`; `mu` and `md` default to one.
Initial state `u0` and output `p0` default to zero; `e0`, the periods already spent in
that state, defaults to max(mu, md). An omitted `net` means one bus. A network gives
`bus`, one index per unit, and `ln`: a DC line `[from, to, reactance, limit]` or a
transfer `[from, to, [lower, upper]]` with from < to and lower < 0 < upper. Unknown fields
are rejected. Periods are one hour; prices use one consistent currency.

## Limits

Energy offers are linear with one start-up cost; the network is base-case and lossless.
Piecewise costs, reserves, storage, stochastic demand, N-1 security, losses, mitigation
and block orders are absent. Optimality holds to solver tolerances, without exact
arithmetic. ISO-scale performance is unmeasured.
