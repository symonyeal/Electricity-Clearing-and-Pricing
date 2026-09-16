# Scope statements superseded by the historical study

Before the study in [docs/MARKET.md](../../docs/MARKET.md), three statements in the active
documents were accurate and are now not. They are recorded here with what replaced them.

| Superseded statement | Where it stood | What replaced it |
| --- | --- | --- |
| "Market-specific storage participation and timestamped out-of-sample evaluation" was one line of remaining work. | `docs/DECISIONS.md`, remaining work 1 | The out-of-sample evaluation exists: one zone, one held-out year, chronological replay. Market-specific participation is still not implemented and remains listed. |
| Passing `q` held an existing offer fixed and still required a nominal physical schedule from the current energy. | `models/storage.py`, `docs/TRADING.md` | A contracted position is financial and imposes no physical schedule; only a position being chosen must be deliverable. Decision 36. |
| "`da` is one supplied day-ahead curve; before clearing, treating it as fixed omits day-ahead price uncertainty and bid acceptance." | `docs/TRADING.md`, scope | Day-ahead prices may now be one curve per scenario. Bid acceptance is still assumed and is stated as an unvalidated assumption in the study. |

The earlier synthetic storage results and their timings remain active in
[docs/VALIDATION.md](../../docs/VALIDATION.md): the historical study adds to them and
replaces nothing there. The [INL review archive](../20260915-inl-review/README.md) is
unchanged.
