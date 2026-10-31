# Electricity Clearing and Pricing

Rust models for unit commitment, electricity prices and uplift on small power systems.
The engine clears generation on DC or directional transport networks, then computes
locational marginal prices (LMP), convex-hull prices (CHP), and average-incremental-cost
prices (AIC). HiGHS solves the linear and mixed-integer programs through a native Rust
binding; running the engine requires no Python interpreter.

## Background

A plant's start-up cost and minimum output can prevent hourly energy prices from covering
its operating cost. Markets compensate plants through side payments called uplift.
This project compares the price rules that determine those payments against exact hulls
on small systems. It is a research benchmark for price formation.

The FERC two-unit case clears at $7,340. Its peak LMP is $90/MWh with $1,690 uplift;
CHP is $276/MWh with $365 uplift. The full p-cut AIC hull gives $422/MWh. The talk's
$146.33 uses a restricted schedule set; both results retain their stated feasible sets.
[Formulation](docs/PRICING.md) and [sources](docs/SOURCES.md).

## Run

Install stable Rust, a C++ toolchain, CMake and libclang. The first build compiles the
bundled HiGHS library. On Windows, use Visual Studio's C++ build tools; set `CMAKE` and
`LIBCLANG_PATH` if those tools are outside `PATH`.

```text
cargo build --locked
cargo run --locked -- case 3
cargo run --locked -- case 4 chp
cargo run --locked -- solve examples/market.json lmp
```

`ecp` writes JSON to standard output and errors to standard error with a nonzero exit
code. Input can also come from standard input: `ecp solve - chp`. Routes are `uc`, `en`,
`rx`, `lmp`, `chp`, `hl`, `cg`, `aic`, and `all` (default). `en` enumerates commitments;
`rx` relaxes them; `hl` uses the trajectory hull; `cg` generates columns.
Output includes the achieved gap, objective bound and
price-selection stage.

## Structure

| Location | Owns |
| --- | --- |
| `src/unit.rs` | Generator data, defaults and the shared feasible set |
| `src/network.rs` | DC and directional transport constraints; network dual term |
| `src/clearing.rs` | Integer clearing, relaxation and fixed-commitment dispatch |
| `src/hull.rs` | Interval and trajectory hull formulations |
| `src/dw.rs` | Column generation and repriced dual certificates |
| `src/pricing.rs` | Self-scheduling bounds, AIC ceilings and uplift |
| `src/lp.rs` | Sparse programs, solver certificates and dual-face selection |
| `src/main.rs` | JSON input and command routing |

The [design](docs/DESIGN.md) records module contracts, input conventions and limits.
The maintained tree contains one implementation. Earlier Python studies and historical
result bundles remain in Git history at `ec91593` and in the local archive.

## Checks

```text
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
```

The Rust parity fixture records outputs from Python revision `ec91593`: published cases,
seeded systems and initial-state, zero-demand and infeasible boundaries. Objectives,
payments and dual bounds are checked separately because schedules and dual prices can
be nonunique. [Validation](docs/VALIDATION.md) gives the scope and reproduction commands.

The engine has no contingencies, losses, reserve co-optimization or market mitigation.
ISO-scale performance is unmeasured. All optimality claims are to solver tolerances.

MIT license. [Bibliography](docs/SOURCES.md).
