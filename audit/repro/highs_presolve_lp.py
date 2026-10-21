"""HiGHS presolve declares a feasible LP infeasible.

The LP is the convex hull program of a two-unit, two-period unit commitment with output
ceilings 1e-6 above the cleared schedule (seed 36 of Electricity-Market-Model's random
family). Solved without presolve it is optimal at 817.1277349106...; with presolve HiGHS
reports it infeasible. The file seed36.npz holds c, A, b, Ae, be for
min c'x s.t. A x <= b, Ae x = be, x free.

Run: python highs_presolve_lp.py [path to seed36.npz, default beside this file]
"""
import sys
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import linprog

f = np.load(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("seed36.npz"))
print("scipy", scipy.__version__)
for pre in (True, False):
    r = linprog(f["c"], A_ub=f["A"], b_ub=f["b"], A_eq=f["Ae"], b_eq=f["be"],
                bounds=(None, None), method="highs", options={"presolve": pre})
    print(f"presolve={pre}: status {r.status}, {r.message}, fun {r.fun}")
    if r.status == 0:
        x = r.x
        print("  max row violation", max(float(np.max(f["A"] @ x - f["b"])),
                                          float(np.max(np.abs(f["Ae"] @ x - f["be"])))))
