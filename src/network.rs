use crate::lp::Problem;
use serde::{Deserialize, Serialize};

/// A DC grid or a set of directional interzonal transfer limits.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Network {
    pub bus: Vec<usize>,
    pub ln: Vec<Line>,
    pub nb: usize,
    #[serde(default = "dc")]
    pub fm: String,
    #[serde(default)]
    pub zn: Vec<String>,
}
fn dc() -> String {
    "dc".into()
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Line {
    Dc((usize, usize, f64, f64)),
    Ntc((usize, usize, (f64, f64))),
}
impl Network {
    pub fn validate(&self, g: usize) -> Result<Self, String> {
        if self.nb == 0 || self.bus.len() != g || self.bus.iter().any(|b| *b >= self.nb) {
            return Err("every unit must sit at a bus of the network".into());
        }
        if self.fm != "dc" && self.fm != "ntc" {
            return Err("the line model must be dc or ntc".into());
        }
        for l in &self.ln {
            match (self.fm.as_str(), l) {
                ("dc", Line::Dc((a, b, x, lim)))
                    if *a < self.nb
                        && *b < self.nb
                        && a != b
                        && x.is_finite()
                        && *x > 0.
                        && lim.is_finite()
                        && *lim > 0. => {}
                ("ntc", Line::Ntc((a, b, (lo, hi))))
                    if *a < *b
                        && *b < self.nb
                        && lo.is_finite()
                        && hi.is_finite()
                        && *lo < 0.
                        && *hi > 0. => {}
                _ => return Err("line shape or limits do not match the network model".into()),
            }
        }
        if !self.zn.is_empty()
            && (self.zn.len() != self.nb
                || self
                    .zn
                    .iter()
                    .collect::<std::collections::HashSet<_>>()
                    .len()
                    != self.nb)
        {
            return Err("zone keys must be one per zone and distinct".into());
        }
        Ok(self.clone())
    }
    /// Add flow variables and their coefficients to existing nodal balance equations.
    pub fn append(&self, t: usize, balance_start: usize, p: &mut Problem) {
        if self.ln.is_empty() {
            return;
        }
        if self.fm == "dc" {
            let mut th = vec![vec![0; t]; self.nb];
            for b in 0..self.nb {
                for k in 0..t {
                    th[b][k] = p.col(
                        0.,
                        if b == 0 { 0. } else { f64::NEG_INFINITY },
                        if b == 0 { 0. } else { f64::INFINITY },
                        false,
                    );
                }
            }
            for line in &self.ln {
                if let Line::Dc((a, b, x, lim)) = line {
                    for k in 0..t {
                        p.ae[balance_start + a * t + k]
                            .extend([(th[*a][k], -1. / x), (th[*b][k], 1. / x)]);
                        p.ae[balance_start + b * t + k]
                            .extend([(th[*a][k], 1. / x), (th[*b][k], -1. / x)]);
                        p.row(vec![(th[*a][k], 1. / x), (th[*b][k], -1. / x)], *lim);
                        p.row(vec![(th[*a][k], -1. / x), (th[*b][k], 1. / x)], *lim);
                    }
                }
            }
        } else {
            for line in &self.ln {
                if let Line::Ntc((a, b, (lo, hi))) = line {
                    for k in 0..t {
                        let f = p.col(0., *lo, *hi, false);
                        p.ae[balance_start + a * t + k].push((f, -1.));
                        p.ae[balance_start + b * t + k].push((f, 1.));
                    }
                }
            }
        }
    }
}

/// Minimise the network term left by relaxing nodal balances at prices pi.
pub fn value(net: &Network, t: usize, pi: &[Vec<f64>]) -> Result<f64, String> {
    if pi.len() != net.nb || pi.iter().any(|r| r.len() != t) {
        return Err("pi must have one price per bus and period".into());
    }
    if net.ln.is_empty() {
        return Ok(0.0);
    }
    let mut p = Problem::new();
    if net.fm == "dc" {
        let mut th = vec![vec![0; t]; net.nb];
        for b in 0..net.nb {
            for k in 0..t {
                let c = net
                    .ln
                    .iter()
                    .filter_map(|l| {
                        if let Line::Dc((a, q, x, _)) = l {
                            Some(if *a == b {
                                -(pi[*q][k] - pi[*a][k]) / x
                            } else if *q == b {
                                -(pi[*a][k] - pi[*q][k]) / x
                            } else {
                                0.
                            })
                        } else {
                            None
                        }
                    })
                    .sum();
                th[b][k] = p.col(
                    c,
                    if b == 0 { 0. } else { f64::NEG_INFINITY },
                    if b == 0 { 0. } else { f64::INFINITY },
                    false,
                );
            }
        }
        for l in &net.ln {
            if let Line::Dc((a, b, x, lim)) = l {
                for k in 0..t {
                    p.row(vec![(th[*a][k], 1. / x), (th[*b][k], -1. / x)], *lim);
                    p.row(vec![(th[*a][k], -1. / x), (th[*b][k], 1. / x)], *lim);
                }
            }
        }
    } else {
        for l in &net.ln {
            if let Line::Ntc((a, b, (lo, hi))) = l {
                for k in 0..t {
                    p.col(pi[*a][k] - pi[*b][k], *lo, *hi, false);
                }
            }
        }
    }
    Ok(p.solve(false)?.z)
}
