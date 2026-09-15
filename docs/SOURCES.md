# Sources

Checked on 2026-09-15. Each note states the source's role and review status.

## Unit commitment and electricity prices

| Source | Use in this repository |
| --- | --- |
| Chen, Y., O'Neill, R. P. and Whitman, P. (2020). ["A Unified Approach to Solve Convex Hull Pricing and Average Incremental Cost Pricing"](https://www.ferc.gov/sites/default/files/2020-06/W2-1_Chen_et_al.pdf). FERC Technical Conference on Increasing Real-Time and Day-Ahead Market Efficiency through Improved Software, 23-25 June 2020. | Read. Defines AIC, payments, and `ex3`. The repository does not reproduce its $146.33 price; see Decisions. |
| Chen, Y., O'Neill, R. P. and Whitman, P. (2020). ["A Unified Approach to Solve Convex Hull Pricing and Average Incremental Cost Pricing"](https://optimization-online.org/2020/09/8004/). Optimization Online. | Read. Proposition 3 gives vanishing make-whole and order-epsilon uplift for restricted blocks only. No journal version was found. |
| Hua, B. and Baldick, R. (2017). ["A Convex Primal Formulation for Convex Hull Pricing"](https://arxiv.org/abs/1605.05002). *IEEE Transactions on Power Systems* 32(5), 3814-3823. | Read. Supplies the primal CHP formulation and Examples 1-2. |
| Gribik, P., Hogan, W. and Pope, S. (2007). ["Market-Clearing Electricity Prices and Energy Uplift"](https://www.semanticscholar.org/paper/69578a6c6c9fcfdc686c0e0633fa360ac4f3fa4a). Harvard University working paper. | Not opened. Original CHP reference cited by Chen et al. and Hua-Baldick. |
| Balas, E. (1998). ["Disjunctive Programming: Properties of the Convex Hull of Feasible Points"](https://doi.org/10.1016/S0166-218X(98)00136-X). *Discrete Applied Mathematics* 89(1-3). | Not opened. Union-of-polyhedra formulation used by `hl`. |
| Knueven, B., Ostrowski, J. and Watson, J.-P. (2020). ["On Mixed-Integer Programming Formulations for the Unit Commitment Problem"](https://pubsonline.informs.org/doi/10.1287/ijoc.2019.0944). *INFORMS Journal on Computing* 32(4), 857-876. | Not opened; its formulation was read through the two repositories that publish it, `MODEL.pdf` in pglib-uc and the code in Egret. That formulation is the reference for the rows in `_rw`, `_eq` and `_fx`, whose minimum up and down inequalities are the Rajan-Takriti pair. This model restricts it: one linear production cost rather than a piecewise-linear convex one, one start-up cost rather than off-time-dependent tiers, and no reserve requirement. |
| Yang, D., Knueven, B., Watson, J.-P. and Ostrowski, J. (2021). ["Near-Optimal Solutions for Day-Ahead Unit Commitment"](https://ieeexplore.ieee.org/document/9638021). *IEEE PES General Meeting*. | Read the abstract and nomenclature. Commitments within 0.1% or 0.001% of optimal are used in practice, and which one is chosen changes generator revenue across pricing schemes. This repository prices one clearing and does not measure that; see Decisions. |
| Andrianesis, P., Bertsimas, D., Caramanis, M. C. and Hogan, W. W. (2022). ["Computation of Convex Hull Prices in Electricity Markets with Non-Convexities using Dantzig-Wolfe Decomposition"](https://arxiv.org/abs/2012.13331). *IEEE Transactions on Power Systems* 37(4), 2578-2589. | Read the abstract. An independent exact method for the same convex hull price computed here by explicit hull: Dantzig-Wolfe decomposition with column generation, with finite convergence. Not implemented. |
| Knueven, B., Ostrowski, J., Castillo, A. and Watson, J.-P. (2022). ["A Computationally Efficient Algorithm for Computing Convex Hull Prices"](https://www.sciencedirect.com/science/article/abs/pii/S0360835221007105). *Computers & Industrial Engineering* 163, 107806. | Not opened; catalogue record. Row generation by Benders decomposition on the same dual, and the nearest exact alternative to the Dantzig-Wolfe route above. Implemented in both `ConvexHullPricing.jl` and `CHPColumnAndRowGeneration`. Not implemented here. |
| Rajan, D. and Takriti, S. (2005). ["Minimum Up/Down Polytopes of the Unit Commitment Problem with Start-Up Costs"](https://www.semanticscholar.org/paper/b88642e36b414d5929fed48593d0ac46ae3e2070). IBM Research Report RC23628. | Not opened; catalogue record. Source for minimum up/down inequalities. |
| O'Neill, R. P., Castillo, A., Eldridge, B. and Hytowitz, R. B. (2017). ["Dual Pricing Algorithm in ISO Markets"](https://ieeexplore.ieee.org/document/7742365). *IEEE Transactions on Power Systems* 32(4), 3301-3310. | Not opened. Source to which Chen et al. attribute AIC pricing. |
| Yu, Y., Guan, Y. and Chen, Y. (2020). ["An Extended Integral Unit Commitment Formulation and an Iterative Algorithm for Convex Hull Pricing"](https://arxiv.org/abs/1910.12994). *IEEE Transactions on Power Systems* 35(6), 4335-4346. | Read. Proves the compact integral unit hull implemented by `hc`; also states the limit of the Hua-Baldick relaxation with ramps. Distinct from the same authors’ earlier ["An Integral Formulation and Convex Hull Pricing for Unit Commitment"](https://arxiv.org/abs/1906.07862). |
| Martin, R. K., Rardin, R. L. and Campbell, B. A. (1990). ["Polyhedral Characterization of Discrete Dynamic Programming"](https://doi.org/10.1287/opre.38.1.127). *Operations Research* 38(1), 127-138. | Not opened. General polyhedral basis for acyclic dynamic programs. |
| Stott, B., Jardim, J. and Alsac, O. (2009). ["DC Power Flow Revisited"](https://doi.org/10.1109/TPWRS.2009.2021235). *IEEE Transactions on Power Systems* 24(3), 1290-1300. | Not opened. Reference for the DC network model. |

### Data used for the published cases

The small published inputs are defined in `models/uc_price.py`.

| Case | Taken from | Anything the source leaves unstated |
| --- | --- | --- |
| `ex1` | Hua and Baldick, Table 1 | Nothing. One period, so no ramp applies. |
| `ex2` | Hua and Baldick, Table 3 | Start-up and shut-down ramps are omitted. Setting them equal to the normal ramps yields the paper's period-2 commitment; a larger start-up ramp does not. |
| `ex3` | The FERC talk, slide 13 | Nothing. Limits, costs and all three ramp rates are tabulated there. |
| `ex4` | Synthetic | Symmetric three-bus loop. Equal reactances send two thirds of an injection over the direct line. |
| `ex5` | [electricity maps `config/exchanges/NO-NO1_NO-NO2.yaml`](https://github.com/electricitymaps/electricitymaps-contrib/blob/master/config/exchanges/NO-NO1_NO-NO2.yaml), capacity `[-3500, 2200]`; zone keys from `config/zones/NO-NO1.yaml` and `NO-NO2.yaml` | The capacity pair and the two zone keys are that record. Offers and demand are synthetic and labelled so: no market publishes the offers behind a cleared price. |

## Ultimate pit model

| Source | Use in this repository |
| --- | --- |
| Lerchs, H. and Grossmann, I. F. (1965). ["Optimum Design of Open-Pit Mines"](https://onetunnel.org/documents/optimum-design-of-open-pit-mines). *CIM Bulletin* 58(633), 47-54. | Original ultimate-pit problem. The often-repeated pages 17-24 belong to a later *Transactions of the CIM* reprint, not the 1965 Bulletin article. |
| Picard, J.-C. (1976). ["Maximal Closure of a Graph and Applications to Combinatorial Problems"](https://pubsonline.informs.org/doi/10.1287/mnsc.22.11.1268). *Management Science* 22(11), 1268-1272. | Exact maximum-closure to minimum-cut reduction implemented by `mc` and `mc_nx`. |
| Hochbaum, D. S. and Chen, A. (2000). ["Performance Analysis and Best Implementations of Old and New Algorithms for the Open-Pit Mining Problem"](https://pubsonline.informs.org/doi/abs/10.1287/opre.48.6.894.12392). *Operations Research* 48(6), 894-914. | Comparison of algorithms for the open-pit problem. |
| Hochbaum, D. S. (2008). ["The Pseudoflow Algorithm: A New Algorithm for the Maximum-Flow Problem"](https://pubsonline.informs.org/doi/10.1287/opre.1080.0524). *Operations Research* 56(4), 992-1009. | Background on a specialized compiled maximum-flow method. OR-Tools is not claimed to use this algorithm. |

## Flow and integer theory

| Source | Use in this repository |
| --- | --- |
| Ford, L. R. and Fulkerson, D. R. (1956). ["Maximal Flow Through a Network"](https://www.cambridge.org/core/journals/canadian-journal-of-mathematics/article/maximal-flow-through-anetwork/5D6E55D3B06C4F7B1043BC1D82D40764). *Canadian Journal of Mathematics* 8, 399-404. | Maximum-flow/minimum-cut theorem. |
| Ahuja, R. K., Magnanti, T. L. and Orlin, J. B. (1993). [*Network Flows: Theory, Algorithms, and Applications*](https://www.pearson.com/en-us/subject-catalog/p/Ahuja-Network-Flows-Theory-Algorithms-and-Applications/P200000003456/9780136175490). Prentice Hall. | General network-flow formulations and algorithms. The capacitated arc is the transport line model in `_tr`. |
| Goldberg, A. V. and Tarjan, R. E. (1988). ["A New Approach to the Maximum-Flow Problem"](https://dl.acm.org/doi/10.1145/48014.61051). *Journal of the ACM* 35(4), 921-940. | Push-relabel maximum flow. NetworkX is asked explicitly to use its preflow-push implementation. |
| Hoffman, A. J. and Kruskal, J. B. (1956). ["Integral Boundary Points of Convex Polyhedra"](https://www.cs.umd.edu/~gasarch/BLOGPAPERS/kruskalhoffman.pdf). In *Linear Inequalities and Related Systems*, Annals of Mathematics Studies 38, 223-246. | Total unimodularity behind the whole-valued closure relaxation. |
| Schrijver, A. (1986). [*Theory of Linear and Integer Programming*](https://www.wiley.com/en-us/Theory+of+Linear+and+Integer+Programming-p-9780471982326). Wiley. | Network matrices and total unimodularity. |
| Nemhauser, G. L. and Wolsey, L. A. (1988). [*Integer and Combinatorial Optimization*](https://onlinelibrary.wiley.com/doi/book/10.1002/9781118627372). Wiley. | Integer-programming foundation for the later model path. |
| Wolsey, L. A. (2020). [*Integer Programming*, second edition](https://onlinelibrary.wiley.com/doi/10.1002/9781119606475.oth1). Wiley. | Strong formulations and variable-specific upper bounds for fixed-charge models. |
| Holzhauser, M., Krumke, S. O. and Thielen, C. (2016). ["Budget-Constrained Minimum Cost Flows"](https://link.springer.com/article/10.1007/s10878-015-9865-y). *Journal of Combinatorial Optimization* 31(4), 1720-1745. | Complexity of integral flow with a budget constraint. |
| Gasse, M., Chetelat, D., Ferroni, N., Charlin, L. and Lodi, A. (2019). ["Exact Combinatorial Optimization with Graph Convolutional Neural Networks"](https://papers.nips.cc/paper/2019/hash/d14c2267d848abeb81fd590f371d39bd-Abstract.html). *NeurIPS 32*. | Concrete learning-to-branch method for a future integer model. |
| Bengio, Y., Lodi, A. and Prouvost, A. (2021). ["Machine Learning for Combinatorial Optimization: a Methodological Tour d'Horizon"](https://doi.org/10.1016/j.ejor.2020.07.063). *European Journal of Operational Research* 290(2), 405-421. | Survey of machine learning in exact combinatorial optimization. |

## MineLib benchmark

The committed fixture is from Espinoza, D., Goycoolea, M., Moreno, E. and Newman, A. (2013),
["MineLib: a Library of Open Pit Mining Problems"](https://link.springer.com/article/10.1007/s10479-012-1258-3).
*Annals of Operations Research* 206(1), 93-114.

The [Newman1 record](https://minelib.org/v1/newman1.xhtml) defines the instance; the
[results table](https://minelib.org/v1/Results.xhtml) gives its rounded value. Tests use
these committed files:

| Local file | Official file | SHA-256 |
| --- | --- | --- |
| `data/minelib/newman1.upit` | [Block values](https://minelib.org/v1/data/newman1.upit) | `BA49AEE15B8869B05DD46ADC9EC266A0161A186E5BCB4E2951B6C5833BD3FE86` |
| `data/minelib/newman1.prec` | [Precedence rows](https://minelib.org/v1/data/newman1.prec) | `5A2AAA53B8C7843DE643AB0F1280B524B047F86AA7C907EAE657909116F05942` |
| `data/minelib/newman1_upit.sol` | [Official selected blocks](https://minelib.org/v1/sols/newman1_upit.sol) | `673C36F72FE7DAD35394D675799D173A6F2F6BA54D7DAFDF855DA7151C55EB10` |

## Other benchmark libraries for later models

| Library | Relevant models | Official home |
| --- | --- | --- |
| MIPLIB 2017 | General mixed-integer models | [MIPLIB](https://miplib.zib.de/) |
| OR-Library | Set covering, location, assignment, and related models | [OR-Library](https://people.brunel.ac.uk/~mastjjb/) |
| SNDlib | Survivable design and multicommodity flow | [SNDlib description](https://webdoc.sub.gwdg.de/ebook/serien/ah/ZIB/ZR-07-15.pdf) |
| CVRPLIB | Vehicle routing | [CVRPLIB](https://galgos.inf.puc-rio.br/cvrplib/en/about) |
| PSPLIB | Resource-constrained project scheduling | [PSPLIB](https://www.om-db.wi.tum.de/psplib/) |
| DIMACS Implementation Challenges | Network flow, matching, and later challenge sets | [DIMACS](https://dimacs.rutgers.edu/programs/implementation-challenges) |

## Production applications reviewed

These applications concern later model classes, not the synthetic mine data.

| Application | Model class | Source |
| --- | --- | --- |
| Delta Air Lines fleet assignment | Time-space network with coupled fleet decisions | Subramanian et al. (1994), ["Coldstart: Fleet Assignment at Delta Air Lines"](https://pubsonline.informs.org/doi/10.1287/inte.24.1.104), *Interfaces* 24(1), 104-120 |
| Airline crew pairing | Set partitioning with column generation | Barnhart et al. (1998), ["Branch-and-Price: Column Generation for Solving Huge Integer Programs"](https://pubsonline.informs.org/doi/10.1287/opre.46.3.316), *Operations Research* 46(3), 316-329 |
| Netherlands Railways timetable | Mixed-integer and constraint models | Kroon et al. (2009), ["The New Dutch Timetable: The OR Revolution"](https://pure.eur.nl/en/publications/the-new-dutch-timetable-the-or-revolution/), *Interfaces* 39(1), 6-17 |
| CSX locomotive scheduling | Multicommodity flow with integer side constraints | Ahuja et al. (2005), ["Solving Real-Life Locomotive-Scheduling Problems"](https://pubsonline.informs.org/doi/10.1287/trsc.1050.0115), *Transportation Science* 39(4), 503-517 |
| Procter & Gamble supply chain | Mixed-integer supply-chain network design | Camm et al. (1997), ["Blending OR/MS, Judgment, and GIS: Restructuring the P&G Supply Chain"](https://pubsonline.informs.org/doi/10.1287/inte.27.1.128), *Interfaces* 27(1), 128-142 |
| Zara store replenishment | Integer allocation over a retail network | Caro and Gallien (2010), ["Inventory Management of a Fast-Fashion Retail Network"](https://pubsonline.informs.org/doi/10.1287/opre.1090.0698), *Operations Research* 58(2), 257-273 |
| Kidney paired donation | Bounded-cycle packing integer program | Abraham, Blum and Sandholm (2007), ["Clearing Algorithms for Barter Exchange Markets"](https://home.ttic.edu/~avrim/Papers/barter.pdf), *ACM EC*, 295-304 |
| Wholesale electricity markets | Security-constrained unit commitment and dispatch | [MISO's 2011 Edelman Award record](https://www.informs.org/News-Room/INFORMS-Releases/Awards-Releases/MISO-Wins-INFORMS-Edelman-Award) |
| Infrastructure vulnerability | Network interdiction | Wood (1993), ["Deterministic Network Interdiction"](https://doi.org/10.1016/0895-7177(93)90236-R), *Mathematical and Computer Modelling* 17(2), 1-18 |

## Software records

| Tool | Role | Primary documentation |
| --- | --- | --- |
| OR-Tools | Maximum-flow interface and integer-capacity contract | [Maximum flow](https://developers.google.com/optimization/flow/maxflow) |
| NetworkX | Minimum-cut and named preflow-push interfaces | [`minimum_cut`](https://networkx.org/documentation/latest/reference/algorithms/generated/networkx.algorithms.flow.minimum_cut.html) |
| SciPy with HiGHS | Linear-program interface used for closure, dispatch, relaxations and price selection | [`linprog`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html) |
| SciPy with HiGHS | Mixed-integer interface used for market clearing and for each unit's best self-schedule | [`milp`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html) |
| NumPy | Values, arcs, and sparse-matrix inputs | [NumPy documentation](https://numpy.org/doc/stable/) |
| pytest | Verification runner | [pytest documentation](https://docs.pytest.org/) |
| Ruff | Python lint check | [Ruff documentation](https://docs.astral.sh/ruff/) |

## Repositories assessed for this pass

| Repository | Outcome |
| --- | --- |
| [google/or-tools](https://github.com/google/or-tools) | Checked `SimpleMaxFlow` and its integer-capacity requirement. |
| [power-grid-lib/pglib-uc](https://github.com/power-grid-lib/pglib-uc) | Read the library description. The IEEE PES Task Force unit-commitment benchmark: JSON instances from CAISO, FERC and RTS-GMLC, and a reference MILP in `MODEL.pdf`. It is the unit-commitment analogue of MineLib. No instance is cleared here yet; see Decisions. |
| [grid-parity-exchange/Egret](https://github.com/grid-parity-exchange/Egret) | Read the package description. A BSD Python and Pyomo implementation of those unit-commitment formulations and of DCOPF, by the authors of the reference paper. Nothing is vendored. |
| [guofei9987/scikit-opt](https://github.com/guofei9987/scikit-opt) | Checked its heuristic algorithms and `.run()` interface. |
| [ebrahimpichka/awesome-optimization](https://github.com/ebrahimpichka/awesome-optimization) | Finding aid only. |
| [Thinklab-SJTU/awesome-ml4co](https://github.com/Thinklab-SJTU/awesome-ml4co) | Finding aid for the two machine-learning papers above. |
| [electricitymaps/electricitymaps-contrib](https://github.com/electricitymaps/electricitymaps-contrib) | Read the zone and exchange records. A zone key is `COUNTRY-REGION`; an exchange is keyed by its two zone keys in ascending order and carries `capacity: [min, max]` on the signed flow from the first to the second. `Net` under `ntc` is that record, and `ex5` uses `NO-NO1_NO-NO2` directly. Code AGPLv3; nothing is vendored. |
| [corneel27/day-ahead](https://github.com/corneel27/day-ahead) | Read. A price-taking mixed-integer program over batteries, boilers and EV charging, on python-mip. The same object as `_om`, on the demand side of the market this repository clears. |
| [JaccoR/hass-entso-e](https://github.com/JaccoR/hass-entso-e) and [oysteinjakobsen/fetch-day-ahead-price](https://github.com/oysteinjakobsen/fetch-day-ahead-price) | Read as the reference for what a published day-ahead price is: one bidding zone, hourly, EUR before currency conversion and VAT. Both read zonal prices, which is why `ntc` exists. Not adopted; see Decisions. |
| [corneel27/day-ahead-prediction](https://github.com/corneel27/day-ahead-prediction) and [piekarsky/Short-Term-Electricity-Price-Forecasting-at-the-Polish-Day-Ahead-Market](https://github.com/piekarsky/Short-Term-Electricity-Price-Forecasting-at-the-Polish-Day-Ahead-Market) | Read. Both fit the price rather than clear it: XGBoost on Dutch generation mix, $R^2$ 0.914; RNN, LSTM, GRU, MLP and Prophet on Polish data, best MAE 16.15 PLN/MWh. Reported for scale, not adopted; see Decisions. |

No commercial pit package or real deposit was used. Synthetic pits use a nine-block,
uniform 45-degree precedence pattern.
