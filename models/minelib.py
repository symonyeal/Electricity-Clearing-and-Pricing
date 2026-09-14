# MineLib UPIT reader.
#
# LEGEND
#   rd      : MineLib reader
#   Path,Decimal,InvalidOperation,np : file, decimal-error and array tools
#   p_u,p_e : paths to the UPIT values and precedence files
#   u,e     : open text files                     ln : one stripped input line
#   n,m,r   : block count, arc count and current arc row
#   b,p,n_p : block, required block and number of required blocks
#   f       : fields on one input line            val : one value as a Decimal
#   v       : economic block value vector         E : int32 precedence matrix
#   sc      : exact decimal scale for integer capacities
#   seen    : blocks already read                 obj : inside the objective section
#   exc     : invalid-decimal exception

from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np


def rd(p_u, p_e):
    """Read one MineLib UPIT instance. Returns (v, E, sc)."""
    p_u, p_e = Path(p_u), Path(p_e)
    n, v, sc, seen, obj = None, None, 1, None, False
    with p_u.open(encoding="utf-8") as u:
        for ln in u:
            ln = ln.strip()
            if not ln or ln.startswith("%"):
                continue
            if not obj:
                if ln.startswith("TYPE:") and ln.split(":", 1)[1].strip().upper() != "UPIT":
                    raise ValueError("model file is not UPIT")
                if ln.startswith("NBLOCKS:"):
                    n = int(ln.split(":", 1)[1])
                    if n < 1 or n > np.iinfo(np.int32).max:
                        raise ValueError("invalid block count")
                elif ln == "OBJECTIVE_FUNCTION:":
                    if n is None:
                        raise ValueError("NBLOCKS must precede OBJECTIVE_FUNCTION")
                    v = np.full(n, np.nan)
                    seen = np.zeros(n, dtype=bool)
                    obj = True
                continue
            f = ln.split()
            if len(f) != 2:
                raise ValueError("invalid objective row")
            b = int(f[0])
            if not 0 <= b < n or seen[b]:
                raise ValueError("invalid or repeated objective block")
            try:
                val = Decimal(f[1])
            except InvalidOperation as exc:
                raise ValueError("invalid objective value") from exc
            if not val.is_finite():
                raise ValueError("objective values must be finite")
            v[b], seen[b] = float(val), True
            sc = max(sc, 10 ** max(0, -val.as_tuple().exponent))
    if v is None or not seen.all():
        raise ValueError("objective rows do not match NBLOCKS")

    m = 0
    seen = np.zeros(n, dtype=bool)
    with p_e.open(encoding="utf-8") as e:
        for ln in e:
            ln = ln.strip()
            if not ln or ln.startswith("%"):
                continue
            f = ln.split()
            if len(f) < 2:
                raise ValueError("invalid precedence row")
            b, n_p = int(f[0]), int(f[1])
            if not 0 <= b < n or seen[b] or n_p < 0 or len(f) != n_p + 2:
                raise ValueError("invalid or repeated precedence block")
            seen[b], m = True, m + n_p
    if not seen.all():
        raise ValueError("precedence rows do not match NBLOCKS")

    E = np.empty((m, 2), dtype=np.int32)
    r = 0
    with p_e.open(encoding="utf-8") as e:
        for ln in e:
            ln = ln.strip()
            if not ln or ln.startswith("%"):
                continue
            f = ln.split()
            b = int(f[0])
            for p in f[2:]:
                p = int(p)
                if not 0 <= p < n:
                    raise ValueError("precedence block is outside NBLOCKS")
                E[r], r = (b, p), r + 1
    return v, E, sc
