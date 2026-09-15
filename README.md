# Network Flow Models

Complete optimisation models, each with several exact ways to check it. A model is not
added until it can meet that standard, and each one is checked against an answer
published by someone else.

[Decisions and remaining work](docs/DECISIONS.md) owns design choices.
[Sources](docs/SOURCES.md) owns the bibliography and data provenance.

| Model | File | Solved as |
| --- | --- | --- |
| Ultimate pit limit of an open-pit mine | `models/lg_pit.py` | Maximum closure, found by one minimum cut |
| Unit commitment and wholesale electricity prices | `models/uc_price.py` | Mixed-integer program, then prices from linear duals |

The two models share the same working rules and nothing else. Each one defines its
feasible set once and lets every solve route read that one definition.

## 1. Ultimate pit limit

### The question

An ore body is divided into blocks. A block's value is its metal revenue less mining and
processing cost. Waste usually has a negative value.

Mining every positive block is wrong. Reaching a deep block requires removing a widening
set of blocks above it so the wall stays stable. A rich block stays in the ground when it
cannot pay for that stripping. The task is to choose the highest-value set that contains
every required upper block.

Lerchs and Grossmann stated the mining problem in 1965. Picard showed in 1976 that this
kind of closed set can be found by one exact minimum cut. There is no search heuristic in
the answer.

### Four solve routes

`models/lg_pit.py` is the only model definition. Every route consumes the same value
vector `v` and precedence array `E`; there is no second copy of the block economics or
slope rules.

| Function | Route | Purpose |
| --- | --- | --- |
| `mc` | OR-Tools maximum flow with exact integer capacities | Default solve |
| `mc_nx` | NetworkX minimum cut with floating-point capacities | Checks the integer scaling and library adapter; same reduction |
| `lp` | SciPy closure linear program | Checks the cut formulation through a different optimisation model |
| `bf` | Generates every valid closed set | Exact ground truth for at most 20 blocks |

The scalable routes deliberately share `E`, so agreement between them cannot prove that
its direction or geometry is right. Separate tests inspect every arc, boundary counts,
closure of the returned pit, hand-worked examples, and the official MineLib solution.
`models/minelib.py` is only the input reader.

### Check against an outside answer

MineLib publishes the Newman1 ultimate-pit instance, a rounded optimum of 26,086,899, and
the official selected blocks. The committed fixture has 1,060 blocks and 3,922 precedence
arcs. Its values require five decimal places, so the reader uses 100,000 exact integer
units per dollar.

This code returns 26,086,899.025970. It rounds to MineLib's published value and selects
exactly the same 1,059 block IDs as MineLib's solution file. OR-Tools, NetworkX and the
linear program all return the same objective. File origins and hashes are in
[Sources](docs/SOURCES.md).

## 2. Unit commitment and electricity prices

### The question

A generating unit is not a smooth supply curve. It costs money to start, costs money per
hour merely to stay on, cannot run below a minimum output, and cannot change output faster
than its ramp rate. Those features are non-convex, and because of them there is generally
no single energy price that makes every unit content with the schedule it was given.

The market operator therefore does two separate things. It picks the cheapest feasible
schedule, which is an integer problem. It then sets a price, which is a different problem
with more than one defensible answer:

- **LMP** holds the chosen commitment fixed and prices the last megawatt. Start-up and
  no-load costs are invisible to it, so units are paid a private side payment afterwards.
- **Convex hull pricing** replaces each unit's feasible set with its convex hull and its
  cost with the convex envelope. Its price is the one that makes the total of those side
  payments as small as any uniform price can.
- **Average incremental cost pricing** first restricts each unit that needed a side
  payment to roughly the output it was told to produce, then prices that restricted
  market. It aims to make the make-whole payment disappear entirely.

`models/uc_price.py` builds all of this on one description of a unit, written once in
`_rw`, `_eq` and `_fx`. Everything else reads that description.

### Seven solve routes over one feasible set

| Function | Route | Purpose |
| --- | --- | --- |
| `uc` | Mixed-integer program over the rows | Clears the market. Scales |
| `rx` | The same rows with the commitment relaxed | Priced relaxation, and a lower bound. Scales |
| `en` | Every joint commitment, each dispatched by its own program | Independent optimum, small cases |
| `hc` | Convex hull built from each unit's on-intervals | Exact convex hull and average incremental cost prices. Default |
| `hl` | The same hull built from each unit's whole schedules | The independent check on `hc`, small cases |
| `lmp` | The rows with the cleared commitment held fixed | Locational marginal prices |
| `qd` | Best self-schedule per unit, as one small integer program each | The Lagrangian dual value, and every unit's foregone profit |

`hc` and `hl` read the feasible set as schedules; `uc`, `rx` and `qd` read it as algebraic
rows. Those are two different descriptions of the same set, which is what makes their
agreement worth something. `run` clears once and derives every price from that one
clearing.

### Why there are two convex hulls

The convex hull price needs each unit replaced by the convex hull of everything it could
have done. `hl` does that the obvious way: list every on/off schedule, attach the dispatch
polytope each one allows, and take the convex hull of that union. It is exact, and it is
useless past about twelve periods, because the list doubles with every period added.

`hc` gets the same hull from a graph. A unit's schedule is a run of on-intervals separated
by off time, so put a node at each period the unit is free to start in, draw an arc across
each possible on-interval, and let that arc carry only its own interval's dispatch
polytope. A schedule is then a path, the minimum down time is the length of the jump each
arc makes, and the hull is the graph's flow polytope with those polytopes hung on its arcs.
That is about T squared over two arcs in place of two-to-the-T schedules.

Its exactness is Yu, Guan and Chen's result, and more generally it is what happens whenever
a problem is solved by a recursion over an acyclic graph. It is not taken on trust here.
The tests hold `hc` against `hl` on every published case and on seeded random units with
ramps, minimum run times and carried-in initial states, and they agree exactly.

### A transmission network

`Net` gives each unit a bus and each line a reactance and a limit, and demand becomes one
row per bus. Flow on a line is the difference of its end voltage angles over its reactance,
which is the approximation wholesale markets actually clear on. `_nw` writes that once and
every route reads it, so a market with no network is this same code with one bus and no
lines rather than a second path through the model. Prices are therefore always one per bus
per period.

`ex4` is the standard symmetric three-bus loop, chosen because its answer is arithmetic.
With equal reactances, two thirds of whatever bus 0 injects takes the direct line to bus 2,
so a 40 MW limit on that line holds the cheap unit at bus 0 to exactly 60 MW. The model
returns 60 MW, and prices of $10, $30 and $50 at buses 0, 1 and 2: bus 1 is electrically
midway and prices midway. Open the limit and the three prices collapse to one.

Adding the network also caught a real error. The program that picks a canonical price
constrains the dual variables of the priced program, and that constraint is an equality. It
had been written as an inequality, which is harmless for as long as every variable carries a
bound row, because that row's own multiplier quietly absorbs the slack. A voltage angle is
free and has no such row. With the inequality in place the three-bus loop priced an
uncongested network at minus $10, $0 and $10 instead of $10 everywhere. No single-bus case
could have exposed it.

### Prices at a kink

A price is the slope of cost against demand, and at a kink that slope is not a single
number. Adding the average incremental cost restriction makes this routine, because the
restriction often leaves the priced market with no headroom at all. A solver returns
whichever of the equally optimal prices its basis happens to land on.

Every priced solve here therefore re-picks, among exactly the prices that are optimal, the
one that pays least for the demand served. That is the lower slope: the marginal cost of
the megawatts actually delivered. Without this rule the same input returns different prices
on different runs or different solver versions.

Even that leaves a face rather than a point, so each period's price is then minimised in
turn and held. It still does not always close to a single point. On one seeded market in
141, the two hulls return visibly different prices once the average incremental cost
ceilings are on. Both maximise the Lagrangian dual, both pay exactly the same for the
demand, and the cleared cost agrees to nine figures. The data genuinely does not choose
between them, and the refinement cannot narrow the face below the solver's own tolerance. A
test asserts what is determined and asserts that the prices differ, so the fact stays
visible rather than being tuned away. It is one more reason to handle the average
incremental cost price with care.

### Check against outside answers

| Published case | What it fixes | Result |
| --- | --- | --- |
| Hua and Baldick (2017) Example 1 | One period, two units, 35 MW | Cleared cost 1,850. LMP $50 with uplift (100, 1,900); exact convex hull price $12 with uplift (1,430, 0). All match Table 2 |
| Hua and Baldick (2017) Example 2 | Three periods with ramping | Dispatch matches Table 4 exactly. LMP (60, 60, 60) with uplift (0, 560); exact convex hull price (60, 60, 65.6) with uplift (168, 0). Both match Table 5 |
| Chen, O'Neill and Whitman, FERC 2020, two-generator case | Three periods, a start-up cost recoverable only at the peak | Dispatch, LMP (10, 10, 90), unit 2's period profits of −1,830, −1,030 and 1,170, its 1,690 make-whole payment and the 1,690 total uplift all match the talk |

At the talk's own average incremental cost price of $146.33 for period three, this model
returns the talk's whole line: total profit 13,633, best achievable profit 14,771, uplift
1,138 and no make-whole payment. The unit data and the payment rules are therefore the
same as the talk's.

The one number this repository does **not** reproduce is that $146.33 itself. Both exact
hulls, the schedule-wise one and the compact one, give $422. The reason is exact and is kept
as a test: $146.33 is precisely the value of mixing unit 2's cleared schedule with being
off, and it is recovered here to the last digit when unit 2's hull is limited to those two
schedules. The exact hull also contains the "start at period 2" schedule, whose mixture is
worth more, and the price follows the better mixture. Both prices leave no make-whole
payment, which is all the talk's Proposition 3 claims. The talk does not publish the rows of
the formulation behind its figure, so no stronger statement is made here than that the two
differ and why. Two independently built exact hulls now agree on $422, so the difference is
at least not an artefact of how the hull was constructed.

The talk's second figure, $1,161 from its three-binary formulation, is not reproduced
either, and for the same reason: which valid inequalities a three-binary formulation
carries changes that number, and the talk does not list them. `rx` returns $218.31 on this
case. That is reported as a measurement of this formulation, not as a replication.

### What the prices actually cost

Two identities are checked on every case and on random prices, not assumed:

- Total uplift at any price equals the cleared cost less the Lagrangian dual value at that
  price. This is the gap between the integer problem and its dual.
- The convex hull program's objective equals the maximum of that dual over all prices, so
  no price leaves less uplift than the convex hull price does.

## Measured run

`run_bench.py` prints the four tables below, measured on 2026-09-14 with Python 3.14.3,
OR-Tools 9.15.6755, NetworkX 3.6.1, SciPy 1.17.1, NumPy 2.4.4, Windows 11 build 26200, and
an Intel64 family 6 model 186 processor. Times are elapsed seconds from one run, not
projections, and will vary by machine.

The pit table and the three market tables come from two runs on that same machine and day.
The pit linear program builds a 2,082,896-row model and needs more memory than was free
when the market tables were measured; it ran on its own earlier the same day.

### Ultimate pit limit

| Model | Blocks | Arcs | Pit value | OR-Tools | NetworkX | LP | Fractional | Strip ratio | Ore left out |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30x30x12 | 10,800 | 85,184 | 2,552.23 | 0.009s | 0.92s | 0.22s | 0 | 2.64 | 73 |
| 60x60x20 | 72,000 | 601,996 | 20,102.47 | 0.080s | 8.67s | 2.21s | 0 | 2.06 | 230 |
| 90x90x30 | 243,000 | 2,082,896 | 68,454.46 | 0.317s | 40.34s | 10.83s | 0 | 2.03 | 602 |

The ore left out is the useful result: each of those blocks makes money by itself, but not
after paying for the waste above it. The linear program returned no fractional block
choices, as expected from its network matrix. That confirms the form of the linear
program; it does not confirm arc direction.

The synthetic generator is designed to produce a non-empty pit, omit at least one positive
block, and keep the waste-to-ore ratio between 1.5 and 3.0. That band is a regression check
for this generator, not a claim about real mines.

The arc representation was measured separately on the 90x90x30 model. The old Python list
of 2,082,896 tuples took 4.454 seconds to build and reached 270.51 MiB of traced
allocation. The one `int32` array now used by every solver took 0.410 seconds and 15.90
MiB. The linear program no longer makes another copy.

### Market clearing and locational prices

| Units x periods | Variables | Cleared cost | uc | rx | pay | Relaxation gap | Units needing make-whole | LMP uplift |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 12 x 8 | 384 | 321,499 | 3.21s | 0.69s | 0.38s | 0.328% | 2 | 1,898 |
| 24 x 16 | 1,536 | 1,264,174 | 7.14s | 5.63s | 0.82s | 0.085% | 6 | 5,478 |
| 48 x 24 | 4,608 | 3,831,805 | 3.98s | 42.12s | 1.35s | 0.035% | 5 | 6,473 |
| 96 x 24 | 9,216 | 7,721,565 | 5.67s | 137.53s | 3.12s | 0.013% | 5 | 6,346 |

The synthetic market runs from cheap, slow, high-minimum baseload to costly, fast peakers
over a daily demand shape. Its economic regression check is that at least one unit needs a
make-whole payment under LMP; a market where none does has no pricing question to answer.

The `rx` column is the odd one, and it is worth reading carefully: a relaxation has no
business being slower than the integer program it relaxes. It is not the solve. It is the
price. Picking one canonical price costs a further linear program per balance row, on the
transpose of the model, and over a 24-period day that is 25 of them.

That was measured on the 48 x 24 market. The relaxed solve and the payment-minimising stage
together take 1.38 seconds; walking the periods one at a time takes 40.78 seconds, and it
moves the price by 2.3 millionths of a dollar. On an uncongested relaxation the extra work
buys almost nothing, because the face is already nearly a point. It earns its keep only
where the average incremental cost ceilings have made the program integral and the face
genuinely fat. Splitting that decision without adding a second code path is the largest
thing still worth fixing here.

### Exact convex hull prices

| Units x periods | Arcs | Schedules | CHP | AIC | Schedule-wise | Price gap | LMP uplift | CHP uplift | AIC uplift | AIC make-whole |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 6 x 4 | 79 | 70 | 0.11s | 0.07s | 0.13s | 4e-13 | 762 | 260 | 486 | 0.00 |
| 8 x 6 | 200 | 332 | 0.38s | 0.40s | 1.40s | 2e-12 | 1,698 | 363 | 686 | 0.00 |
| 10 x 8 | 409 | 1,528 | 1.89s | 1.18s | 14.37s | 1e-07 | 1,924 | 366 | 38,447,064 | 0.00 |
| 12 x 10 | 730 | 6,924 | 5.65s | 4.01s | 212.67s | 8e-11 | 1,855 | 752 | 3,651 | 0.00 |
| 8 x 14 | 896 | over the ceiling | 16.69s | 10.06s | refused | n/a | 5,460 | 1,964 | 4,727 | 0.00 |

The CHP and AIC columns are `hc`, the interval form. The schedule-wise column is `hl`
solving the identical hull the obvious way, and the price gap is the largest difference
between the two prices. They are the same answer: at 12 x 10, 730 arcs in place of 6,924
schedules, 5.65 seconds in place of 212.67, and prices apart by eight in the eleventh
decimal. At 8 x 14 the schedule-wise route will not start at all.

Three economic things are visible here and all three are real.

The convex hull price always leaves less uplift than LMP, as the theory requires. The
average incremental cost price always removes the make-whole payment entirely, as its
sponsors claim. And the price it charges to do so is not bounded: on the 10 x 8 market it
leaves 38.4 million in foregone profit. That is not a defect in the solve. The restriction
squeezes the priced market until supply barely meets demand in the binding period, and the
marginal cost of the last megawatt in such a market can be arbitrarily large. Anyone
proposing this rule for real settlement has to answer that, and this repository measures it
rather than describing it.

### A congested network

`ex4` again, at four limits on the direct line. Every number here can be checked by hand
from the two-thirds flow split.

| Line 0-2 limit | Bus 0 output | Bus 2 output | Cost | Price at 0 | Price at 1 | Price at 2 | Congestion rent |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 MW | 90 | 0 | 900 | 10.00 | 10.00 | 10.00 | 0 |
| 60 MW | 90 | 0 | 900 | 10.00 | 10.00 | 10.00 | 0 |
| 40 MW | 60 | 30 | 2,100 | 10.00 | 30.00 | 50.00 | 2,400 |
| 20 MW | 30 | 60 | 3,300 | 10.00 | 30.00 | 50.00 | 1,200 |

At a 60 MW limit the line is exactly full and nothing has yet been given up, so there is
still one price. Tighten it and the cheap unit is held to one and a half times the limit,
the three buses price apart, and the market collects a congestion rent it pays to nobody:
load at bus 2 pays 90 MW at $50 while generators are paid $10 and $50 for what they made.
That rent is the money financial transmission rights are written against, and it is also
the reason the talk ends by warning that lines which do not bind in the clearing can bind
in the pricing run.

## Run it

Use the one system Python on this machine; no virtual environment is needed.

```text
python -m pip install -r requirements.txt
python -m pytest -q
python -m ruff check .
python run_bench.py
```

The last full verification on 2026-09-14 passed 118 tests and the complete lint check.
