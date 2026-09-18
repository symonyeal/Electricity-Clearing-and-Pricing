# Working contract

Read before changing anything. [README](README.md) states what the models are;
[Decisions](docs/DECISIONS.md) states why they are that way; [Validation](docs/VALIDATION.md)
states what has been checked. This file states the rules a change must not break.

Codex reads the same file through [AGENTS.md](AGENTS.md).

## Always on

| Rule | Reason |
| --- | --- |
| Report no solve outcome that was not read back from the result that produced it. | A requested tolerance is not a result. HiGHS stops at `mip_rel_gap = 1e-4` by default, so an unread `opt` is a claim about a default, not about the solve. |
| Build a bound from `mip_dual_bound`, never from an incumbent. | An incumbent can understate a subproblem optimum and carry a reported dual past the primal, which weak duality forbids. |
| Name a failed solve by the solver's status: infeasible, limit, unbounded, numerical. | Malformed data and a demand no commitment can serve both end in a failed solve. Only the second is an infeasibility. |
| Cite only what [Sources](docs/SOURCES.md) records, and add the entry in the change that uses it. | A formulation is validated by the paper it implements, not by the solver that ran it. |
| Add a dependency only after measurement. | SciPy and HiGHS solve every live model. No result here shows that a commercial solver or a modeling layer is required. |
| State what was measured and what was not. | "Not measured" is a finding. A projection from row counts is not a runtime. |

## The feasible set is written once

`_rw`, `_eq` and `_fx` in `models/uc_price.py` are the unit's rows, equalities and bounds.
Every route reaches them:

| Route | Path to the rows |
| --- | --- |
| `uc`, `rx` | `_sy` |
| `lmp`, `pay` | `_hold`, `_pl` |
| `en`, `hl` | `_cl`, `_pl` |
| `hc` | `_ar`, `_iv`, `_pl` |
| `_om` | direct |
| `models/joint.py`, and `models/stoch.py` through `joint._sy` | direct |

`models/pglib_uc.py` imports only `_px` and writes its own rows. That independence is the
test, not an oversight.

A second copy of those rows destroys the agreement checks, which are the evidence the
repository rests on. Change the rows in one place, or state why a route needs its own.

## Pinned results, and why they are not defects

| Observation | Status |
| --- | --- |
| `ex3`'s full p-cut hull is $422 while the FERC talk reports $146.33. | Both are reproducible under different restrictions. The cleared/off restriction gives $146.33, and the talk's later AIC34 binary cuts induce it here. Do not tune the unrestricted hull toward the restricted value. |
| `stoch.lmp` returns `cv` as `nan` and a `z` unequal to `cl`'s. | Correct. `lmp` prices a new expected-cost re-dispatch; [Joint](docs/JOINT.md) says so. |
| `market/bid.py` charges `tar` in settlement but the policy optimizes `kd + fee`. | Deliberate. `arb + spread - net` therefore misses by exactly the metered tariff when `tar > 0`. [Market interface](docs/MARKET.md) states the boundary; the repair is open work item 2. |
| The storage mode cut `c/C + d/D <= 1` is not the hull of the resource. | Correct as documented. The state-of-charge rows couple periods the cut treats separately. Do not upgrade the claim. |
| Reserve prices at zero in `pglib_uc` on most periods. | Correct. Reserve carries no cost of its own and prices only where ramping or start-up binds. |
| Two hulls disagree on one seeded market in 141. | Correct. Both are dual-optimal and pay the same; the data does not choose. The test asserts the difference. |

## Before a change is finished

```text
python -m pytest -q
python -m ruff check .
python -m pip check
```

A behavioural change states its effect in numbers. The analog-alignment change, for
instance, is recorded as +18.114167 on the committed fixture with the day it lands on, not
as "prices improved". Committed result bundles under `docs/results/` carry the revision
that produced them; a change that would move them says so rather than restating them.
