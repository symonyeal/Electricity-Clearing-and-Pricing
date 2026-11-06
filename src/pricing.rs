//! Settlement at a price, AIC output ceilings and the full comparison of price rules.
use crate::error::Error;
use crate::lp::{Problem, Solution};
use crate::{
    clearing::{lmp, rx, uc},
    hull::hc,
    market::{Clearing, Market, Sol},
    unit::{self, Unit},
};
use serde::Serialize;

/// Quality of price selection, independent of optimality of the primal solve.
#[derive(Clone, Copy, Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Selection {
    Raw,
    Payment,
    Probe,
    Walk,
    Partial,
}

impl Selection {
    /// Require successful demand-payment minimisation; raw primal duals do not meet it.
    pub fn require_payment(self) -> Result<(), Error> {
        if self == Self::Raw {
            Err(Error::Solver("demand-payment selection failed".into()))
        } else {
            Ok(())
        }
    }
}

const TOL: f64 = 1e-7;
/// AIC output relaxation above a losing block's cleared dispatch, MW.
const EP: f64 = 1e-6;

/// Per unit: realised profit r, make-whole mw, lost opportunity loc and total uplift up.
#[derive(Clone, Debug, Serialize)]
pub struct Pay {
    pub r: Vec<f64>,
    pub mw: Vec<f64>,
    pub loc: Vec<f64>,
    pub up: Vec<f64>,
}

/// The integer clearing, each rule's prices and the uplift each rule's prices leave.
/// chp_r and aic_r price the continuous relaxation of the same feasible sets.
#[derive(Clone, Debug, Serialize)]
pub struct Run {
    pub uc: Clearing,
    pub lmp: Clearing,
    pub chp: Sol,
    pub chp_r: Sol,
    pub aic: Sol,
    pub aic_r: Sol,
    pub pay_lmp: Pay,
    pub pay_chp: Pay,
    pub pay_aic: Pay,
}

/// Maximal on-blocks [s, e] of commitment u, with whether each begins with a start-up.
fn blocks(x: &Unit, u: &[f64]) -> Vec<(usize, usize, bool)> {
    let mut v = Vec::new();
    let mut k = 0;
    while k < u.len() {
        if u[k] < 0.5 {
            k += 1;
            continue;
        }
        let s = k;
        while k + 1 < u.len() && u[k + 1] > 0.5 {
            k += 1;
        }
        v.push((s, k, s > 0 || x.u0 == 0));
        k += 1;
    }
    v
}

fn profit(x: &Unit, pi: &[f64], p: &[f64], (s, e, start): (usize, usize, bool)) -> f64 {
    (s..=e).map(|k| (pi[k] - x.c) * p[k]).sum::<f64>()
        - x.nl * (e - s + 1) as f64
        - if start { x.su } else { 0. }
}

/// Settle clearing s at prices pi. Total uplift is the best self-scheduled profit less
/// realised profit; make-whole covers losing blocks up to that uplift; lost opportunity
/// is the remainder. The cap binds only on losses a unit's initial state forces on it:
/// a unit that starts offline can always drop a losing block.
pub fn pay(m: &Market, s: &Clearing, pi: &[Vec<f64>]) -> Result<Pay, Error> {
    s.check(m)?;
    m.prices(pi)?;
    let t = m.t();
    let (mut r, mut mw, mut up) = (vec![], vec![], vec![]);
    for (i, x) in m.g.iter().enumerate() {
        let pi = &pi[m.net.bus[i]];
        let z: Vec<f64> = blocks(x, &s.u[i])
            .into_iter()
            .map(|b| profit(x, pi, &s.p[i], b))
            .collect();
        let best = -unit::oracle(x, t, pi, None).solve(true)?.lb;
        r.push(z.iter().sum::<f64>());
        up.push(best - r[i]);
        mw.push(
            z.iter()
                .map(|z| (-z).max(0.))
                .sum::<f64>()
                .min(up[i].max(0.)),
        );
    }
    let loc = up.iter().zip(&mw).map(|(a, b)| a - b).collect();
    Ok(Pay { r, mw, loc, up })
}

/// AIC ceilings: full capacity, except cleared blocks that lose money at prices pi are
/// capped at their dispatch plus EP, and periods with no cleared output at zero.
pub fn pc(m: &Market, s: &Clearing, pi: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, Error> {
    s.check(m)?;
    m.prices(pi)?;
    let mut cap = vec![];
    for (i, x) in m.g.iter().enumerate() {
        let mut c = vec![x.hi; m.t()];
        for b @ (s0, e, _) in blocks(x, &s.u[i]) {
            if profit(x, &pi[m.net.bus[i]], &s.p[i], b) < 0. {
                for k in s0..=e {
                    c[k] = x.hi.min(s.p[i][k] + EP);
                }
            }
        }
        for (c, &p) in c.iter_mut().zip(&s.p[i]) {
            if p <= TOL {
                *c = 0.;
            }
        }
        cap.push(c);
    }
    Ok(cap)
}

/// Clear once, then price with LMP, CHP and AIC and settle the clearing at each.
pub fn run(m: &Market) -> Result<Run, Error> {
    let uc = uc(m, None)?;
    let lmp = lmp(m, &uc, None)?;
    let cap = pc(m, &uc, &lmp.pi)?;
    let chp = hc(m, None)?;
    let aic = hc(m, Some(&cap))?;
    for sol in [&*lmp, &chp, &aic] {
        sol.price_selection
            .ok_or("missing price selection")?
            .require_payment()?;
    }
    Ok(Run {
        pay_lmp: pay(m, &uc, &lmp.pi)?,
        pay_chp: pay(m, &uc, &chp.pi)?,
        pay_aic: pay(m, &uc, &aic.pi)?,
        chp_r: rx(m, None)?,
        aic_r: rx(m, Some(&cap))?,
        uc,
        lmp,
        chp,
        aic,
    })
}

fn ceiling(v: f64) -> f64 {
    v + 1e-9 * v.abs().max(1.0)
}

/// Minimise demand payment over the optimal dual face, then refine balance prices.
/// `balances` identifies the balance equalities; all primal bounds enter the dual
/// explicitly, and stationarity is an equality. Stages: raw (face LP failed), pay
/// (nt > 24: payment only), probe (an interior point of the face agrees with the vertex),
/// walk (lexicographic minimum over the balance prices), part (walk stopped early).
pub(crate) fn price(p: &Problem, balances: &[usize]) -> Result<(Solution, Selection), Error> {
    price_with(p, balances, |d| d.solve(false))
}

fn price_with(
    p: &Problem,
    balances: &[usize],
    face: impl FnOnce(&Problem) -> Result<Solution, Error>,
) -> Result<(Solution, Selection), Error> {
    let nt = balances.len();
    let unique: std::collections::BTreeSet<_> = balances.iter().collect();
    if nt == 0
        || unique.len() != nt
        || balances.iter().any(|&j| j >= p.be.len())
        || p.integer.iter().any(|x| *x)
    {
        return Err(
            "price selection needs distinct valid balance rows of a continuous program".into(),
        );
    }
    let mut p = p.clone();
    for j in 0..p.c.len() {
        if p.lb[j].is_finite() {
            p.row(vec![(j, -1.0)], -p.lb[j]);
        }
        if p.ub[j].is_finite() {
            p.row(vec![(j, 1.0)], p.ub[j]);
        }
        p.lb[j] = f64::NEG_INFINITY;
        p.ub[j] = f64::INFINITY;
    }
    let mut s = p.solve(false)?;
    let (m, e, n) = (p.a.len(), p.ae.len(), p.c.len());
    let mut d = Problem::default();
    for j in 0..m + e {
        let c = if j >= m && balances.contains(&(j - m)) {
            p.be[j - m]
        } else {
            0.0
        };
        d.col(
            c,
            f64::NEG_INFINITY,
            if j < m { 0.0 } else { f64::INFINITY },
            false,
        );
    }
    let mut stationarity = vec![vec![]; n];
    for (i, row) in p.a.iter().chain(&p.ae).enumerate() {
        for &(j, v) in row {
            stationarity[j].push((i, v));
        }
    }
    for (row, c) in stationarity.into_iter().zip(&p.c) {
        d.eq(row, *c);
    }
    d.row(
        p.b.iter()
            .chain(&p.be)
            .enumerate()
            .map(|(j, v)| (j, -v))
            .collect(),
        ceiling(-s.z),
    );
    let Ok(q) = face(&d) else {
        return Ok((s, Selection::Raw));
    };
    s.dual = q.x[m..].to_vec();
    d.row(
        d.c.iter()
            .enumerate()
            .filter(|(_, v)| **v != 0.0)
            .map(|(j, v)| (j, *v))
            .collect(),
        ceiling(q.z),
    );
    if nt > 24 {
        return Ok((s, Selection::Payment));
    }
    let mut probe = d.clone();
    probe.c.fill(0.0);
    for b in &mut probe.b {
        *b += 1e-7 * b.abs().max(1.0);
    }
    if let Ok(q) = probe.solve_with(false, false, true) {
        let delta = balances
            .iter()
            .map(|&j| (q.x[m + j] - s.dual[j]).abs())
            .fold(0.0, f64::max);
        if delta <= 1e-3 {
            return Ok((s, Selection::Probe));
        }
    }
    for &j in balances {
        d.c.fill(0.0);
        d.c[m + j] = 1.0;
        let Ok(q) = d.solve(false) else {
            return Ok((s, Selection::Partial));
        };
        s.dual = q.x[m..].to_vec();
        d.row(vec![(m + j, 1.0)], ceiling(q.z));
    }
    Ok((s, Selection::Walk))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn failed_face_selection_cannot_satisfy_payment_policy() {
        let mut p = Problem::default();
        p.col(7., 0., 10., false);
        p.eq(vec![(0, 1.)], 3.);
        let (s, selection) = price_with(&p, &[0], |_| {
            Err(Error::Solver("injected face failure".into()))
        })
        .unwrap();
        assert!((s.z - 21.).abs() < 1e-8);
        assert_eq!(selection, Selection::Raw);
        assert!(selection.require_payment().is_err());
    }

    #[test]
    fn large_balance_sets_report_payment_selection_only() {
        let mut p = Problem::default();
        for j in 0..25 {
            p.col(7., 0., 10., false);
            p.eq(vec![(j, 1.)], 3.);
        }
        let (_, selection) = price(&p, &(0..25).collect::<Vec<_>>()).unwrap();
        assert_eq!(selection, Selection::Payment);
        selection.require_payment().unwrap();
    }

    fn market(x: Unit, d: Vec<f64>) -> Market {
        Market::new(vec![x], vec![d], None).unwrap()
    }

    #[test]
    fn negative_energy_cost_keeps_hull_output_bounded() {
        let s = hc(&market(Unit::new(0., 10., -5.), vec![5.]), None).unwrap();
        assert!((s.z + 25.).abs() < 1e-7);
        assert!((s.p[0][0] - 5.).abs() < 1e-7);
        assert!((s.pi[0][0] + 5.).abs() < 1e-7);
    }

    #[test]
    fn forced_initial_loss_is_not_make_whole() {
        // On for two more periods whatever the price: losing 20 is the unit's best schedule.
        let x = Unit {
            nl: 20.,
            u0: 1,
            p0: 50.,
            mu: 3,
            e0: Some(1),
            ..Unit::new(10., 50., 45.)
        };
        let m = market(x, vec![12.4]);
        let s = uc(&m, None).unwrap();
        let q = pay(&m, &s, &lmp(&m, &s, None).unwrap().pi).unwrap();
        assert!((q.r[0] + 20.).abs() < 1e-5);
        assert!(q.up[0].abs() < 1e-5 && q.mw[0].abs() < 1e-5 && q.loc[0].abs() < 1e-5);
    }

    #[test]
    fn hull_is_certified_at_initial_on_and_down_states() {
        let on = Unit {
            u0: 1,
            p0: 5.,
            mu: 2,
            e0: Some(1),
            ..Unit::new(0., 10., 10.)
        };
        let down = Unit {
            md: 2,
            e0: Some(1),
            ..Unit::new(0., 10., 20.)
        };
        for (x, d, z) in [(on, vec![5., 0.], 50.), (down, vec![0., 5.], 100.)] {
            let s = hc(&market(x, d), None).unwrap();
            assert!((s.z - z).abs() < 1e-7, "{} != {z}", s.z);
            assert!(s.gap.abs() < 1e-7, "lb {} below z {}", s.lb, s.z);
        }
    }
}
