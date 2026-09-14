# Decisions and remaining work

This file records design choices, rejected work, and what remains open. The
[README](../README.md) owns measured results and run instructions.
[Sources](SOURCES.md) owns citations and data provenance.

## Rules for every model

- Solve it by at least two routes. Use exhaustive enumeration when the instance is small
  enough.
- Prefer two different *descriptions* of the feasible set over two solvers reading one
  description. Two solvers on one description cannot detect a wrong description.
- Compare objective values when several optimal solutions exist. Comparing sets in a tie
  creates a false failure.
- Check against an answer published by someone else, and say plainly where the result
  differs from theirs.
- Label synthetic inputs and give each generator a measurable economic check.
- Add a dependency only when it replaces existing work, is measured on the actual model,
  and leaves an independent check in place.

## Ultimate pit limit

1. **Use Picard's minimum-cut reduction.** A positive block gets an arc from the source, a
   negative block gets an arc to the sink, and a deep block `b` gets a precedence arc to
   each required upper block `p`. The returned pit is the source side without the source.
   A precedence capacity is the sum of all positive scaled values plus one, so cutting even
   one costs more than the always-available cut of every source arc.
2. **OR-Tools 9.15.6755 is the default solver.** It replaced NetworkX in `mc` after it ran
   faster at all three measured sizes. NetworkX remains as `mc_nx`, and the SciPy linear
   program remains the separate formulation.
3. **Integer scaling must be exact.** Synthetic values are rounded to cents. The MineLib
   reader derives the required decimal scale from the file. `mc` rejects a value that is
   not an exact multiple of its declared unit and rejects capacities that do not fit in a
   signed 64-bit integer. Multiplying every closure value by one positive scale preserves
   the order of all pits, so it preserves the optimum.
4. **Charge mining cost to every block.** An ore block is worth `rev * q - c_p - c_m`;
   waste is worth `-c_m`. This is what makes a profitable block capable of losing money
   after stripping.
5. **Keep one compact arc array.** `mk_E` returns a two-column `int32` array used directly
   by all solvers. The measured memory result is in the README.
6. **Keep `bf` as a small exact check.** It generates valid closed sets in
   prerequisite-first order instead of testing every raw subset. Its ceiling is 20 blocks.
7. **Keep direct economic and geometric tests.** Solver agreement cannot detect a shared
   bad `E`. The suite checks arc direction, boundary counts, closure, a non-trivial
   synthetic pit, hand-worked cases, and the external MineLib pit.

## Unit commitment and electricity prices

8. **One unit description, read two ways.** `_rw`, `_eq` and `_fx` hold every row, equality
   and bound: output limits, start-up and shut-down output ceilings, ramp limits, minimum
   run and down times after Rajan and Takriti, the start/stop state equation, and the
   carried-in initial state. `uc`, `rx` and `qd` read those rows algebraically. `_pl` fixes
   the binaries in those same rows to produce one schedule's dispatch polytope, and `hl`
   and `en` read the feasible set that way instead. The two descriptions are checked
   against each other directly, not merely compared through a solver.
9. **Two separate output ceilings, not one combined row.** A unit that starts and stops
   inside the horizon needs `p <= start-up ramp` and `p <= shut-down ramp` both to hold.
   The usual single combined row is only valid when the minimum run time is at least two
   periods, and it can cut off feasible points otherwise. Two rows are weaker and always
   correct, and the exact hull is a separate route anyway.
10. **The convex hull is built by Balas' union-of-polyhedra form.** Each feasible on/off
    schedule contributes a weight and a scaled output vector constrained by that schedule's
    own polytope. This is exact for a union of bounded polyhedra, so the balance dual is
    the exact convex hull price, and the same machinery with the average-incremental-cost
    ceilings gives the exact price of the restricted market. No vertex enumeration and no
    iterative algorithm are involved.
11. **Every priced solve re-picks the cheapest of its equally optimal prices.** A balance
    dual is a subgradient of cost in demand, and at a kink many prices are optimal. The
    average-incremental-cost restriction manufactures such kinks deliberately, so leaving
    the choice to the solver's basis makes the answer depend on the solver version. A
    second program keeps the dual optimal and minimises what is paid for the demand
    served, which is the lower slope: the marginal cost of what was actually delivered.
12. **A unit's best self-schedule is its own integer program.** `_om` solves one small
    integer program per unit over that unit's rows. It therefore does not inherit the
    schedule-enumeration ceiling, payments and dual values work at any horizon, and the
    agreement between `hl` and `qd` becomes a check across the two descriptions.
13. **Make-whole is summed per commitment block.** A block is a run of consecutive on
    periods, and its start-up cost is charged to it when it starts inside the horizon. The
    talk's own restricted set is defined per block, so the payment is too. Lost opportunity
    is total uplift less make-whole, reported as computed rather than clamped at zero.
14. **The talk's average incremental cost figure is not reproduced, and the reason is a
    test.** Its $146.33 is exactly the value of mixing the cleared schedule with being off.
    The exact hull also contains the "start at period 2" schedule, and prices at $422. Both
    remove the make-whole payment. The talk does not publish its formulation's rows, so the
    repository states the difference and its mechanism rather than guessing at a match.
15. **The restricted price is measured, not defended.** On the 10 x 8 synthetic market the
    average incremental cost price leaves 38.5 million in foregone profit while removing a
    1,513 make-whole payment. That is a property of squeezing the priced market until
    supply barely meets demand, and it belongs in the README table rather than in a
    footnote.

## Shared choices

16. **Make `models` an explicit package.** Its empty `__init__.py` removes the accidental
    reliance on an implicit namespace package.
17. **Declare Ruff in the one requirements file.** Ruff was already the required lint
    check; the missing line made the documented install incomplete.
18. **The source register was checked on 2026-09-14.** Incorrect publication details were
    corrected and unrelated scouting material was archived. Checked links and exact data
    hashes are in Sources.

## Still open

1. **Variable wall angles.** The pit model's nine-block pattern is one uniform 45-degree
   wall. A real deposit varies slope by direction and rock type. Only construction of `E`
   changes; the solve does not.
2. **A transmission network in the market model.** Every published case here is a single
   bus. Adding lines makes the price locational in fact as well as in name, and introduces
   the congestion uplift the talk raises at its close.
3. **Piecewise-linear and quadratic offers.** Offers here are one energy price per unit.
   Hua and Baldick handle quadratic costs with a second-order cone program.
4. **A compact convex hull formulation.** `hl` enumerates schedules, so its cost doubles
   with every period. The published route to a compact form is the extended formulation of
   Yu, Guan and Chen. That is the work that would make exact hull pricing usable at a real
   horizon, and it is also the thing most likely to explain the difference recorded in
   choice 14.
5. **Mine production scheduling.** The pit model chooses the final pit but not when to mine
   each block. Periods, discounting and capacity limits turn it into an integer program;
   the market model in this repository is that same class of problem for a different asset.

## Model path

| Stage | Model | Solution class |
| --- | --- | --- |
| Built | Ultimate pit limit | Maximum closure, solved by minimum cut |
| Built | Unit commitment, dispatch and pricing | Mixed-integer program, with prices from linear duals |
| Exact flow | Shortest path and maximum flow | Network flow |
| Exact flow | Transportation and transshipment | Minimum-cost flow |
| Exact flow | Assignment | Bipartite minimum-cost flow |
| Branch point | Integer minimum-cost flow plus one budget row | The continuous relaxation is a linear program, but the required whole-flow version loses the network guarantee and can be NP-hard |
| Integer network | Mine production scheduling and integral multicommodity flow | Mixed-integer models with shared limits |
| Integer network | Fixed-charge flow | Binary arc opening with variable-specific upper bounds |
| Integer network | Facility location and set covering | Mixed-integer selection models |
| Bilevel network | Network interdiction | Attacker and operator models, commonly reformulated with duality |

Learning to branch becomes relevant from the branch point onward. The two machine-learning
sources actually reviewed for that direction are recorded in Sources. The unit commitment
model is now a real integer program, so it is the first place in this repository where a
learned branching rule could be measured against an exact baseline rather than argued for.

## Rejected work

- **A single solve route:** it cannot catch a bad formulation.
- **The original 1965 graph procedure as a second code path:** Picard's exact reduction
  already has three checks. A historical duplicate would add upkeep, not evidence.
- **A subgradient search for the convex hull price:** Hua and Baldick measure a standard
  subgradient method at 0.88% sub-optimal after 550 iterations with no non-heuristic
  stopping rule. An exact linear program with no tuning is strictly better here.
- **scikit-opt or another metaheuristic for the pit:** it would replace nothing and cannot
  improve an exact optimum. Heuristics may be reconsidered for scheduling or interdiction
  after those models exist.
- **A neural dependency:** the relevant research is retained as a future direction, not
  code.
- **Copying titles from reading lists:** the lists reviewed are finding aids. Only sources
  that were opened and used appear in the bibliography.
- **Random geometry or random offers with no economic test:** every generated benchmark
  must state and test what it is supposed to exhibit.
