# The detached launcher used for the delivery runs

The twelve delivery-band runs of 2026-09-16 were started by this script, from the
repository root, against a `.venv` interpreter that is not part of the repository.
It backgrounded each `run_market.py run` with its own log and wrote the child's exit
status to `<policy>.exit`, which `run_delivery.py audit` still reads.

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
