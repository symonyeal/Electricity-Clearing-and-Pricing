# Held-out results, 2025

Outputs from the [NYISO replay](../MARKET.md).

| File | Content |
| --- | --- |
| `tables.md` | Settlement, volume, solver, and monthly tables |
| `cumulative.svg` | Cumulative net settlement |
| `monthly.svg` | Monthly net settlement |
| `concentration.svg` | Net settlement concentrated by day |
| `trace.svg` | Prices, energy, and power for one day |
| `<policy>/metrics.json` | Aggregates, diagnostics, fit record, and environment |
| `<policy>/daily.csv` | Daily settlement and solver outcome |
| `<policy>/monthly.csv` | Monthly settlement |
| `<policy>/config.toml` | Executed configuration |
| `coverage.json` | Price-archive coverage |
| `tune.md`, `selected.json` | Validation grid and selected settings |

The five-minute `intervals.csv.gz` exports are omitted because each is about 2 MB. The
executed revision is recorded in each `metrics.json`. A later delivery-band sensitivity is
preserved in the [scope archive](../../_archive/20260916-focus-reset/delivery/results/README.md).
