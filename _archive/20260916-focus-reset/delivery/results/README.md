# Delivery sensitivity

The [study](../../MARKET.md) reports the delivery-cap experiment. Each
`<zone>/<year>/cap-<limit>/<policy>/` directory contains the run's unchanged
`metrics.json`, `config.toml`, `daily.csv` and `monthly.csv`. Caps are MW; `None` is
unbounded. The interval files stay under `results/delivery/` locally, as in the original
experiment, because one is about two megabytes a run. `audit.json` records independent
checks against those six-decimal interval exports, source SHA-256 hashes and the actual
commands. Each run's own `metrics.json` also records the base revision and whether the
working tree was dirty. The hashes identify the executed source even when the measurement
precedes the commit that publishes it.

Settings come from `../selected.json`, with no selection or fitting based on the cap:
`L=30, S=16` for `det` and `L=30, S=8` for `neutral`. Foresight has no forecast
hyperparameters, so its original `config/nyiso.toml` values, `L=60, S=8`, are retained.
The ordinary `run` command refits persistence before the evaluated year using data from
2022-10-01 through 2024-12-31, then holds that coefficient for the year; the fit does not
depend on the cap.

## The twelve settings

TOML has no null, so a configuration file omits `cap` for the unbounded case. On the
command line the equivalent is `--set cap=None`; finite examples are `--set cap=0.25` and
`--set cap=0.0`. These are the commands the runs recorded, from the repository root:

```bash
.venv/bin/python -u run_market.py run --period test --pol <policy> \
    --out results/delivery/nyc/2025/cap-<cap> \
    --set zone=N.Y.C. --set 'te=["2025-01-01", "2025-12-31"]' \
    --set cap=<cap> --set L=<L> --set S=<S> --set w=0.0 --set al=0.95
```

over `<cap>` in `None 1.0 0.25 0.0` and `<policy>` in `det neutral fore`, with `L` and `S`
as above. Each was launched detached, with its own log, its own `<policy>.launch.json`
recording the command, the process id and the source hashes, and a wrapper that writes the
child's status to `<policy>.exit`:

```bash
.venv/bin/python - <<'PY'
import subprocess
from pathlib import Path

PY_ = '.venv/bin/python'
MARK = ('import pathlib,subprocess,sys; r=subprocess.run(sys.argv[2:]); '
        'pathlib.Path(sys.argv[1]).write_text(str(r.returncode)+"\n"); '
        'sys.exit(r.returncode)')
SET = {'det': ('30', '16'), 'neutral': ('30', '8'), 'fore': ('60', '8')}
for cap in ('None', '1.0', '0.25', '0.0'):
    out = Path(f'results/delivery/nyc/2025/cap-{cap}')
    out.mkdir(parents=True, exist_ok=True)
    for pol, (L, S) in SET.items():
        cmd = [PY_, '-u', 'run_market.py', 'run', '--period', 'test', '--pol', pol,
               '--out', str(out), '--set', 'zone=N.Y.C.',
               '--set', 'te=["2025-01-01", "2025-12-31"]', '--set', f'cap={cap}',
               '--set', f'L={L}', '--set', f'S={S}', '--set', 'w=0.0', '--set', 'al=0.95']
        log = (out / f'{pol}.log').open('w')
        subprocess.Popen([PY_, '-c', MARK, str(out / f'{pol}.exit'), *cmd],
                         stdout=log, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
PY
```

Launch from a persistent shell: an execution sandbox that destroys its process namespace
on exit also destroys detached children. Check the twelve `.exit` files, each containing
zero, and the corresponding `metrics.json` and `config.toml`, before reading any result. A
process-name search is not a completion check, and neither is the tail of a log. Before
relaunching a run, delete its output directory, its log and its `.exit` file, and confirm
no earlier process is still writing there: a stale `.exit` file, or two processes sharing
one output directory, will otherwise be read as a finished result.

## Checking the runs

`audit.json` is rebuilt from the exported results by the script below. Every setting must
have finished: either it exported and exited zero, or it exited nonzero having stopped on
an infeasible capped dispatch, which is decision 52's specified outcome and is recorded
as `completed: false` with the date, step and solver message. Any other nonzero exit is
refused. For each completed run it rebuilds net settlement
and stored energy from the six-decimal interval export alone, by a path that shares no
arithmetic with the replay; re-derives the largest excess over the cap; re-derives July,
the year without July and the ten best days from the daily export; and, for the unbounded
runs, differences every metric against the original study in `docs/results/<policy>/`,
which must be zero throughout.

Some capped runs report a large raw relative MIP gap when the remaining variable objective
is nearly zero after the contract's constant profit has been removed. The raw values are
kept as reported. For every day whose recorded gap exceeds the requested 1e-4, the audit
re-solves that day from its own exported configuration and records each solve's raw ratio
beside its variable score, full score and certified bound; those records are also written
to `results/delivery/nyc/2025/gap-probes.json`. A day passes this exception only when the
absolute difference between the full score and its bound is below $0.0000001. No solver
setting is changed, and no reported ratio is replaced.

```bash
.venv/bin/python run_delivery.py audit    # verifies, publishes and writes audit.json
.venv/bin/python run_delivery.py tables   # prints the tables used in docs/MARKET.md
```

`audit` copies each verified run's `metrics.json`, `config.toml`, `daily.csv` and
`monthly.csv` from `results/delivery/` into this directory; the interval files stay
local. `tables` reads the published copies.

## Reading the numbers

One of the twelve settings has no result: `neutral` at a 0.25 MW cap stopped on 2025-12-15
with an infeasible capped dispatch, so there is no `cap-0.25/neutral/` directory here.
`audit.json` carries its termination record, with the date, step and solver message, in
place of that run's metrics, and the log and launch record remain under
`results/delivery/` locally.

The existing split is `arb = sum(g * RT - costs)` and `spread = sum(q * (DA - RT))`, with
interval durations included; the two sum to net by identity. The spread is an accounting
basis term, not a measure of undelivered energy: it may be nonzero even when `g=q`
everywhere. Dependence on the delivery assumption is measured by the change in net between
the unbounded and the capped replay of the same policy. The annual tables also carry
imbalance MWh and the largest absolute deviation, which say what was actually delivered.
