# Prices under a risk-averse commitment: which dual is a price, of which program.
#
# models/stoch.py clears one commitment against S demands under the objective
# rho(C) = (1 - w) E[C] + w CVaR_al(C) and prices it by re-dispatching that commitment at
# expected cost (stoch.lmp). stoch.cvd reads the duals of the risk-averse program itself.
# This module names each object by the program it comes from, computes the value-of-
# information measures under E and under rho, and settles one clearing under each
# candidate price. Nothing here re-derives a row; everything reads stoch and joint.
#
# The candidate prices, per scenario s, all with the clearing's integers held:
#   ec  : stoch.lmp, the expected-cost re-dispatch's balance dual over p_s
#   raw : y_s / p_s, the risk-averse program's balance dual over p_s
#   nrm : y_s / om_s, the same dual over its own weight om_s = (1 - w) p_s + mu_s; nan
#         where om_s = 0, where the program carries no price for the scenario at all
#
# LEGEND
#   Vi         : SP, WS and EEV under E and under rho, with EVPI and VSS in each
#   Se         : one clearing settled at one candidate price, scenario by scenario
#   rho        : (1 - w) E[q] + w CVaR_al(q) of scenario costs q
#   vi,se      : the value-of-information measures; the settlement
#   r1..r5     : the five examples
#   g,st,d,pr  : units, resources, scenario demand (S, B, T), probabilities
#   net,w,al   : network, risk weight, CVaR confidence
#   s,s0,ub    : the risk-averse clearing, the risk-neutral one, the mean-value commitment
#   q          : scenario costs                 p : scenario dispatch (S, G, T)
#   pi         : a candidate price (S, B, T)    L : load payment per scenario
#   r,mw,loc   : unit profit, make-whole, lost opportunity per scenario and unit
#   E          : expectation under pr

from typing import NamedTuple

import numpy as np

from models.joint import cl as jcl
from models.stoch import Sc, _cv, cl, ck, lmp
from models.uc_price import U, Sol, pay


class Vi(NamedTuple):
    """Value of information under E and under rho, each in its own units.

    ws, sp, ee are the wait-and-see, stochastic and expected-mean-value values; evpi is
    sp - ws and vss is ee - sp. The E triple is Birge and Louveaux's; the rho triple
    applies rho to the same scenario cost vectors. mr is E[C] at the rho-optimal
    commitment, re-dispatched at expected cost: what the risk-averse commitment costs on
    average, which is neither SP_E nor SP_rho.
    """

    ws: float
    sp: float
    ee: float
    evpi: float
    vss: float
    wsr: float
    spr: float
    eer: float
    evpir: float
    vssr: float
    mr: float


class Se(NamedTuple):
    """One clearing settled at one candidate price, scenario by scenario, and in expectation.

    L, r, mw and loc are (S,), (S, G), (S, G) and (S, G); EL, Er, Emw and Eloc their
    expectations under pr, summed over units.
    """

    L: np.ndarray
    r: np.ndarray
    mw: np.ndarray
    loc: np.ndarray
    EL: float
    Er: float
    Emw: float
    Eloc: float


def rho(q, pr, w, al):
    """(1 - w) E[q] + w CVaR_al(q), with CVaR read from the weighted tail."""
    return float((1.0 - w) * (pr @ q) + w * _cv(np.asarray(q, dtype=float), pr, al))


def vi(g, st, d, pr, net=None, w=0.0, al=0.95):
    """SP <= ... : WS <= SP <= EEV under E, and again under rho.

    WS solves each scenario knowing it, SP commits once, EEV commits to the mean demand and
    meets each scenario with that commitment. Each scenario cost is the cheapest recourse,
    which is optimal under any monotone rho, so the second chain holds for the same reason
    as the first: rho is monotone and each triple compares the same scenario vectors.
    """
    g, st, d, net, pr, w, al = ck(g, st, d, pr, net, w, al)
    z = np.array([jcl(g, st, d[k], net).z for k in range(len(pr))])
    s0, s = cl(g, st, d, pr, net), cl(g, st, d, pr, net, w, al)
    ub = jcl(g, st, (pr[:, None, None] * d).sum(0), net)
    e = lmp(g, st, d, Sc(0.0, 0.0, 0.0, None, ub.u, None, None, None, None,
                         np.repeat(ub.sm[None], len(pr), 0), None), pr, net).q
    mr = lmp(g, st, d, s, pr, net).mean
    return Vi(float(pr @ z), s0.z, float(pr @ e), s0.z - float(pr @ z), float(pr @ e) - s0.z,
              rho(z, pr, w, al), s.z, rho(e, pr, w, al), s.z - rho(z, pr, w, al),
              rho(e, pr, w, al) - s.z, mr)


def se(g, d, pr, u, p, pi, net=None):
    """Settle scenario dispatch p under commitment u at price pi, scenario by scenario.

    Each scenario is settled as uc_price.pay settles a clearing: profit by commitment
    block, make-whole where a block loses, lost opportunity against the unit's best
    self-schedule at that scenario's price. Scenarios where pi is nan carry no price and
    are left out of the expectations; the caller sees which by the nan rows.
    """
    S, G = len(pr), len(g)
    L, r, mw, loc = np.full(S, np.nan), np.full((S, G), np.nan), np.full((S, G), np.nan), \
        np.full((S, G), np.nan)
    for k in range(S):
        if np.isnan(pi[k]).any():
            continue
        P = pay(g, Sol(0.0, p[k], u, pi[k]), pi[k], net)
        L[k], r[k], mw[k], loc[k] = float((pi[k] * d[k]).sum()), P.r, P.mw, P.loc
    h = ~np.isnan(L)
    return Se(L, r, mw, loc, float(pr[h] @ L[h]), float(pr[h] @ r[h].sum(1)),
              float(pr[h] @ mw[h].sum(1)), float(pr[h] @ loc[h].sum(1)))


# The units shared by the examples, all at one bus. C is cheap and small, M a mid-merit unit
# that costs 1,000 a period merely to be on, P a peaker at 500/MWh with no fixed cost.

def _u(hm=100.0):
    return [U(0.0, 40.0, 20.0), U(0.0, hm, 40.0, nl=1000.0), U(0.0, 200.0, 500.0)]


def r1():
    """Agreement: tests/test_stoch.py's two scenarios at al = 0, where CVaR is the mean.

    Every scenario is in the tail with its own probability, so mu = w pr, om = pr, and the
    raw dual over p_s is already the scenario price.
    """
    return _u(), [], np.array([[[10.0, 20.0]], [[10.0, 120.0]]]), np.array([0.9, 0.1]), 0.5, 0.0


def r2():
    """Disagreement: the same market at w = 0.5, al = 0.5.

    The commitment is the risk-neutral one, so the scenario prices are too. The raw dual
    over p_s is not: om = (0.85, 0.15), and y_s / p_s scales each price by om_s / p_s.
    """
    return _u(), [], np.array([[[10.0, 20.0]], [[10.0, 120.0]]]), np.array([0.9, 0.1]), 0.5, 0.5


def r3():
    """Risk changes the commitment and not one price.

    One period; 20 MW with probability 0.98 and 120 MW with 0.02. M holds 50 MW. Risk
    neutral, M is not worth its 1,000: 1,208 against 1,748. At w = 0.5, al = 0.95 it is:
    CVaR falls from 16,560 to 8,360. With or without M the spike's price is P's 500 and
    the base price C's 20, because M cannot cover the spike alone.
    """
    return _u(50.0), [], np.array([[[20.0]], [[120.0]]]), np.array([0.98, 0.02]), 0.5, 0.95


def r4():
    """No price: r2's market at w = 1, al = 0.95.

    The 0.05 tail holds all of the 0.1 spike, so the base scenario lies wholly below the
    quantile, mu = 0 there, om = 0, and its balance dual is zero. The program puts no
    weight on that scenario's cost; its dispatch there is not determined by it.
    """
    return _u(), [], np.array([[[10.0, 20.0]], [[10.0, 120.0]]]), np.array([0.9, 0.1]), 1.0, 0.95


def r5():
    """Risk changes the commitment and the price: r3 with M able to cover the spike.

    With M at 100 MW, committing it moves the spike's marginal unit from P at 500 to M at
    40. Risk neutral, M is again not worth its cost at 0.02; risk averse, it is.
    """
    return _u(), [], np.array([[[20.0]], [[120.0]]]), np.array([0.98, 0.02]), 0.5, 0.95
