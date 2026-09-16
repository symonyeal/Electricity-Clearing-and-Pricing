# One configuration record for a historical experiment, read from TOML.
# Every field a result depends on is here, and every run writes this record beside it.
#
# LEGEND
#   zone,root    : NYISO zone name and archive directory
#   tr,va,te     : training, validation and held-out date ranges, inclusive
#   e,c,d,ec,ed  : usable MWh, charge and discharge MW, charge and discharge efficiency
#   e0,ef        : energy at the first midnight and the common end-of-day target, MWh
#   kd,fee       : degradation cost and transaction cost, currency per grid MWh
#   sp,lag,bid   : bins per decision, real-time posting lag in bins, bid close local hour
#   L,S,mn       : lookback days, scenarios, smallest node a tree may split
#   bd,bt        : day-ahead branch hours and real-time branch steps
#   w,al         : CVaR risk weight and confidence
#   gap,lim      : requested relative MIP gap and solver seconds per solve
#   rho          : fitted hourly persistence, zero until fit() supplies it
#   cache        : keep parsed months as arrays beside the archive

import tomllib
from pathlib import Path
from typing import NamedTuple


class Cf(NamedTuple):
    zone: str = "N.Y.C."
    root: str = "data/nyiso"
    tr: tuple = ("2022-10-01", "2023-12-31")
    va: tuple = ("2024-01-01", "2024-12-31")
    te: tuple = ("2025-01-01", "2025-12-31")
    e: float = 4.0
    c: float = 1.0
    d: float = 1.0
    ec: float = 0.92
    ed: float = 0.92
    e0: float = 2.0
    ef: float = 2.0
    kd: float = 2.0
    fee: float = 0.5
    sp: int = 3
    lag: int = 2
    bid: int = 5
    L: int = 60
    S: int = 8
    mn: int = 2
    bd: tuple = (6, 12, 18)
    bt: tuple = (4, 12)
    w: float = 0.0
    al: float = 0.95
    gap: float = 1e-4
    lim: float = 20.0
    rho: float = 0.0
    cache: bool = True

    def rep(self, **kw):
        return self._replace(**kw)


def read(p):
    """Read a configuration file. Unknown keys are refused rather than ignored."""
    d = tomllib.loads(Path(p).read_text())
    d = {k: v for s in d.values() for k, v in (s.items() if isinstance(s, dict) else ())} | \
        {k: v for k, v in d.items() if not isinstance(v, dict)}
    bad = set(d) - set(Cf._fields)
    if bad:
        raise ValueError(f"unknown configuration keys: {sorted(bad)}")
    for k in ("tr", "va", "te", "bd", "bt"):
        if k in d:
            d[k] = tuple(d[k])
    return Cf(**d)
