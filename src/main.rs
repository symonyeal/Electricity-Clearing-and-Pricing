use ecp::{
    cases,
    clearing::{self, Market},
    dw, pricing,
};
use std::{
    env, fs,
    io::{self, Read},
};

fn execute(args: &[String]) -> Result<(), String> {
    if args.is_empty() || args == ["--help"] || args == ["-h"] {
        println!(
            "ecp case <1..5> [uc|en|lmp|rx|chp|hl|cg|aic|all]\necp solve <market.json|-> [uc|en|lmp|rx|chp|hl|cg|aic|all]\n\nDefault route: all. JSON output on stdout; errors on stderr."
        );
        return Ok(());
    }
    if !(2..=3).contains(&args.len()) {
        return Err("expected case <n> or solve <path>; use --help".into());
    }
    let m = match args[0].as_str() {
        "case" => {
            let n: usize = args[1].parse().map_err(|_| "case number must be 1..5")?;
            if !(1..=5).contains(&n) {
                return Err("case number must be 1..5".into());
            }
            cases::case(n)
        }
        "solve" => {
            let data = if args[1] == "-" {
                let mut data = String::new();
                io::stdin()
                    .read_to_string(&mut data)
                    .map_err(|e| e.to_string())?;
                data
            } else {
                fs::read_to_string(&args[1]).map_err(|e| e.to_string())?
            };
            serde_json::from_str::<Market>(&data).map_err(|e| format!("market JSON: {e}"))?
        }
        _ => return Err("expected case or solve; use --help".into()),
    }
    .validated()?;
    let route = args.get(2).map(String::as_str).unwrap_or("all");
    let result = match route {
        "uc" => serde_json::to_value(clearing::uc(&m, None)?),
        "en" => serde_json::to_value(clearing::en(&m, None)?),
        "cg" => serde_json::to_value(dw::cg(&m, None)?),
        "rx" => serde_json::to_value(clearing::rx(&m, None)?),
        "lmp" => {
            let s = clearing::uc(&m, None)?;
            serde_json::to_value(clearing::lmp(&m, &s, None)?)
        }
        "chp" => serde_json::to_value(ecp::hull::hc(&m, None)?),
        "hl" => serde_json::to_value(ecp::hull::hl(&m, None)?),
        "aic" => {
            let s = clearing::uc(&m, None)?;
            let cap = pricing::pc(&m, &s, 1e-6, None)?;
            serde_json::to_value(ecp::hull::hc(&m, Some(&cap))?)
        }
        "all" => serde_json::to_value(pricing::run(&m, 1e-6)?),
        _ => return Err(format!("unknown route: {route}")),
    }
    .map_err(|e| e.to_string())?;
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
