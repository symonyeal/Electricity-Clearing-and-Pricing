# Validation

The native engine is compared against the independent Python implementation at revision
`ec91593`. `tests/fixtures/pricing.json` records input data, solver-stack versions,
outcomes and the expected infeasibility for 29 markets:

- Five published or synthetic network cases, `ex1` through `ex5`.
- Twenty seeded two-unit, three-period markets, seeds 0 through 19.
- Initial-on and initial-off duration obligations, zero demand and infeasible minimum output.

The parity test checks UC, relaxation, LMP, both direct hull values and their AIC-capped
values; output ceilings; Lagrangian values at hull and arbitrary prices; and payment
components for the five named cases. It checks demand payment separately from price
coordinates. It also verifies that its comparator rejects a deliberately wrong pair.
This is a numerical comparison over that fixture, not bitwise identity for every input.

Other native checks cover free-column dual stationarity, integer bound read-back,
infeasibility, negative energy cost, initial-state hull agreement, clearing enumeration
and generated hulls against direct hulls.

The comparison tolerance is 1e-6 plus 1e-7 times the larger magnitude, with a minimum
scale of one. It applies to numeric values without rounding the fixture. The suite also
checks JSON/stdin routing and rejects malformed offers and unknown routes.

Before archiving the old runtime, its full suite passed 649 tests on Python 3.14.7,
NumPy 2.5.3 and SciPy 1.18.1 (2026-10-30). This establishes the baseline's test state;
the maintained gates below execute only Rust.

## Reproduce

```text
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
```

The fixture's producing implementation is recoverable from Git revision `ec91593`.
The generator and original numerical outputs are preserved in the local archive.
Their runtime is unnecessary for the maintained checks. Later solver versions can choose
different optimal faces, so the comparator checks values and payments at stated tolerances.

Historical validation and larger Python experiments remain in Git history at that
revision. They do not establish native runtime, native scale or a full-year replay after
clock-alignment repairs.
