//! Adaptive demand sensitivity using the same clearing, pricing and settlement route.
use crate::{
    market::Market,
    pricing::{self, Run},
};
use serde::Serialize;

#[derive(Debug, Serialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum Outcome {
    Computed { run: Box<Run> },
    Failed { error: crate::error::Error },
}

#[derive(Debug, Serialize)]
pub struct Point {
    pub demand_scale: f64,
    pub outcome: Outcome,
}

/// The complete input and sampled results. Intervals are exploratory, not certified
/// transition boundaries; a stable sampled commitment may hide intermediate changes.
#[derive(Debug, Serialize)]
pub struct Study {
    pub model_version: &'static str,
    pub market: Market,
    pub points: Vec<Point>,
}

fn point(m: &Market, scale: f64) -> Point {
    let demand = m
        .demand()
        .iter()
        .map(|r| r.iter().map(|v| v * scale).collect())
        .collect();
    let result = Market::new(m.units().to_vec(), demand, Some(m.network().clone()))
        .map_err(crate::error::Error::from)
        .and_then(|m| pricing::run(&m));
    let outcome = match result {
        Ok(run) => Outcome::Computed { run: Box::new(run) },
        Err(error) => Outcome::Failed { error },
    };
    Point {
        demand_scale: scale,
        outcome,
    }
}

/// Prioritize intervals whose sampled commitments or solve availability change,
/// then uplift variation; width prevents one small interval consuming the sample budget.
fn priority(a: &Point, b: &Point) -> f64 {
    let change = match (&a.outcome, &b.outcome) {
        (Outcome::Computed { run: a }, Outcome::Computed { run: b }) => {
            let ua: f64 = a.pay_lmp.up.iter().sum();
            let ub: f64 = b.pay_lmp.up.iter().sum();
            (if a.uc.u != b.uc.u { 10. } else { 0. })
                + (ua - ub).abs() / ua.abs().max(ub.abs()).max(1.)
        }
        (Outcome::Failed { .. }, Outcome::Failed { .. }) => 0.,
        _ => 10.,
    };
    (b.demand_scale - a.demand_scale) * (1. + change)
}

/// Explore 80–100% of the input demand with 17 deterministic solves. Five initial
/// points seed the search; each later solve bisects the highest-priority interval.
/// Scaling is a modeled perturbation of supplied inputs, never an observed demand forecast.
pub fn demand(m: &Market) -> Study {
    let mut points: Vec<_> = (0..5)
        .map(|i| point(m, 0.8 + 0.05 * f64::from(i)))
        .collect();
    while points.len() < 17 {
        let j = points
            .windows(2)
            .enumerate()
            .max_by(|(_, a), (_, b)| priority(&a[0], &a[1]).total_cmp(&priority(&b[0], &b[1])))
            .unwrap()
            .0;
        let next = point(
            m,
            (points[j].demand_scale + points[j + 1].demand_scale) / 2.,
        );
        points.insert(j + 1, next);
    }
    Study {
        model_version: env!("CARGO_PKG_VERSION"),
        market: m.clone(),
        points,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::unit::Unit;
    #[test]
    fn adaptive_samples_preserve_input_and_match_direct_solves() {
        let m = Market::new(vec![Unit::new(0., 100., 5.)], vec![vec![50.]], None).unwrap();
        let s = demand(&m);
        assert_eq!(s.market, m);
        assert_eq!(s.points.len(), 17);
        assert_eq!(s.points.first().unwrap().demand_scale, 0.8);
        assert_eq!(s.points.last().unwrap().demand_scale, 1.);
        for p in s.points {
            let Outcome::Computed { run } = p.outcome else {
                panic!("feasible point failed")
            };
            assert!((run.uc.z - 250. * p.demand_scale).abs() < 1e-7);
            assert!(run.pay_chp.up.iter().sum::<f64>().abs() < 1e-5);
        }
    }
}
