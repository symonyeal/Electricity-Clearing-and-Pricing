# Design

## Mathematical ownership

`unit::rows` defines one generator's complete problem over `[p | u | v | w]`: dispatch,
commitment, start and stop. It owns costs, bounds, initial-state obligations, minimum
up/down times, ramps and state transitions. `unit::trajectory` fixes a binary schedule
in those same inequalities and returns its dispatch polytope and fixed cost.

`clearing` combines unit problems and bus balances. `network` adds DC angle columns or
directional exchange columns; its separate `value` minimizes the network term left by
relaxing those balances. Omitting that term can put the Lagrangian value above the
clearing cost on congested systems.

The two direct hulls derive from the dispatch polytopes. `hl` uses whole trajectories;
`hc` uses on-interval arcs and graph-flow conservation. Column generation in `dw` builds
an extreme-point master and reprices each selected dual against the resource oracles.
Historical generation/storage and pglib studies are outside the maintained tree.

## Solver boundary

`lp::Problem` holds sparse rows and plain numerical values. HiGHS access lives in `lp`.
Integer programs request zero relative gap; each result reads back the achieved gap and
objective bound. Bound routes disable presolve and use 1e-9 feasibility tolerances.
An infeasibility with presolve is retried without it. Other solver outcomes retain the
solver status instead of being called infeasible.

Prices are equality duals. `lp::price` first minimizes demand payment over the optimal
dual face, probes that face with an interior-point solve without crossover, and walks
balance prices if necessary. Dual stationarity is an equality, including at free angle
columns. The last balance equalities must remain the final rows. The selected price
stage is returned, including incomplete refinement.

| Constant | Value | Purpose |
| --- | ---: | --- |
| Trajectory horizon | 16 | Enumerated unit schedules |
| Trajectory hull variables | 100,000 | Explicit trajectory formulation |
| Joint commitments | 20,000 | Independent clearing enumeration |
| Price walk rows | 24 | Bound on lexicographic refinement |
| Face ceiling | 1e-9 relative, scale at least 1 | Hold prior stage within numerical tolerance |
| Face probe relaxation | 1e-7 relative, scale at least 1 | Avoid false infeasibility on thin faces |
| Probe price threshold | 1e-3 currency/MWh | Skip walk when probe and vertex agree |
| AIC output relaxation | 1e-6 MW | Default output ceiling above losing blocks |

## Input

`g` is a nonempty array of generators; `d` is a nonempty rectangular matrix indexed
by bus then period. Each generator requires `lo`, `hi`, and energy cost `c`. Costs
`nl` and `su` default to zero. Ramps `ru`, `rd`, `sr`, `dr` default to `hi`; minimum
durations `mu`, `md` default to one. Initial state `u0` and output `p0` default to
zero; elapsed state duration `e0` defaults to `max(mu,md)`.

An omitted `net` means one bus. A network supplies `bus` (one index per generator),
`nb`, and `ln`. A DC line is `[from,to,reactance,limit]`. A transport network sets
`fm` to `ntc`; each exchange is `[from,to,[lower,upper]]`, with ascending endpoints
and signed bounds from the first zone to the second. Optional `zn` names the zones.
Period duration is one hour; quantities use MW, MWh and a consistent currency.

## Limits

The core has linear energy offers, one start-up cost, and base-case lossless DC or
transport limits. Piecewise costs, reserve, storage, stochastic demand and replay are
outside its scope. The earlier Python studies are preserved at revision `ec91593`.
No N-1 security model, transmission losses, mitigation, block orders or ISO-scale
validation is provided. Floating-point optimality and column-generation certificates
hold to solver tolerances; exact arithmetic certification is absent.

Historical annual NYISO bundles retain their producing revision and clock-alignment
caveat in Git history and the local archive. They are not a current-code full-year backtest.
Large direct-hull performance remains unmeasured
in Rust; fewer source files do not establish a speed improvement.
