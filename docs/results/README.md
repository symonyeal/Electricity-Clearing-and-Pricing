# Held-out results, 2025

The evidence behind [the study](../MARKET.md), as the run wrote it. Nothing here is read
by the code; regenerate it with the commands in that document.

| File | What it is |
| --- | --- |
| `tables.md` | settlement, volume, solver and monthly tables |
| `cumulative.svg` | cumulative net settlement of every policy over the held-out year |
| `monthly.svg` | net settlement by calendar month |
| `concentration.svg` | share of the year's net settlement against share of days, best first |
| `trace.svg` | one day of prices, stored energy and grid power |
| `<policy>/metrics.json` | measured aggregates, run diagnostics, the fit record and the environment that produced them |
| `<policy>/daily.csv` | one row per local day: settlement, energy, solver outcome |
| `<policy>/monthly.csv` | the same by calendar month |
| `<policy>/config.toml` | the configuration that run used, readable back by `market.cfg` |
| `coverage.json` | archive coverage and long real-time postings over the whole record |
| `tune.md`, `selected.json` | the validation search and what the stated rule chose from it |

`intervals.csv.gz`, one row per five-minute settlement bin per policy, is about two
megabytes a policy and is not kept here. The run writes it beside these files, and the
reconciliation in `tests/test_market.py` is what reads it.

Every run in this directory was produced at the repository revision its `metrics.json`
records, before the commit that added these files.
