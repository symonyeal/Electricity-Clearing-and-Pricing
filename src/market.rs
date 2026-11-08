//! Validated market data, the nodal balance shared by every program, and the result type.
use crate::{
    error::Error,
    lp::{Selection, Status},
};
use crate::{
    lp::{Problem, Solution},
    network::Network,
    unit::Unit,
};
use serde::{Deserialize, Serialize};

/// Units g, demand d[b][k] in MW at bus b in hourly period k, and the network.
/// Constructed only through validation; library functions rely on its invariants.
///
/// ```compile_fail
/// # use ecp::{market::Market, unit::Unit};
/// let mut m = Market::new(vec![Unit::new(0.,10.,5.)],vec![vec![5.]],None).unwrap();
/// m.d.clear();
/// ```
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(try_from = "Input")]
pub struct Market {
    pub(crate) g: Vec<Unit>,
    pub(crate) d: Vec<Vec<f64>>,
    pub(crate) net: Network,
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
/// bound lb and relative gap. Primal solve status and price-selection quality are separate.
#[derive(Clone, Debug, Serialize)]
pub struct Sol {
    pub z: f64,
    pub p: Vec<Vec<f64>>,
    pub u: Vec<Vec<f64>>,
    pub pi: Vec<Vec<f64>>,
    pub status: Status,
    pub price_selection: Option<Selection>,
    pub gap: f64,
    pub lb: f64,
}

/// An immutable binary clearing, attached to the exact validated market it clears.
/// Fractional relaxations cannot be passed to fixed-commitment pricing or settlement.
#[derive(Clone, Debug, Serialize)]
#[serde(transparent)]
pub struct Clearing {
    pub(crate) sol: Sol,
    #[serde(skip)]
    pub(crate) market: Market,
}

impl std::ops::Deref for Clearing {
    type Target = Sol;
    fn deref(&self) -> &Sol {
        &self.sol
    }
}

impl Clearing {
    pub(crate) fn check(&self, m: &Market) -> Result<(), Error> {
        if self.market != *m {
            return Err("clearing belongs to a different market".into());
        }
        Ok(())
    }
}

impl Market {
    pub fn units(&self) -> &[Unit] {
        &self.g
    }
    pub fn demand(&self) -> &[Vec<f64>] {
        &self.d
    }
    pub fn network(&self) -> &Network {
        &self.net
    }

    /// Require finite bus-by-period prices before any certificate or settlement.
    pub(crate) fn prices(&self, pi: &[Vec<f64>]) -> Result<(), Error> {
        matrix(pi, self.d.len(), self.t(), "prices", false).map_err(Into::into)
    }

    pub(crate) fn caps(&self, cap: Option<&[Vec<f64>]>) -> Result<(), Error> {
        if let Some(cap) = cap {
            matrix(cap, self.g.len(), self.t(), "caps", true)?;
        }
        Ok(())
    }
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

    /// Append the nodal balances, injections + network imports = d; return their row ids.
    /// inj: (unit i, period k, column j, coefficient a).
    pub(crate) fn close(
        &self,
        p: &mut Problem,
        inj: impl IntoIterator<Item = (usize, usize, usize, f64)>,
    ) -> Vec<usize> {
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
        (r0..r0 + self.d.len() * t).collect()
    }

    /// Solve a closed continuous program and select its balance prices pi[b][k].
    pub(crate) fn price(
        &self,
        p: &Problem,
        rows: &[usize],
    ) -> Result<(Solution, Vec<Vec<f64>>, Selection), Error> {
        let (s, selection) = crate::lp::price(p, rows)?;
        let prices: Vec<_> = rows.iter().map(|&j| s.dual[j]).collect();
        let pi = prices.chunks(self.t()).map(<[f64]>::to_vec).collect();
        Ok((s, pi, selection))
    }
}

fn matrix(x: &[Vec<f64>], n: usize, t: usize, name: &str, nonnegative: bool) -> Result<(), String> {
    if x.len() != n
        || x.iter()
            .any(|r| r.len() != t || r.iter().any(|v| !v.is_finite() || (nonnegative && *v < 0.)))
    {
        return Err(format!(
            "{name} must be a finite {n} by {t} matrix{}",
            if nonnegative {
                " with nonnegative entries"
            } else {
                ""
            }
        ));
    }
    Ok(())
}

/// Unit i's output ceilings cap[i][k], when a capped feasible set is priced.
pub(crate) fn cap(cap: Option<&[Vec<f64>]>, i: usize) -> Option<&[f64]> {
    cap.map(|c| c[i].as_slice())
}
