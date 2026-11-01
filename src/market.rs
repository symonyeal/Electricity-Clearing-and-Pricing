//! Validated market data, the nodal balance shared by every program, and the result type.
use crate::{
    lp::{self, Problem, Solution},
    network::Network,
    unit::Unit,
};
use serde::{Deserialize, Serialize};

/// Units g, demand d[b][k] in MW at bus b in hourly period k, and the network.
/// Constructed only through validation; library functions rely on its invariants.
#[derive(Clone, Debug, Deserialize)]
#[serde(try_from = "Input")]
pub struct Market {
    pub g: Vec<Unit>,
    pub d: Vec<Vec<f64>>,
    pub net: Network,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    g: Vec<Unit>,
    d: Vec<Vec<f64>>,
    #[serde(default)]
    net: Option<Network>,
}

impl TryFrom<Input> for Market {
    type Error = String;
    fn try_from(x: Input) -> Result<Self, String> {
        Market::new(x.g, x.d, x.net)
    }
}

/// Output p[i][k] and commitment u[i][k] per unit; prices pi[b][k] per bus; cost z with
/// bound lb and relative gap; st, the solver or price-selection stage.
#[derive(Clone, Debug, Serialize)]
pub struct Sol {
    pub z: f64,
    pub p: Vec<Vec<f64>>,
    pub u: Vec<Vec<f64>>,
    pub pi: Vec<Vec<f64>>,
    pub st: &'static str,
    pub gap: f64,
    pub lb: f64,
}

impl Market {
    /// Validate a market; an omitted network is one bus.
    pub fn new(g: Vec<Unit>, d: Vec<Vec<f64>>, net: Option<Network>) -> Result<Self, String> {
        if g.is_empty() {
            return Err("a market needs at least one unit".into());
        }
        for x in &g {
            x.check()?;
        }
        if d.is_empty()
            || d[0].is_empty()
            || d.iter()
                .any(|r| r.len() != d[0].len() || r.iter().any(|v| !v.is_finite() || *v < 0.))
        {
            return Err("demand must be a non-empty finite non-negative matrix".into());
        }
        let net = match net {
            Some(n) => n,
            None if d.len() == 1 => Network {
                bus: vec![0; g.len()],
                ln: vec![],
            },
            None => return Err("demand at several buses needs a network".into()),
        };
        net.check(g.len(), d.len())?;
        let hi: f64 = g.iter().map(|x| x.hi).sum();
        if (0..d[0].len()).any(|k| d.iter().map(|r| r[k]).sum::<f64>() > hi) {
            return Err("demand exceeds total generating capacity".into());
        }
        Ok(Self { g, d, net })
    }

    /// Number of periods.
    pub fn t(&self) -> usize {
        self.d[0].len()
    }

    /// Append the nodal balances, injections + network imports = d, as the last nb·t
    /// equalities of p. inj: (unit i, period k, column j, coefficient a).
    pub(crate) fn close(
        &self,
        p: &mut Problem,
        inj: impl IntoIterator<Item = (usize, usize, usize, f64)>,
    ) {
        let t = self.t();
        let r0 = p.ae.len();
        for &d in self.d.iter().flatten() {
            p.eq(vec![], d);
        }
        for (i, k, j, a) in inj {
            p.ae[r0 + self.net.bus[i] * t + k].push((j, a));
        }
        for (r, j, a) in self.net.grid(self.d.len(), t, p) {
            p.ae[r0 + r].push((j, a));
        }
    }

    /// Solve a closed continuous program and select its balance prices pi[b][k].
    pub(crate) fn price(&self, p: &Problem) -> Result<(Solution, Vec<Vec<f64>>), String> {
        let n = self.d.len() * self.t();
        let s = lp::price(p, n)?;
        let pi = s.dual[s.dual.len() - n..]
            .chunks(self.t())
            .map(<[f64]>::to_vec)
            .collect();
        Ok((s, pi))
    }
}

/// Unit i's output ceilings cap[i][k], when a capped feasible set is priced.
pub(crate) fn cap(cap: Option<&[Vec<f64>]>, i: usize) -> Option<&[f64]> {
    cap.map(|c| c[i].as_slice())
}
