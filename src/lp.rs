//! Sparse linear programs, HiGHS translation and primal certificates.
//!
//! Problem: minimise c·x subject to a x ≤ b, ae x = be, lb ≤ x ≤ ub, x_j integer where
//! integer[j]. Solution.dual holds the equality duals. Only an optimal outcome produces
//! a solution; infeasible, unbounded, limited and solver-fault outcomes are typed errors.
use crate::error::Error;
use highs::{HighsModelStatus, RowProblem, Sense};
use serde::Serialize;

/// Tolerance for feasibility and sign tests on model quantities.
pub const TOL: f64 = 1e-7;

#[derive(Clone, Copy, Debug, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Status {
    Optimal,
}

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
    pub status: Status,
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
    pub fn solve(&self, bound: bool) -> Result<Solution, Error> {
        self.solve_with(bound, false, false)
    }

    pub(crate) fn solve_with(
        &self,
        bound: bool,
        no_presolve: bool,
        ipm: bool,
    ) -> Result<Solution, Error> {
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
            .map_err(|e| Error::Solver(format!("model: {e:?}")))?;
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
        let solved = model
            .try_solve()
            .map_err(|e| Error::Solver(format!("solve: {e:?}")))?;
        let status = solved.status();
        // Presolve can report infeasibility of a feasible program; confirm without it.
        if status == HighsModelStatus::Infeasible && !bound && !no_presolve {
            return self.solve_with(false, true, ipm);
        }
        if status != HighsModelStatus::Optimal {
            return Err(match status {
                HighsModelStatus::Infeasible => Error::Infeasible,
                HighsModelStatus::Unbounded => Error::Unbounded,
                HighsModelStatus::UnboundedOrInfeasible => Error::UnboundedOrInfeasible,
                HighsModelStatus::ReachedTimeLimit
                | HighsModelStatus::ReachedIterationLimit
                | HighsModelStatus::ReachedSolutionLimit
                | HighsModelStatus::ReachedInterrupt
                | HighsModelStatus::ReachedMemoryLimit
                | HighsModelStatus::ObjectiveBound
                | HighsModelStatus::ObjectiveTarget => Error::Limited,
                _ => Error::Solver(format!("{status:?}")),
            });
        }
        let integer = self.integer.iter().any(|x| *x);
        let z = solved.objective_value();
        let gap = if integer { solved.mip_gap() } else { 0.0 };
        let lb = if integer {
            solved
                .double_info_value(c"mip_dual_bound")
                .map_err(|e| Error::Solver(format!("bound: {e:?}")))?
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
            status: Status::Optimal,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pricing::price;
    #[test]
    fn prices_follow_handles_when_an_equality_is_appended() {
        let mut p = Problem::default();
        p.col(7., 0., 10., false);
        p.eq(vec![(0, 1.)], 3.);
        let (a, _) = price(&p, &[0]).unwrap();
        let j = p.col(0., 0., 0., false);
        p.eq(vec![(j, 1.)], 0.);
        let (b, _) = price(&p, &[0]).unwrap();
        assert!((a.dual[0] - b.dual[0]).abs() < 1e-8);
        assert!((b.dual[0] - 7.).abs() < 1e-8);
    }
    #[test]
    fn free_column_dual_is_equality() {
        let mut p = Problem::default();
        p.col(7.0, f64::NEG_INFINITY, f64::INFINITY, false);
        p.eq(vec![(0, 1.0)], 3.0);
        let (s, _) = price(&p, &[0]).unwrap();
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
        assert_eq!(p.solve(false).unwrap_err(), Error::Infeasible);
    }

    #[test]
    fn unbounded_outcome_is_distinct_from_a_solver_fault() {
        let mut p = Problem::default();
        p.col(-1., 0., f64::INFINITY, false);
        assert_eq!(p.solve(false).unwrap_err(), Error::Unbounded);
    }
}
