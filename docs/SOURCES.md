# Sources

| Source | Implemented use |
| --- | --- |
| Gribik, Hogan and Pope (2007), [Market-Clearing Electricity Prices and Energy Uplift](http://www.lmpmarketdesign.com/papers/Gribik_Hogan_Pope_Price_Uplift_123107.pdf) | Convex-hull pricing and uplift |
| Liberopoulos and Andrianesis (2016), [Critical Review of Pricing Schemes in Markets with Non-Convex Costs](https://doi.org/10.1287/opre.2015.1451), Operations Research 64(1), 17-31 | Classification of price rules |
| Hua and Baldick (2017), [A Convex Primal Formulation for Convex Hull Pricing](https://arxiv.org/abs/1605.05002), IEEE TPWRS 32(5), 3814-3823 | Convex primal pricing; cases 1 and 2 |
| Chen, O'Neill and Whitman (2020), [A Unified Approach to Solve Convex Hull Pricing and Average Incremental Cost Pricing](https://www.ferc.gov/sites/default/files/2020-06/W2-1_Chen_et_al.pdf) | AIC and case 3; [Optimization Online version](https://optimization-online.org/2020/09/8004/) records the restricted-block result |
| Yu, Guan and Chen (2020), [An Extended Integral Unit Commitment Formulation and an Iterative Algorithm for Convex Hull Pricing](https://arxiv.org/abs/1910.12994) | Interval-graph hull `chp` |
| Knueven, Ostrowski and Watson (2020), [On Mixed-Integer Programming Formulations for the Unit Commitment Problem](https://doi.org/10.1287/ijoc.2019.0944) | Unit rows; [pglib formulation](https://github.com/power-grid-lib/pglib-uc/blob/master/MODEL.pdf) |
| Rajan and Takriti (2005), [Minimum Up/Down Polytopes of the Unit Commitment Problem with Start-Up Costs](https://www.semanticscholar.org/paper/b88642e36b414d5929fed48593d0ac46ae3e2070) | Minimum run/down inequalities |
| Stott, Jardim and Alsac (2009), [DC Power Flow Revisited](https://doi.org/10.1109/TPWRS.2009.2021235) | Lossless DC lines |
| Beck (2014), [Introduction to Nonlinear Optimization](https://doi.org/10.1137/1.9781611973655), chapter 12, Theorem 12.3 | Lagrangian dual and weak duality |
| Bertsimas and Tsitsiklis (1997), Introduction to Linear Optimization, sections 4.3 and 5.3 | Duality and subgradients |
| [electricitymaps directional exchange](https://github.com/electricitymaps/electricitymaps-contrib/blob/master/config/exchanges/NO-NO1_NO-NO2.yaml) | Case 5 transfer bounds; offers and demand are synthetic |
| [HiGHS](https://highs.dev/), [Rust binding](https://docs.rs/highs/2.4.0/highs/) | LP/MIP solves, equality duals and objective bounds |
