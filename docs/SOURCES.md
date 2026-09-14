# Sources

Everything read or cited while building this project, with what each one was
actually used for. Web addresses were checked on 2026-09-14.

## The model implemented here

| Source | Used for |
| --- | --- |
| Lerchs, H. and Grossmann, I. F. (1965). "Optimum Design of Open-Pit Mines." *CIM Bulletin* 58, 17-24. | The original statement of the ultimate pit limit problem. Published by the Canadian Institute of Mining. |
| Picard, J.-C. (1976). "Maximal Closure of a Graph and Applications to Combinatorial Problems." *Management Science* 22(11), 1268-1272. | The reduction this code implements: maximum closure is a minimum cut. This is the paper `mc` follows. |
| Hochbaum, D. S. and Chen, A. (2000). "Performance Analysis and Best Implementations of Old and New Algorithms for the Open-Pit Mining Problem." *Operations Research* 48(6), 894-914. | Why the flow formulation beats the original graph-theoretic procedure in practice. |
| Hochbaum, D. S. (2008). "The Pseudoflow Algorithm: A New Algorithm for the Maximum-Flow Problem." *Operations Research* 56(4), 992-1009. | The algorithm commercial pit software uses. Explains why a compiled solver reverses the timing shown in the README. |

## The general theory

| Source | Used for |
| --- | --- |
| Ahuja, R. K., Magnanti, T. L. and Orlin, J. B. (1993). *Network Flows: Theory, Algorithms, and Applications.* Prentice Hall. | The standard reference. Closure, minimum cut, and the sequence of models listed in DECISIONS.md. |
| Ford, L. R. and Fulkerson, D. R. (1956). "Maximal Flow Through a Network." *Canadian Journal of Mathematics* 8, 399-404. | Maximum flow equals minimum cut, the theorem the whole reduction rests on. |
| Goldberg, A. V. and Tarjan, R. E. (1988). "A New Approach to the Maximum-Flow Problem." *Journal of the ACM* 35(4), 921-940. | Push-relabel, which is what NetworkX runs underneath `nx.minimum_cut`. |
| Hoffman, A. J. and Kruskal, J. B. (1956). "Integral Boundary Points of Convex Polyhedra." In *Linear Inequalities and Related Systems*, Princeton University Press, 223-246. | Total unimodularity. Why the linear program returns whole blocks with no branching, which the tests assert directly. |
| Schrijver, A. (1998). *Theory of Linear and Integer Programming.* Wiley. | Reference for total unimodularity and network matrices. |
| Nemhauser, G. L. and Wolsey, L. A. (1988). *Integer and Combinatorial Optimization.* Wiley. | Standard integer programming reference. |
| Wolsey, L. A. (2020). *Integer Programming*, 2nd edition. Wiley. | Formulation strength, and why a fixed-charge model needs variable upper bounds rather than a plain big-M. |

## Public benchmark instances

Real instances with known values, so an implementation can be scored rather than
described.

| Library | Covers | Where |
| --- | --- | --- |
| **MineLib** — Espinoza, D., Goycoolea, M., Moreno, E. and Newman, A. (2013). "MineLib: a library of open pit mining problems." *Annals of Operations Research* 206(1), 93-114. | Ultimate pit limit and two production scheduling variants. The direct benchmark for the model in this repository. | [Springer](https://link.springer.com/article/10.1007/s10479-012-1258-3) |
| MIPLIB 2017 | The standard mixed-integer benchmark set, with status and best known bounds | [miplib.zib.de](https://miplib.zib.de/) |
| OR-Library (Beasley) | Set covering, p-median, facility location, assignment, bin packing | [brunel.ac.uk](http://people.brunel.ac.uk/~mastjjb/jeb/info.html) |
| SNDlib | Survivable network design, multicommodity flow | [sndlib.zib.de](http://sndlib.zib.de/) |
| CVRPLIB | Vehicle routing, with and without time windows | [vrp.galgos.inf.puc-rio.br](http://vrp.galgos.inf.puc-rio.br/) |
| PSPLIB | Resource-constrained project scheduling | [om-db.wi.tum.de](https://www.om-db.wi.tum.de/psplib/) |
| DIMACS Implementation Challenges | Maximum flow, matching | [dimacs.rutgers.edu](http://dimacs.rutgers.edu/programs/challenge/) |

## Deployed applications surveyed

Read while choosing what to build. Each is a documented production system, not a
textbook exercise.

| Application | Model class | Source |
| --- | --- | --- |
| Delta Air Lines fleet assignment, "Coldstart" | Multicommodity flow on a time-space network | Subramanian et al., *Interfaces*; Edelman Award 1993 |
| Airline crew pairing and rostering | Set partitioning with column generation | Barnhart, C., Johnson, E. L., Nemhauser, G. L., Savelsbergh, M. W. P. and Vance, P. H. (1998). "Branch-and-Price: Column Generation for Solving Huge Integer Programs." *Operations Research* 46(3), 316-329. |
| Netherlands Railways national timetable | Mixed integer programming with constraint programming | Abbink et al., "The New Dutch Timetable: The OR Revolution"; Edelman Award 2008 |
| CSX locomotive scheduling | Multicommodity flow with integer side constraints | Ahuja, R. K., Liu, J., Orlin, J. B., Sharma, D. and Shughart, L. A. (2005). "Solving Real-Life Locomotive-Scheduling Problems." *Transportation Science* 39(4), 503-517. |
| Procter and Gamble North American supply chain | Capacitated facility location | Camm, J. D. et al. (1997). "Blending OR/MS, Judgment, and GIS: Restructuring the Procter and Gamble Supply Chain." *Interfaces* 27(1), 128-142. |
| Zara store replenishment | Integer allocation over a retail network | Caro, F. and Gallien, J. (2010). "Inventory Management of a Fast-Fashion Retail Network." *Operations Research* 58(2), 257-273. |
| Kidney paired donation | Cycle and chain integer programming | Abraham, D. J., Blum, A. and Sandholm, T. (2007). "Clearing Algorithms for Barter Exchange Markets." *ACM Conference on Electronic Commerce*. |
| Wholesale electricity markets | Security-constrained unit commitment | MISO; Edelman Award 2011 |
| Infrastructure vulnerability analysis | Network interdiction, solved as one mixed-integer program by duality | Wood, R. K. (1993). "Deterministic Network Interdiction." *Mathematical and Computer Modelling* 17(2), 1-18. |

The award record is at
[Franz Edelman past winners](https://www.informs.org/Recognizing-Excellence/INFORMS-Prizes/Franz-Edelman-Award/Franz-Edelman-Award-Past-Winners).

## Canadian public data checked

Reviewed while scoping a model built on real rather than synthetic data. None of
it is used by the current code. All were confirmed live on 2026-09-14.

| Dataset | Holds | Address |
| --- | --- | --- |
| CAF Regular Force Members by Rank | Headcount at every rank, 1997-2022 | [open.canada.ca](https://open.canada.ca/data/en/dataset/460aa2e0-5a37-47cf-a858-98b4327d29de) |
| CAF Regular Force Attrition | Attrition rate, 1998-2025 | [open.canada.ca](https://open.canada.ca/data/en/dataset/c48a7ca3-8d53-470b-90c9-87decc3801c1) |
| CAF Regular Force Intake | Recruitment inflow, 1997-2025 | [open.canada.ca](https://open.canada.ca/data/en/dataset/80c75c39-80fe-4fff-8290-49e2b66e07e6) |
| CAF Regular Force Outflow | Releases, 1997-2025 | [open.canada.ca](https://open.canada.ca/data/en/dataset/0e13d730-ba30-4500-a0d9-6437c4fcd148) |
| CAF Regular Force Promotions by Rank | Realised promotion counts, 1998-2022 | [open.canada.ca](https://open.canada.ca/data/en/dataset/71124206-d0d1-41c1-ac97-fb72e1ee5b93) |
| Promotable CAF Regular Force Members by Rank | The eligible pool, 1997-2025 | [open.canada.ca](https://open.canada.ca/data/en/dataset/195cca4c-882f-49cd-bae7-1d3cf99c80bd) |
| Proactive Publication - Contracts | Every federal contract over $10,000: vendor, value, commodity, dates | [open.canada.ca](https://open.canada.ca/data/en/dataset/d8f85d91-7dec-4fd1-8055-483b77225d8b) |
| CanadaBuys tender and award notices | Solicitations and awards | [canadabuys.canada.ca](https://canadabuys.canada.ca/en/procurement-and-contracting-data) |
| Directory of Federal Real Property | Every federal property with location and custodian | [open.canada.ca](https://open.canada.ca/data/en/dataset/08013e71-101a-457c-af76-c7b13a08ff64) |
| Canadian airports with air navigation services | Aerodrome coordinates | [open.canada.ca](https://open.canada.ca/data/en/dataset/3a1eb6ef-6054-4f9d-b1f6-c30322cd7abf) |
| Canadian Ice Service ice charts | Weekly ice concentration polygons, 2006 onward | [open.canada.ca](https://open.canada.ca/data/en/dataset/c80b950d-0a0a-44ed-87cc-53f69354750b) and [NSIDC](https://nsidc.org/data/g02171/versions/1) |
| Defence Capabilities Blueprint | 136 major defence projects with funding ranges and timelines. No bulk download; pages must be read individually. | [apps.forces.gc.ca](https://apps.forces.gc.ca/en/defence-capabilities-blueprint/index.asp) |

## Software

| Tool | Used for | Source |
| --- | --- | --- |
| NetworkX | `nx.minimum_cut`, the production solve | networkx.org |
| SciPy `linprog` with HiGHS | The independent linear programming check | Huangfu, Q. and Hall, J. A. J. (2018). "Parallelizing the dual revised simplex method." *Mathematical Programming Computation* 10, 119-142. |
| NumPy | Block model arrays | numpy.org |

## What was not used

Listed so a later reader does not go looking for an influence that is not there.
No commercial pit software was consulted, so the block values and the slope
pattern follow the published formulation rather than any vendor's conventions.
No real deposit data was used. The slope pattern is the simple nine-block cone
for a 45 degree wall; real models vary the angle by direction and by rock type.
