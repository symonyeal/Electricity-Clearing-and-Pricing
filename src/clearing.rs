//! Integer clearing, its continuous relaxation and fixed-commitment dispatch.
//!
//! Each program stacks one block per unit, whose first t columns are dispatch, and closes
//! the nodal balances over them.
use crate::{
    lp::Problem,
    market::{Market, Sol, cap},
    unit,
};

fn stack(m: &Market, blocks: impl IntoIterator<Item = Problem>) -> (Problem, Vec<usize>) {
    let t = m.t();
    let mut p = Problem::default();
    let o: Vec<usize> = blocks.into_iter().map(|q| p.append(&q)).collect();
    m.close(
        &mut p,
        o.iter()
            .enumerate()
            .flat_map(|(i, &j)| (0..t).map(move |k| (i, k, j + k, 1.))),
    );
    (p, o)
}

/// The commitment program over every unit's full feasible set.
fn system(m: &Market, ceil: Option<&[Vec<f64>]>, integer: bool) -> (Problem, Vec<usize>) {
    let t = m.t();
    stack(
        m,
        m.g.iter().enumerate().map(|(i, x)| {
            let mut q = unit::rows(x, t, cap(ceil, i));
            q.integer[t..].fill(integer);
            q
        }),
    )
}

/// x[o_i + s + k] for each unit i and period k, with magnitudes below 1e-9 set to zero.
fn take(x: &[f64], o: &[usize], s: usize, t: usize) -> Vec<Vec<f64>> {
    o.iter()
        .map(|&j| {
            x[j + s..j + s + t]
                .iter()
                .map(|&v| if v.abs() < 1e-9 { 0. } else { v })
                .collect()
        })
        .collect()
}

/// Minimise commitment and dispatch cost on the market's complete feasible set.
pub fn uc(m: &Market, ceil: Option<&[Vec<f64>]>) -> Result<Sol, String> {
    let t = m.t();
    let (p, o) = system(m, ceil, true);
    let s = p.solve(false)?;
    let u = take(&s.x, &o, t, t)
        .into_iter()
        .map(|r| r.into_iter().map(f64::round).collect())
        .collect();
    Ok(Sol {
        z: s.z,
        p: take(&s.x, &o, 0, t),
        u,
        pi: vec![],
        st: s.st,
        gap: s.gap,
        lb: s.lb,
    })
}

/// Relax commitment integrality and select canonical balance prices.
pub fn rx(m: &Market, ceil: Option<&[Vec<f64>]>) -> Result<Sol, String> {
    let t = m.t();
    let (p, o) = system(m, ceil, false);
    let (s, pi) = m.price(&p)?;
    Ok(Sol {
        z: s.z,
        p: take(&s.x, &o, 0, t),
        u: take(&s.x, &o, t, t),
        pi,
        st: s.st,
        gap: 0.,
        lb: s.z,
    })
}

/// Re-dispatch with binary commitment s.u fixed and select its balance prices; the
/// commitment's fixed costs are added after pricing.
pub fn lmp(m: &Market, s: &Sol, ceil: Option<&[Vec<f64>]>) -> Result<Sol, String> {
    let t = m.t();
    let mut k = 0.;
    let mut blocks = Vec::with_capacity(m.g.len());
    for (i, x) in m.g.iter().enumerate() {
        let (q, f) = unit::trajectory(x, t, &s.u[i], cap(ceil, i))
            .ok_or("the fixed commitment breaks a unit's own limits")?;
        k += f;
        blocks.push(q);
    }
    let (p, o) = stack(m, blocks);
    let (r, pi) = m.price(&p)?;
    Ok(Sol {
        z: r.z + k,
        p: take(&r.x, &o, 0, t),
        u: s.u.clone(),
        pi,
        st: r.st,
        gap: 0.,
        lb: r.z + k,
    })
}
