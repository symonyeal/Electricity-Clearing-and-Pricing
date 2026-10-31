//! Self-scheduling bounds, AIC output ceilings and settlement.
use crate::{
    clearing::{self, Market, Sol},
    hull::hc,
    unit::{self, Unit},
};
const TOL: f64 = 1e-7;

/// Evaluate the unit-commitment Lagrangian dual from certified unit bounds.
pub fn qd(m: &Market, pi: &[Vec<f64>], cap: Option<&[Vec<f64>]>) -> Result<f64, String> {
    let m = m.validated()?;
    let net = m.net.as_ref().unwrap();
    let t = m.d[0].len();
    m.check_cap(cap)?;
    if pi.len() != net.nb
        || pi
            .iter()
            .any(|r| r.len() != t || r.iter().any(|v| !v.is_finite()))
    {
        return Err("pi must hold one finite price per bus and period".into());
    }
    let mut val = 0.;
    for b in 0..net.nb {
        for k in 0..t {
            val += pi[b][k] * m.d[b][k];
        }
    }
    for (i, x) in m.g.iter().enumerate() {
        let p = unit::oracle(x, t, &pi[net.bus[i]], cap.map(|c| c[i].as_slice()));
        let s = p.solve(true)?;
        val += s.lb;
    }
    val += crate::network::value(net, t, pi)?;
    Ok(val)
}

#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
pub struct Pay {
    pub r: Vec<f64>,
    pub mw: Vec<f64>,
    pub loc: Vec<f64>,
    pub up: Vec<f64>,
}
#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
pub struct Run {
    pub uc: Sol,
    pub lmp: Sol,
    pub chp: Sol,
    pub chp_r: Sol,
    pub aic: Sol,
    pub aic_r: Sol,
}
fn blocks(x: &Unit, u: &[f64]) -> Vec<(usize, usize, bool)> {
    let mut v = Vec::new();
    let mut t = 0;
    while t < u.len() {
        if u[t] < 0.5 {
            t += 1;
            continue;
        }
        let s = t;
        while t + 1 < u.len() && u[t + 1] > 0.5 {
            t += 1;
        }
        v.push((s, t, s > 0 || x.u0 == 0));
        t += 1;
    }
    v
}
fn profit(x: &Unit, pi: &[f64], p: &[f64], s: usize, e: usize, start: bool) -> f64 {
    (s..=e).map(|k| (pi[k] - x.c) * p[k]).sum::<f64>()
        - x.nl * (e - s + 1) as f64
        - x.su * if start { 1. } else { 0. }
}
/// Realised block profit and make-whole, lost-opportunity and total uplift.
pub fn pay(m: &Market, s: &Sol, pi: &[Vec<f64>]) -> Result<Pay, String> {
    let m = m.validated()?;
    let net = m.net.as_ref().unwrap();
    let t = m.d[0].len();
    if s.p.len() != m.g.len()
        || s.u.len() != m.g.len()
        || pi.len() != net.nb
        || pi
            .iter()
            .any(|r| r.len() != t || r.iter().any(|v| !v.is_finite()))
    {
        return Err("pay needs one finite price, output and commitment per unit and period".into());
    }
    let mut r = vec![0.; m.g.len()];
    let mut mw = r.clone();
    for (i, x) in m.g.iter().enumerate() {
        if s.p[i].len() != t
            || s.u[i].len() != t
            || s.p[i].iter().any(|v| !v.is_finite())
            || s.u[i].iter().any(|v| ![0., 1.].contains(v))
        {
            return Err("pay needs an integer commitment and finite output".into());
        }
        let Some((a, b, _)) = unit::trajectory(x, t, &s.u[i], None) else {
            return Err("the cleared commitment breaks a unit's limits".into());
        };
        if a.iter().zip(&b).any(|(row, rhs)| {
            row.iter().zip(&s.p[i]).map(|(a, p)| a * p).sum::<f64>() > *rhs + 1e-6
        }) {
            return Err("the cleared output breaks a unit's limits".into());
        }
        for (a, b, start) in blocks(x, &s.u[i]) {
            let z = profit(x, &pi[net.bus[i]], &s.p[i], a, b, start);
            r[i] += z;
            mw[i] += (-z).max(0.);
        }
    }
    let mut up = vec![0.; m.g.len()];
    for (i, x) in m.g.iter().enumerate() {
        let q = unit::oracle(x, t, &pi[net.bus[i]], None);
        let o = q.solve(true)?;
        up[i] = -o.lb - r[i];
    }
    let loc = up.iter().zip(&mw).map(|(a, b)| a - b).collect();
    Ok(Pay { r, mw, loc, up })
}
/// Cap output on cleared blocks that fail to cover their cost at LMP.
pub fn pc(m: &Market, s: &Sol, ep: f64, l: Option<&Sol>) -> Result<Vec<Vec<f64>>, String> {
    let m = m.validated()?;
    if !ep.is_finite() || ep <= 0. {
        return Err("ep must be positive and finite".into());
    }
    let l = match l {
        Some(q) => q.clone(),
        None => clearing::lmp(&m, s, None)?,
    };
    let net = m.net.as_ref().unwrap();
    let t = m.d[0].len();
    if s.p.len() != m.g.len()
        || s.u.len() != m.g.len()
        || s.p
            .iter()
            .any(|r| r.len() != t || r.iter().any(|x| !x.is_finite()))
        || s.u
            .iter()
            .any(|r| r.len() != t || r.iter().any(|x| ![0.0, 1.0].contains(x)))
        || l.pi.len() != net.nb
        || l.pi
            .iter()
            .any(|r| r.len() != t || r.iter().any(|x| !x.is_finite()))
    {
        return Err(
            "pc needs one cleared output, commitment and LMP per unit, bus and period".into(),
        );
    }
    let mut cap = vec![vec![0.; t]; m.g.len()];
    for (i, x) in m.g.iter().enumerate() {
        cap[i].fill(x.hi);
        for (a, b, start) in blocks(x, &s.u[i]) {
            if profit(x, &l.pi[net.bus[i]], &s.p[i], a, b, start) < 0. {
                for k in a..=b {
                    cap[i][k] = x.hi.min(s.p[i][k] + ep);
                }
            }
        }
        for k in 0..t {
            if s.p[i][k] <= TOL {
                cap[i][k] = 0.;
            }
        }
    }
    Ok(cap)
}
/// Clear once, then calculate LMP and unrestricted and capped hull prices.
pub fn run(m: &Market, ep: f64) -> Result<Run, String> {
    let m = m.validated()?;
    let uc = clearing::uc(&m, None)?;
    let lmp = clearing::lmp(&m, &uc, None)?;
    let cap = pc(&m, &uc, ep, Some(&lmp))?;
    Ok(Run {
        chp: hc(&m, None)?,
        chp_r: clearing::rx(&m, None)?,
        aic: hc(&m, Some(&cap))?,
        aic_r: clearing::rx(&m, Some(&cap))?,
        uc,
        lmp,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn unit(c: f64, hi: f64) -> Unit {
        Unit {
            lo: 0.,
            hi,
            c,
            nl: 0.,
            su: 0.,
            ru: None,
            rd: None,
            sr: None,
            dr: None,
            mu: 1,
            md: 1,
            u0: 0,
            p0: 0.,
            e0: None,
        }
    }
    fn market(g: Unit, d: Vec<f64>) -> Market {
        Market {
            g: vec![g],
            d: vec![d],
            net: None,
        }
    }
    fn same_price(m: &Market) {
        let a = crate::hull::hl(m, None).unwrap();
        let b = hc(m, None).unwrap();
        assert!((a.z - b.z).abs() < 1e-7, "{} != {}", a.z, b.z);
        assert!((a.pi[0][0] - b.pi[0][0]).abs() < 1e-7);
    }

    #[test]
    fn negative_energy_cost_keeps_hull_output_bounded() {
        let m = market(unit(-5., 10.), vec![5.]);
        let s = hc(&m, None).unwrap();
        assert!((s.z + 25.).abs() < 1e-7);
        assert!((s.p[0][0] - 5.).abs() < 1e-7);
        assert!((s.pi[0][0] + 5.).abs() < 1e-7);
    }

    #[test]
    fn interval_hulls_match_at_initial_on_and_down_states() {
        let mut on = unit(10., 10.);
        on.u0 = 1;
        on.p0 = 5.;
        on.mu = 2;
        on.e0 = Some(1);
        same_price(&market(on, vec![5., 0.]));

        let mut down = unit(20., 10.);
        down.md = 2;
        down.e0 = Some(1);
        same_price(&market(down, vec![0., 5.]));
    }
}
