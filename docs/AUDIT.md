# Audit of the decomposition, settlement and risk studies

**Subject.** The uncommitted tree on `8f2e74c` that adds `models/dw.py`, `models/settle.py`
and `models/risk.py`, with their runners, tests and documents.
**Dates.** Audited 2026-09-24 and 25; findings resolved 2026-09-26.
**Stack.** Python 3.14.7, NumPy 2.5.3, SciPy 1.18.1 with HiGHS 1.12.0, Windows 10.

The formulations are sound. Two results were wrong, five claims outran their evidence, and
two kinds of test could pass a wrong program; all are resolved below. What remains is items
8–13 of [Open issues](ISSUES.md).

## Findings

| | Finding | Resolution | Record |
| --- | --- | --- | --- |
| W1 | The Lagrangian bound exceeded the hull value, on 6 of 208 routes at the family's own cost scale, hidden by the tests' $10^{-8}$ bracket; DW.md called the bound certified while recording its excess. | Every bound route runs as `_mi(..., bd=True)`: presolve off, feasibility tolerances $10^{-9}$. "Certified" now reads "to the solver's tolerances". | [Pricing](PRICING.md#what-a-clearing-certifies), [Decomposition](DW.md#tolerances); `python run_dw.py oracle` |
| W2 | A pglib instance without thermal units crashed in `_gen` ($G=0$). | Fixed. | `test_no_thermal_unit`, `test_pglib_bound_carries_the_renewables` |
| U1 | A fixed reduced-cost floor stalled seed 98 capped at cost scale 10. | W1's tolerances remove it at every scale measured; $A_B=10^{-5}$ is now measured; `run_dw.py rts` prints the tag. | [Decomposition](DW.md#tolerances) |
| U2 | `rent = rf` holds for any balanced flows at any price, so it checks only the payments. | Prices now checked by congestion complementarity, which a price raised by 5 at one bus violates in four periods, and by their place on the optimal face; `_fl`'s docstring corrected. | [Storage in the clearing](SETTLE.md); `test_congestion_is_priced_only_on_a_full_line`, `test_the_load_price_lies_on_the_optimal_face` |
| U3 | CVaR multipliers compared as points at a quantile tie; $y=\omega\lambda$ compared two separately selected duals. | Envelope optimality asserted by objective, a tied example added, price uniqueness proved per example. | [Risk-averse prices](RISK.md), [Validation](VALIDATION.md#risk-averse-prices) |
| U4 | `cvd` read $\omega_s\le10^{-9}$ as zero without saying so. | Stated. | `cvd`, [Risk-averse prices](RISK.md) |
| U5 | AIC prices depend on $\epsilon$, unmeasured. | Measured; $\epsilon$ stays $10^{-6}$. | [Pricing](PRICING.md); `python run_face_scan.py aic` |
| T1 | `test_seeded_family` counted a numerical failure as an infeasible seed. | `_clear` excludes a seed only on a proved infeasibility; tests and runners use it. | [Validation](VALIDATION.md#generated-master); `test_a_numerical_failure_does_not_exclude_a_seed` |
| T2 | Point assertions on possibly nonunique duals. | Uniqueness proved (risk), load prices bounded on the face (settlement), equal CHP prices shown to test one rule on one face (decomposition). s1's load saving of 4,000 is the payment rule's choice. | [Storage in the clearing](SETTLE.md), [Risk-averse prices](RISK.md) |
| S1 | Legends incomplete. | `bd`, `BD`, `_ext`'s symbols and dw's two meanings of `pi` defined. | module legends |

Equal CHP prices test one rule because `cg`'s final selected dual prices every unit, so it
lies in the hull's face to $\tau$, and a minimiser over the master's larger face that lies
in the smaller one minimises over it. At the audit, with HiGHS's MIP seed changed to 42 and
heuristic effort 0, all 159 new tests passed; SciPy passes both options to HiGHS verbatim.

## The report's own defects, corrected

- It cited `docs/INDUSTRY.md` four times; that file was never written. The citations are
  removed.
- It deferred the isolated presolve timings, which had finished. They are below.
- Its evidence lived in `../emm-audit-scratch`. Every finding is now recorded in a test or
  a runner table here; the scratch directory holds only the evidence below.

## Evidence recorded only here

**Presolve in `_om`.** On against off in `_om` alone, default tolerances
(`../emm-audit-scratch/performance/om.py`):

| | Presolve on | Presolve off |
| --- | ---: | ---: |
| Test suite | 612 passed, 1 failed | 613 passed |
| `_om` in the suite, 607 calls | 5.68 s | 12.45 s |
| `qd`, 96 × 24, price 40 | 1.10–1.13 s | 0.95–0.98 s |
| `qd`, 96 × 24, at the LMP | 1.14–1.18 s | 1.01–1.08 s |

The failure is `test_seeded_family[123]`: `qd` gives 1,384.0841601 against $L$ =
1,384.0841245, $2.6\times10^{-8}$ relative. Turning presolve off is load-bearing.

**Regression against `8f2e74c`.** HEAD passes 454 tests; the tree passed 613 at the audit
and passes 648 now. Of eight pricing routes on each of the 104 feasible markets, the 825
that succeeded at HEAD return the same value and price, and the other seven now succeed:
capped `rx` at seed 2, and both capped hulls at seeds 36, 116 and 129. None is a bound
route.

**HiGHS reproducers** (`../emm-audit-scratch/repro`), runnable without this repository:

| Script | Result |
| --- | --- |
| `highs_presolve_lp.py`, seed 36 | Presolve: infeasible. Off: optimal, 817.127734910633, row residual $4.0\times10^{-9}$ |
| `highs_presolve_mip_bound.py`, seed 88 | Presolve bound $3.1\times10^{-4}$ above an integral witness; off, equal to it |
