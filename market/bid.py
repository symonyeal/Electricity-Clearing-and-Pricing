# What a market accepts, what it charges, and what it admits.
#
# The replay's day-ahead position is otherwise taken in full: the model names a quantity
# and the market is assumed to buy all of it at the cleared price. A real market is offered
# a curve and accepts the part of it the clearing price supports, charges the energy that
# crosses the meter, and admits only resources that meet its qualification rules.
#
# None of this is any one market's rule set, and it is not NYISO's. The curve shape, the
# charge and the thresholds are parameters; their defaults reproduce full acceptance at no
# charge, so a configuration that sets none of them replays exactly as before. Calibrating
# them means reading a tariff and a set of manuals, which is a different kind of work from
# this: what is here is the mechanism those documents would parameterise.
#
# LEGEND
#   cv         : one hour's offer curve, (price, quantity) rows, in no particular order
#   curve      : build that curve around an intended position
#   clear      : the quantity one clearing price accepts from a curve
#   accept     : both of the above over a day of hours
#   charge     : the per-MWh charge on metered energy
#   qual       : the qualification screens, and why a resource fails one
#   q,ref,p    : intended position MW, the reference price it was chosen at, the cleared price
#   k,sp       : steps in the curve, and the fractional spread it covers
#   j          : one step

import numpy as np


def curve(q, ref, k, sp):
    """One hour's offer curve: k equal slices of q spread by sp around ref.

    A resource that means to discharge q offers it in slices whose reservation prices span
    the band between ref(1 - sp) and ref(1 + sp); one that means to charge bids for it over
    the same band. What makes a single clearing price pick out one quantity is that clear
    tests each slice against its own reservation, so the accepted quantity is monotone in
    the cleared price however the rows happen to be ordered.

    The rows ascend in price for a discharging resource only while ref is positive; at a
    negative reference the same band is walked the other way, because the band is ref
    scaled rather than ref offset. Nothing reads the order, so this changes the listing
    and not the clearing. NYISO day-ahead prices in the committed archive are never
    negative, but the real-time ones are, and a market may price either way.

    sp is a bidding stance, not a derivation. sp = 0 collapses the curve to one block at
    ref and reproduces full acceptance whenever the cleared price is on the right side of
    ref; k = 0 is refused, because a curve with no steps is not a curve.

    A step count is a count and a spread is a fraction, so both are tested for what they are
    and not only for their sign. Every comparison with a nan is false, so k < 1 and sp < 0
    let one through: the count then died inside np.full naming sequences of integers, and the
    spread returned a curve of nan reservation prices that clear accepts nothing from at any
    price, which switches the offer off instead of refusing it.
    """
    if not np.isfinite(k) or float(k) != int(k):
        raise ValueError("an offer curve needs a whole number of steps")
    if k < 1:
        raise ValueError("an offer curve needs at least one step")
    if not np.isfinite(sp) or sp < 0:
        raise ValueError("the bid spread must be finite and non-negative")
    k = int(k)
    q = float(q)
    if q == 0.0:
        return np.zeros((0, 2))
    w = np.full(k, abs(q) / k)
    j = np.zeros(k) if k == 1 else np.linspace(-1.0, 1.0, k)
    pr = float(ref) * (1.0 + sp * (j if q > 0 else -j))
    return np.c_[pr, np.sign(q) * w]


def clear(cv, p):
    """The quantity a clearing price p accepts from one curve.

    A discharge slice is accepted when the price is at or above its reservation; a charge
    slice when the price is at or below its bid. Ties go to acceptance, which is the
    convention that keeps sp = 0 equal to full acceptance.
    """
    if not len(cv):
        return 0.0
    pr, w = cv[:, 0], cv[:, 1]
    ok = np.where(w > 0, p >= pr - 1e-12, p <= pr + 1e-12)
    return float(w[ok].sum())


def accept(q, ref, p, k, sp):
    """Clear a day of hourly offers against the day's cleared prices.

    Returns the accepted position. With k = 0 the position is taken in full, which is the
    replay's own assumption and the default.
    """
    q = np.asarray(q, dtype=float)
    if k < 1:
        return q.copy()
    ref = np.asarray(ref, dtype=float)
    p = np.asarray(p, dtype=float)
    if ref.shape != q.shape or p.shape != q.shape:
        raise ValueError("position, reference price and cleared price must share a shape")
    return np.array([clear(curve(q[h], ref[h], k, sp), p[h]) for h in range(len(q))])


def charge(c, d, tar):
    """The per-MWh charge on metered energy, applied to both directions.

    Charged on energy at the meter, so a round trip pays twice. tar = 0 is no charge. A
    non-finite rate is refused here rather than allowed to turn every settled charge into
    nan; replay validates its configuration before this function, but charge is public.
    """
    if not np.isfinite(tar) or tar < 0:
        raise ValueError("a tariff rate must be finite and non-negative")
    return float(tar) * (np.asarray(c, dtype=float) + np.asarray(d, dtype=float))


def qual(pw, en, qmin, qdur):
    """Whether a resource qualifies, and the first rule it fails.

    pw is rated power in MW and en usable energy in MWh, so en / pw is the duration the
    resource can hold rated output. A market that requires a minimum size states qmin; one
    that requires a sustained duration states qdur. Both default to zero, which admits
    everything.

    A threshold is compared with a tolerance, so a nan threshold compares false and admits
    every resource while reading as a screen that was applied. A screen that cannot refuse
    anything is not a screen, so the thresholds are required to be finite numbers here.
    """
    if not np.isfinite(pw) or not np.isfinite(en) or pw <= 0 or en <= 0:
        raise ValueError("rated power and usable energy must be finite and positive")
    if not np.isfinite(qmin) or not np.isfinite(qdur) or qmin < 0 or qdur < 0:
        raise ValueError("qualification thresholds must be finite and non-negative")
    if pw < qmin - 1e-12:
        return False, f"rated power {pw:g} MW is below the {qmin:g} MW minimum"
    if en / pw < qdur - 1e-12:
        return False, f"duration {en / pw:g} h is below the {qdur:g} h minimum"
    return True, ""
