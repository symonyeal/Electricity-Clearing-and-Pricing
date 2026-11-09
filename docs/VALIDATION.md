# Validation

## Cases

`cases/1.json` to `cases/5.json` are the built-in cases, run with `ecp case <n>`.

| Case | Construction | Pinned result |
| --- | --- | --- |
| 1 | Hua-Baldick, one period | LMP 50/MWh; CHP 12/MWh |
| 2 | Hua-Baldick, three periods and ramping | CHP (60, 60, 65.6)/MWh |
| 3 | Chen-O'Neill-Whitman FERC case | Clearing 7,340; peak LMP 90, CHP 276, full p-cut AIC 422/MWh |
| 4 | Synthetic equal-reactance three-bus loop | Clearing 2,100; hull nodal prices (10, 30, 50)/MWh |
| 5 | Synthetic two-zone offers and demand | Transfer bounds [−3500, 2200] MW; clearing 275,000 |

In case 3, LMP leaves 1,690 of uplift, all make-whole; CHP leaves 365, all lost
opportunity. The FERC talk reports an AIC price of 146.33/MWh. Restricting the second
unit to its cleared and off schedules gives that value; the full p-cut hull used here
gives 422. These are different feasible sets, and the talk does not establish that its
AIC row used the later cuts, so 146.33 is not treated as the unrestricted answer.

## Checks

`tests/fixtures/pricing.json` holds 29 markets and their outputs from the earlier
implementation at revision `ec91593`, with its solver-stack versions:

- the five cases above;
- twenty seeded two-unit, three-period markets, seeds 0 to 19;
- initial-on and initial-off duration obligations, zero demand and infeasible minimum
  output.

`tests/parity.rs` compares the clearing, relaxation, LMP and hull costs, the hull and
relaxation costs under AIC ceilings, the ceilings themselves, the Lagrangian value at the
hull price and at arbitrary prices, and, for the five cases, every payment component and
demand payment. Price coordinates can be nonunique when value and demand payment agree,
so coordinates are not compared. The tolerance is 1e-6 plus 1e-7 times the larger
magnitude, with scale at least one; the comparator is shown to reject a wrong pair. This
is a numerical comparison over the fixture, not identity for every input.

`tests/cli.rs` reproduces the case 3 results above from the command line and checks
standard-input routing and rejection of malformed input. Unit tests cover free-column
dual stationarity, integer bound read-back, infeasibility, negative energy cost, hull
certificates at initial-on and initial-off states, mixed DC and transfer networks, and
a loss forced by initial state.

`tests/boundaries.rs` rejects ragged/nonfinite prices, malformed ceilings, fractional
or incomplete fixed schedules, and clearing reuse after a market change. Compile-fail
examples prevent market mutation and supplying a relaxation to fixed-commitment pricing.
Handle tests append a continuous auxiliary column and an equality after balances;
prices and integer domains keep their meanings. A finite price grid checks weak duality
on the original two-bus counterexample. These are bounded regressions, not a proof over
all markets. Injected dual-face failure verifies that raw prices cannot satisfy the
payment-selection policy; a 25-row case is priced by the probe, skipping the walk, and a 2-bus 24-period CLI run reports it without a warning. Typed
infeasible and unbounded outcomes are checked separately from solver faults.

The adaptive study is checked against analytic costs and zero uplift for a one-unit
linear market. Its FERC case run retains all 17 settlements; it is exploratory sensitivity
analysis, with the input and limitations described in [the method](STUDY.md).

## CHP timing

CHP time grows quickly with the horizon and the unit count (hull columns are O(T³) per unit).
One `ecp solve MARKET chp` run each, single bus, 24 hourly periods, units of 40–70 MW with
minimum output, start-up and no-load costs and 2-hour minimum up and down times, on a shared
laptop; `uc` and `lmp` on the same markets take seconds:

| Units | CHP time |
|---:|---:|
| 3 | 10 s |
| 6 | 197 s |
| 12 | stopped unfinished after 11.3 h |

Above 24 balance rows (buses × periods) the lexicographic walk is skipped: prices are accepted
when the interior-point probe agrees with the vertex (`price_selection: "probe"`), and
otherwise minimise demand payment only (`"payment"`, with a warning on standard error).

## Reproduce

```text
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
```

The fixture's producing implementation and earlier studies are recoverable from revision
`ec91593`; their runtime is not needed for these checks. Later solver versions can choose
different optimal faces, which is why values and payments, not coordinates, are compared.
