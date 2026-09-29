# Open issues

This is the single register of unresolved model scope, numerical, and verification work.

Everything that remains, in one place. Items 1–7 are modelling work; items 8–13 are what
the [audit](AUDIT.md) of the decomposition, settlement and risk studies left open.

## Modelling

1. **Calibrate `market/bid.py`** to one market's published tariff and qualification manual.
   The mechanism is implemented; the parameters are not anyone's.
2. **Price `tar` inside the policy** rather than after it: put it into `_bat(...).k`, give
   the report identity its own tariff component, and add a high-rate no-trade regression.
   [Market interface](MARKET.md) states the boundary this leaves. It is not bundled with
   item 1 because moving a cost into the objective changes which trades a policy takes, so
   it changes every result it touches and belongs with the calibration that gives the rate
   a number.
3. **A convex hull price for the joint feasible set.** The joint and stochastic clearings
   pin the integers, so the nonconvexity is left as make-whole. `models/settle.py` builds
   one resource's hull exactly for small horizons; a storage oracle for `models/dw.py` is
   the route to the joint hull, and is not implemented.
4. **A multi-stage scenario tree.** The stochastic clearing branches once.
5. **Ramping and reserve carried between scenarios**, and a reserve product in `uc_price`.
6. **Stabilise the generated master's duals.** With one seed column per unit every price is
   dual-optimal, and the first raw dual on one capped seed was $2.2\times10^{10}$/MWh.
7. **The Benders form of Knueven, Ostrowski, Castillo and Watson**, over a compact per-unit
   hull. It is named in [Decomposition](DW.md) and not measured.

## Numerics and verification

8. **A certificate free of solver tolerances.** The Lagrangian bound is exact only to
   HiGHS's feasibility tolerances, $10^{-9}$ in a bound route. It is measured against
   enumeration only on the seeded family, $T\le5$ and $G\le3$, at offer-cost scales
   $10^{-3}$ to $10^3$ ([Decomposition](DW.md#tolerances)); no larger market has an
   independent check of its oracle. A rigorous bound needs an exact per-unit oracle,
   evaluated with directed rounding; a branch-and-bound bound is not one.
9. **`hc` at 48 × 24, and bound-aware price selection.** `_px` writes each finite bound as
   a row: at 48 × 24, 908,650 rows against 139,230 variables, and a price-face problem of
   909,922 variables. The first LP had not finished after 120 s at a 1.21 GiB peak. Native
   bounds would enter the dual as multipliers $\alpha,\beta\ge0$: $+\alpha-\beta$ in
   stationarity and $l^\top\alpha-u^\top\beta$ in the objective. Success is a completed
   48 × 24 and 96 × 24 run with unchanged value, payment and certificate.
10. **The declared dependency floor.** `requirements.txt` admits SciPy 1.12.0, and CI had
    installed only the newest. The job pinned to Python 3.12, NumPy 1.26.0 and SciPy
    1.12.0 has not run; SciPy 1.12 has no CPython 3.14 wheel, so it cannot run here.
11. **HiGHS upstream reports.** The two presolve defects have extracted reproducers in
    `../emm-audit-scratch/repro`, outside the repository ([Audit](AUDIT.md)). No issue is
    filed. File both, then delete the scratch directory.
12. **Settlement prices away from the load.** Load-bus prices are bounded on the optimal
    face; prices at buses without load are not, since demand cannot fall below zero there,
    so tests on them test the payment rule. Complementary slackness is checked on radial
    networks only; no settlement case is meshed.
13. **Tables not re-run after the bound-route change.** [Decomposition](DW.md)'s size table
    and RTS-GMLC row date from 2026-09-24. The change costs nothing measurable on the
    seeded family; on the large markets it is unmeasured. The default `run_dw.py` exceeded
    600 s at the audit, and `run_face_scan.py`'s large-market section did not finish in
    45 s.
