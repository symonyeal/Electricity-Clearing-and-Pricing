//! Lossless DC lines and directional transfer limits between buses.
//!
//! A DC line [a, b, x, f] carries (θ_a − θ_b)/x from a to b with |flow| ≤ f; θ_0 = 0.
//! A transfer [a, b, [lo, hi]] with a < b carries a free flow in [lo, hi] from a to b.
use crate::lp::Problem;
use serde::Deserialize;

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Network {
    pub bus: Vec<usize>,
    #[serde(default)]
    pub ln: Vec<Line>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(untagged)]
pub enum Line {
    Dc((usize, usize, f64, f64)),
    Ntc((usize, usize, (f64, f64))),
}

impl Network {
    /// Check g unit locations and the lines against nb buses.
    pub fn check(&self, g: usize, nb: usize) -> Result<(), String> {
        if self.bus.len() != g || self.bus.iter().any(|b| *b >= nb) {
            return Err("every unit must sit at a bus of the network".into());
        }
        for l in &self.ln {
            let ok = match *l {
                Line::Dc((a, b, x, f)) => {
                    a < nb && b < nb && a != b && x.is_finite() && x > 0. && f.is_finite() && f > 0.
                }
                Line::Ntc((a, b, (lo, hi))) => {
                    a < b && b < nb && lo.is_finite() && hi.is_finite() && lo < 0. && hi > 0.
                }
            };
            if !ok {
                return Err("line endpoints or limits are invalid".into());
            }
        }
        Ok(())
    }

    /// Add the network's columns and rows for nb buses over t periods to p. Returns its
    /// balance terms (b·t + k, column, coefficient): net import into bus b in period k.
    pub(crate) fn grid(&self, nb: usize, t: usize, p: &mut Problem) -> Vec<(usize, usize, f64)> {
        let th: Vec<usize> = if self.ln.iter().any(|l| matches!(l, Line::Dc(_))) {
            (0..nb * t)
                .map(|j| {
                    let r = if j < t { 0. } else { f64::INFINITY };
                    p.col(0., -r, r, false)
                })
                .collect()
        } else {
            vec![]
        };
        let mut terms = vec![];
        for l in &self.ln {
            match *l {
                Line::Dc((a, b, x, f)) => {
                    for k in 0..t {
                        let (i, j, y) = (th[a * t + k], th[b * t + k], 1. / x);
                        terms.extend([
                            (a * t + k, i, -y),
                            (a * t + k, j, y),
                            (b * t + k, i, y),
                            (b * t + k, j, -y),
                        ]);
                        p.row(vec![(i, y), (j, -y)], f);
                        p.row(vec![(i, -y), (j, y)], f);
                    }
                }
                Line::Ntc((a, b, (lo, hi))) => {
                    for k in 0..t {
                        let j = p.col(0., lo, hi, false);
                        terms.extend([(a * t + k, j, -1.), (b * t + k, j, 1.)]);
                    }
                }
            }
        }
        terms
    }

    /// W(π) = min over network flows of −Σ π_bk · (net import into b in k): the network
    /// term left by relaxing the nodal balances at prices π[b][k].
    pub fn value(&self, t: usize, pi: &[Vec<f64>]) -> Result<f64, String> {
        if self.ln.is_empty() {
            return Ok(0.);
        }
        let mut p = Problem::default();
        for (r, j, a) in self.grid(pi.len(), t, &mut p) {
            p.c[j] -= pi[r / t][r % t] * a;
        }
        Ok(p.solve(false)?.z)
    }
}

#[cfg(test)]
mod tests {
    use crate::{clearing::uc, hull::hc, market::Market, network::*, unit::Unit};

    #[test]
    fn mixed_dc_and_transfer_lines_clear_and_certify() {
        let g = vec![Unit::new(0., 100., 10.), Unit::new(0., 100., 50.)];
        let net = Network {
            bus: vec![0, 2],
            ln: vec![Line::Dc((0, 1, 1., 30.)), Line::Ntc((1, 2, (-20., 20.)))],
        };
        let m = Market::new(g, vec![vec![0.], vec![10.], vec![60.]], Some(net)).unwrap();
        let s = hc(&m, None).unwrap();
        // 30 MW crosses the DC line, 20 MW of it reaches bus 2; unit 1 serves the rest.
        assert!((uc(&m, None).unwrap().z - (30. * 10. + 40. * 50.)).abs() < 1e-6);
        assert!((s.z - 2_300.).abs() < 1e-6);
        assert!(s.gap.abs() < 1e-7);
    }
}
