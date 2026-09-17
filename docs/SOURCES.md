# Sources

Only sources used by a live formulation, dataset, or validation case are listed.

## Unit commitment and prices

| Source | Use |
| --- | --- |
| Gribik, P. R., Hogan, W. W. and Pope, S. L. (2007), [“Market-Clearing Electricity Prices and Energy Uplift”](http://www.lmpmarketdesign.com/papers/Gribik_Hogan_Pope_Price_Uplift_123107.pdf), working paper, 31 December 2007 | Convex hull pricing and the uplift it minimizes; the origin of the rule `hc` and `hl` compute |
| Liberopoulos, G. and Andrianesis, P. (2016), [“Critical Review of Pricing Schemes in Markets with Non-Convex Costs”](https://doi.org/10.1287/opre.2015.1451), *Operations Research* 64(1), 17–31 | The taxonomy the three priced rules sit inside |
| Hua, B. and Baldick, R. (2017), [“A Convex Primal Formulation for Convex Hull Pricing”](https://arxiv.org/abs/1605.05002), *IEEE Transactions on Power Systems* 32(5), 3814–3823 | Convex-primal CHP and examples `ex1` and `ex2` |
| O'Neill, R. P., Castillo, A., Eldridge, B. and Hytowitz, R. B. (2017), [“Dual Pricing Algorithm in ISO Markets”](https://doi.org/10.1109/TPWRS.2016.2614891), *IEEE Transactions on Power Systems* 32(4), 3308–3310 | Axiomatic dual pricing; reference [4] of the FERC talk the AIC case rests on |
| Chen, Y., O'Neill, R. P. and Whitman, P. (2020), [“A Unified Approach to Solve Convex Hull Pricing and Average Incremental Cost Pricing”](https://www.ferc.gov/sites/default/files/2020-06/W2-1_Chen_et_al.pdf) | AIC, payments, and `ex3` |
| Chen, Y., O'Neill, R. P. and Whitman, P. (2020), [Optimization Online version](https://optimization-online.org/2020/09/8004/) | Restricted-block result used to interpret AIC make-whole payments |
| Balas, E. (1998), [“Disjunctive Programming: Properties of the Convex Hull of Feasible Points”](https://doi.org/10.1016/S0166-218X(98)00136-X) | Schedule-wise union-of-polyhedra formulation `hl` |
| Yu, Y., Guan, Y. and Chen, Y. (2020), [“An Extended Integral Unit Commitment Formulation and an Iterative Algorithm for Convex Hull Pricing”](https://arxiv.org/abs/1910.12994) | Interval-graph unit hull `hc` |
| Knueven, B., Ostrowski, J. and Watson, J.-P. (2020), [“On Mixed-Integer Programming Formulations for the Unit Commitment Problem”](https://doi.org/10.1287/ijoc.2019.0944) | Unit-commitment rows and pglib-uc reference formulation |
| Rajan, D. and Takriti, S. (2005), [“Minimum Up/Down Polytopes of the Unit Commitment Problem with Start-Up Costs”](https://www.semanticscholar.org/paper/b88642e36b414d5929fed48593d0ac46ae3e2070) | Minimum up/down inequalities |
| Stott, B., Jardim, J. and Alsac, O. (2009), [“DC Power Flow Revisited”](https://doi.org/10.1109/TPWRS.2009.2021235) | Lossless DC network model |
| Beck, A. (2014), [*Introduction to Nonlinear Optimization: Theory, Algorithms, and Applications with MATLAB*](https://doi.org/10.1137/1.9781611973655), MOS-SIAM, ch. 12, pp. 237–240 | Definition of the Lagrangian dual and Theorem 12.3, weak duality, which fixes what `qd` must minimize over |

The FERC talk is also stored locally as `Research PDF Files\electricity pricing.pdf`, and
Beck as `Research PDF Files\beck.pdf`.

### Production practice

What is actually settled, against which the priced rules here are a measurement. Cited by
[Pricing](PRICING.md), "What is settled in practice".

| Source | Use |
| --- | --- |
| MISO (2024), [“Fast Start Pricing / ELMP at MISO”](https://stakeholdercenter.caiso.com/InitiativeDocuments/Presentation-Fast%20Start-Pricing-ELMP-at-MISO-Dec-19-2024.pdf), presented to the CAISO stakeholder process, 19 December 2024 | The partial-commitment relaxation, the unenforced ramp-down row, Fast Start Resource eligibility, the phase dates, and the Phase I and Phase II results |
| Guan, Y. (2019), [“Optimal Convex Hull Pricing and MISO Case Studies”](https://www.ferc.gov/sites/default/files/2020-09/T4-3-Guan.pdf), FERC Technical Conference, June 2019 | The interval dynamic program behind `hc`, and its $O(T^2)$ proposition |
| Ahunbay, M. Ş., Bichler, M., Dobos, T. and Knörr, J. (2023), [“Solving Large-Scale Electricity Market Pricing Problems in Polynomial Time”](https://arxiv.org/abs/2312.07071) | An alternative that changes the allocation rather than the price: approximate competitive equilibrium with no budget deficit |
| FERC Staff (2014), [“Staff Analysis of Uplift in RTO and ISO Markets”](https://www.ferc.gov/sites/default/files/2020-05/08-13-14-uplift_3.pdf), August 2014 | The uplift problem as the regulator states it. Docket No. AD14-14-000, *Price Formation in Energy and Ancillary Services Markets Operated by Regional Transmission Organizations and Independent System Operators*, Notice of 19 June 2014, named in the README |
| NYISO, [“Formulas For Determining Bid Production Cost Guarantee”](https://www.nyiso.com/documents/20142/36318208/MST%2018%20022223%20MC.pdf/ef89c9e4-27ac-cce8-e1be-50922168e5aa), Market Services Tariff §18 | The name and form of the make-whole payment in the market this repository replays |
| Monitoring Analytics (2025), [*2024 State of the Market Report for PJM*, §4 Energy Uplift](https://www.monitoringanalytics.com/reports/PJM_State_of_the_Market/2024/2024-som-pjm-sec4.pdf) | PJM's operating reserve credits, and an independent market monitor's annual uplift accounting |

Guan's deck is served from FERC's `2020-09` directory; its slides and PDF date are June 2019.
Reference [4] of the FERC talk gives the O'Neill dual-pricing pages as 3301–3310; the
publisher's own deposit gives 3308–3310, which is what is recorded above.

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
