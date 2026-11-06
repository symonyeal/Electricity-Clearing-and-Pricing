//! Values and payments against the independent baseline in fixtures/pricing.json.
use ecp::{
    clearing, hull,
    market::Market,
    pricing::{self, Pay},
};
use serde_json::Value;

const FIXTURE: &str = include_str!("fixtures/pricing.json");

fn close(got: f64, want: f64, where_: &str) {
    let tol = 1e-6 + 1e-7 * got.abs().max(want.abs()).max(1.0);
    assert!(
        (got - want).abs() <= tol,
        "{where_}: got {got:.17}, expected {want:.17}, tolerance {tol:.3e}"
    );
}

fn number(v: &Value) -> f64 {
    v.as_f64().expect("fixture value is numeric")
}

fn matrix(v: &Value) -> Vec<Vec<f64>> {
    serde_json::from_value(v.clone()).expect("fixture matrix is numeric")
}

fn vector(v: &Value) -> Vec<f64> {
    serde_json::from_value(v.clone()).expect("fixture vector is numeric")
}

fn expect_cost(actual: f64, expected: &Value, name: &str, route: &str) {
    close(
        actual,
        number(&expected[route]["z"]),
        &format!("{name}.{route}.z"),
    );
}

fn expect_pay(actual: &Pay, expected: &Value, name: &str, route: &str) {
    let want = &expected[route];
    for (field, got) in [
        ("r", &actual.r),
        ("mw", &actual.mw),
        ("loc", &actual.loc),
        ("up", &actual.up),
    ] {
        let values = vector(&want[field]);
        assert_eq!(got.len(), values.len(), "{name}.{route}.{field} length");
        for (i, (&a, &b)) in got.iter().zip(&values).enumerate() {
            close(a, b, &format!("{name}.{route}.{field}[{i}]"));
        }
    }
}

fn demand_payment(pi: &[Vec<f64>], d: &[Vec<f64>]) -> f64 {
    pi.iter()
        .zip(d)
        .flat_map(|(p, q)| p.iter().zip(q).map(|(a, b)| a * b))
        .sum()
}

#[test]
fn baseline_values_and_payments_match() {
    let fixture: Value = serde_json::from_str(FIXTURE).expect("pricing fixture is valid JSON");
    let cases = fixture["cases"].as_array().expect("fixture has cases");
    assert_eq!(cases.len(), 29, "fixture case count changed");

    for case in cases {
        let name = case["name"].as_str().expect("case has a name");
        let market: Market = serde_json::from_value(case["input"].clone())
            .unwrap_or_else(|e| panic!("{name}: cannot decode market: {e}"));
        let expected = &case["expected"];
        let failures = &case["failures"];

        let uc = match clearing::uc(&market, None) {
            Ok(s) => {
                assert!(
                    expected.get("uc").is_some(),
                    "{name}: unexpected UC success"
                );
                expect_cost(s.z, expected, name, "uc");
                Some(s)
            }
            Err(e) => {
                assert!(
                    expected.get("uc").is_none(),
                    "{name}: unexpected UC error: {e}"
                );
                let want = failures["uc"]["message"]
                    .as_str()
                    .unwrap_or_else(|| panic!("{name}: unexpected UC error: {e}"));
                if want.contains("infeasible") {
                    assert!(
                        e.to_string().to_lowercase().contains("infeasible"),
                        "{name}: {e}"
                    );
                }
                None
            }
        };

        let rx = clearing::rx(&market, None).unwrap_or_else(|e| panic!("{name}.rx failed: {e}"));
        expect_cost(rx.z, expected, name, "rx");
        let chp = hull::hc(&market, None).unwrap_or_else(|e| panic!("{name}.hc failed: {e}"));
        expect_cost(chp.z, expected, name, "hc");
        close(
            chp.lb,
            number(&expected["qd_chp"]),
            &format!("{name}.qd_chp"),
        );
        let arbitrary = matrix(&case["arbitrary_prices"]);
        let qd = hull::qd(&market, &arbitrary, None)
            .unwrap_or_else(|e| panic!("{name}.qd_arbitrary failed: {e}"));
        close(
            qd,
            number(&expected["qd_arbitrary"]),
            &format!("{name}.qd_arbitrary"),
        );

        if let Some(uc) = uc {
            let lmp = clearing::lmp(&market, &uc, None)
                .unwrap_or_else(|e| panic!("{name}: LMP failed: {e}"));
            expect_cost(lmp.z, expected, name, "lmp");
            let cap = pricing::pc(&market, &uc, &lmp.pi).unwrap();
            let cap_want = matrix(&expected["pc"]);
            for (i, (got, want)) in cap.iter().zip(&cap_want).enumerate() {
                for (t, (&a, &b)) in got.iter().zip(want).enumerate() {
                    close(a, b, &format!("{name}.pc[{i}][{t}]"));
                }
            }

            for (route, sol) in [
                ("rx_capped", clearing::rx(&market, Some(&cap))),
                ("hc_capped", hull::hc(&market, Some(&cap))),
            ] {
                let sol = sol.unwrap_or_else(|e| panic!("{name}.{route} failed: {e}"));
                expect_cost(sol.z, expected, name, route);
            }

            if expected.get("pay_lmp").is_some() {
                let pay = pricing::pay(&market, &uc, &lmp.pi)
                    .unwrap_or_else(|e| panic!("{name}.pay_lmp failed: {e}"));
                expect_pay(&pay, expected, name, "pay_lmp");
                let paid = demand_payment(&lmp.pi, market.demand());
                let want = demand_payment(&matrix(&expected["lmp"]["pi"]), market.demand());
                close(paid, want, &format!("{name}.lmp demand payment"));

                let pay = pricing::pay(&market, &uc, &chp.pi)
                    .unwrap_or_else(|e| panic!("{name}.pay_chp failed: {e}"));
                expect_pay(&pay, expected, name, "pay_chp");
                let paid = demand_payment(&chp.pi, market.demand());
                let want = demand_payment(&matrix(&expected["hc"]["pi"]), market.demand());
                close(paid, want, &format!("{name}.chp demand payment"));

                let pay = pricing::pay(&market, &uc, &arbitrary)
                    .unwrap_or_else(|e| panic!("{name}.pay_arbitrary failed: {e}"));
                expect_pay(&pay, expected, name, "pay_arbitrary");
            }
        }
    }
}

#[test]
fn parity_comparator_rejects_a_known_bad_pair() {
    let failure = std::panic::catch_unwind(|| close(1.0, 2.0, "deliberately wrong pair"));
    assert!(failure.is_err(), "comparator accepted a known bad pair");
}
