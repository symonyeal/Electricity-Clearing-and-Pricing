//! Integer clearing, its continuous relaxation and fixed-commitment dispatch.
use crate::error::Error;
use crate::{
    lp::Problem,
    market::{Clearing, Market, Sol, cap},
    unit::{self, Block},
};

struct System {
    p: Problem,
    dispatch: Vec<Vec<usize>>,
    commitment: Vec<Vec<usize>>,
    balances: Vec<usize>,
}

fn stack(m: &Market, blocks: impl IntoIterator<Item = Block>) -> System {
    let mut p = Problem::default();
    let (mut dispatch, mut commitment) = (vec![], vec![]);
    for q in blocks {
        let o = p.append(&q.p);
        dispatch.push(q.dispatch.iter().map(|j| o + j).collect::<Vec<_>>());
        commitment.push(q.commitment.iter().map(|j| o + j).collect::<Vec<_>>());
    }
    let balances = m.close(
        &mut p,
        dispatch
            .iter()
            .enumerate()
            .flat_map(|(i, r)| r.iter().enumerate().map(move |(k, &j)| (i, k, j, 1.))),
    );
    System {
        p,
        dispatch,
        commitment,
        balances,
    }
}

fn system(m: &Market, ceil: Option<&[Vec<f64>]>, integer: bool) -> Result<System, Error> {
    m.caps(ceil)?;
    Ok(stack(
        m,
        m.g.iter().enumerate().map(|(i, x)| {
            let mut q = unit::rows(x, m.t(), cap(ceil, i));
            q.integrality(integer);
            q
        }),
    ))
}

fn take(x: &[f64], cols: &[Vec<usize>]) -> Vec<Vec<f64>> {
    cols.iter()
        .map(|r| {
            r.iter()
                .map(|&j| if x[j].abs() < 1e-9 { 0. } else { x[j] })
                .collect()
        })
        .collect()
}

/// Minimise commitment and dispatch cost. Only this binary result can be settled or fixed.
///
/// ```compile_fail
/// # use ecp::{clearing, market::Market, unit::Unit};
/// # let m = Market::new(vec![Unit::new(0.,10.,5.)],vec![vec![5.]],None).unwrap();
/// let relaxation = clearing::rx(&m, None).unwrap();
/// clearing::lmp(&m, &relaxation, None); // fractional result is not a Clearing
/// ```
pub fn uc(m: &Market, ceil: Option<&[Vec<f64>]>) -> Result<Clearing, Error> {
    let q = system(m, ceil, true)?;
    let s = q.p.solve(false)?;
    let mut u = take(&s.x, &q.commitment);
    for v in u.iter_mut().flatten() {
        if (*v - v.round()).abs() > 1e-6 {
            return Err("solver returned a nonbinary commitment".into());
        }
        *v = v.round();
    }
    Ok(Clearing {
        market: m.clone(),
        sol: Sol {
            z: s.z,
            p: take(&s.x, &q.dispatch),
            u,
            pi: vec![],
            status: s.status,
            price_selection: None,
            gap: s.gap,
            lb: s.lb,
        },
    })
}

/// Relax commitment integrality and select balance prices.
pub fn rx(m: &Market, ceil: Option<&[Vec<f64>]>) -> Result<Sol, Error> {
    let q = system(m, ceil, false)?;
    let (s, pi, selection) = m.price(&q.p, &q.balances)?;
    Ok(Sol {
        z: s.z,
        p: take(&s.x, &q.dispatch),
        u: take(&s.x, &q.commitment),
        pi,
        status: s.status,
        price_selection: Some(selection),
        gap: 0.,
        lb: s.z,
    })
}

/// Re-dispatch a binary clearing from this exact market and select its balance prices.
pub fn lmp(m: &Market, s: &Clearing, ceil: Option<&[Vec<f64>]>) -> Result<Clearing, Error> {
    s.check(m)?;
    m.caps(ceil)?;
    let mut fixed = 0.;
    let mut blocks = vec![];
    for (i, x) in m.g.iter().enumerate() {
        let (p, f) = unit::trajectory(x, m.t(), &s.u[i], cap(ceil, i))
            .ok_or("the fixed commitment breaks a unit's own limits")?;
        fixed += f;
        blocks.push(Block {
            p,
            dispatch: (0..m.t()).collect(),
            commitment: vec![],
            start: vec![],
            stop: vec![],
        });
    }
    let q = stack(m, blocks);
    let (r, pi, selection) = m.price(&q.p, &q.balances)?;
    Ok(Clearing {
        market: m.clone(),
        sol: Sol {
            z: r.z + fixed,
            p: take(&r.x, &q.dispatch),
            u: s.u.clone(),
            pi,
            status: r.status,
            price_selection: Some(selection),
            gap: 0.,
            lb: r.z + fixed,
        },
    })
}
