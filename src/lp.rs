//! Sparse linear programs and canonical balance duals; no market-specific rows.
//!
//! Problem: minimise c·x subject to a x ≤ b, ae x = be, lb ≤ x ≤ ub, x_j integer where
//! integer[j]. Solution.dual holds the equality duals; st names the stage that produced
//! them: opt or gap for a direct solve, otherwise a `price` stage.
use highs::{HighsModelStatus, RowProblem, Sense};

pub type Row = Vec<(usize, f64)>;

#[derive(Clone, Debug, Default)]
pub struct Problem {
    pub c: Vec<f64>,
    pub lb: Vec<f64>,
    pub ub: Vec<f64>,
    pub integer: Vec<bool>,
    pub a: Vec<Row>,
    pub b: Vec<f64>,
    pub ae: Vec<Row>,
    pub be: Vec<f64>,
}

#[derive(Clone, Debug)]
pub struct Solution {
    pub z: f64,
    pub x: Vec<f64>,
    pub dual: Vec<f64>,
    pub gap: f64,
    pub lb: f64,
    pub st: &'static str,
}

impl Problem {
    pub fn col(&mut self, c: f64, lo: f64, hi: f64, integer: bool) -> usize {
        let j = self.c.len();
        self.c.push(c);
        self.lb.push(lo);
        self.ub.push(hi);
        self.integer.push(integer);
        j
    }

    pub fn row(&mut self, a: Row, b: f64) {
        self.a.push(a);
        self.b.push(b);
    }

    pub fn eq(&mut self, a: Row, b: f64) {
        self.ae.push(a);
        self.be.push(b);
    }

    /// Copy q's columns and rows into self; returns the index of q's first column.
    pub fn append(&mut self, q: &Problem) -> usize {
        let o = self.c.len();
        self.c.extend(&q.c);
        self.lb.extend(&q.lb);
        self.ub.extend(&q.ub);
        self.integer.extend(&q.integer);
        let shift = |a: &Row| a.iter().map(|&(j, v)| (o + j, v)).collect();
        for (a, &b) in q.a.iter().zip(&q.b) {
            self.row(shift(a), b);
        }
        for (a, &b) in q.ae.iter().zip(&q.be) {
            self.eq(shift(a), b);
        }
        o
    }

    /// Solve with HiGHS. A bound solve disables presolve and tightens feasibility to 1e-9
    /// so that `lb` is the solver's certified objective bound.
    pub fn solve(&self, bound: bool) -> Result<Solution, String> {
        self.solve_with(bound, false, false)
    }

    fn solve_with(&self, bound: bool, no_presolve: bool, ipm: bool) -> Result<Solution, String> {
        let n = self.c.len();
        if self.lb.len() != n
            || self.ub.len() != n
            || self.integer.len() != n
            || self.a.len() != self.b.len()
            || self.ae.len() != self.be.len()
            || self.c.iter().any(|x| !x.is_finite())
            || self
                .lb
                .iter()
                .zip(&self.ub)
                .any(|(a, b)| a.is_nan() || b.is_nan() || a > b)
            || self.b.iter().chain(&self.be).any(|x| !x.is_finite())
            || self
                .a
                .iter()
                .chain(&self.ae)
                .flatten()
                .any(|(j, x)| *j >= n || !x.is_finite())
        {
            return Err("invalid linear program".into());
        }
        let mut p = RowProblem::new();
        let cols: Vec<_> = (0..n)
            .map(|j| {
                p.add_column_with_integrality(self.c[j], self.lb[j]..=self.ub[j], self.integer[j])
            })
            .collect();
        // Combine repeated indices: row assembly may add several line terms to one angle.
        for (rows, rhs, equality) in [(&self.a, &self.b, false), (&self.ae, &self.be, true)] {
            for (a, b) in rows.iter().zip(rhs) {
                let mut terms = std::collections::BTreeMap::<usize, f64>::new();
                for &(j, v) in a {
                    *terms.entry(j).or_default() += v;
                }
                let terms: Vec<_> = terms
                    .into_iter()
                    .filter(|(_, v)| *v != 0.0)
                    .map(|(j, v)| (cols[j], v))
                    .collect();
                if equality {
                    p.add_row(*b..=*b, terms);
                } else {
                    p.add_row(..=*b, terms);
                }
            }
        }
        let mut model = p
            .try_optimise(Sense::Minimise)
            .map_err(|e| format!("model: {e:?}"))?;
        model.set_option("output_flag", false);
        model.set_option("threads", 1_i32);
        model.set_option("mip_rel_gap", 0.0);
        if bound || no_presolve {
            model.set_option("presolve", "off");
        }
        if bound {
            for key in [
                "primal_feasibility_tolerance",
                "dual_feasibility_tolerance",
                "mip_feasibility_tolerance",
            ] {
                model.set_option(key, 1e-9);
            }
        }
        if ipm {
            model.set_option("solver", "ipm");
            model.set_option("run_crossover", "off");
        }
        let solved = model.try_solve().map_err(|e| format!("solve: {e:?}"))?;
        let status = solved.status();
        // Presolve can report infeasibility of a feasible program; confirm without it.
        if status == HighsModelStatus::Infeasible && !bound && !no_presolve {
            return self.solve_with(false, true, ipm);
        }
        if status != HighsModelStatus::Optimal {
            return Err(format!("{status:?}"));
        }
        let integer = self.integer.iter().any(|x| *x);
        let z = solved.objective_value();
        let gap = if integer { solved.mip_gap() } else { 0.0 };
        let lb = if integer {
            solved
                .double_info_value(c"mip_dual_bound")
                .map_err(|e| format!("bound: {e:?}"))?
        } else {
            z
        };
        let s = solved.get_solution();
        Ok(Solution {
            z,
            x: s.columns().to_vec(),
            dual: s.dual_rows()[self.a.len()..].to_vec(),
            gap,
            lb,
            st: if gap == 0.0 { "opt" } else { "gap" },
        })
    }
}

fn ceiling(v: f64) -> f64 {
    v + 1e-9 * v.abs().max(1.0)
}

/// Minimise demand payment over the optimal dual face, then refine balance prices.
/// The last nt ≥ 1 equalities are balance rows; all primal bounds enter the dual
/// explicitly, and stationarity is an equality. Stages: raw (face LP failed), pay
/// (nt > 24: payment only), probe (an interior point of the face agrees with the vertex),
/// walk (lexicographic minimum over the balance prices), part (walk stopped early).
pub fn price(p: &Problem, nt: usize) -> Result<Solution, String> {
    assert!((1..=p.be.len()).contains(&nt) && !p.integer.iter().any(|x| *x));
    let mut p = p.clone();
    for j in 0..p.c.len() {
        if p.lb[j].is_finite() {
            p.row(vec![(j, -1.0)], -p.lb[j]);
        }
        if p.ub[j].is_finite() {
            p.row(vec![(j, 1.0)], p.ub[j]);
        }
        p.lb[j] = f64::NEG_INFINITY;
        p.ub[j] = f64::INFINITY;
    }
    let mut s = p.solve(false)?;
    let (m, e, n) = (p.a.len(), p.ae.len(), p.c.len());
    let mut d = Problem::default();
    for j in 0..m + e {
        let c = if j >= m + e - nt { p.be[j - m] } else { 0.0 };
        d.col(
            c,
            f64::NEG_INFINITY,
            if j < m { 0.0 } else { f64::INFINITY },
            false,
        );
    }
    let mut stationarity = vec![vec![]; n];
    for (i, row) in p.a.iter().chain(&p.ae).enumerate() {
        for &(j, v) in row {
            stationarity[j].push((i, v));
        }
    }
    for (row, c) in stationarity.into_iter().zip(&p.c) {
        d.eq(row, *c);
    }
    d.row(
        p.b.iter()
            .chain(&p.be)
            .enumerate()
            .map(|(j, v)| (j, -v))
            .collect(),
        ceiling(-s.z),
    );
    let Ok(q) = d.solve(false) else {
        s.st = "raw";
        return Ok(s);
    };
    s.dual = q.x[m..].to_vec();
    d.row(
        d.c.iter()
            .enumerate()
            .filter(|(_, v)| **v != 0.0)
            .map(|(j, v)| (j, *v))
            .collect(),
        ceiling(q.z),
    );
    if nt > 24 {
        s.st = "pay";
        return Ok(s);
    }
    let mut probe = d.clone();
    probe.c.fill(0.0);
    for b in &mut probe.b {
        *b += 1e-7 * b.abs().max(1.0);
    }
    if let Ok(q) = probe.solve_with(false, false, true) {
        let delta = q.x[m + e - nt..]
            .iter()
            .zip(&s.dual[e - nt..])
            .map(|(a, b)| (a - b).abs())
            .fold(0.0, f64::max);
        if delta <= 1e-3 {
            s.st = "probe";
            return Ok(s);
        }
    }
    for t in 0..nt {
        d.c.fill(0.0);
        d.c[m + e - nt + t] = 1.0;
        let Ok(q) = d.solve(false) else {
            s.st = "part";
            return Ok(s);
        };
        s.dual = q.x[m..].to_vec();
        d.row(vec![(m + e - nt + t, 1.0)], ceiling(q.z));
    }
    s.st = "walk";
    Ok(s)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn free_column_dual_is_equality() {
        let mut p = Problem::default();
        p.col(7.0, f64::NEG_INFINITY, f64::INFINITY, false);
        p.eq(vec![(0, 1.0)], 3.0);
        let s = price(&p, 1).unwrap();
        assert!((s.z - 21.0).abs() < 1e-8);
        assert!((s.dual[0] - 7.0).abs() < 1e-8);
    }
    #[test]
    fn integer_certificate_and_failure() {
        let mut p = Problem::default();
        p.col(1.0, 0.0, 3.0, true);
        p.row(vec![(0, -1.0)], -1.5);
        let s = p.solve(true).unwrap();
        assert_eq!((s.z, s.lb, s.gap), (2.0, 2.0, 0.0));
        p.row(vec![(0, 1.0)], 1.0);
        assert!(p.solve(false).unwrap_err().contains("Infeasible"));
    }
}
