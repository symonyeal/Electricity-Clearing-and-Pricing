# Sources

Publication details and links were checked on 2026-09-15. The note beside each
source says what it supports; a title was not added merely because it appeared
in a reading list.

## Ultimate pit model

| Source | Use in this repository |
| --- | --- |
| Lerchs, H. and Grossmann, I. F. (1965). ["Optimum Design of Open-Pit Mines"](https://onetunnel.org/documents/optimum-design-of-open-pit-mines). *CIM Bulletin* 58(633), 47-54. | Original ultimate-pit problem. The often-repeated pages 17-24 belong to a later *Transactions of the CIM* reprint, not the 1965 Bulletin article. |
| Picard, J.-C. (1976). ["Maximal Closure of a Graph and Applications to Combinatorial Problems"](https://pubsonline.informs.org/doi/10.1287/mnsc.22.11.1268). *Management Science* 22(11), 1268-1272. | Exact maximum-closure to minimum-cut reduction implemented by `mc` and `mc_nx`. |
| Hochbaum, D. S. and Chen, A. (2000). ["Performance Analysis and Best Implementations of Old and New Algorithms for the Open-Pit Mining Problem"](https://pubsonline.informs.org/doi/abs/10.1287/opre.48.6.894.12392). *Operations Research* 48(6), 894-914. | Comparison of algorithms for the open-pit problem. |
| Hochbaum, D. S. (2008). ["The Pseudoflow Algorithm: A New Algorithm for the Maximum-Flow Problem"](https://pubsonline.informs.org/doi/10.1287/opre.1080.0524). *Operations Research* 56(4), 992-1009. | Background on a specialized compiled maximum-flow method. OR-Tools is not claimed to use this algorithm. |

## Unit commitment and electricity prices

| Source | Use in this repository |
| --- | --- |
| Chen, Y., O'Neill, R. P. and Whitman, P. (2020). ["A Unified Approach to Solve Convex Hull Pricing and Average Incremental Cost Pricing"](https://www.ferc.gov/sites/default/files/2020-06/W2-1_Chen_et_al.pdf). FERC Technical Conference on Increasing Real-Time and Day-Ahead Market Efficiency through Improved Software, 23-25 June 2020. | The targeted talk, read in full. It supplies the two-stage design used here, the average-incremental-cost output restriction, the make-whole and lost-opportunity definitions, and the two-generator case reproduced as `ex3`. Its period-three price of $146.33 is the one published figure this repository does not reproduce; see Decisions. |
| Chen, Y., O'Neill, R. P. and Whitman, P. (2020). ["A Unified Approach to Solve Convex Hull Pricing and Average Incremental Cost Pricing"](https://optimization-online.org/2020/09/8004/). Optimization Online. | The talk's companion paper, read in full. Proposition 3 applies the output restriction to commitment blocks that lose money under LMP and proves that those blocks' make-whole tends to zero with epsilon, while their added uplift is order epsilon. It does not cover losses induced on unrestricted blocks; that boundary is used to interpret the epsilon sweep. No journal version was found on a 2026-09-15 search, so this is cited as a preprint. |
| Hua, B. and Baldick, R. (2017). ["A Convex Primal Formulation for Convex Hull Pricing"](https://arxiv.org/abs/1605.05002). *IEEE Transactions on Power Systems* 32(5), 3814-3823. | Read in full, from the author's arXiv version of 16 June 2020. Supplies the primal convex hull idea, and Examples 1 and 2, whose Tables 1-5 are reproduced exactly by `ex1` and `ex2`. |
| Gribik, P., Hogan, W. and Pope, S. (2007). ["Market-Clearing Electricity Prices and Energy Uplift"](https://www.semanticscholar.org/paper/69578a6c6c9fcfdc686c0e0633fa360ac4f3fa4a). Harvard University working paper. | The origin of convex hull pricing, credited as such by both sources above. Not opened here: the definitions implemented came from the two sources above, which restate them. |
| Balas, E. (1998). ["Disjunctive Programming: Properties of the Convex Hull of Feasible Points"](https://doi.org/10.1016/S0166-218X(98)00136-X). *Discrete Applied Mathematics* 89(1-3). | The standard reference for the union-of-polyhedra form `hl` uses. Not opened; the construction is textbook. Indexes give the page range as both 3-44 and 1-44 because the invited paper carries a two-page foreword. |
| Rajan, D. and Takriti, S. (2005). ["Minimum Up/Down Polytopes of the Unit Commitment Problem with Start-Up Costs"](https://www.semanticscholar.org/paper/b88642e36b414d5929fed48593d0ac46ae3e2070). IBM Research Report RC23628. | The minimum run and minimum down inequalities used in `_rw`. Not opened; the report is no longer served by IBM, so the link is a catalogue record. |
| O'Neill, R. P., Castillo, A., Eldridge, B. and Hytowitz, R. B. (2017). ["Dual Pricing Algorithm in ISO Markets"](https://ieeexplore.ieee.org/document/7742365). *IEEE Transactions on Power Systems* 32(4), 3301-3310. | The talk's source for average incremental cost pricing. Not opened; recorded because the rule implemented here is attributed to it. |
| Yu, Y., Guan, Y. and Chen, Y. (2020). ["An Extended Integral Unit Commitment Formulation and an Iterative Algorithm for Convex Hull Pricing"](https://arxiv.org/abs/1906.07862). *IEEE Transactions on Power Systems*. | Read in full. Its result is that one unit's convex hull, with ramping, minimum run times and start-up costs all present, has a compact description whose linear program is integral, proved through a dynamic-programming argument. `hc` implements that as an interval graph. The paper also states plainly that Hua and Baldick's primal form only approximates the hull once ramping is present. |
| Martin, R. K., Rardin, R. L. and Campbell, B. A. (1990). ["Polyhedral Characterization of Discrete Dynamic Programming"](https://doi.org/10.1287/opre.38.1.127). *Operations Research* 38(1), 127-138. | The general reason `hc` is exact: a problem solved by a recursion over an acyclic graph has a polyhedral description built from that graph, and the flow polytope is integral. Not opened; cited as the general result behind the specific one above. |
| Stott, B., Jardim, J. and Alsac, O. (2009). ["DC Power Flow Revisited"](https://doi.org/10.1109/TPWRS.2009.2021235). *IEEE Transactions on Power Systems* 24(3), 1290-1300. | The direct-current flow approximation `_nw` uses, and what it does and does not capture. Not opened; cited for the standard method and its known limits. |

### Data used for the published cases

No file is committed for these; the inputs are small enough to live in `ex1`, `ex2` and
`ex3` in `models/uc_price.py`, each taken from the table named below.

| Case | Taken from | Anything the source leaves unstated |
| --- | --- | --- |
| `ex1` | Hua and Baldick, Table 1 | Nothing. One period, so no ramp applies. |
| `ex2` | Hua and Baldick, Table 3 | Start-up and shut-down ramps are not given. They are set equal to each unit's normal ramp, which is what makes the paper's own statement true, that ramping forces unit 2 to commit at t = 2 rather than start at t = 3. Any larger start-up ramp contradicts the paper's text. |
| `ex3` | The FERC talk, slide 13 | Nothing. Limits, costs and all three ramp rates are tabulated there. |
| `ex4` | Not from any source | The symmetric three-bus loop is a teaching case, not a published result. It is here because its answer is arithmetic: with equal reactances the direct line carries two thirds of the injection, so every number in it can be checked without the model. |

## Flow and integer theory

| Source | Use in this repository |
| --- | --- |
| Ford, L. R. and Fulkerson, D. R. (1956). ["Maximal Flow Through a Network"](https://www.cambridge.org/core/journals/canadian-journal-of-mathematics/article/maximal-flow-through-anetwork/5D6E55D3B06C4F7B1043BC1D82D40764). *Canadian Journal of Mathematics* 8, 399-404. | Maximum-flow/minimum-cut theorem. |
| Ahuja, R. K., Magnanti, T. L. and Orlin, J. B. (1993). [*Network Flows: Theory, Algorithms, and Applications*](https://www.pearson.com/en-us/subject-catalog/p/Ahuja-Network-Flows-Theory-Algorithms-and-Applications/P200000003456/9780136175490). Prentice Hall. | General network-flow formulations and algorithms. |
| Goldberg, A. V. and Tarjan, R. E. (1988). ["A New Approach to the Maximum-Flow Problem"](https://dl.acm.org/doi/10.1145/48014.61051). *Journal of the ACM* 35(4), 921-940. | Push-relabel maximum flow. NetworkX is asked explicitly to use its preflow-push implementation. |
| Hoffman, A. J. and Kruskal, J. B. (1956). ["Integral Boundary Points of Convex Polyhedra"](https://www.cs.umd.edu/~gasarch/BLOGPAPERS/kruskalhoffman.pdf). In *Linear Inequalities and Related Systems*, Annals of Mathematics Studies 38, 223-246. | Total unimodularity behind the whole-valued closure relaxation. |
| Schrijver, A. (1986). [*Theory of Linear and Integer Programming*](https://www.wiley.com/en-us/Theory+of+Linear+and+Integer+Programming-p-9780471982326). Wiley. | Network matrices and total unimodularity. The linked paperback is later; 1986 is the original publication year. |
| Nemhauser, G. L. and Wolsey, L. A. (1988). [*Integer and Combinatorial Optimization*](https://onlinelibrary.wiley.com/doi/book/10.1002/9781118627372). Wiley. | Integer-programming foundation for the later model path. |
| Wolsey, L. A. (2020). [*Integer Programming*, second edition](https://onlinelibrary.wiley.com/doi/10.1002/9781119606475.oth1). Wiley. | Strong formulations and variable-specific upper bounds for fixed-charge models. |
| Holzhauser, M., Krumke, S. O. and Thielen, C. (2016). ["Budget-Constrained Minimum Cost Flows"](https://link.springer.com/article/10.1007/s10878-015-9865-y). *Journal of Combinatorial Optimization* 31(4), 1720-1745. | The complexity change caused by a budget row when flows must remain integral. It prevents the false claim that every continuous flow with one extra row is automatically a mixed-integer problem. |
| Gasse, M., Chetelat, D., Ferroni, N., Charlin, L. and Lodi, A. (2019). ["Exact Combinatorial Optimization with Graph Convolutional Neural Networks"](https://papers.nips.cc/paper/2019/hash/d14c2267d848abeb81fd590f371d39bd-Abstract.html). *NeurIPS 32*. | Concrete learning-to-branch method for a future integer model. |
| Bengio, Y., Lodi, A. and Prouvost, A. (2021). ["Machine Learning for Combinatorial Optimization: a Methodological Tour d'Horizon"](https://doi.org/10.1016/j.ejor.2020.07.063). *European Journal of Operational Research* 290(2), 405-421. | Limits and roles of machine learning around exact combinatorial optimization. |

## MineLib benchmark

MineLib is the outside authority for the committed test case: Espinoza, D.,
Goycoolea, M., Moreno, E. and Newman, A. (2013).
["MineLib: a Library of Open Pit Mining Problems"](https://link.springer.com/article/10.1007/s10479-012-1258-3).
*Annals of Operations Research* 206(1), 93-114.

The [Newman1 record](https://minelib.org/v1/newman1.xhtml) documents the
instance, and MineLib's [results table](https://minelib.org/v1/Results.xhtml)
gives the rounded ultimate-pit value. These exact official downloads are kept
locally so the test does not depend on the network:

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

These papers show where the later model classes have been used. They are not
evidence for the current synthetic mine economics.

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
| [google/or-tools](https://github.com/google/or-tools) | Read for the `SimpleMaxFlow` Python interface and integer-capacity requirement. |
| [guofei9987/scikit-opt](https://github.com/guofei9987/scikit-opt) | Reviewed its heuristic algorithms and common `.run()` interface. |
| [ebrahimpichka/awesome-optimization](https://github.com/ebrahimpichka/awesome-optimization) | Used only as a finding aid. No unread title was copied into this file. |
| [Thinklab-SJTU/awesome-ml4co](https://github.com/Thinklab-SJTU/awesome-ml4co) | Led to the two machine-learning papers above. |

No commercial pit package or real deposit was used. The synthetic geometry is
the simple nine-block pattern for a uniform 45-degree wall; it is not presented
as a site design.
