use crate::{
    lp::{Problem, price},
    network::Network,
    unit::{Unit, rows, trajectory},
};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Market {
    pub g: Vec<Unit>,
    pub d: Vec<Vec<f64>>,
    #[serde(default)]
    pub net: Option<Network>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Sol {
    pub z: f64,
    pub p: Vec<Vec<f64>>,
    pub u: Vec<Vec<f64>>,
    pub pi: Vec<Vec<f64>>,
    pub st: String,
    pub gap: f64,
    pub lb: f64,
}

impl Market {
    pub(crate) fn check_cap(&self, cap: Option<&[Vec<f64>]>) -> Result<(), String> {
        if let Some(c) = cap
            && (c.len() != self.g.len()
                || c.iter().any(|r| {
                    r.len() != self.d[0].len() || r.iter().any(|v| !v.is_finite() || *v < 0.0)
                }))
        {
            return Err("cap must give one finite non-negative ceiling per unit and period".into());
        }
        Ok(())
    }
    pub fn validated(&self) -> Result<Self, String> {
        if self.g.is_empty() {
            return Err("a market needs at least one unit".into());
        }
        let g = self
            .g
            .iter()
            .map(Unit::validate)
            .collect::<Result<Vec<_>, _>>()?;
        if self.d.is_empty()
            || self.d[0].is_empty()
            || self
                .d
                .iter()
                .any(|r| r.len() != self.d[0].len() || r.iter().any(|v| !v.is_finite() || *v < 0.))
        {
            return Err("demand must be a non-empty finite non-negative matrix".into());
        }
        let net = match &self.net {
            Some(n) => n.validate(g.len())?,
            None => Network {
                bus: vec![0; g.len()],
                ln: vec![],
                nb: 1,
                fm: "dc".into(),
                zn: vec![],
            },
        };
        if self.d.len() != net.nb {
            return Err("demand must have one row per bus".into());
        }
        let t = self.d[0].len();
        if (0..t)
            .any(|k| self.d.iter().map(|r| r[k]).sum::<f64>() > g.iter().map(|u| u.hi).sum::<f64>())
        {
            return Err("demand exceeds total generating capacity".into());
        }
        Ok(Self {
            g,
            d: self.d.clone(),
            net: Some(net),
        })
    }
}

fn system(
    m: &Market,
    cap: Option<&[Vec<f64>]>,
    integer: bool,
) -> Result<(Problem, usize, usize), String> {
    let m = m.validated()?;
    let net = m.net.as_ref().unwrap();
    let t = m.d[0].len();
    let g = m.g.len();
    m.check_cap(cap)?;
    let mut p = Problem::new();
    for (i, x) in m.g.iter().enumerate() {
        let off = p.c.len();
        let r = rows(x, t, cap.map(|c| c[i].as_slice()));
        p.c.extend(&r.c);
        p.lb.extend(&r.lb);
        p.ub.extend(&r.ub);
        p.integer.extend(
            r.integer
                .iter()
                .enumerate()
                .map(|(j, flag)| *flag || (integer && j >= t && j < 4 * t)),
        );
        for (row, rhs) in r.a.iter().zip(&r.b) {
            p.row(row.iter().map(|(a, b)| (off + *a, *b)).collect(), *rhs);
        }
        for (row, rhs) in r.ae.iter().zip(&r.be) {
            p.eq(row.iter().map(|(a, b)| (off + *a, *b)).collect(), *rhs);
        }
    }
    let bal = p.ae.len();
    for b in 0..net.nb {
        for k in 0..t {
            p.eq(vec![], m.d[b][k]);
        }
    }
    for (i, _) in m.g.iter().enumerate() {
        let off = i * 4 * t;
        for k in 0..t {
            p.ae[bal + net.bus[i] * t + k].push((off + k, 1.));
        }
    }
    net.append(t, bal, &mut p);
    Ok((p, t, g))
}

fn unpack(s: &crate::lp::Solution, t: usize, g: usize) -> (Vec<Vec<f64>>, Vec<Vec<f64>>) {
    let mut p = vec![vec![0.; t]; g];
    let mut u = p.clone();
    for i in 0..g {
        for k in 0..t {
            p[i][k] = s.x[4 * t * i + k];
            u[i][k] = s.x[4 * t * i + t + k];
        }
    }
    (p, u)
}
/// Minimise commitment and dispatch cost on the market's complete feasible set.
pub fn uc(m: &Market, cap: Option<&[Vec<f64>]>) -> Result<Sol, String> {
    let (p, t, g) = system(m, cap, true)?;
    let s = p.solve(false)?;
    let (mut out, mut u) = unpack(&s, t, g);
    for row in &mut out {
        for v in row {
            if v.abs() < 1e-9 {
                *v = 0.;
            }
        }
    }
    for row in &mut u {
        for v in row {
            *v = v.round();
        }
    }
    Ok(Sol {
        z: s.z,
        p: out,
        u,
        pi: vec![],
        st: s.st,
        gap: s.gap,
        lb: s.lb,
    })
}

/// Enumerate joint binary schedules and solve the dispatch LP for each feasible schedule.
pub fn en(m: &Market, cap: Option<&[Vec<f64>]>) -> Result<Sol, String> {
    let m = m.validated()?;
    let t = m.d[0].len();
    let g = m.g.len();
    let _ = system(&m, cap, false)?;
    if t > 16 {
        return Err("en is limited to 16 periods".into());
    }
    let mut schedules = Vec::with_capacity(g);
    let mut total = 1usize;
    for (i, x) in m.g.iter().enumerate() {
        let mut cs = Vec::new();
        for mask in 0..(1usize << t) {
            let u: Vec<f64> = (0..t).map(|k| ((mask >> k) & 1) as f64).collect();
            if trajectory(x, t, &u, cap.map(|c| c[i].as_slice())).is_some() {
                cs.push(u);
            }
        }
        if cs.is_empty() {
            return Err("a unit has no feasible schedule".into());
        }
        total = total.saturating_mul(cs.len());
        if total > 20_000 {
            return Err(
                "en is limited to 20000 joint commitments; this market exceeds the limit".into(),
            );
        }
        schedules.push(cs);
    }
    let mut best: Option<Sol> = None;
    for mut index in 0..total {
        let mut u = Vec::with_capacity(g);
        for cs in &schedules {
            u.push(cs[index % cs.len()].clone());
            index /= cs.len();
        }
        let (mut p, _, _) = system(&m, cap, false)?;
        for i in 0..g {
            for k in 0..t {
                let j = 4 * t * i + t + k;
                p.lb[j] = u[i][k];
                p.ub[j] = u[i][k];
            }
        }
        let solved = match p.solve(false) {
            Ok(s) => s,
            Err(e) if e.contains("Infeasible") => continue,
            Err(e) => return Err(e),
        };
        if best.as_ref().is_none_or(|b| solved.z < b.z - 1e-9) {
            let (dispatch, commit) = unpack(&solved, t, g);
            best = Some(Sol {
                z: solved.z,
                p: dispatch,
                u: commit,
                pi: vec![],
                st: "enum".into(),
                gap: 0.,
                lb: solved.z,
            });
        }
    }
    best.ok_or_else(|| "this demand did not clear [infeasible: no trajectory serves it]".into())
}
/// Relax commitment integrality and select canonical dual prices for the balance rows.
pub fn rx(m: &Market, cap: Option<&[Vec<f64>]>) -> Result<Sol, String> {
    let (p, t, g) = system(m, cap, false)?;
    let s = price(&p, m.d.iter().map(|r| r.len()).sum::<usize>())?;
    let (out, u) = unpack(&s, t, g);
    let pi = s.dual[s.dual.len() - m.d.iter().map(|r| r.len()).sum::<usize>()..]
        .chunks(t)
        .map(|r| r.to_vec())
        .collect();
    Ok(Sol {
        z: s.z,
        p: out,
        u,
        pi,
        st: s.st,
        gap: 0.,
        lb: s.z,
    })
}
/// Re-dispatch with the given binary commitment fixed, then select its balance duals.
pub fn lmp(m: &Market, s: &Sol, cap: Option<&[Vec<f64>]>) -> Result<Sol, String> {
    let m = m.validated()?;
    if s.u.len() != m.g.len() {
        return Err("commitment has wrong unit count".into());
    }
    let t = m.d[0].len();
    let g = m.g.len();
    let net = m.net.as_ref().unwrap();
    m.check_cap(cap)?;
    let mut p = Problem::new();
    let mut offsets = Vec::with_capacity(g);
    let mut fixed = 0.;
    for i in 0..g {
        if s.u[i].len() != t {
            return Err("commitment has wrong horizon".into());
        }
        if s.u[i].iter().any(|u| ![0., 1.].contains(u)) {
            return Err("commitment must be binary".into());
        }
        let Some((a, b, k)) = trajectory(&m.g[i], t, &s.u[i], cap.map(|c| c[i].as_slice())) else {
            return Err("the fixed commitment breaks a unit's own limits".into());
        };
        fixed += k;
        let off = p.c.len();
        offsets.push(off);
        for _ in 0..t {
            p.col(m.g[i].c, 0., m.g[i].hi, false);
        }
        for (row, rhs) in a.iter().zip(&b) {
            p.row(
                row.iter()
                    .enumerate()
                    .filter(|(_, v)| v.abs() > 0.)
                    .map(|(j, v)| (off + j, *v))
                    .collect(),
                *rhs,
            );
        }
    }
    let bal = p.ae.len();
    for b in 0..net.nb {
        for k in 0..t {
            p.eq(vec![], m.d[b][k]);
        }
    }
    for (i, off) in offsets.iter().enumerate() {
        for k in 0..t {
            p.ae[bal + net.bus[i] * t + k].push((*off + k, 1.));
        }
    }
    net.append(t, bal, &mut p);
    let lp = price(&p, net.nb * t)?;
    let mut dispatch = vec![vec![0.; t]; g];
    for i in 0..g {
        for k in 0..t {
            dispatch[i][k] = lp.x[offsets[i] + k];
            if dispatch[i][k].abs() < 1e-9 {
                dispatch[i][k] = 0.;
            }
        }
    }
    let pi = lp.dual[lp.dual.len() - net.nb * t..]
        .chunks(t)
        .map(|r| r.to_vec())
        .collect();
    Ok(Sol {
        z: lp.z + fixed,
        p: dispatch,
        u: s.u.clone(),
        pi,
        st: lp.st,
        gap: 0.,
        lb: lp.z + fixed,
    })
}
