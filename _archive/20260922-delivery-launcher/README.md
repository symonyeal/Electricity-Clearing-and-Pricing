# 2026-09-22 — the delivery-run launcher

| Removed | Reason |
| --- | --- |
| The detached `subprocess.Popen` launcher from `docs/results/delivery/README.md` | It launched twelve runs against a `.venv` interpreter the repository does not carry, and nothing needs it to reproduce them |

[`launch.md`](launch.md) holds the script as it stood.

What reproduces the runs is the `run_market.py run` command template and the twelve
cap-and-policy settings, both still in
[`docs/results/delivery/README.md`](../../docs/results/delivery/README.md). What the
script contributed beyond that was backgrounding, and the `<policy>.exit` and
`<policy>.log` files it wrote, which `run_delivery.py audit` reads and which that document
still specifies. `audit.json` carries the executed commands and the source hashes.
