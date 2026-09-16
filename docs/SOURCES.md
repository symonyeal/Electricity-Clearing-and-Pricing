# Sources

Only sources used by a live formulation, dataset, or validation case are listed.

## Unit commitment and prices

| Source | Use |
| --- | --- |
| Hua, B. and Baldick, R. (2017), [“A Convex Primal Formulation for Convex Hull Pricing”](https://arxiv.org/abs/1605.05002), *IEEE Transactions on Power Systems* 32(5), 3814–3823 | Convex-primal CHP and examples `ex1` and `ex2` |
| Chen, Y., O'Neill, R. P. and Whitman, P. (2020), [“A Unified Approach to Solve Convex Hull Pricing and Average Incremental Cost Pricing”](https://www.ferc.gov/sites/default/files/2020-06/W2-1_Chen_et_al.pdf) | AIC, payments, and `ex3` |
| Chen, Y., O'Neill, R. P. and Whitman, P. (2020), [Optimization Online version](https://optimization-online.org/2020/09/8004/) | Restricted-block result used to interpret AIC make-whole payments |
| Balas, E. (1998), [“Disjunctive Programming: Properties of the Convex Hull of Feasible Points”](https://doi.org/10.1016/S0166-218X(98)00136-X) | Schedule-wise union-of-polyhedra formulation `hl` |
| Yu, Y., Guan, Y. and Chen, Y. (2020), [“An Extended Integral Unit Commitment Formulation and an Iterative Algorithm for Convex Hull Pricing”](https://arxiv.org/abs/1910.12994) | Interval-graph unit hull `hc` |
| Knueven, B., Ostrowski, J. and Watson, J.-P. (2020), [“On Mixed-Integer Programming Formulations for the Unit Commitment Problem”](https://doi.org/10.1287/ijoc.2019.0944) | Unit-commitment rows and pglib-uc reference formulation |
| Rajan, D. and Takriti, S. (2005), [“Minimum Up/Down Polytopes of the Unit Commitment Problem with Start-Up Costs”](https://www.semanticscholar.org/paper/b88642e36b414d5929fed48593d0ac46ae3e2070) | Minimum up/down inequalities |
| Stott, B., Jardim, J. and Alsac, O. (2009), [“DC Power Flow Revisited”](https://doi.org/10.1109/TPWRS.2009.2021235) | Lossless DC network model |

The FERC talk is also stored locally as `Research PDF Files\electricity pricing.pdf`.

### Small cases

| Case | Source and restriction |
| --- | --- |
| `ex1` | Hua–Baldick Table 1; one period |
| `ex2` | Hua–Baldick Table 3; start-up and shut-down ramps are set equal to normal ramps to recover the published period-2 commitment |
| `ex3` | Chen–O'Neill–Whitman slide 13; both exact hulls give AIC price $(10,10,422)$ rather than the reported $(10,10,146.33)$ |
| `ex4` | Synthetic three-bus DC loop |
| `ex5` | Synthetic offers and demand with the directional `NO-NO1_NO-NO2` capacity from [electricitymaps](https://github.com/electricitymaps/electricitymaps-contrib/blob/master/config/exchanges/NO-NO1_NO-NO2.yaml) |

## pglib-uc

[`models/pglib_uc.py`](../models/pglib_uc.py) implements equations (1)–(24) of the
[pglib-uc model](https://github.com/power-grid-lib/pglib-uc/blob/master/MODEL.pdf) from
independent rows. The library's reference code is MIT-licensed; its cases are CC-BY-4.0.

| Local file | Official file | SHA-256 |
| --- | --- | --- |
| `data/pglib_uc/rts_gmlc_2020-03-05.json` | [RTS-GMLC 2020-03-05](https://github.com/power-grid-lib/pglib-uc/blob/master/rts_gmlc/2020-03-05.json) | `0F89BF93327B5F90BB7381C1E7AE08614B60DEF2390E2E8940F40B9CF825045F` |

The official `uc_model.py` relaxation under HiGHS gives `2480427.041110388`; the local
independent formulation gives `2480427.0411103913`.

## Storage

| Source | Use |
| --- | --- |
| Rockafellar, R. T. and Uryasev, S. (2000), [“Optimization of Conditional Value-at-Risk”](https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf) | Scenario epigraph for loss CVaR |
| Rockafellar, R. T. and Uryasev, S. (2002), [“Conditional Value-at-Risk for General Loss Distributions”](https://sites.math.washington.edu/~rtr/papers/rtr187-CVaR2.pdf) | Discrete tails and probability atoms |
| [HydroBoost `a7bea5e`](https://github.com/idaholab/HydroBoost/tree/a7bea5eb05ae) | Storage balance and mutually exclusive operating modes, restricted here to one battery and energy trading |
| [LOGOS `5a09f88`](https://github.com/idaholab/LOGOS/tree/5a09f888535a) | Independent precedent for the mean/CVaR objective |
| [PJM two-settlement overview](https://learn.pjm.com/three-priorities/buying-and-selling-energy/energy-markets.aspx) | General forward-plus-deviation accounting convention; no PJM rule set is implemented |

No upstream package is a runtime dependency. The equations are implemented directly in
SciPy. The completed local-code review is in the
[archive](../_archive/20260916-focus-reset/documentation/INL.md).

## NYISO replay

| Source | Use |
| --- | --- |
| [NYISO day-ahead zonal LBMP, P-2A](http://mis.nyiso.com/public/P-2Alist.htm) | Hourly day-ahead prices |
| [NYISO real-time zonal LBMP, P-24A](http://mis.nyiso.com/public/P-24Alist.htm) | Five-minute real-time prices |
| Monthly files under `http://mis.nyiso.com/public/csv/{report}/{YYYYMM01}{report}_zone_csv.zip` | Executed price record, downloaded 2026-09-15 |
| Künsch, H. R. (1989), [“The Jackknife and the Bootstrap for General Stationary Observations”](https://doi.org/10.1214/aos/1176347265) | Moving-block bootstrap for annual net settlement |

NYISO states that corrected prices are reposted. The replay uses the archive as downloaded,
not the original price available at each historical decision time. The difference is not
measured. Bid time, information lag, full acceptance, self-dispatch, and settlement are
explicit study assumptions; they are not attributed to NYISO manuals.

## Decomposition

[Decomposition](DW.md) relates the two direct hull formulations to the Dantzig–Wolfe
extreme-point master and states the requirements for column generation. It cites
Andrianesis et al. (2020) §§II–III, Wolsey (2021) chapters 10–11 with page pinpoints, and
Dantzig and Wolfe (1960), DOI 10.1287/opre.8.1.101. No column-generation implementation or
benchmark is reported, so those sources are listed there rather than here.

## Solver contracts

| Tool | Contract used |
| --- | --- |
| [SciPy `milp`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html) | MIP status, `mip_gap`, and `mip_dual_bound` |
| [SciPy `linprog`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html) | LP solution and equality marginals |
| [HiGHS](https://highs.dev/) | LP and MIP backend |
| [pytest](https://docs.pytest.org/) | Verification runner |
| [Ruff](https://docs.astral.sh/ruff/) | Static check |

The previous reading list, pit references, and repository-review notes are preserved in the
[archived source register](../_archive/20260916-focus-reset/documentation/SOURCES.md).
