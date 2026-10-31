# Working contract

Read [README](README.md), [design](docs/DESIGN.md) and [validation](docs/VALIDATION.md).

- Rust is the sole maintained runtime. Retain code only for an indispensable consumer
  or check; archive redundant reference and legacy implementations outside the repository.
- `unit::rows` owns the complete generator feasible set. Clearing, hulls and oracles
  derive from it. Network assembly and its Lagrangian term belong to `network`.
- `lp` alone handles HiGHS, achieved gaps, certified bounds and dual-price selection.
  Bounds use the solver's bound; failed solves retain their status.
- Price stationarity is an equality, including for free voltage angles. The last balance
  equalities determine the price suffix. Preserve that row order.
- AIC's output relaxation defaults to 1e-6 MW. Keep restricted and unrestricted schedule
  sets distinct; never tune the full $422 FERC hull toward the restricted $146.33 result.
- Cite formulations through [Sources](docs/SOURCES.md). New dependencies need
  a concrete requirement and a measured check.
- Preserve archived work outside the maintained tree. Historical results stay attached
  to the revision that produced them.
- Run the README checks. Report numerical differences
  and limitations at their measured scope.
