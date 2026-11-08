use std::{
    io::Write,
    process::{Command, Stdio},
};

#[test]
fn builtin_case_file_and_stdin_agree() {
    let run = |args: &[&str]| {
        let out = Command::new(env!("CARGO_BIN_EXE_ecp"))
            .args(args)
            .current_dir(env!("CARGO_MANIFEST_DIR"))
            .output()
            .unwrap();
        assert!(out.status.success());
        out.stdout
    };
    let named = run(&["case", "1", "chp"]);
    assert_eq!(named, run(&["solve", "cases/1.json", "chp"]));
    let mut process = Command::new(env!("CARGO_BIN_EXE_ecp"))
        .args(["solve", "-", "chp"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .unwrap();
    process
        .stdin
        .take()
        .unwrap()
        .write_all(include_bytes!("../cases/1.json"))
        .unwrap();
    let from_json = process.wait_with_output().unwrap();
    assert!(from_json.status.success());
    let a: serde_json::Value = serde_json::from_slice(&named).unwrap();
    let b: serde_json::Value = serde_json::from_slice(&from_json.stdout).unwrap();
    assert_eq!(a, b);
    assert!((a["pi"][0][0].as_f64().unwrap() - 12.0).abs() < 1e-5);
}

#[test]
fn invalid_input_is_an_error_without_a_result() {
    for args in [["case", "0", "uc"], ["case", "1", "unknown"]] {
        let result = Command::new(env!("CARGO_BIN_EXE_ecp"))
            .args(args)
            .output()
            .unwrap();
        assert!(!result.status.success());
        assert!(result.stdout.is_empty());
        assert!(!result.stderr.is_empty());
    }
    let bad = br#"{"g":[{"lo":0,"hi":10,"c":5,"typo":2}],"d":[[3]]}"#;
    let mut process = Command::new(env!("CARGO_BIN_EXE_ecp"))
        .args(["solve", "-", "uc"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    process.stdin.take().unwrap().write_all(bad).unwrap();
    let result = process.wait_with_output().unwrap();
    assert!(!result.status.success());
    assert!(result.stdout.is_empty());
    assert!(
        String::from_utf8(result.stderr)
            .unwrap()
            .contains("unknown field")
    );
}

#[test]
fn case_3_reproduces_the_published_prices_and_uplift() {
    let out = Command::new(env!("CARGO_BIN_EXE_ecp"))
        .args(["case", "3"])
        .output()
        .unwrap();
    assert!(out.status.success());
    let r: serde_json::Value = serde_json::from_slice(&out.stdout).unwrap();
    // Prices and payments hold to the solver tolerances of the parity comparator.
    let at = |v: &serde_json::Value| v.as_f64().unwrap();
    let close = |a: f64, b: f64| (a - b).abs() <= 1e-6 + 1e-7 * b.abs().max(1.);
    let up = |rule: &str| {
        r[format!("pay_{rule}")]["up"]
            .as_array()
            .unwrap()
            .iter()
            .map(at)
            .sum::<f64>()
    };
    assert!(close(at(&r["uc"]["z"]), 7_340.));
    for (rule, peak, uplift) in [("lmp", 90., 1_690.), ("chp", 276., 365.)] {
        assert!(close(at(&r[rule]["pi"][0][2]), peak), "{rule} peak");
        assert!(close(up(rule), uplift), "{rule} uplift");
    }
    // The 1e-6 MW AIC ceiling relaxation lowers the peak price by about 1.2e-4.
    assert!((at(&r["aic"]["pi"][0][2]) - 422.).abs() < 1e-3, "aic peak");
}

#[test]
fn payment_only_selection_is_reported_on_stderr() {
    let market = serde_json::json!({
        "g": [{"lo": 0, "hi": 10, "c": 5}, {"lo": 0, "hi": 10, "c": 7}],
        "d": [vec![4; 24], vec![4; 24]],
        "net": {"bus": [0, 1], "ln": [[0, 1, 0.1, 50.0]]}
    });
    let mut process = Command::new(env!("CARGO_BIN_EXE_ecp"))
        .args(["solve", "-", "lmp"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    process
        .stdin
        .take()
        .unwrap()
        .write_all(market.to_string().as_bytes())
        .unwrap();
    let out = process.wait_with_output().unwrap();
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    let r: serde_json::Value = serde_json::from_slice(&out.stdout).unwrap();
    assert_eq!(r["price_selection"], "payment");
    assert!(String::from_utf8(out.stderr).unwrap().contains("warning"));
}
