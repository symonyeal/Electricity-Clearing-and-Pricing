# The pglib-uc reference unit commitment, built from its own rows.
#
# Equation numbers are the ones in pglib-uc MODEL.pdf and uc_model.py, the reference
# implementation the IEEE PES Task Force publishes with the library. This is the benchmark
# formulation, not the one models/uc_price.py prices: output is carried above the minimum,
# production cost is a convex piecewise curve in lambda form, start-up cost depends on how
# long the unit was off, and a reserve requirement sits beside the energy balance. Nothing
# here shares a row builder with uc_price, which is the point: it is an independent route
# over an externally curated instance.
#
# LEGEND
#   d            : one parsed instance      T,G,W : periods, thermal units, renewables
#   th,re        : the thermal and renewable records, in a fixed order
#   S,L          : start-up categories and piecewise points of one unit
#   cg,pg,rg     : production cost, output above minimum, reserve  (1),(2),(3)
#   ug,vg,wg     : on, start, stop                                  (6),(12)
#   dg           : which start-up category a start falls in         (15),(16)
#   lg           : convex weights on the piecewise points           (21),(22),(23)
#   pw           : renewable output                                 (24)
#   o            : first column of each variable block
#   od,ol        : first column of unit i's dg and lg blocks
#   pmin,pmax    : power_output_minimum and power_output_maximum
#   RU,RD,SU,SD  : ramp up, ramp down, start-up ramp, shut-down ramp
#   UT,DT        : minimum run and minimum down periods
#   u0,p0,td0,tu0: initial on/off, initial output, periods down, periods up
#   A,b          : inequality rows and right side  Ae,be : equality rows and right side
#   ri,ci,va     : sparse row, column and value lists   ei,ec,ev : the same for equalities
#   c,lb,ub,it   : objective, bounds and integrality
#   m,e,n        : inequality, equality and column counters
#   i,t,s,l,k    : unit, period, category, piece and scratch indices
#   res,gap      : solver result and the relative gap it was asked for
#   Run          : cost, status and gap of one clearing

import json
from typing import NamedTuple

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csc_array

TH = ("must_run", "power_output_minimum", "power_output_maximum", "ramp_up_limit",
      "ramp_down_limit", "ramp_startup_limit", "ramp_shutdown_limit", "time_up_minimum",
      "time_down_minimum", "power_output_t0", "unit_on_t0", "time_down_t0", "time_up_t0",
      "startup", "piecewise_production", "name")
RE = ("power_output_minimum", "power_output_maximum", "name")


class Run(NamedTuple):
    """Cost, solver status and the relative gap the clearing was asked to reach."""

    z: float
    st: str
    gap: float


def ld(p):
    """Read one pglib-uc instance, rejecting any field this model does not represent.

    Silence about an unread field is the failure this guards: a loader that keeps the first
    piecewise point and the first start-up category still solves, and still reports a number
    that is not the benchmark's.
    """
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    k = set(d) - {"time_periods", "demand", "reserves", "thermal_generators",
                  "renewable_generators"}
    if k:
        raise ValueError(f"this instance carries fields the model does not represent: {sorted(k)}")
    T = int(d["time_periods"])
    th = [dict(v, name=g) for g, v in sorted(d["thermal_generators"].items())]
    re = [dict(v, name=g) for g, v in sorted(d.get("renewable_generators", {}).items())]
    for x in th:
        k = set(x) - set(TH)
        if k:
            raise ValueError(f"thermal unit {x['name']} carries unread fields: {sorted(k)}")
        if len(x["piecewise_production"]) < 1 or len(x["startup"]) < 1:
            raise ValueError(f"thermal unit {x['name']} has no cost or no start-up category")
    for x in re:
        k = set(x) - set(RE)
        if k:
            raise ValueError(f"renewable unit {x['name']} carries unread fields: {sorted(k)}")
    if len(d["demand"]) != T or len(d.get("reserves", [0] * T)) != T:
        raise ValueError("demand and reserves must carry one value per period")
    return {"T": T, "demand": np.asarray(d["demand"], dtype=float),
            "reserves": np.asarray(d.get("reserves", [0.0] * T), dtype=float),
            "th": th, "re": re}


def _sy(d):
    """Assemble (1) to (24) as one sparse mixed-integer program."""
    T, th, re = d["T"], d["th"], d["re"]
    G, W = len(th), len(re)
    S = [len(x["startup"]) for x in th]
    L = [len(x["piecewise_production"]) for x in th]
    o = {k: i * G * T for i, k in enumerate(("cg", "pg", "rg", "ug", "vg", "wg"))}
    n = 6 * G * T
    od, ol = [], []
    for i in range(G):
        od.append(n)
        n += S[i] * T
    for i in range(G):
        ol.append(n)
        n += L[i] * T
    o["pw"] = n
    n += W * T

    c = np.zeros(n)
    lb, ub, it = np.zeros(n), np.full(n, np.inf), np.zeros(n)
    lb[o["cg"] : o["cg"] + G * T] = -np.inf
    for k in ("ug", "vg", "wg"):
        ub[o[k] : o[k] + G * T] = 1.0
        it[o[k] : o[k] + G * T] = 1.0
    for i in range(G):
        it[od[i] : od[i] + S[i] * T] = 1.0
        ub[od[i] : od[i] + S[i] * T] = 1.0
        ub[ol[i] : ol[i] + L[i] * T] = 1.0

    ri, ci, va, b = [], [], [], []
    ei, ec, ev, be = [], [], [], []
    m = e = 0

    def iq(cols, vals, r):
        nonlocal m
        ri.extend([m] * len(cols))
        ci.extend(cols)
        va.extend(vals)
        b.append(r)
        m += 1

    def eq(cols, vals, r):
        nonlocal e
        ei.extend([e] * len(cols))
        ec.extend(cols)
        ev.extend(vals)
        be.append(r)
        e += 1

    for i, x in enumerate(th):
        for t in range(T):
            c[o["cg"] + i * T + t] = 1.0
            c[o["ug"] + i * T + t] = x["piecewise_production"][0]["cost"]
            for s in range(S[i]):
                c[od[i] + s * T + t] = x["startup"][s]["cost"]

    for t in range(T):                                                          # (2)
        cols = [o["pg"] + i * T + t for i in range(G)]
        vals = [1.0] * G
        cols += [o["ug"] + i * T + t for i in range(G)]
        vals += [float(th[i]["power_output_minimum"]) for i in range(G)]
        cols += [o["pw"] + w * T + t for w in range(W)]
        vals += [1.0] * W
        eq(cols, vals, float(d["demand"][t]))
        if d["reserves"][t] > 0.0:                                              # (3)
            iq([o["rg"] + i * T + t for i in range(G)], [-1.0] * G,
               -float(d["reserves"][t]))

    for i, x in enumerate(th):
        pmin, pmax = float(x["power_output_minimum"]), float(x["power_output_maximum"])
        RU, RD = float(x["ramp_up_limit"]), float(x["ramp_down_limit"])
        SU, SD = float(x["ramp_startup_limit"]), float(x["ramp_shutdown_limit"])
        UT, DT = min(int(x["time_up_minimum"]), T), min(int(x["time_down_minimum"]), T)
        u0, p0 = int(x["unit_on_t0"]), float(x["power_output_t0"])
        td0, tu0 = int(x["time_down_t0"]), int(x["time_up_t0"])
        if u0 not in (0, 1):
            raise ValueError(f"thermal unit {x['name']} has unit_on_t0={u0}")

        if u0 == 1:                                                             # (4)
            k = min(int(x["time_up_minimum"]) - tu0, T)
            if k >= 1:
                eq([o["ug"] + i * T + t for t in range(k)], [1.0] * k, float(k))
        else:                                                                   # (5)
            k = min(int(x["time_down_minimum"]) - td0, T)
            if k >= 1:
                eq([o["ug"] + i * T + t for t in range(k)], [1.0] * k, 0.0)

        eq([o["ug"] + i * T, o["vg"] + i * T, o["wg"] + i * T],                  # (6)
           [1.0, -1.0, 1.0], float(u0))

        cols = []                                                               # (7)
        for s in range(S[i] - 1):
            for t in range(max(1, x["startup"][s + 1]["lag"] - td0 + 1),
                           min(x["startup"][s + 1]["lag"] - 1, T) + 1):
                cols.append(od[i] + s * T + t - 1)
        if cols:
            eq(cols, [1.0] * len(cols), 0.0)

        iq([o["pg"] + i * T, o["rg"] + i * T], [1.0, 1.0],                       # (8)
           RU + u0 * (p0 - pmin))
        iq([o["pg"] + i * T], [-1.0], RD - u0 * (p0 - pmin))                      # (9)
        k = max(pmax - SD, 0.0)                                                  # (10)
        if k:
            iq([o["wg"] + i * T], [k], u0 * (pmax - pmin) - u0 * (p0 - pmin))

        for t in range(T):
            if x["must_run"]:                                                    # (11)
                iq([o["ug"] + i * T + t], [-1.0], -float(x["must_run"]))
            if t > 0:                                                            # (12)
                eq([o["ug"] + i * T + t, o["ug"] + i * T + t - 1,
                    o["vg"] + i * T + t, o["wg"] + i * T + t],
                   [1.0, -1.0, -1.0, 1.0], 0.0)
            if t >= UT - 1:                                                      # (13)
                cols = [o["vg"] + i * T + k for k in range(t - UT + 1, t + 1)]
                iq(cols + [o["ug"] + i * T + t], [1.0] * len(cols) + [-1.0], 0.0)
            if t >= DT - 1:                                                      # (14)
                cols = [o["wg"] + i * T + k for k in range(t - DT + 1, t + 1)]
                iq(cols + [o["ug"] + i * T + t], [1.0] * len(cols) + [1.0], 1.0)
            eq([od[i] + s * T + t for s in range(S[i])] + [o["vg"] + i * T + t],  # (16)
               [1.0] * S[i] + [-1.0], 0.0)
            iq([o["pg"] + i * T + t, o["rg"] + i * T + t, o["ug"] + i * T + t,    # (17)
                o["vg"] + i * T + t],
               [1.0, 1.0, -(pmax - pmin), max(pmax - SU, 0.0)], 0.0)
            if t < T - 1:                                                        # (18)
                iq([o["pg"] + i * T + t, o["rg"] + i * T + t, o["ug"] + i * T + t,
                    o["wg"] + i * T + t + 1],
                   [1.0, 1.0, -(pmax - pmin), max(pmax - SD, 0.0)], 0.0)
            if t > 0:                                                            # (19)
                iq([o["pg"] + i * T + t, o["rg"] + i * T + t, o["pg"] + i * T + t - 1],
                   [1.0, 1.0, -1.0], RU)
                iq([o["pg"] + i * T + t - 1, o["pg"] + i * T + t], [1.0, -1.0], RD)  # (20)
            p1 = float(x["piecewise_production"][0]["mw"])                       # (21)
            k1 = float(x["piecewise_production"][0]["cost"])
            eq([o["pg"] + i * T + t] + [ol[i] + l * T + t for l in range(L[i])],
               [1.0] + [-(float(x["piecewise_production"][l]["mw"]) - p1)
                        for l in range(L[i])], 0.0)
            eq([o["cg"] + i * T + t] + [ol[i] + l * T + t for l in range(L[i])],  # (22)
               [1.0] + [-(float(x["piecewise_production"][l]["cost"]) - k1)
                        for l in range(L[i])], 0.0)
            eq([o["ug"] + i * T + t] + [ol[i] + l * T + t for l in range(L[i])],  # (23)
               [1.0] + [-1.0] * L[i], 0.0)

        for s in range(S[i] - 1):                                                # (15)
            for t in range(T):
                if t + 1 >= x["startup"][s + 1]["lag"]:
                    cols = [o["wg"] + i * T + t - k for k
                            in range(x["startup"][s]["lag"], x["startup"][s + 1]["lag"])
                            if t - k >= 0]
                    iq([od[i] + s * T + t] + cols, [1.0] + [-1.0] * len(cols), 0.0)

    for w, x in enumerate(re):                                                   # (24)
        lb[o["pw"] + w * T : o["pw"] + (w + 1) * T] = x["power_output_minimum"]
        ub[o["pw"] + w * T : o["pw"] + (w + 1) * T] = x["power_output_maximum"]

    A = csc_array((va, (ri, ci)), shape=(m, n))
    Ae = csc_array((ev, (ei, ec)), shape=(e, n))
    return c, A, np.asarray(b, dtype=float), Ae, np.asarray(be, dtype=float), lb, ub, it


def cl(d, gap=0.0):
    """Clear one instance. gap is the relative MIP gap; the reference script uses 0.01."""
    c, A, b, Ae, be, lb, ub, it = _sy(d)
    res = milp(
        c,
        integrality=it,
        bounds=Bounds(lb, ub),
        constraints=[LinearConstraint(A, -np.inf, b), LinearConstraint(Ae, be, be)],
        options={"mip_rel_gap": gap},
    )
    if not res.success:
        raise ValueError(f"this instance did not clear: {res.message}")
    return Run(float(res.fun), "opt", gap)
