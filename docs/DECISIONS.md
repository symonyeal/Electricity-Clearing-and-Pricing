# Open decisions, remaining work and settled ground

The one register for unresolved choices, work still to do, accepted limitations,
and things already tried and refused. Sources are in [Sources](SOURCES.md).

## Rules that bind every change

- **Every model is solved at least twice.** One production method, one
  independent check, and exhaustive enumeration wherever the instance is small
  enough. A model with a single solve path is not finished.
- **A test that cannot distinguish a tie from a defect is not a test.** Where an
  optimum is not unique, compare objective values, never the chosen set.
- **Synthetic data is labelled as synthetic**, in the code and in the README.

## Settled

1. **The pit is solved by minimum cut, not by the 1965 graph procedure.**
   Picard's reduction is exact, and Hochbaum and Chen showed the flow route is
   faster in practice. The original procedure is of historical interest only.
2. **Block values carry mining cost on every block, including ore.** An ore block
   is worth `rev * q - c_p - c_m`, a waste block `-c_m`. Charging processing cost
   only to ore is what makes stripping bite.
3. **The 18.0 tie case stays in the test suite.** It is the one instance that
   proves the tests are sensitive to degeneracy rather than accidentally passing.
4. **Single system Python, no virtual environment.** Matches the rest of the
   machine.

## Open

1. **Real instances instead of synthetic.** MineLib publishes ultimate pit limit
   instances with known optimal values. Until the code is run against them, the
   only external validation is two hand-checked toy models. This is the largest
   open item.
2. **Variable slope angles.** The nine-block cone assumes a uniform 45 degree
   wall in every direction. Real pits vary the angle by azimuth and rock type,
   which changes the precedence set and nothing else about the method.
3. **A compiled maximum flow.** NetworkX is pure Python and runs slower than the
   linear program at 243,000 blocks. Pseudoflow would reverse that. Worth doing
   only if instance size grows.
4. **Production scheduling, not just the pit outline.** The ultimate pit says
   which blocks to mine, never when. Adding time periods, discounting and
   capacity limits gives the constrained pit limit problem, which is a genuine
   mixed-integer program with no exact flow solution. MineLib carries instances
   for this too.

## The sequence of models this repository is meant to hold

Ordered so each one is the previous with a constraint added, which is where the
problem stops being a flow problem and starts needing branching.

| Model | Class | Solves as |
| --- | --- | --- |
| Ultimate pit limit | Maximum closure | Minimum cut. **Built.** |
| Transportation and transshipment | Minimum cost flow | Linear program, integral |
| Shortest path, maximum flow | Flow | Linear program, integral |
| Assignment | Bipartite matching | Linear program, integral |
| Minimum cost flow with a budget side constraint | Flow plus one row | Mixed integer. The first model that needs branching |
| Multicommodity flow | Shared arc capacity | Mixed integer |
| Fixed charge network flow | Binary arc opening | Mixed integer, needs variable upper bounds |
| Facility location, set covering | Location | Mixed integer |
| Network interdiction | Bilevel | Mixed integer by duality |

## Refused

- **Anything with a single solve path.** Rejected on the first version of the pit
  model, which reported a number no second method had confirmed.
- **Random geometry without an economic check.** The first block model put the
  ore lens deep enough that no pit was worth digging. The solver correctly
  returned an empty pit, and the result looked like a bug for long enough to be
  worth recording. Any new instance generator states its expected strip ratio.
