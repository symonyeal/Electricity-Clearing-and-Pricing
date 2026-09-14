# Network Flow Models

One complete network model, with several exact ways to check it. The current
model finds the most valuable final outline of an open-pit mine. The next model
is not added until it can meet the same standard.

[Decisions and remaining work](docs/DECISIONS.md) owns design choices.
[Sources](docs/SOURCES.md) owns the bibliography and data provenance.

## The question

An ore body is divided into blocks. A block's value is its metal revenue less
mining and processing cost. Waste usually has a negative value.

Mining every positive block is wrong. Reaching a deep block requires removing a
widening set of blocks above it so the wall remains stable. A rich block stays
in the ground when it cannot pay for that stripping. The task is therefore to
choose the highest-value set that contains every required upper block.

Lerchs and Grossmann stated the mining problem in 1965. Picard showed in 1976
that this kind of closed set can be found by one exact minimum cut. There is no
search heuristic in the answer.

## One model, four solve routes

`models/lg_pit.py` is the only model definition. Every route consumes the same
value vector `v` and precedence array `E`; there is no second copy of the block
economics or slope rules.

| Function | Route | Purpose |
| --- | --- | --- |
| `mc` | OR-Tools maximum flow with exact integer capacities | Default solve |
| `mc_nx` | NetworkX minimum cut with floating-point capacities | Checks the integer scaling and library adapter; it uses the same reduction |
| `lp` | SciPy closure linear program | Checks the cut formulation through a different optimization model |
| `bf` | Generates every valid closed set | Exact ground truth for at most 20 blocks |

The scalable routes deliberately share `E`, so agreement between them cannot
prove that its direction or geometry is right. Separate tests inspect every arc,
boundary counts, closure of the returned pit, hand-worked examples, and the
official MineLib solution. `models/minelib.py` is only the input reader.

## Measured run

`run_bench.py` creates one synthetic ore lens at each size and solves the same
instance with OR-Tools, NetworkX, and the linear program. This is the full run
made on 2026-09-14 with Python 3.14.3, OR-Tools 9.15.6755, NetworkX 3.6.1,
SciPy 1.17.1, NumPy 2.4.4, Windows 11 build 26200, and an Intel64 family 6,
model 186 processor. Times are elapsed seconds from one run, not projections.

| Model | Blocks | Arcs | Pit value | OR-Tools | NetworkX | LP | Fractional | Strip ratio | Positive blocks left out |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30x30x12 | 10,800 | 85,184 | 2,552.23 | 0.011s | 1.21s | 0.44s | 0 | 2.64 | 73 |
| 60x60x20 | 72,000 | 601,996 | 20,102.47 | 0.100s | 14.38s | 5.62s | 0 | 2.06 | 230 |
| 90x90x30 | 243,000 | 2,082,896 | 68,454.46 | 0.886s | 54.32s | 16.94s | 0 | 2.03 | 602 |

The positive blocks left out are the useful result: each makes money by itself,
but not after paying for the waste above it. The linear program returned no
fractional block choices, as expected from its network matrix. That confirms the
form of the linear program; it does not confirm arc direction.

The synthetic generator is designed to produce a non-empty pit, omit at least
one positive block, and keep the waste-to-positive-block ratio between 1.5 and
3.0. That band is a regression check for this generator, not a claim about all
real mines.

The arc representation was measured separately on the 90x90x30 model. The old
Python list of 2,082,896 tuples took 4.454 seconds to build and reached 270.51
MiB of traced allocation. The one `int32` array now used by every solver took
0.410 seconds and 15.90 MiB. The linear program no longer makes another copy.

## Check against an outside answer

MineLib publishes the Newman1 ultimate-pit instance, a rounded optimum of
26,086,899, and the official selected blocks. The committed fixture has 1,060
blocks and 3,922 precedence arcs. Its values require five decimal places, so the
reader uses 100,000 exact integer units per dollar.

This code returns 26,086,899.025970. It rounds to MineLib's published value and
selects exactly the same 1,059 block IDs as MineLib's solution file. OR-Tools,
NetworkX, and the linear program also return the same objective. File origins
and hashes are in [Sources](docs/SOURCES.md).

## Run it

Use the one system Python on this machine; no virtual environment is needed.

```text
python -m pip install -r requirements.txt
python -m pytest -q
python -m ruff check .
python run_bench.py
```

The last full verification on 2026-09-14 passed 34 tests and the complete lint
check. Benchmark times will vary by machine and run.
