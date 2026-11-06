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
            _ => write!(f, "{self:?}"),
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
