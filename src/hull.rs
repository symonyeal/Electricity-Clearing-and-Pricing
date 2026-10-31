//! Direct generator hulls from trajectories and interval graphs.
//!
//! `hl` uses Balas' union formulation over every feasible on/off trajectory. `hc`
//! uses the equivalent source-to-sink interval graph, whose run arcs number O(T²).
use crate::clearing::{Market, Sol};
use crate::{
    lp::{self, Problem},
    unit::{self, Unit},
};

const ENUM_T: usize = 16;
const HULL_VARIABLES: usize = 100_000;
const TOL: f64 = 1e-7;

#[derive(Clone)]
struct Disjunct {
    a: Vec<Vec<f64>>,
    b: Vec<f64>,
    k: f64,
    u: Vec<f64>,
}
#[derive(Clone)]
struct Arc {
    from: usize,
    to: usize,
    s: usize,
    e: usize,
    a: Vec<Vec<f64>>,
    b: Vec<f64>,
    k: f64,
}

fn bits(t: usize) -> Result<Vec<Vec<f64>>, String> {
    if t > ENUM_T {
        return Err(format!(
            "trajectory enumeration is limited to {ENUM_T} periods"
        ));
    }
    Ok((0..(1usize << t))
        .map(|mask| (0..t).map(|k| ((mask >> k) & 1) as f64).collect())
        .collect())
}

fn disjuncts(x: &Unit, t: usize, cap: Option<&[f64]>) -> Result<Vec<Disjunct>, String> {
    let mut out = Vec::new();
    for u in bits(t)? {
        if let Some((a, b, k)) = unit::trajectory(x, t, &u, cap) {
            out.push(Disjunct { a, b, k, u });
        }
    }
    if out.is_empty() {
        return Err("a unit has no feasible schedule".into());
    }
    Ok(out)
}

fn interval(
    x: &Unit,
    t: usize,
    s: usize,
    e: usize,
    cap: Option<&[f64]>,
) -> Option<(Vec<Vec<f64>>, Vec<f64>, f64)> {
    let mut u = vec![0.; t];
    u[s..=e].fill(1.);
    let (a, b, k) = unit::trajectory(x, t, &u, cap)?;
    let mut aa = Vec::new();
    let mut bb = Vec::new();
    for (row, rhs) in a.iter().zip(b) {
        let q = row[s..=e].to_vec();
        if q.iter().all(|v| v.abs() <= TOL) {
            if rhs < -TOL {
                return None;
            }
        } else {
            aa.push(q);
            bb.push(rhs);
        }
    }
    Some((aa, bb, k))
}

/// Balas trajectory hull; at most 16 periods per unit.
pub fn hl(m: &Market, cap: Option<&[Vec<f64>]>) -> Result<Sol, String> {
    let m = m.clone().validated()?;
    let t = m.d[0].len();
    let net = m.net.as_ref().unwrap();
    m.check_cap(cap)?;
    let sets: Vec<Vec<Disjunct>> =
        m.g.iter()
            .enumerate()
            .map(|(i, x)| disjuncts(x, t, cap.map(|c| c[i].as_slice())))
            .collect::<Result<_, _>>()?;
    let count: usize = sets.iter().map(|s| s.len() * (t + 1)).sum();
    if count > HULL_VARIABLES {
        return Err(format!(
            "hl is limited to {HULL_VARIABLES} variables; this market needs {count}"
        ));
    }
    let mut p = Problem::new();
    let mut offsets = Vec::new();
    for (i, set) in sets.iter().enumerate() {
        let mut os = Vec::new();
        for d in set {
            let o = p.col(m.g[i].c, 0., f64::INFINITY, false);
            for _ in 1..t {
                p.col(m.g[i].c, 0., f64::INFINITY, false);
            }
            let l = p.col(d.k, 0., 1., false);
            os.push((o, l, d));
        }
        offsets.push(os);
    }
    for set in &offsets {
        let terms: Vec<_> = set.iter().map(|(_, l, _)| (*l, 1.)).collect();
        p.eq(terms, 1.);
    }
    let balance_start = p.ae.len();
    for b in 0..net.nb {
        for k in 0..t {
            p.eq(vec![], m.d[b][k]);
        }
    }
    for (i, set) in offsets.iter().enumerate() {
        for (o, _, _) in set {
            for k in 0..t {
                p.ae[balance_start + net.bus[i] * t + k].push((*o + k, 1.));
            }
        }
    }
    for set in &offsets {
        for (o, l, d) in set {
            for (a, b) in d.a.iter().zip(&d.b) {
                let mut terms: Vec<_> = a
                    .iter()
                    .enumerate()
                    .filter(|(_, v)| v.abs() > 0.)
                    .map(|(k, v)| (*o + k, *v))
                    .collect();
                terms.push((*l, -*b));
                p.row(terms, 0.);
            }
        }
    }
    net.append(t, balance_start, &mut p);
    let r = lp::price(&p, net.nb * t)?;
    let mut outp = vec![vec![0.; t]; m.g.len()];
    let mut outu = outp.clone();
    for (i, set) in offsets.iter().enumerate() {
        for (o, l, d) in set {
            for k in 0..t {
                outp[i][k] += r.x[o + k];
                outu[i][k] += r.x[*l] * d.u[k];
            }
        }
    }
    Ok(Sol {
        z: r.z,
        p: outp,
        u: outu,
        pi: r.dual[r.dual.len() - net.nb * t..]
            .chunks(t)
            .map(|q| q.to_vec())
            .collect(),
        st: r.st,
        gap: r.gap,
        lb: r.lb,
    })
}

/// Exact interval-graph hull with O(T^2) candidate run arcs.
pub fn hc(m: &Market, cap: Option<&[Vec<f64>]>) -> Result<Sol, String> {
    let m = m.clone().validated()?;
    let t = m.d[0].len();
    let net = m.net.as_ref().unwrap();
    m.check_cap(cap)?;
    let mut sets: Vec<Vec<Arc>> = Vec::new();
    for x0 in &m.g {
        let x = x0.filled();
        let mut arcs = Vec::new();
        for q in 0..t {
            arcs.push(Arc {
                from: q,
                to: q + 1,
                s: 0,
                e: 0,
                a: vec![],
                b: vec![],
                k: 0.,
            });
        }
        if x.u0 == 1 {
            for e in 0..t {
                if let Some((a, b, k)) =
                    interval(&x, t, 0, e, cap.map(|c| c[sets.len()].as_slice()))
                {
                    arcs.push(Arc {
                        from: t + 1,
                        to: (e + 1 + x.md).min(t),
                        s: 0,
                        e,
                        a,
                        b,
                        k,
                    });
                }
            }
            let u = vec![0.; t];
            if let Some((_, b, k)) =
                unit::trajectory(&x, t, &u, cap.map(|c| c[sets.len()].as_slice()))
                && b.iter().all(|z| *z >= -TOL)
            {
                arcs.push(Arc {
                    from: t + 1,
                    to: x.md.min(t),
                    s: 0,
                    e: 0,
                    a: vec![],
                    b: vec![],
                    k,
                });
            }
        } else {
            let init = (x.md.saturating_sub(x.e0.unwrap_or(x.md))).min(t);
            arcs.push(Arc {
                from: t + 1,
                to: init,
                s: 0,
                e: 0,
                a: vec![],
                b: vec![],
                k: 0.,
            });
        }
        let mut y = x.clone();
        y.u0 = 0;
        y.p0 = 0.;
        y.e0 = Some(y.mu.max(y.md));
        for s in 0..t {
            for e in s..t {
                if let Some((a, b, k)) =
                    interval(&y, t, s, e, cap.map(|c| c[sets.len()].as_slice()))
                {
                    arcs.push(Arc {
                        from: s,
                        to: (e + 1 + x.md).min(t),
                        s,
                        e,
                        a,
                        b,
                        k,
                    });
                }
            }
        }
        sets.push(arcs);
    }
    let mut p = Problem::new();
    let mut os = Vec::<Vec<(usize, usize, &Arc)>>::new();
    for (i, set) in sets.iter().enumerate() {
        let mut v = Vec::new();
        for a in set {
            let n = if a.a.is_empty() { 0 } else { a.e - a.s + 1 };
            let o = if n > 0 {
                let o = p.col(m.g[i].c, 0., f64::INFINITY, false);
                for _ in 1..n {
                    p.col(m.g[i].c, 0., f64::INFINITY, false);
                }
                o
            } else {
                p.c.len()
            };
            let lam = p.col(a.k, 0., 1., false);
            v.push((o, lam, a));
        }
        os.push(v);
    }
    let w = t + 2;
    let balance_start = p.ae.len();
    for _ in 0..m.g.len() * w + net.nb * t {
        p.eq(vec![], 0.);
    }
    for i in 0..m.g.len() {
        p.be[i * w + t + 1] = 1.;
    }
    for b in 0..net.nb {
        for k in 0..t {
            p.be[m.g.len() * w + b * t + k] = m.d[b][k];
        }
    }
    for (i, set) in os.iter().enumerate() {
        for (o, l, a) in set {
            for (q, r) in [(a.from, 1.), (a.to, -1.)] {
                if q != t {
                    p.ae[balance_start + i * w + q].push((*l, r));
                }
            }
            if !a.a.is_empty() {
                for k in a.s..=a.e {
                    p.ae[balance_start + m.g.len() * w + net.bus[i] * t + k]
                        .push((*o + k - a.s, 1.));
                }
                for (ar, br) in a.a.iter().zip(&a.b) {
                    let mut terms: Vec<_> = ar
                        .iter()
                        .enumerate()
                        .filter(|(_, v)| v.abs() > 0.)
                        .map(|(j, v)| (*o + j, *v))
                        .collect();
                    terms.push((*l, -*br));
                    p.row(terms, 0.);
                }
            }
        }
    }
    let bs = balance_start + m.g.len() * w;
    net.append(t, bs, &mut p);
    let r = lp::price(&p, net.nb * t)?;
    let mut outp = vec![vec![0.; t]; m.g.len()];
    let mut outu = outp.clone();
    for (i, set) in os.iter().enumerate() {
        for (o, l, a) in set {
            if !a.a.is_empty() {
                for k in a.s..=a.e {
                    outp[i][k] += r.x[o + k - a.s];
                    outu[i][k] += r.x[*l];
                }
            }
        }
    }
    Ok(Sol {
        z: r.z,
        p: outp,
        u: outu,
        pi: r.dual[r.dual.len() - net.nb * t..]
            .chunks(t)
            .map(|q| q.to_vec())
            .collect(),
        st: r.st,
        gap: r.gap,
        lb: r.lb,
    })
}
