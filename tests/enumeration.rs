//! Unit commitment against exhaustive enumeration of commitments. Ramps never bind here
//! (they default to hi), so each commitment dispatches by merit order and the check shares
//! no formulation with the program.
use ecp::{clearing::uc, market::Market, unit::Unit};

const N: usize = 3;
const T: usize = 4;

/// Minimum-time feasibility of u, preceded by e periods in state u0.
fn timed(x: &Unit, u: &[bool]) -> bool {
    let (mut s, mut run) = (x.u0 == 1, x.e0.unwrap_or(x.mu.max(x.md)));
    for &b in u {
        if b == s {
            run += 1;
        } else {
            if run < if s { x.mu } else { x.md } {
                return false;
            }
            (s, run) = (b, 1);
        }
    }
    true
}

/// Cost of commitment u (one row per unit) at demand d, None if demand is not met.
fn cost(g: &[Unit], u: &[Vec<bool>], d: &[f64]) -> Option<f64> {
    let mut z = 0.;
    for (x, u) in g.iter().zip(u) {
        let mut s = x.u0 == 1;
        for &b in u {
            z += x.nl * f64::from(b) + if b && !s { x.su } else { 0. };
            s = b;
        }
    }
    for (k, &dk) in d.iter().enumerate() {
        let on: Vec<&Unit> = g
            .iter()
            .zip(u)
            .filter(|(_, u)| u[k])
            .map(|(x, _)| x)
            .collect();
        let (lo, hi) = (
            on.iter().map(|x| x.lo).sum::<f64>(),
            on.iter().map(|x| x.hi).sum::<f64>(),
        );
        if dk < lo - 1e-9 || dk > hi + 1e-9 {
            return None;
        }
        let mut left = dk - lo;
        z += on.iter().map(|x| x.lo * x.c).sum::<f64>();
        let mut order = on;
        order.sort_by(|a, b| a.c.total_cmp(&b.c));
        for x in order {
            let q = left.min(x.hi - x.lo);
            z += q * x.c;
            left -= q;
        }
    }
    Some(z)
}

fn best(g: &[Unit], d: &[f64]) -> Option<f64> {
    let mut z: Option<f64> = None;
    for code in 0..1usize << (N * T) {
        let u: Vec<Vec<bool>> = (0..N)
            .map(|i| (0..T).map(|k| code >> (i * T + k) & 1 == 1).collect())
            .collect();
        if let Some(c) = cost(g, &u, d).filter(|_| g.iter().zip(&u).all(|(x, u)| timed(x, u))) {
            z = Some(z.map_or(c, |z| z.min(c)));
        }
    }
    z
}

#[test]
fn commitment_cost_matches_enumeration() {
    let mut seed = 12345u64;
    let mut r = |n: u64| {
        seed = seed
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        (seed >> 33) % n
    };
    let (mut feasible, mut infeasible) = (0, 0);
    for _ in 0..40 {
        let g: Vec<Unit> = (0..N)
            .map(|_| {
                let lo = 5. * r(3) as f64;
                let mut x = Unit::new(lo, lo + 10. * (1 + r(4)) as f64, 5. + r(30) as f64);
                (x.nl, x.su) = (10. * r(4) as f64, 50. * r(4) as f64);
                (x.mu, x.md) = (1 + r(3) as usize, 1 + r(3) as usize);
                x.u0 = r(2) as u8;
                x.p0 = if x.u0 == 1 { x.lo } else { 0. };
                x.e0 = Some(1 + r(3) as usize);
                x
            })
            .collect();
        let d: Vec<f64> = (0..T).map(|_| 5. * r(14) as f64).collect();
        let Ok(m) = Market::new(g.clone(), vec![d.clone()], None) else {
            continue;
        };
        match (uc(&m, None), best(&g, &d)) {
            (Ok(s), Some(z)) => {
                feasible += 1;
                assert!(
                    (s.z - z).abs() < 1e-5 * z.abs().max(1.),
                    "uc {} != {z}",
                    s.z
                );
            }
            (Err(_), None) => infeasible += 1,
            (a, b) => panic!("uc {:?} vs enumeration {b:?}", a.map(|s| s.z)),
        }
    }
    assert!(
        feasible >= 20,
        "{feasible} feasible, {infeasible} infeasible"
    );
}
