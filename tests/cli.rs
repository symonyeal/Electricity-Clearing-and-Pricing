use std::{
    io::Write,
    process::{Command, Stdio},
};

#[test]
fn json_input_and_builtin_case_use_the_same_engine() {
    let named = Command::new(env!("CARGO_BIN_EXE_ecp"))
        .args(["case", "1", "chp"])
        .output()
        .unwrap();
    assert!(named.status.success());
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
        .write_all(include_bytes!("../examples/market.json"))
        .unwrap();
    let from_json = process.wait_with_output().unwrap();
    assert!(from_json.status.success());
    let a: serde_json::Value = serde_json::from_slice(&named.stdout).unwrap();
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
