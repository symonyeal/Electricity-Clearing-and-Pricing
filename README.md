# Electricity Clearing and Pricing

Rust models for unit commitment, electricity prices and uplift on small power systems.
The engine clears generation over DC lines and transfer limits, then computes locational
marginal prices (LMP), convex-hull prices (CHP) and average-incremental-cost prices
(AIC), and settles the clearing at each. HiGHS solves the linear and mixed-integer
programs through a native Rust binding.

## Background

A plant's start-up cost and minimum output can prevent hourly energy prices from covering
its operating cost. Markets compensate plants through side payments called uplift. This
project compares price rules by the uplift they leave, using exact unit hulls on small
systems. It is a research benchmark for price formation.

The FERC two-unit case clears at $7,340. Its peak LMP is $90/MWh with $1,690 uplift;
CHP is $276/MWh with $365 uplift. The full p-cut AIC hull gives $422/MWh; the talk's
$146.33 prices a restricted schedule set. [Model](docs/MODEL.md),
[validation](docs/VALIDATION.md) and [sources](docs/SOURCES.md).

## Run

Install stable Rust, a C++ toolchain, CMake and libclang. The first build compiles the
bundled HiGHS library. On Windows, use Visual Studio's C++ build tools and set `CMAKE`
and `LIBCLANG_PATH` if those tools are outside `PATH`.

```text
cargo build --locked
cargo run --locked -- case 3
cargo run --locked -- case 4 chp
cargo run --locked -- solve cases/2.json lmp
```

`ecp` writes JSON to standard output, and errors to standard error with a nonzero exit
code; `ecp solve - chp` reads standard input. Routes are `uc`, `lmp`, `rx`, `chp`,
`aic` and `all` (default), which reports every rule's prices and the settlement
(`pay_lmp`, `pay_chp`, `pay_aic`). Results carry the bound, gap and price-selection stage.

## Structure

| Location | Owns |
| --- | --- |
| `src/unit.rs` | Unit data, defaults, the feasible set and fixed-schedule dispatch |
| `src/network.rs` | DC lines and transfer limits; the network Lagrangian term |
| `src/market.rs` | Validated input, nodal balances and balance prices |
| `src/clearing.rs` | Integer clearing, relaxation and fixed-commitment dispatch |
| `src/hull.rs` | Interval-graph hulls and the Lagrangian certificate |
| `src/pricing.rs` | Settlement, AIC ceilings and the comparison of rules |
| `src/lp.rs` | Sparse programs, HiGHS, solver certificates and dual-face selection |
| `src/main.rs` | Command routing and the built-in cases in `cases/` |

## Checks

```text
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
```

The parity fixture pins 29 markets to an independent implementation at revision
`ec91593`. The engine has no contingencies, losses, reserves or market mitigation;
ISO-scale performance is unmeasured, and optimality holds to solver tolerances.

MIT license.
