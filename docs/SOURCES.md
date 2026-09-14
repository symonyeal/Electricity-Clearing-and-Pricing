# Sources

Publication details and links were checked on 2026-09-14. The note beside each
source says what it supports; a title was not added merely because it appeared
in a reading list.

## Current pit model

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
| SciPy with HiGHS | Linear-program interface used for closure | [`linprog`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html) |
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
