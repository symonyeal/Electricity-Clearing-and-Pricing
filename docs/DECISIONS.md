# Decisions and remaining work

This file records design choices, rejected work, and what remains open. The
[README](../README.md) owns measured results and run instructions.
[Sources](SOURCES.md) owns citations and data provenance.

## Rules for every model

- Solve it by at least two routes. Use exhaustive enumeration when the instance
  is small enough.
- Compare objective values when several optimal solutions exist. Comparing sets
  in a tie creates a false failure.
- Label synthetic inputs and give each generator a measurable economic check.
- Add a dependency only when it replaces existing work, is measured on the
  actual model, and leaves an independent check in place.

## Settled choices

1. **Use Picard's minimum-cut reduction.** A positive block gets an arc from the
   source, a negative block gets an arc to the sink, and a deep block `b` gets a
   precedence arc to each required upper block `p`. The returned pit is the
   source side without the source. A precedence capacity is the sum of all
   positive scaled values plus one, so cutting even one costs more than the
   always-available cut of every source arc.
2. **OR-Tools 9.15.6755 is the default solver.** It replaced NetworkX in `mc`
   after it ran faster at all three measured sizes. The measured comparison is
   kept only in the README. NetworkX remains as `mc_nx`, and the SciPy linear
   program remains the separate formulation.
3. **Integer scaling must be exact.** Synthetic values are rounded to cents.
   The MineLib reader derives the required decimal scale from the file. `mc`
   rejects a value that is not an exact multiple of its declared unit and
   rejects capacities that do not fit in a signed 64-bit integer. Multiplying
   every closure value by one positive scale preserves the order of all pits,
   so it preserves the optimum.
4. **Charge mining cost to every block.** An ore block is worth
   `rev * q - c_p - c_m`; waste is worth `-c_m`. This is what makes a profitable
   block capable of losing money after stripping.
5. **Keep one compact arc array.** `mk_E` returns a two-column `int32` array used
   directly by all solvers. The measured memory result is in the README.
6. **Keep `bf` as a small exact check.** It generates valid closed sets in
   prerequisite-first order instead of testing every raw subset. Its enforced
   ceiling is 20 blocks.
7. **Keep direct economic and geometric tests.** Solver agreement cannot detect
   a shared bad `E`. The suite therefore checks arc direction, boundary counts,
   closure, a non-trivial synthetic pit, hand-worked cases, and the external
   MineLib pit.
8. **Outside validation is mandatory and the current audit item is closed.**
   The result is kept only in the README; file provenance is kept only in
   Sources.
9. **Make `models` an explicit package.** Its empty `__init__.py` removes the
   accidental reliance on an implicit namespace package.
10. **The source register was checked on 2026-09-14.** Incorrect publication
    details were corrected and unrelated scouting material was archived. The
    checked links and exact data hashes are in Sources.
11. **Declare Ruff in the one requirements file.** Ruff was already the required
    lint check; the missing line made the documented install incomplete. It
    replaces no model code and carries no timing claim.

## Still open

1. **Variable wall angles.** The current nine-block pattern represents one
   uniform 45-degree wall. A real deposit can vary slope by direction and rock
   type. Only construction of `E` changes; the solve does not.
2. **Production scheduling.** The current model chooses the final pit but not
   when to mine each block. Time periods, discounting, and mining or processing
   limits introduce integer decisions that no single minimum cut can solve.

## Model path

The order below separates models that remain exact flow problems from those
that require integer branching.

| Stage | Model | Solution class |
| --- | --- | --- |
| Built | Ultimate pit limit | Maximum closure, solved by minimum cut |
| Exact flow | Shortest path and maximum flow | Network flow |
| Exact flow | Transportation and transshipment | Minimum-cost flow |
| Exact flow | Assignment | Bipartite minimum-cost flow |
| First branch point | Integer minimum-cost flow plus one budget row | The continuous relaxation is an LP, but the required whole-flow version loses the network guarantee and can be NP-hard |
| Integer network | Production scheduling and integral multicommodity flow | Mixed-integer models with shared limits |
| Integer network | Fixed-charge flow | Binary arc opening with variable-specific upper bounds |
| Integer network | Facility location and set covering | Mixed-integer selection models |
| Bilevel network | Network interdiction | Attacker and operator models, commonly reformulated with duality |

Learning to branch becomes relevant at the first branch point and later, not in
the exact flow stages. The two machine-learning sources actually reviewed for
that direction are recorded in Sources. No neural package belongs in the
repository before one of those integer models exists.

## Rejected work

- **A single solve route:** it cannot catch a bad formulation.
- **The original 1965 graph procedure as a second code path:** Picard's exact
  reduction already has three checks. A historical duplicate would add upkeep,
  not independent evidence.
- **scikit-opt or another metaheuristic for the current pit:** it would replace
  nothing and cannot improve an exact optimum. It was not timed because the
  optional below-optimum demonstration would add another public path without
  validating the model. Heuristics may be reconsidered for scheduling or
  interdiction after those models exist.
- **A neural dependency:** the current problem needs no branching. The relevant
  research is retained as a future direction, not code.
- **Copying titles from reading lists:** the two lists reviewed are finding
  aids. Only sources that were opened and used appear in the bibliography.
- **Random geometry with no economic test:** every generated benchmark must
  state and test its expected non-empty result, omitted positive blocks, and
  strip-ratio band.
