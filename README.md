# Network Flow Models

Working implementations of network flow and mixed-integer models that industry
actually runs, each one solved more than one way so the answer can be checked
rather than trusted.

The first model is the open-pit ultimate pit limit. More are listed in
[Open decisions and settled ground](docs/DECISIONS.md); every source read is in
[Sources](docs/SOURCES.md).

## The argument

An ore body is cut into a grid of blocks. Each block has a value: what the metal
in it is worth, less what it costs to dig and process. Most blocks are waste and
carry a negative value. The question is which blocks to mine.

It is not simply "mine the profitable ones". A pit wall cannot stand vertically,
so reaching a block deep in the ground means removing a widening cone of blocks
above it first. A rich block buried under enough waste loses money. That
dependency is the whole problem, and it is what separates the real answer from
the naive one.

Lerchs and Grossmann asked this question in 1965. Picard showed in 1976 that it
is a maximum closure problem, and that maximum closure is a minimum cut. So the
pit that maximises value is found by one maximum flow calculation, exactly, with
no search and no approximation.

## What is implemented

`models/lg_pit.py` builds the block model and the slope constraints, then solves
the pit three ways:

| Method | What it is | Used for |
| --- | --- | --- |
| `mc` | Minimum cut on the Picard reduction | The production method |
| `lp` | The closure linear program | Independent check at every size |
| `bf` | Exhaustive enumeration of all closures | Ground truth, small models only |

All three must agree. A disagreement means the precedence arcs are wrong, which
is the defect this arrangement is built to catch.

## What the model shows

`run_bench.py` produces this table. Block values are synthetic: an ellipsoidal
ore lens under barren overburden.

| Model | Blocks | Arcs | Pit value | Min cut | LP | Fractional | Strip ratio | Ore left out |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30x30x12 | 10,800 | 85,184 | 2,552.28 | 0.69s | 0.20s | 0 | 2.64 | 73 |
| 60x60x20 | 72,000 | 601,996 | 20,102.60 | 6.05s | 1.91s | 0 | 2.06 | 230 |
| 90x90x30 | 243,000 | 2,082,896 | 68,454.79 | 30.96s | 9.59s | 0 | 2.03 | 602 |

Three things in that table are the point of the exercise.

**Ore left out.** 73, 230 and 602 blocks carry a positive value of their own and
are still left in the ground, because they do not pay for the waste above them.
A rule of "mine every profitable block" takes all of them and loses money. The
gap between the two answers is the entire value of the model.

**Fractional is zero everywhere.** The linear program lands on a whole-block
answer without being told to. That is a property of the constraint matrix, not
luck, and it is why a scheduling-shaped problem can be solved as a flow problem.
If a reimplementation returns fractions, its precedence arcs are wrong.

**Strip ratio settles near 2.** Two blocks of waste for every block of ore, which
is the range real open pits operate in. The number was not set anywhere; it falls
out of the geometry and the prices.

The minimum cut runs slower than the linear program here because NetworkX is
pure Python. That is a fact about the library, not about the method — commercial
pit software uses a compiled pseudoflow solver and reverses the ordering.

## Verification

```text
python -m pytest -q          23 tests
python -m ruff check .
```

Two instances are checkable by hand. One ore block worth $40 sits under nine
waste blocks costing $2 each, so the pit is worth $22 and holds 10 blocks. The
same ore block worth $10 does not cover its own stripping and the correct pit is
empty. The tests assert both, and check them against exhaustive enumeration.

At $18 the ore exactly cancels the waste, both answers are worth zero, and the
two methods may legitimately return different sets. The tests compare values
there and not block sets. That case is deliberate: a comparison that cannot tell
a tie from a defect is not a test.

## Running it

```text
pip install -r requirements.txt
python run_bench.py
```

One system Python, no virtual environment.
