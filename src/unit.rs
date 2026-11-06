//! One generator: offer, operating limits and its complete feasible set.
//!
//! Legend: t periods; p dispatch (MW), u commitment, v start-up, w shut-down; lo, hi output
//! limits; c energy cost; nl no-load cost; su start-up cost; ru, rd ramp up/down; sr, dr
//! start-up and shut-down ramps; mu, md minimum up/down periods; u0, p0 state and output
//! before the horizon; e0 periods spent in state u0. Omitted ramps default to hi and e0 to
//! max(mu, md).
use crate::lp::Problem;
use serde::{Deserialize, Serialize};

const TOL: f64 = 1e-7;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Unit {
    pub lo: f64,
    pub hi: f64,
    pub c: f64,
    #[serde(default)]
    pub nl: f64,
    #[serde(default)]
    pub su: f64,
    #[serde(default)]
    pub ru: Option<f64>,
    #[serde(default)]
    pub rd: Option<f64>,
    #[serde(default)]
    pub sr: Option<f64>,
    #[serde(default)]
    pub dr: Option<f64>,
    #[serde(default = "one")]
    pub mu: usize,
    #[serde(default = "one")]
    pub md: usize,
    #[serde(default)]
    pub u0: u8,
    #[serde(default)]
    pub p0: f64,
    #[serde(default)]
    pub e0: Option<usize>,
}

fn one() -> usize {
    1
}

impl Unit {
    /// A unit with no commitment costs, unlimited ramps and one-period minimum times.
    pub fn new(lo: f64, hi: f64, c: f64) -> Self {
        Self {
            lo,
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

    fn ramps(&self) -> [f64; 4] {
        [self.ru, self.rd, self.sr, self.dr].map(|r| r.unwrap_or(self.hi))
    }

    pub fn e0(&self) -> usize {
        self.e0.unwrap_or(self.mu.max(self.md))
    }

    pub fn check(&self) -> Result<(), String> {
        let r = self.ramps();
        if [self.lo, self.hi, self.c, self.nl, self.su, self.p0]
            .iter()
            .chain(&r)
            .any(|v| !v.is_finite())
        {
            return Err("unit offers, limits and ramps must be finite".into());
        }
        if self.hi <= 0. || self.lo < 0. || self.lo > self.hi {
            return Err("require 0 <= lo <= hi with hi > 0".into());
        }
        if self.nl < 0. || self.su < 0. {
            return Err("no-load and start-up costs must be non-negative".into());
        }
        if r.iter().any(|v| *v <= 0.) {
            return Err("every ramp limit must be positive".into());
        }
        if self.mu == 0 || self.md == 0 || self.u0 > 1 {
            return Err("minimum times must be positive and u0 binary".into());
        }
        if self.u0 == 0 && self.p0 != 0. {
            return Err("a unit that starts offline must start at zero output".into());
        }
        if self.u0 == 1 && !(self.lo..=self.hi).contains(&self.p0) {
            return Err("initial output must lie inside a running unit's limits".into());
        }
        Ok(())
    }
}

/// The unit's feasible set over columns [p | u | v | w], with cost c p + nl u + su v.
/// Initial-state obligations fix u by bounds; cap[k] bounds p_k.
pub(crate) struct Block {
    pub p: Problem,
    pub dispatch: Vec<usize>,
    pub commitment: Vec<usize>,
    pub start: Vec<usize>,
    pub stop: Vec<usize>,
}

impl Block {
    pub fn integrality(&mut self, integer: bool) {
        for &j in self.commitment.iter().chain(&self.start).chain(&self.stop) {
            self.p.integer[j] = integer;
        }
    }
}

pub(crate) fn rows(x: &Unit, t: usize, cap: Option<&[f64]>) -> Block {
    let [ru, rd, sr, dr] = x.ramps();
    let (e0, u0) = (x.e0(), f64::from(x.u0));
    let mut q = Problem::default();
    for _ in 0..t {
        q.col(x.c, 0., x.hi, false);
    }
    for k in 0..t {
        let (lo, hi) = if x.u0 == 1 && k.saturating_add(e0) < x.mu {
            (1., 1.)
        } else if x.u0 == 0 && k.saturating_add(e0) < x.md {
            (0., 0.)
        } else {
            (0., 1.)
        };
        q.col(x.nl, lo, hi, false);
    }
    for _ in 0..t {
        q.col(x.su, 0., 1., false);
    }
    for _ in 0..t {
        q.col(0., 0., 1., false);
    }
    let (p, u, v, w) = (0, t, 2 * t, 3 * t);
    for k in 0..t {
        q.row(vec![(p + k, -1.), (u + k, x.lo)], 0.);
        q.row(vec![(p + k, 1.), (u + k, -x.hi)], 0.);
        q.row(vec![(p + k, 1.), (u + k, -x.hi), (v + k, x.hi - sr)], 0.);
        if k + 1 < t {
            q.row(
                vec![(p + k, 1.), (u + k, -x.hi), (w + k + 1, x.hi - dr)],
                0.,
            );
        }
        if k > 0 {
            q.row(
                vec![
                    (p + k, 1.),
                    (p + k - 1, -1.),
                    (u + k - 1, -ru),
                    (v + k, -sr),
                ],
                0.,
            );
            q.row(
                vec![(p + k - 1, 1.), (p + k, -1.), (u + k, -rd), (w + k, -dr)],
                0.,
            );
        } else {
            q.row(vec![(p, 1.), (v, -sr)], x.p0 + ru * u0);
            q.row(vec![(p, -1.), (u, -rd), (w, -dr)], -x.p0);
        }
        q.row(vec![(v + k, 1.), (w + k, 1.)], 1.);
        q.row(vec![(v + k, 1.), (u + k, -1.)], 0.);
        q.row(vec![(w + k, 1.), (u + k, 1.)], 1.);
        let mut a = vec![(u + k, -1.)];
        a.extend((k.saturating_sub(x.mu - 1)..=k).map(|j| (v + j, 1.)));
        q.row(a, 0.);
        let mut a = vec![(u + k, 1.)];
        a.extend((k.saturating_sub(x.md - 1)..=k).map(|j| (w + j, 1.)));
        q.row(a, 1.);
        if let Some(cap) = cap {
            q.row(vec![(p + k, 1.)], cap[k]);
        }
    }
    for k in 0..t {
        let mut a = vec![(v + k, 1.), (w + k, -1.), (u + k, -1.)];
        if k > 0 {
            a.push((u + k - 1, 1.));
        }
        q.eq(a, if k == 0 { -u0 } else { 0. });
    }
    Block {
        p: q,
        dispatch: (0..t).collect(),
        commitment: (t..2 * t).collect(),
        start: (2 * t..3 * t).collect(),
        stop: (3 * t..4 * t).collect(),
    }
}

/// The unit's self-schedule at prices pi: its feasible set with revenue pi·p subtracted.
pub(crate) fn oracle(x: &Unit, t: usize, pi: &[f64], cap: Option<&[f64]>) -> Problem {
    let mut p = rows(x, t, cap);
    for (&j, &v) in p.dispatch.iter().zip(pi) {
        p.p.c[j] -= v;
    }
    p.integrality(true);
    p.p
}

/// Fix binary schedule u in `rows`: returns the dispatch block {p : a p ≤ b, 0 ≤ p ≤ hi}
/// over t columns and its fixed cost nl Σu + su Σv, or None when u breaks the unit's limits.
pub fn trajectory(x: &Unit, t: usize, u: &[f64], cap: Option<&[f64]>) -> Option<(Problem, f64)> {
    if t == 0
        || x.check().is_err()
        || u.len() != t
        || u.iter().any(|v| *v != 0. && *v != 1.)
        || cap.is_some_and(|c| c.len() != t || c.iter().any(|v| !v.is_finite() || *v < 0.))
    {
        return None;
    }
    let full = rows(x, t, cap).p;
    if (0..t).any(|k| u[k] < full.lb[t + k] || u[k] > full.ub[t + k]) {
        return None;
    }
    // v and w follow from u, so the transition equalities hold by construction.
    let mut y = u.to_vec();
    let mut prev = f64::from(x.u0);
    y.extend(
        u.iter()
            .map(|&q| (q - std::mem::replace(&mut prev, q)).max(0.)),
    );
    prev = f64::from(x.u0);
    y.extend(
        u.iter()
            .map(|&q| (std::mem::replace(&mut prev, q) - q).max(0.)),
    );
    let mut q = Problem::default();
    for j in 0..t {
        q.col(full.c[j], full.lb[j], full.ub[j], false);
    }
    for (a, &b) in full.a.iter().zip(&full.b) {
        let mut r = vec![];
        let mut b = b;
        for &(j, val) in a {
            if j < t {
                r.push((j, val));
            } else {
                b -= val * y[j - t];
            }
        }
        if !r.is_empty() {
            q.row(r, b);
        } else if b < -TOL {
            return None;
        }
    }
    let k = x.nl * y[..t].iter().sum::<f64>() + x.su * y[t..2 * t].iter().sum::<f64>();
    Some((q, k))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn auxiliary_column_is_not_a_commitment_variable() {
        let mut q = rows(&Unit::new(0., 10., 5.), 1, None);
        let j = q.p.col(0., 0., 2., false);
        q.integrality(true);
        assert!(!q.p.integer[j]);
        assert!(!q.p.integer[q.dispatch[0]]);
        assert!(
            q.commitment
                .iter()
                .chain(&q.start)
                .chain(&q.stop)
                .all(|&j| q.p.integer[j])
        );
    }
    #[test]
    fn trajectory_fixes_schedule_and_respects_minimum_up_time() {
        let x = Unit {
            nl: 3.,
            su: 7.,
            ..Unit::new(10., 50., 20.)
        };
        let (q, k) = trajectory(&x, 1, &[1.], None).unwrap();
        assert_eq!(k, 10.);
        assert_eq!(q.a.len(), q.b.len());
        assert!(!q.a.is_empty());
        let slow = Unit { mu: 2, ..x };
        assert!(trajectory(&slow, 2, &[1., 0.], None).is_none());
    }
}
