"""HiGHS presolve returns a MIP dual bound above a feasible point's objective.

One unit's self-schedule problem (seed 88 of Electricity-Market-Model's random family, unit
0, at a fixed price). An output ceiling lies 1e-6 above a lower limit implied by the ramp
rows. With presolve, HiGHS reports optimal with mip_dual_bound -1534.482060816755; a
feasible witness, also returned by HiGHS without presolve and checked here row by row,
has objective -1534.482371644303, about 3.1e-4 lower. A dual bound above a feasible
objective is invalid for a minimisation.

The file seed88.npz holds c, it, lb, ub, A, b, Ae, be and the witness.
Run: python highs_presolve_mip_bound.py [path to seed88.npz, default beside this file]
"""
import sys
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import Bounds, LinearConstraint, milp

f = np.load(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("seed88.npz"))
print("scipy", scipy.__version__)
w = f["witness"]
res = max(float(np.max(f["A"] @ w - f["b"])), float(np.max(np.abs(f["Ae"] @ w - f["be"]))),
          float(np.max(f["lb"] - w)), float(np.max(w - f["ub"])))
k = f["it"] > 0
print("witness objective", float(f["c"] @ w), "max violation", res,
      "integers integral", bool(np.all(np.abs(w[k] - np.rint(w[k])) < 1e-9)))
for pre in (True, False):
    r = milp(f["c"], integrality=f["it"], bounds=Bounds(f["lb"], f["ub"]),
             constraints=[LinearConstraint(f["A"], -np.inf, f["b"]),
                          LinearConstraint(f["Ae"], f["be"], f["be"])],
             options={"presolve": pre, "mip_rel_gap": 0.0})
    print(f"presolve={pre}: status {r.status}, fun {r.fun!r}, mip_dual_bound "
          f"{r.mip_dual_bound!r}, bound - witness {r.mip_dual_bound - float(f['c'] @ w):.3e}")
