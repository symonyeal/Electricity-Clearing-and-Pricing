use crate::{
    clearing::Market,
    network::{Line, Network},
    unit::Unit,
};
fn u(
    lo: f64,
    hi: f64,
    c: f64,
    nl: f64,
    su: f64,
    ru: Option<f64>,
    rd: Option<f64>,
    sr: Option<f64>,
    dr: Option<f64>,
    mu: usize,
    md: usize,
) -> Unit {
    Unit {
        lo,
        hi,
        c,
        nl,
        su,
        ru,
        rd,
        sr,
        dr,
        mu,
        md,
        u0: 0,
        p0: 0.,
        e0: None,
    }
}
pub fn case(n: usize) -> Market {
    match n {
        1 => Market {
            g: vec![
                u(10., 50., 50., 0., 100., None, None, None, None, 1, 1),
                u(50., 50., 10., 0., 100., None, None, None, None, 1, 1),
            ],
            d: vec![vec![35.]],
            net: None,
        },
        2 => Market {
            g: vec![
                u(
                    0.,
                    100.,
                    60.,
                    0.,
                    0.,
                    Some(120.),
                    Some(120.),
                    Some(120.),
                    Some(120.),
                    1,
                    1,
                ),
                u(
                    0.,
                    100.,
                    56.,
                    600.,
                    0.,
                    Some(60.),
                    Some(60.),
                    Some(60.),
                    Some(60.),
                    1,
                    1,
                ),
            ],
            d: vec![vec![70., 100., 170.]],
            net: None,
        },
        3 => Market {
            g: vec![
                u(
                    0.,
                    100.,
                    10.,
                    0.,
                    0.,
                    Some(100.),
                    Some(100.),
                    Some(100.),
                    Some(100.),
                    1,
                    1,
                ),
                u(
                    20.,
                    35.,
                    50.,
                    30.,
                    1000.,
                    Some(5.),
                    Some(5.),
                    Some(22.5),
                    Some(35.),
                    1,
                    1,
                ),
            ],
            d: vec![vec![95., 100., 130.]],
            net: None,
        },
        4 => Market {
            g: vec![
                u(0., 100., 10., 0., 0., None, None, None, None, 1, 1),
                u(0., 100., 50., 0., 0., None, None, None, None, 1, 1),
            ],
            d: vec![vec![0.], vec![0.], vec![90.]],
            net: Some(Network {
                bus: vec![0, 2],
                ln: vec![
                    Line::Dc((0, 1, 1., 100.)),
                    Line::Dc((1, 2, 1., 100.)),
                    Line::Dc((0, 2, 1., 40.)),
                ],
                nb: 3,
                fm: "dc".into(),
                zn: vec![],
            }),
        },
        5 => Market {
            g: vec![
                u(0., 5000., 40., 0., 0., None, None, None, None, 1, 1),
                u(0., 6000., 10., 0., 0., None, None, None, None, 1, 1),
                u(0., 3000., 90., 0., 0., None, None, None, None, 1, 1),
            ],
            d: vec![vec![4000., 0.], vec![0., 9000.]],
            net: Some(Network {
                bus: vec![0, 1, 1],
                ln: vec![Line::Ntc((0, 1, (-3500., 2200.)))],
                nb: 2,
                fm: "ntc".into(),
                zn: vec!["NO-NO1".into(), "NO-NO2".into()],
            }),
        },
        _ => panic!("case number must be in 1..=5"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::clearing::{en, uc};
    #[test]
    fn published_cases_keep_their_demand_and_grid_shapes() {
        assert_eq!(case(1).d, vec![vec![35.]]);
        let loop_case = case(4).validated().unwrap();
        assert_eq!(loop_case.net.unwrap().ln.len(), 3);
        let zones = case(5).validated().unwrap();
        assert_eq!(zones.net.unwrap().fm, "ntc");
    }

    #[test]
    fn dc_loop_and_ntc_cases_clear_at_their_expected_costs() {
        assert!((uc(&case(4), None).unwrap().z - 2_100.).abs() < 1e-6);
        assert!((uc(&case(5), None).unwrap().z - 275_000.).abs() < 1e-6);
    }

    #[test]
    fn enumerated_clearing_matches_integer_clearing_on_examples() {
        for n in [1, 4, 5] {
            let m = case(n);
            assert!((en(&m, None).unwrap().z - uc(&m, None).unwrap().z).abs() < 1e-6);
        }
    }
}
