# Validation

This page records the independent evidence supporting each formulation and market use case.

Validation is divided by formulation. Agreement between two calls to the same row builder
is not treated as an independent check.

| Component | Primary check | Independent check |
| --- | --- | --- |
| Unit commitment and prices | Published cases `ex1`–`ex3`; synthetic network cases | Joint commitment enumeration; trajectory and interval hulls |
| Hull formulation sizes | Deterministic `run_bench.py sizes` report | Variable-count and enumeration-ceiling tests |
| pglib-uc | Equations (1)–(24), assembled independently | Official RTS-GMLC relaxation objective |
| Storage | Sparse MIP | Signed-flow enumeration and analytical cases |
| NYISO replay | Chronological fixture runs | Settlement and energy reconstructed from exports |
| Joint clearing | Seeded markets and arithmetic cases | The same markets cleared by `uc_price` |
| Stochastic clearing | Seeded scenarios | The wait-and-see and mean-value bounds, from `joint` |
| Market interface | Curve arithmetic by hand | The baseline replay, which its defaults must reproduce |
| Generated master | A Lagrangian bound at every reported price | `hc` and `hl` on 208 routes; pglib-uc records against `hc`; oracle bounds against enumeration |
| Storage in the clearing | Settlement identity; congestion complementarity; load prices on the optimal face | The no-resource clearing of `joint`; the resource's exact hull |
| Risk-averse prices | KKT identities of the held CVaR program | `stoch.lmp`; CVaR's dual weights in closed form |

## Commands

Run from the repository root:

```text
python -m pytest -q
python -m ruff check .
python -m pip check
python run_bench.py sizes
python run_storage.py
python run_dw.py
python run_settle.py
python run_risk.py
git diff --check
```

The pglib-uc MIP test is marked `slow`. Tests pin the `opt` tag against a solve made to
return a positive gap, and pin that `qd` is built from the solver's bound rather than its
incumbent.

## Pricing

The small unit-commitment model is checked against three published cases. The integer
program and joint enumeration agree on ten seeded markets. The compact interval hull and
the schedule hull agree on every feasible instance among seeds 0 through 140: relative
objective tolerance $10^{-9}$ and price tolerance $10^{-4}$/MWh. A capped case also checks
hull value and demand payment when the price coordinates are not uniquely determined.

`python run_bench.py sizes` reproduces the decomposition-size table from the seed-7
synthetic markets. It reports graph arcs and actual LP variables separately for `hc`, and
feasible commitment trajectories and actual LP variables for `hl`. Tests pin the counting
rule, the 100,000-variable `hl` boundary, and the loss of full-hull dual feasibility when a
restricted trajectory set happens to retain the same primal objective.

DC and directional-NTC cases check uncongested reduction, congestion, loop flow, exchange
direction, and malformed networks. The full pglib-uc formulation reproduces the official
RTS-GMLC relaxation objective to relative tolerance $10^{-9}$.

## Storage

The MIP and signed-flow formulation are compared on 24 seeded cases with chosen and fixed
positions. Twelve additional seeded cases impose a binding deviation band. Tests cover
unequal probabilities, shared and branching information nodes, three risk weights,
full-delivery feasibility, fixed-position infeasibility, and `cap=None` regression values.

Analytical cases check efficiency loss, negative prices, terminal energy, two-settlement
accounting, scenario-dependent day-ahead prices, nonanticipativity, and discrete CVaR.
Failure tests cover invalid inputs, infeasibility, enumeration limits, and solver status.
A test that accepts a missing result because the program was infeasible reads the solver's
diagnosis, so a limit or a numerical failure is not counted as an infeasibility.

Discrete fields are checked before they are converted. A fractional minimum run time, a
fractional bus or line endpoint, a nan ramp, a fractional or nan offer-curve step count and
a nan qualification threshold are each refused by name rather than truncated, silently
disabled, or passed to a later routine that fails somewhere else.

## Joint and stochastic clearing

With no resource the joint program reproduces `uc_price` on seeded markets: cost to
relative $10^{-9}$, dispatch to $10^{-6}$ MW, locational price to $10^{-4}$/MWh. A lossless
20 MW battery moving energy from a 20/MWh period to an 80/MWh period lowers the clearing by
exactly 1,200. A 40 MWh battery behind a 5 MW line delivers 20 MWh rather than 40, and the
clearing rises from 2,300 to 2,700. Charge and discharge never run together, and stored
energy follows its recursion to $10^{-9}$ MWh.

The stochastic clearing reproduces the joint clearing on one scenario of probability one,
cost and price. On seeded scenarios it satisfies $\text{WS}\le\text{SP}\le\text{EEV}$,
both bounds computed with `models/joint.py`; on the instance in the tests the expected value
of perfect information is 900 and the value of the stochastic solution is 2,680. The
reported CVaR is checked against an independently weighted tail of the scenario costs.

## Generated master

`dw.cg` is checked against both direct hulls, which write the same hull in full. On the
five published cases and on all 104 feasible markets of seeds 0 through 140, uncapped and
capped, its value lies in the bracket $[L(\hat\lambda),z]$ it reports, and the convex hull
price and uplift agree with `hc`; where the AIC face is wide, value, payment and dual
optimality are asserted instead. The oracle's bound is checked against enumeration of
every trajectory at every call, at four offer-cost scales. [Decomposition](DW.md#tolerances)
tabulates each tolerance and what it measured. The tests run every third seed;
`run_dw.py` runs all. A seed excluded from the family must be a proved infeasibility; a
numerical failure is raised, and joint enumeration confirms all 37 exclusions. Three
stopping tests are
asserted to fail where they should. A master whose value equals the hull's prices at 8
where the hull prices at 12. A pricing step restricted to two of a unit's schedules
certifies its own price, 146.33, which the exact oracle refutes by 1,137.5. A seed
schedule outside its unit is refused.

`dw.cgp` shares no row builder with `cg`. Given ex1 and ex2 written as pglib records, it
reaches `hc`'s values and prices. On pglib's two-unit case with reserve, its value lies
between pglib's LP relaxation and its clearing, and meets the relaxation; with wind added it
still does, which fails if the renewable term is left out of $L$. A market of renewables
alone clears at value and price zero. On RTS-GMLC it lies in
[2,501,406.3307, 2,501,406.3332], between the relaxation and the 1% incumbent.

## Storage in the clearing

`models/settle.py` reads joint's rows and is checked by identities that hold at any price.
The settlement identity, load payment less cost equals units' profit plus storage profit
plus rent, holds to $10^{-12}$ on all seven cases under X, H and R. The rent from line
flows, congestion complementarity on every line and period, and each load-bus price's place
on the optimal face are checked as [Storage in the clearing](SETTLE.md) derives them. With
the resource removed, each case clears and prices exactly as
`joint` does. The three descriptions nest, $z_X\ge z_H\ge z_R$, on every case, with equality
in s6 and $6{,}000=6{,}000>2{,}270$ in s7. The storage hull is Balas' union of the $2^T$
mode-pattern polytopes built from joint's own rows.

Two theorems are tested rather than assumed. At the held-integer price, the resource's
profit equals its best over its held-mode polytope, on every case. On six seeded
resources, the cut's best profit equals the binary model's at prices above
$-k(1+\eta_c\eta_d)/(1-\eta_c\eta_d)$, and exceeds it below that threshold with a full store.
Each case's own numbers are arithmetic in its docstring and are asserted to a tenth of a
cent.

## Risk-averse prices

`stoch.cvd` reads the duals of the risk-averse program with its integers held. On the five
examples: its value equals the clearing's; $\sum\mu=w$ and $0\le\mu\le wp/(1-\alpha)$;
$\mu/w$ attains CVaR, checked against the maximiser computed in closed form from the
scenario costs, and equals it where the costs are distinct; and $y=\omega\lambda$ with
$\lambda$ the price `stoch.lmp` reads from the expected-cost re-dispatch, to
$10^{-4}$/MWh. That price is unique on every example: a unit runs strictly inside its
range in each scenario and period, and complementary slackness fixes the price at its
cost. A sixth example with two equal scenarios, where the costs determine no single
multiplier, passes the same checks. The chains $\mathrm{WS}\le\mathrm{SP}\le\mathrm{EEV}$
hold under the expectation and under $\rho$. The one scenario with $\omega=0$ is asserted
to carry no price, and the program is asserted not to determine its cost.

## Market interface

Offer curves, the metered charge and the qualification screens are checked against the
slices by hand. The load-bearing check is that the defaults change nothing: `bk = 0`,
`tar = 0`, `qmin = 0` and `qdur = 0` reproduce the baseline replay's positions and flows
exactly.

`tar` is tested as what it is: a charge applied after the schedule was chosen. The tests
assert that it raises the charge line and never raises settlement. They do not assert that
the policy responds to it, because it does not; [Market interface](MARKET.md) states that
boundary and [Open issues](ISSUES.md) carries the repair.

## Historical replay

Committed NYISO fixtures cover ordinary and daylight-saving days. Tests check timestamp
conversion, subhourly weighting, missing-data treatment, information cutoffs, fallback
rules, settlement, energy conservation, figures, exports, and three-policy report
generation. They run without network access.

Analog alignment is tested on the convention and not on array length alone. A 24-hour
analog put on the 25-hour autumn day serves local `01` twice and leaves every later hour on
its own clock hour; on the 23-hour spring day it drops local `02`, which that day does not
settle; and a 25-hour analog put on an ordinary day drops the second pass of `01`. The
tests read the local labels from the zone, so they would fail if alignment reverted to
elapsed position.

The change is not cosmetic and its size is measured rather than asserted. Replaying
`config/ci.toml` at $\rho=0.5$ over 2025-11-01 to 2025-11-03 under both rules, with the
25-hour 2025-11-02 in the middle:

| Policy | Net, elapsed position | Net, local clock | Change |
| --- | ---: | ---: | ---: |
| `neutral` | 139.872877 | 157.987043 | +18.114167 |
| `cvar`, $w=0.5$ | 113.872361 | 131.986528 | +18.114167 |
| `det` | 143.271929 | 161.386096 | +18.114167 |

Every cent of that lands on 2025-11-02. The two ordinary days either side are identical to
the bit under both rules, which is the check that the two alignments are the same map
between days of equal length. Under the old rule the appended hour repeated one real-time
quote twelve times, so it carried no spread to trade; under the new one it carries the
prices local 01 actually settled at.

The persistence coefficient sets how large that is and not where it lands: the file's own
$\rho=0$ moves the same three policies by +0.842533 and the $\rho=0.75$ that
`run_market.py smoke` imposes by +10.978352, each time the whole of it on 2025-11-02 and
each time identical across the three. A figure from this fixture is reported with the
coefficient that produced it.

The committed 2025 result bundles are evidence from the recorded revisions, not a result
of the local test command. Their metrics, daily rows, configurations, and coverage report
remain under [`docs/results/`](results/README.md). Interval exports and source archives are
not committed; a fresh checkout must reacquire the NYISO files to repeat the full annual
reconciliation.

The delivery band is replayed over the same year by `run_delivery.py`; its runs are checked
against their own interval exports and recorded in
[`docs/results/delivery/`](results/delivery/README.md).

The former benchmark tables and the completed local-code review are preserved in the
[dated archive](../_archive/20260916-focus-reset/README.md).
