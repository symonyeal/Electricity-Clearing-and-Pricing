//! Convex-hull prices from each unit's interval graph (Yu, Guan and Chen 2020).
//!
//! Nodes 0..t are periods at which a unit is free to start, t is the sink and t + 1 the
//! source. An idle arc spends one period off; an on-arc runs an interval [s, s + n) and then
//! spends md periods off, carrying the perspective of that interval's dispatch polytope.
//! A unit's hull is the flow polytope of its graph: O(T²) arcs and O(T³) dispatch columns.
use crate::error::Error;
use crate::{
    lp::Problem,
    market::{Market, Sol, cap},
    unit::{self, Unit},
};

const TOL: f64 = 1e-7;

/// Arc from → to, running periods s..s + n (n = 0 when idle) under rows a q ≤ b λ.
struct Arc {
    from: usize,
    to: usize,
    s: usize,
    n: usize,
    q: Problem,
    k: f64,
}

/// Dispatch rows of the single on-interval [s, s + n) and its fixed cost, or None.
fn interval(
    y: &Unit,
    t: usize,
    s: usize,
    n: usize,
    ceil: Option<&[f64]>,
) -> Option<(Problem, f64)> {
    let mut u = vec![0.; t];
    u[s..s + n].fill(1.);
    let (q, k) = unit::trajectory(y, t, &u, ceil)?;
    let mut r = Problem::default();
    for (a, &b) in q.a.iter().zip(&q.b) {
        let a: Vec<_> = a
            .iter()
            .filter(|(j, _)| (s..s + n).contains(j))
            .map(|&(j, v)| (j - s, v))
            .collect();
        if !a.is_empty() {
            r.row(a, b);
        } else if b < -TOL {
            return None;
        }
    }
    Some((r, k))
}

fn arcs(x: &Unit, t: usize, ceil: Option<&[f64]>) -> Vec<Arc> {
    let on = |y: &Unit, from: usize, s: usize, n: usize| {
        interval(y, t, s, n, ceil).map(|(q, k)| Arc {
            from,
            to: (s + n + x.md).min(t),
            s,
            n,
            q,
            k,
        })
    };
    let idle = |from, to| Arc {
        from,
        to,
        s: 0,
        n: 0,
        q: Problem::default(),
        k: 0.,
    };
    let mut v: Vec<Arc> = (0..t).map(|q| idle(q, q + 1)).collect();
    if x.u0 == 1 {
        // Continue the initial run for n periods, or stop at once (n = 0).
        v.extend((1..=t).filter_map(|n| on(x, t + 1, 0, n)));
        v.extend(on(x, t + 1, 0, 0));
    } else {
        v.push(idle(t + 1, x.md.saturating_sub(x.e0()).min(t)));
    }
    // Later runs start from rest, free of the initial state.
    let y = Unit {
        u0: 0,
        p0: 0.,
        e0: None,
        ..x.clone()
    };
    for s in 0..t {
        v.extend((1..=t - s).filter_map(|n| on(&y, s, s, n)));
    }
    v
}

/// Price the product of the units' exact hulls. lb is the Lagrangian value at the
/// selected price, which certifies it: lb = z at a convex-hull price.
pub fn hc(m: &Market, ceil: Option<&[Vec<f64>]>) -> Result<Sol, Error> {
    m.caps(ceil)?;
    let t = m.t();
    let w = t + 2;
    let sets: Vec<Vec<Arc>> =
        m.g.iter()
            .enumerate()
            .map(|(i, x)| arcs(x, t, cap(ceil, i)))
            .collect();
    let mut p = Problem::default();
    // Columns per arc: n dispatch columns from o, then its flow λ.
    let cols: Vec<Vec<(usize, usize)>> = sets
        .iter()
        .zip(&m.g)
        .map(|(set, x)| {
            set.iter()
                .map(|a| {
                    let o = p.c.len();
                    for _ in 0..a.n {
                        p.col(x.c, 0., f64::INFINITY, false);
                    }
                    (o, p.col(a.k, 0., 1., false))
                })
                .collect()
        })
        .collect();
    // Flow conservation: one unit of flow leaves each source; the sink row stays empty.
    for (set, c) in sets.iter().zip(&cols) {
        let r0 = p.ae.len();
        for q in 0..w {
            p.eq(vec![], if q == t + 1 { 1. } else { 0. });
        }
        for (a, &(_, l)) in set.iter().zip(c) {
            p.ae[r0 + a.from].push((l, 1.));
            if a.to != t {
                p.ae[r0 + a.to].push((l, -1.));
            }
        }
    }
    let mut inj = vec![];
    for (i, (set, c)) in sets.iter().zip(&cols).enumerate() {
        for (a, &(o, l)) in set.iter().zip(c) {
            for (r, &b) in a.q.a.iter().zip(&a.q.b) {
                let mut terms: Vec<_> = r.iter().map(|&(j, v)| (o + j, v)).collect();
                terms.push((l, -b));
                p.row(terms, 0.);
            }
            inj.extend((0..a.n).map(|j| (i, a.s + j, o + j, 1.)));
        }
    }
    let balances = m.close(&mut p, inj);
    let (r, pi, selection) = m.price(&p, &balances)?;
    let mut out = vec![vec![0.; t]; m.g.len()];
    let mut u = out.clone();
    for (i, (set, c)) in sets.iter().zip(&cols).enumerate() {
        for (a, &(o, l)) in set.iter().zip(c) {
            for j in 0..a.n {
                out[i][a.s + j] += r.x[o + j];
                u[i][a.s + j] += r.x[l];
            }
        }
    }
    let lb = qd(m, &pi, ceil)?;
    Ok(Sol {
        z: r.z,
        p: out,
        u,
        pi,
        status: r.status,
        price_selection: Some(selection),
        gap: (r.z - lb) / r.z.abs().max(1.),
        lb,
    })
}

/// Lagrangian value q(π) = π·d + Σ_i min self-schedule cost_i(π) + W(π) from certified
/// unit bounds; q(π) ≤ clearing cost for every π (weak duality).
pub fn qd(m: &Market, pi: &[Vec<f64>], ceil: Option<&[Vec<f64>]>) -> Result<f64, Error> {
    m.prices(pi)?;
    m.caps(ceil)?;
    let t = m.t();
    let mut z: f64 = pi
        .iter()
        .flatten()
        .zip(m.d.iter().flatten())
        .map(|(a, b)| a * b)
        .sum();
    for (i, x) in m.g.iter().enumerate() {
        z += unit::oracle(x, t, &pi[m.net.bus[i]], cap(ceil, i))
            .solve(true)?
            .lb;
    }
    Ok(z + m.net.value(t, pi)?)
}
