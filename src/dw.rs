//! Column generation for the unit convex hull, with a whole network master.
use crate::{
    clearing::{self, Market, Sol},
    lp::{self, Problem},
    unit::{self, Unit},
};

const AB: f64 = 1e-5;
const DUP_TOL: f64 = 1e-9;

#[derive(Clone, Debug)]
struct Column {
    p: Vec<f64>,
    u: Vec<f64>,
    cost: f64,
}

/// Generated convex-hull result and certificate information.
#[derive(Clone, Debug, serde::Serialize)]
pub struct Dw {
    pub s: Sol,
    pub k: usize,
    pub ng: usize,
    pub nr: usize,
    pub nk: usize,
    pub na: usize,
    pub rho: Vec<f64>,
    pub tau: f64,
}

fn unit_cost(x: &Unit, p: &[f64], u: &[f64]) -> f64 {
    let mut z = x.c * p.iter().sum::<f64>() + x.nl * u.iter().sum::<f64>();
    let mut prev = f64::from(x.u0);
    for &q in u {
        if q > 0.5 && prev < 0.5 {
            z += x.su;
        }
        prev = q;
    }
    z
}

fn oracle(x: &Unit, t: usize, price: &[f64], cap: Option<&[f64]>) -> Result<(Column, f64), String> {
    let q = unit::oracle(x, t, price, cap);
    let mip = q.solve(true).map_err(|e| format!("unit oracle: {e}"))?;
    let mut vertex = q;
    for j in t..4 * t {
        let y = mip.x[j].round();
        vertex.lb[j] = y;
        vertex.ub[j] = y;
        vertex.integer[j] = false;
    }
    let lp = vertex
        .solve(false)
        .map_err(|e| format!("oracle vertex: {e}"))?;
    let p = lp.x[..t].to_vec();
    let u = lp.x[t..2 * t].to_vec();
    let cost = unit_cost(x, &p, &u);
    Ok((Column { p, u, cost }, mip.lb))
}

fn master(m: &Market, columns: &[Vec<Column>]) -> Result<(Problem, usize), String> {
    let net = m.net.as_ref().unwrap();
    let t = m.d[0].len();
    let g = m.g.len();
    let mut p = Problem::new();
    let mut offsets = Vec::with_capacity(g);
    for set in columns {
        let mut ids = Vec::with_capacity(set.len());
        for c in set {
            ids.push(p.col(c.cost, 0., f64::INFINITY, false));
        }
        offsets.push(ids);
    }
    for ids in &offsets {
        p.eq(ids.iter().map(|j| (*j, 1.)).collect(), 1.);
    }
    let balance_start = p.ae.len();
    for b in 0..net.nb {
        for k in 0..t {
            p.eq(vec![], m.d[b][k]);
        }
    }
    for (i, set) in columns.iter().enumerate() {
        for (j, c) in set.iter().enumerate() {
            for k in 0..t {
                if c.p[k] != 0. {
                    p.ae[balance_start + net.bus[i] * t + k].push((offsets[i][j], c.p[k]));
                }
            }
        }
    }
    net.append(t, balance_start, &mut p);
    Ok((p, offsets.iter().map(Vec::len).sum()))
}

fn reduced_residual(m: &Market, columns: &[Vec<Column>], dual: &[f64], z: f64) -> (f64, f64) {
    let g = m.g.len();
    let t = m.d[0].len();
    let mut r: f64 = 0.;
    for (i, set) in columns.iter().enumerate() {
        for c in set {
            let value: f64 = (0..t)
                .map(|k| dual[g + m.net.as_ref().unwrap().bus[i] * t + k] * c.p[k])
                .sum();
            r = r.max(dual[i] + value - c.cost);
        }
    }
    (r, (1e-9 * z.abs().max(1.) / g.max(1) as f64).max(AB + r))
}

/// Generate hull columns from an integer clearing, reprice each reported dual, and bound it.
pub fn cg(market: &Market, cap: Option<&[Vec<f64>]>) -> Result<Dw, String> {
    let m = market.validated()?;
    let t = m.d[0].len();
    let g = m.g.len();
    let net = m.net.as_ref().unwrap();
    m.check_cap(cap)?;
    let cleared = clearing::uc(&m, cap).map_err(|e| format!("master seed: {e}"))?;
    // MIP feasibility tolerance can leave a 1e-6 MW balance residual on AIC caps.
    // Re-dispatch the commitment before requiring its column to satisfy the master exactly.
    let seed = clearing::lmp(&m, &cleared, cap).map_err(|e| format!("seed dispatch: {e}"))?;
    let mut columns = Vec::with_capacity(g);
    for i in 0..g {
        columns.push(vec![Column {
            p: seed.p[i].clone(),
            u: seed.u[i].clone(),
            cost: unit_cost(&m.g[i], &seed.p[i], &seed.u[i]),
        }]);
    }

    let (mut z, mut y, mut dual, mut st);
    let mut k_solve = 0;
    let mut ng = 0;
    let mut nr = 0;
    let mut selected = false;
    let mut rho: Vec<f64>;
    let mut tau;
    let values;
    loop {
        let (p, ncol) = master(&m, &columns)?;
        let s = if selected {
            lp::price(&p, net.nb * t).map_err(|e| format!("selected master: {e}"))?
        } else {
            lp::price(&p, 0).map_err(|e| format!("restricted master: {e}"))?
        };
        k_solve += 1;
        z = s.z;
        y = s.x[..ncol].to_vec();
        dual = s.dual;
        st = s.st;
        let (_, threshold) = reduced_residual(&m, &columns, &dual, z);
        tau = threshold;

        let mut priced = Vec::with_capacity(g);
        for (i, x) in m.g.iter().enumerate() {
            let prices = &dual[g + net.bus[i] * t..g + (net.bus[i] + 1) * t];
            priced.push(oracle(x, t, prices, cap.map(|c| c[i].as_slice()))?);
        }
        rho = (0..g).map(|i| priced[i].1 - dual[i]).collect();
        if rho.iter().all(|v| *v >= -tau) {
            if selected {
                values = priced.iter().map(|p| p.1).collect::<Vec<_>>();
                break;
            }
            selected = true;
            continue;
        }

        let mut added = 0;
        for i in 0..g {
            let (c, _) = &priced[i];
            let reduced = c.cost
                - (0..t)
                    .map(|q| dual[g + net.bus[i] * t + q] * c.p[q])
                    .sum::<f64>()
                - dual[i];
            if reduced >= -tau {
                continue;
            }
            let exists = columns[i].iter().any(|v| {
                v.p.iter().zip(&c.p).all(|(a, b)| (a - b).abs() <= DUP_TOL)
                    && v.u.iter().zip(&c.u).all(|(a, b)| (a - b).abs() <= DUP_TOL)
                    && (v.cost - c.cost).abs() <= DUP_TOL * c.cost.abs().max(1.)
            });
            if !exists {
                columns[i].push(c.clone());
                added += 1;
            }
        }
        if added == 0 {
            st = "stall".into();
            values = priced.iter().map(|p| p.1).collect::<Vec<_>>();
            break;
        }
        ng += added;
        if selected {
            nr += added;
        }
        selected = false;
    }

    let offsets: Vec<usize> = std::iter::once(0)
        .chain(columns.iter().scan(0usize, |sum, set| {
            *sum += set.len();
            Some(*sum)
        }))
        .collect();
    let mut p = vec![vec![0.; t]; g];
    let mut u = vec![vec![0.; t]; g];
    for i in 0..g {
        for (j, c) in columns[i].iter().enumerate() {
            for q in 0..t {
                p[i][q] += y[offsets[i] + j] * c.p[q];
                u[i][q] += y[offsets[i] + j] * c.u[q];
            }
        }
    }
    let pi: Vec<Vec<f64>> = dual[g..g + net.nb * t]
        .chunks(t)
        .map(|r| r.to_vec())
        .collect();
    let mut lb: f64 = values.iter().sum();
    for b in 0..net.nb {
        for q in 0..t {
            lb += pi[b][q] * m.d[b][q];
        }
    }
    lb += crate::network::value(net, t, &pi)?;
    let gap = (z - lb) / z.abs().max(1.);
    let sol = Sol {
        z,
        p,
        u,
        pi,
        st,
        gap,
        lb,
    };
    Ok(Dw {
        s: sol,
        k: k_solve,
        ng,
        nr,
        nk: columns.iter().map(Vec::len).sum(),
        na: y.iter().filter(|v| **v > 1e-9).count(),
        rho,
        tau,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generated_hull_matches_interval_and_trajectory_hulls() {
        for n in 1..=5 {
            let m = crate::cases::case(n);
            let dw = cg(&m, None).unwrap();
            let hc = crate::hull::hc(&m, None).unwrap();
            let hl = crate::hull::hl(&m, None).unwrap();
            assert!(
                (dw.s.z - hc.z).abs() < 1e-5,
                "case {n}: dw {}, hc {}",
                dw.s.z,
                hc.z
            );
            assert!(
                (dw.s.z - hl.z).abs() < 1e-5,
                "case {n}: dw {}, hl {}",
                dw.s.z,
                hl.z
            );
            assert!(
                dw.s.lb <= dw.s.z + 1e-5,
                "case {n}: {} > {}",
                dw.s.lb,
                dw.s.z
            );
        }
    }

    #[test]
    fn generated_hull_matches_the_restricted_aic_hull() {
        for n in 1..=5 {
            let m = crate::cases::case(n).validated().unwrap();
            let s = clearing::uc(&m, None).unwrap();
            let cap = crate::pricing::pc(&m, &s, 1e-6, None).unwrap();
            let dw = cg(&m, Some(&cap)).unwrap_or_else(|e| panic!("case {n}: {e}"));
            let hc = crate::hull::hc(&m, Some(&cap)).unwrap();
            assert!(
                (dw.s.z - hc.z).abs() < 1e-5,
                "case {n}: dw {}, hc {}",
                dw.s.z,
                hc.z
            );
        }
    }
}
