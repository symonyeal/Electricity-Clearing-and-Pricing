//! Regression cases from the independent architecture review.
use ecp::{
    clearing, hull,
    market::Market,
    network::Network,
    pricing,
    unit::{self, Unit},
};

fn market() -> Market {
    Market::new(
        vec![Unit::new(0., 10., 5.); 2],
        vec![vec![5.]; 2],
        Some(Network {
            bus: vec![0, 1],
            ln: vec![],
        }),
    )
    .unwrap()
}

#[test]
fn malformed_prices_and_caps_fail_before_numerical_work() {
    let m = market();
    let s = clearing::uc(&m, None).unwrap();
    assert_eq!(s.z, 50.);
    for pi in [
        vec![vec![10., 999.], vec![20.]],
        vec![],
        vec![vec![f64::NAN]; 2],
    ] {
        assert!(hull::qd(&m, &pi, None).is_err());
        assert!(pricing::pay(&m, &s, &pi).is_err());
        assert!(pricing::pc(&m, &s, &pi).is_err());
    }
    for cap in [
        vec![],
        vec![vec![-1.]; 2],
        vec![vec![f64::INFINITY]; 2],
        vec![vec![1., 2.]; 2],
    ] {
        assert!(clearing::uc(&m, Some(&cap)).is_err());
        assert!(clearing::rx(&m, Some(&cap)).is_err());
        assert!(clearing::lmp(&m, &s, Some(&cap)).is_err());
        assert!(hull::hc(&m, Some(&cap)).is_err());
        assert!(hull::qd(&m, &[vec![10.], vec![20.]], Some(&cap)).is_err());
    }
}

#[test]
fn fixed_schedule_requires_binary_finite_complete_commitment() {
    let x = Unit::new(0., 10., 5.);
    for u in [
        vec![0.5],
        vec![f64::NAN],
        vec![f64::INFINITY],
        vec![],
        vec![0., 1.],
    ] {
        assert!(unit::trajectory(&x, 1, &u, None).is_none());
    }
    assert!(unit::trajectory(&x, 1, &[1.], Some(&[])).is_none());
}

#[test]
fn clearing_cannot_be_reused_after_market_changes() {
    let m = market();
    let s = clearing::uc(&m, None).unwrap();
    let other = Market::new(
        m.units().to_vec(),
        vec![vec![4.]; 2],
        Some(m.network().clone()),
    )
    .unwrap();
    assert!(clearing::lmp(&other, &s, None).is_err());
    assert!(pricing::pay(&other, &s, &vec![vec![5.]; 2]).is_err());
    assert!(pricing::pc(&other, &s, &vec![vec![5.]; 2]).is_err());
}

#[test]
fn finite_prices_respect_weak_duality_on_a_price_grid() {
    let m = market();
    let optimum = clearing::uc(&m, None).unwrap().z;
    for a in [-100., 0., 5., 10., 999.] {
        for b in [-20., 5., 50.] {
            let q = hull::qd(&m, &[vec![a], vec![b]], None).unwrap();
            assert!(q <= optimum + 1e-6, "q={q}, optimum={optimum}");
        }
    }
}

#[test]
fn invalid_market_shapes_are_rejected() {
    let g = vec![Unit::new(0., 10., 5.)];
    assert!(Market::new(g.clone(), vec![], None).is_err());
    assert!(Market::new(g.clone(), vec![vec![]], None).is_err());
    assert!(
        Market::new(
            g.clone(),
            vec![vec![1.], vec![1., 2.]],
            Some(Network {
                bus: vec![0],
                ln: vec![]
            })
        )
        .is_err()
    );
    assert!(
        Market::new(
            g,
            vec![vec![1.]],
            Some(Network {
                bus: vec![1],
                ln: vec![]
            })
        )
        .is_err()
    );
}
