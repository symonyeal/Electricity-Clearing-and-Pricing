//! Numerical outcomes and model/solver faults are distinct at library boundaries.
use serde::Serialize;

#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(tag = "kind", content = "detail", rename_all = "snake_case")]
pub enum Error {
    Invalid(String),
    Solver(String),
    Infeasible,
    Unbounded,
    UnboundedOrInfeasible,
    Limited,
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Invalid(s) | Self::Solver(s) => f.write_str(s),
            Self::Infeasible => f.write_str("infeasible: the market has no feasible schedule"),
            Self::Unbounded => f.write_str("the program is unbounded"),
            Self::UnboundedOrInfeasible => f.write_str("unbounded or infeasible program"),
            Self::Limited => f.write_str("the solver stopped at its limit"),
        }
    }
}
impl std::error::Error for Error {}
impl From<String> for Error {
    fn from(s: String) -> Self {
        Self::Invalid(s)
    }
}
impl From<&str> for Error {
    fn from(s: &str) -> Self {
        Self::Invalid(s.into())
    }
}
impl From<Error> for String {
    fn from(e: Error) -> Self {
        e.to_string()
    }
}
