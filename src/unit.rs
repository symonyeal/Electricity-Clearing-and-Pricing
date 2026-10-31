use crate::lp::Problem;
use serde::{Deserialize, Serialize};

/// One generator's offer, operating limits, and state immediately before the horizon.
#[derive(Clone, Debug, Serialize, Deserialize)]
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
    pub fn filled(&self) -> Self {
        let mut x = self.clone();
        x.ru = Some(x.ru.unwrap_or(x.hi));
        x.rd = Some(x.rd.unwrap_or(x.hi));
        x.sr = Some(x.sr.unwrap_or(x.hi));
        x.dr = Some(x.dr.unwrap_or(x.hi));
        x.e0 = Some(x.e0.unwrap_or(x.mu.max(x.md)));
        x
    }
    pub fn validate(&self) -> Result<Self, String> {
        let x = self.filled();
        let vals = [
            x.lo,
            x.hi,
            x.c,
            x.nl,
            x.su,
            x.p0,
            x.ru.unwrap(),
            x.rd.unwrap(),
            x.sr.unwrap(),
            x.dr.unwrap(),
        ];
        if vals.iter().any(|v| !v.is_finite()) {
            return Err("unit offers, limits and ramps must be finite".into());
        }
        if x.hi <= 0. || x.lo < 0. || x.lo > x.hi {
            return Err("require 0 <= lo <= hi with hi > 0".into());
        }
        if x.nl < 0. || x.su < 0. {
            return Err("no-load and start-up costs must be non-negative".into());
        }
        if [x.ru.unwrap(), x.rd.unwrap(), x.sr.unwrap(), x.dr.unwrap()]
            .iter()
            .any(|v| *v <= 0.)
        {
            return Err("every ramp limit must be positive".into());
        }
        if x.mu == 0 || x.md == 0 || x.u0 > 1 {
            return Err("minimum times must be positive and u0 binary".into());
        }
        if x.u0 == 0 && x.p0 != 0. {
            return Err("a unit that starts offline must start at zero output".into());
        }
        if x.u0 == 1 && !(x.lo..=x.hi).contains(&x.p0) {
            return Err("initial output must lie inside a running unit's limits".into());
        }
        Ok(x)
    }
}

/// Unit inequalities in [p | u | start | stop] order, with rhs b.
pub fn rows(x: &Unit, t: usize, cap: Option<&[f64]>) -> Problem {
    let x = x.filled();
    let mut q = Problem::new();
    for _ in 0..t {
        q.col(x.c, 0., x.hi, false);
    }
    for k in 0..t {
        let e0 = x.e0.unwrap();
        let (lo, hi) = if x.u0 == 1 && e0 < x.mu && k < x.mu - e0 {
            (1., 1.)
        } else if x.u0 == 0 && e0 < x.md && k < x.md - e0 {
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
        let mut row = vec![];
        row.extend([(p + k, -1.), (u + k, x.lo)]);
        q.row(row, 0.);
        q.row(vec![(p + k, 1.), (u + k, -x.hi)], 0.);
        q.row(
            vec![(p + k, 1.), (u + k, -x.hi), (v + k, x.hi - x.sr.unwrap())],
            0.,
        );
        if k + 1 < t {
            q.row(
                vec![
                    (p + k, 1.),
                    (u + k, -x.hi),
                    (w + k + 1, x.hi - x.dr.unwrap()),
                ],
                0.,
            );
        }
        if k > 0 {
            q.row(
                vec![
                    (p + k, 1.),
                    (p + k - 1, -1.),
                    (u + k - 1, -x.ru.unwrap()),
                    (v + k, -x.sr.unwrap()),
                ],
                0.,
            );
            q.row(
                vec![
                    (p + k - 1, 1.),
                    (p + k, -1.),
                    (u + k, -x.rd.unwrap()),
                    (w + k, -x.dr.unwrap()),
                ],
                0.,
            );
        } else {
            q.row(
                vec![(p, 1.), (v, -x.sr.unwrap())],
                x.p0 + x.ru.unwrap() * f64::from(x.u0),
            );
            q.row(
                vec![(p, -1.), (u, -x.rd.unwrap()), (w, -x.dr.unwrap())],
                -x.p0,
            );
        }
        q.row(vec![(v + k, 1.), (w + k, 1.)], 1.);
        q.row(vec![(v + k, 1.), (u + k, -1.)], 0.);
        q.row(vec![(w + k, 1.), (u + k, 1.)], 1.);
        let mut a = vec![(u + k, -1.)];
        for j in k.saturating_sub(x.mu - 1)..=k {
            a.push((v + j, 1.));
        }
        q.row(a, 0.);
        let mut a = vec![(u + k, 1.)];
        for j in k.saturating_sub(x.md - 1)..=k {
            a.push((w + j, 1.));
        }
        q.row(a, 1.);
        if let Some(cap) = cap {
            q.row(vec![(p + k, 1.)], cap[k]);
        }
    }
    for k in 0..t {
        let mut a = vec![(2 * t + k, 1.), (3 * t + k, -1.), (t + k, -1.)];
        if k > 0 {
            a.push((t + k - 1, 1.));
        }
        q.eq(a, if k == 0 { -(x.u0 as f64) } else { 0. });
    }
    q
}

/// A unit self-scheduling problem: energy revenue is subtracted from its own cost.
pub(crate) fn oracle(x: &Unit, t: usize, pi: &[f64], cap: Option<&[f64]>) -> Problem {
    let mut p = rows(x, t, cap);
    for k in 0..t {
        p.c[k] -= pi[k];
    }
    p.integer[t..].fill(true);
    p
}

/// Fix a binary schedule and return its dispatch polytope and fixed cost.
pub fn trajectory(
    x: &Unit,
    t: usize,
    u: &[f64],
    cap: Option<&[f64]>,
) -> Option<(Vec<Vec<f64>>, Vec<f64>, f64)> {
    if u.len() != t || u.iter().any(|v| ![0., 1.].contains(v)) {
        return None;
    }
    let x = x.filled();
    let mut v = vec![0.; t];
    let mut w = vec![0.; t];
    let mut prev = f64::from(x.u0);
    for k in 0..t {
        v[k] = (u[k] - prev).max(0.);
        w[k] = (prev - u[k]).max(0.);
        prev = u[k];
    }
    let full = rows(&x, t, cap);
    let mut a = vec![vec![0.; t]; full.b.len()];
    let mut b = full.b.clone();
    for (i, r) in full.a.iter().enumerate() {
        for &(j, val) in r {
            if j < t {
                a[i][j] = val;
            } else {
                let y = if j < 2 * t {
                    u[j - t]
                } else if j < 3 * t {
                    v[j - 2 * t]
                } else {
                    w[j - 3 * t]
                };
                b[i] -= val * y;
            }
        }
    }
    let mut eq_ok = true;
    for k in 0..t {
        let prev_u = if k == 0 { f64::from(x.u0) } else { u[k - 1] };
        if (v[k] - w[k] - u[k] + prev_u).abs() > 1e-7 {
            eq_ok = false;
        }
        if x.u0 == 1 && x.e0.unwrap() < x.mu && k < x.mu - x.e0.unwrap() && u[k] < 1. {
            eq_ok = false;
        }
        if x.u0 == 0 && x.e0.unwrap() < x.md && k < x.md - x.e0.unwrap() && u[k] > 0. {
            eq_ok = false;
        }
    }
    if !eq_ok {
        return None;
    }
    if (0..a.len()).any(|i| a[i].iter().all(|v| v.abs() == 0.) && b[i] < -1e-7) {
        return None;
    }
    let keep: Vec<usize> = (0..a.len())
        .filter(|&i| a[i].iter().any(|v| v.abs() > 0.))
        .collect();
    let aa = keep.iter().map(|&i| a[i].clone()).collect();
    let bb = keep.iter().map(|&i| b[i]).collect();
    Some((
        aa,
        bb,
        x.nl * u.iter().sum::<f64>() + x.su * v.iter().sum::<f64>(),
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn unit() -> Unit {
        Unit {
            lo: 10.,
            hi: 50.,
            c: 20.,
            nl: 3.,
            su: 7.,
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
    #[test]
    fn fills_optional_operating_data_from_source_defaults() {
        let x = unit().filled();
        assert_eq!(x.ru, Some(50.));
        assert_eq!(x.e0, Some(1));
    }
    #[test]
    fn trajectory_rows_express_fixed_schedule_dispatch() {
        let x = unit();
        let (a, b, k) = trajectory(&x, 1, &[1.], None).unwrap();
        assert_eq!(k, 10.);
        assert!(!a.is_empty());
        assert_eq!(a.len(), b.len());
        let mut slow = x.clone();
        slow.mu = 2;
        assert!(trajectory(&slow, 2, &[1., 0.], None).is_none());
    }
}
