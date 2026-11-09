# Electricity Clearing and Pricing

## Background

A plant's start-up cost and minimum output can prevent hourly energy prices from covering its operating cost. Markets compensate plants through side payments called uplift. This project compares price rules by the uplift they leave, using exact unit hulls on small systems. It is a research benchmark for price formation.

## Methods

- Rust models for unit commitment, electricity prices and uplift on small power systems.
- The engine clears generation over DC lines and transfer limits.
- Prices: locational marginal prices (LMP), convex-hull prices (CHP) and average-incremental-cost prices (AIC). The clearing is settled at each.
- HiGHS solves the linear and mixed-integer programs through a native Rust binding.
- CHP hull columns are O(T³) per unit, so CHP time grows quickly with the horizon and the unit count. `uc` and `lmp` on the same markets take seconds.
- Above 24 balance rows (buses × periods) the lexicographic walk is skipped. Prices are accepted when the interior-point probe agrees with the vertex (`price_selection: "probe"`); otherwise they minimise demand payment only (`"payment"`, with a warning on standard error).
- Not modelled: contingencies, losses, reserves, market mitigation. ISO-scale performance is unmeasured. Optimality holds to solver tolerances.
- Parity fixture: 29 markets pinned to outputs of the earlier implementation at revision `ec91593`, frozen as JSON.
- Details: [model](docs/MODEL.md), [sources](docs/SOURCES.md), [demand-sensitivity study](docs/STUDY.md).

## Execution

- Install stable Rust, a C++ toolchain, CMake and libclang. The first build compiles the bundled HiGHS library. On Windows, use Visual Studio's C++ build tools and set `CMAKE` and `LIBCLANG_PATH` if those tools are outside `PATH`.

```text
cargo build --locked
cargo run --locked -- case 3
cargo run --locked -- case 4 chp
cargo run --locked -- solve cases/2.json lmp
cargo run --locked -- case 3 study
```

- `ecp` writes JSON to standard output, and errors to standard error with a nonzero exit code. `ecp solve - chp` reads standard input.
- Routes: `uc`, `lmp`, `rx`, `chp`, `aic` and `all` (default). `all` reports every rule's prices and the settlement (`pay_lmp`, `pay_chp`, `pay_aic`).
- Results carry the bound, gap, primal `status` and separate `price_selection`.
- `study` explores demand sensitivity with 17 adaptively placed samples over 80–100% of the supplied demand, retaining the full input and each settlement.
- Library: `Market` and binary `Clearing` are immutable. Read market data through `units()`, `demand()` and `network()`; rebuild through `Market::new` after a change. Fixed-commitment pricing and settlement accept `Clearing`, while relaxations return `Sol`. Price and ceiling matrices are checked at each public entry point. Numerical failures use typed `Error` variants. In version 0.4, `pc` returns `Result` and the old combined `st` output is replaced by `status` and `price_selection`.
- Checks:

```text
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
```

## Layout

| Location | Owns |
| --- | --- |
| `src/unit.rs` | Unit data, defaults, the feasible set and fixed-schedule dispatch |
| `src/network.rs` | DC lines and transfer limits; the network Lagrangian term |
| `src/market.rs` | Validated input, nodal balances and balance prices |
| `src/clearing.rs` | Integer clearing, relaxation and fixed-commitment dispatch |
| `src/hull.rs` | Interval-graph hulls and the Lagrangian certificate |
| `src/pricing.rs` | Settlement, AIC ceilings and the comparison of rules |
| `src/lp.rs` | Sparse programs, HiGHS and solver certificates |
| `src/study.rs` | Adaptive demand sensitivity using the existing pricing route |
| `src/main.rs` | Command routing and the built-in cases in `cases/` |

## Results

Results are in [docs/VALIDATION.md](docs/VALIDATION.md) and [docs/results/ferc-study.json](docs/results/ferc-study.json).

MIT license.
