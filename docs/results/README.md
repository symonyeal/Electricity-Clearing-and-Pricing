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
executed revision is recorded in each `metrics.json`. The delivery-band sensitivity on the
same year is in [`delivery/`](delivery/README.md).

## Provenance note: analog alignment

These bundles were produced at revision `88d244d` on 2026-09-16, before analog days were
aligned by local clock hour rather than by array position. Re-running the year would
reproduce them on every day whose analogs are the same length as the target, which is all
but a few: at the executed `L = 30`, the change can reach at most 18 of the 365 replay
days, and only 2 of those with certainty.

| Days | Why they can move |
| ---: | --- |
| 2 | 2025-03-09 and 2025-11-02 are themselves 23- and 25-hour days |
| up to 16 | weekend days through 2025-04-06 and 2025-11-30 whose lookback can select one of those two as an analog |

The second group is an upper bound on reach, not a count of changes: `pick` then selects
$S$ quantile-spaced days by mean real-time price, and whether a transition day survives
that selection cannot be determined without the archives, which are not committed. The
other 347 days are untouched, because alignment by position and alignment by clock hour are
the same map between two days of equal length. The bundles are not restated here; the
recorded revision is what they are evidence from.
