use ecp::{clearing, hull, market::Market, pricing, study};
use std::{
    env, fs,
    io::{self, Read},
};

const USAGE: &str = "ecp case <1..5> [uc|lmp|rx|chp|aic|all|study]
ecp solve <market.json|-> [uc|lmp|rx|chp|aic|all|study]

Default route: all. JSON output on stdout; errors on stderr.";

const CASES: [&str; 5] = [
    include_str!("../cases/1.json"),
    include_str!("../cases/2.json"),
    include_str!("../cases/3.json"),
    include_str!("../cases/4.json"),
    include_str!("../cases/5.json"),
];

/// Whether any result carries `price_selection: "payment"`.
fn payment_only(v: &serde_json::Value) -> bool {
    match v {
        serde_json::Value::Object(o) => o
            .iter()
            .any(|(k, x)| (k == "price_selection" && x == "payment") || payment_only(x)),
        serde_json::Value::Array(a) => a.iter().any(payment_only),
        _ => false,
    }
}

fn execute(args: &[String]) -> Result<(), String> {
    if args.is_empty() || args == ["--help"] || args == ["-h"] {
        println!("{USAGE}");
        return Ok(());
    }
    if !(2..=3).contains(&args.len()) {
        return Err("expected case <n> or solve <path>; use --help".into());
    }
    let data = match (args[0].as_str(), args[1].as_str()) {
        ("case", n) => match n.parse::<usize>() {
            Ok(n @ 1..=5) => CASES[n - 1].to_string(),
            _ => return Err("case number must be 1..5".into()),
        },
        ("solve", "-") => {
            let mut data = String::new();
            io::stdin()
                .read_to_string(&mut data)
                .map_err(|e| e.to_string())?;
            data
        }
        ("solve", path) => fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?,
        _ => return Err("expected case or solve; use --help".into()),
    };
    let m: Market = serde_json::from_str(&data).map_err(|e| format!("market JSON: {e}"))?;
    let route = args.get(2).map_or("all", String::as_str);
    let result = match route {
        "uc" => serde_json::to_value(clearing::uc(&m, None)?),
        "lmp" => serde_json::to_value(clearing::lmp(&m, &clearing::uc(&m, None)?, None)?),
        "rx" => serde_json::to_value(clearing::rx(&m, None)?),
        "chp" => serde_json::to_value(hull::hc(&m, None)?),
        "aic" => {
            let s = clearing::uc(&m, None)?;
            let cap = pricing::pc(&m, &s, &clearing::lmp(&m, &s, None)?.pi)?;
            serde_json::to_value(hull::hc(&m, Some(&cap))?)
        }
        "all" => serde_json::to_value(pricing::run(&m)?),
        "study" => serde_json::to_value(study::demand(&m)),
        _ => return Err(format!("unknown route: {route}")),
    }
    .map_err(|e| e.to_string())?;
    if payment_only(&result) {
        eprintln!(
            "ecp: warning: more than 24 balance rows; prices minimise demand payment only \
             (price_selection \"payment\") and are one vertex of the optimal dual face"
        );
    }
    println!(
        "{}",
        serde_json::to_string_pretty(&result).map_err(|e| e.to_string())?
    );
    Ok(())
}

fn main() {
    if let Err(e) = execute(&env::args().skip(1).collect::<Vec<_>>()) {
        eprintln!("ecp: {e}");
        std::process::exit(1);
    }
}
