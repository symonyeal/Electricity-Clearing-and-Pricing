# Scope archive, 2026-09-16

This archive preserves material removed from the live electricity-market scope at commit
`f265a9f`.

| Directory | Former live material | Reason archived |
| --- | --- | --- |
| `pit/` | Ultimate-pit model, MineLib data, tests, and the combined benchmark driver | Exact and tested, but unrelated to electricity markets |
| `documentation/` | The long-form README, decision log, INL review, market study, source register, trading note, and validation snapshot | Superseded by the concise live documents |
| `delivery/` | Delivery-cap replay, audit program, and eleven completed runs plus one infeasible setting | Valid post-hoc sensitivity, but not part of the primary held-out study |

The delivery archive is not a failed result. Its hashes and reconciliation checks matched
the executed source. It was removed from the live path to keep one empirical study and one
result set in scope.

Restore a component to its former path before running it. The archive is historical and is
not exercised by continuous integration.
