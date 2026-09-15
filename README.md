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
  market. As the restriction shrinks, it aims to remove make-whole from the commitment
  blocks placed in that restricted set.

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
ramps, minimum run times and carried-in initial states. The suite covers all 104 feasible
markets among seeds 0 through 140; objectives agree to relative tolerance 1e-9 and prices
to $0.0001/MWh.

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

Even that can leave a face rather than a point. Before minimising each period's price in
turn, one zero-objective interior-point program probes the payment-optimal face without
crossover. If its balance prices are within $0.001/MWh of the payment-minimising vertex,
the walk is skipped. Otherwise every period is still minimised and held. This is a measured
screen, not a bound on the face's diameter, and it does not branch on whether output
ceilings are present.

A forced-walk scan covered 410 compact, schedule-wise, capped and uncapped solve routes
from seeds 0 through 140. The probe skipped 391; the largest price change it omitted was
$0.00000444/MWh. It retained the materially wide seeded faces. One of those, seed 61 with
the ceilings on, still makes the two hulls return visibly different prices. Both maximise
the Lagrangian dual, pay the same for demand, and agree on cleared cost to nine figures.
A regression test preserves those facts, including the price difference.

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
payment. This is consistent with Proposition 3 of
[Chen, O'Neill and Whitman (2020)](docs/SOURCES.md#unit-commitment-and-electricity-prices),
whose precise claim is zero make-whole in the epsilon limit for the commitment blocks in
its restricted set. The talk does not publish the rows of the formulation behind its
figure, so no stronger statement is made here than that the two differ and why. Two
independently built exact hulls agree on $422, so the difference is not an artefact of how
the hull was constructed.

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

`run_bench.py` prints the six tables below, measured on 2026-09-15 with Python 3.14.3,
OR-Tools 9.15.6755, NetworkX 3.6.1, SciPy 1.17.1, NumPy 2.4.4, Windows 11 build 26200, and
an Intel64 family 6 model 186 processor. Times are elapsed seconds from one run, not
projections, and will vary by machine.

Every table came from one complete run. The largest pit linear program built and solved all
2,082,896 rows without a memory failure.

### Ultimate pit limit

| Model | Blocks | Arcs | Pit value | OR-Tools | NetworkX | LP | Fractional | Strip ratio | Ore left out |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 30x30x12 | 10,800 | 85,184 | 2,552.23 | 0.009s | 0.83s | 0.23s | 0 | 2.64 | 73 |
| 60x60x20 | 72,000 | 601,996 | 20,102.47 | 0.085s | 8.14s | 2.06s | 0 | 2.06 | 230 |
| 90x90x30 | 243,000 | 2,082,896 | 68,454.46 | 0.420s | 41.69s | 10.83s | 0 | 2.03 | 602 |

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
| 12 x 8 | 384 | 321,499 | 1.69s | 0.29s | 0.18s | 0.328% | 2 | 1,898 |
| 24 x 16 | 1,536 | 1,264,174 | 2.64s | 0.40s | 0.39s | 0.085% | 6 | 5,478 |
| 48 x 24 | 4,608 | 3,831,805 | 2.14s | 2.71s | 0.90s | 0.035% | 5 | 6,473 |
| 96 x 24 | 9,216 | 7,721,565 | 3.95s | 95.18s | 1.82s | 0.013% | 5 | 6,346 |

The synthetic market runs from cheap, slow, high-minimum baseload to costly, fast peakers
over a daily demand shape. Its economic regression check is that at least one unit needs a
make-whole payment under LMP; a market where none does has no pricing question to answer.

`rx` includes price selection as well as the relaxation. On the 48 x 24 market, an isolated
split measured 1.46 seconds for the relaxation and payment stage, 2.66 seconds with the
face probe, and 32.50 seconds when the 24-period walk was forced. The walk changed the price
by only $0.00000226/MWh, so the default route skips it. The full benchmark's corresponding
`rx` time is 2.71 seconds.

The screen does not hide a wide face. At 96 x 24 the probe differed from the payment vertex
by $0.02298/MWh, so the walk ran. A forced comparison moved the selected price by
$0.15225/MWh; the cheap path took 6.48 seconds and the specified walk took 94.82 seconds.
`LIM` remains the explicit cap on how many balance rows may be walked.

### Exact convex hull prices

| Units x periods | Arcs | Schedules | CHP | AIC | Schedule-wise | Price gap | LMP uplift | CHP uplift | AIC uplift | AIC make-whole |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 6 x 4 | 79 | 70 | 0.05s | 0.04s | 0.06s | 3e-13 | 762 | 260 | 486 | 0.00 |
| 8 x 6 | 200 | 332 | 0.15s | 0.11s | 0.39s | 4e-12 | 1,698 | 363 | 686 | 0.00 |
| 10 x 8 | 409 | 1,528 | 0.51s | 0.87s | 4.60s | 7e-11 | 1,924 | 366 | 38,447,064 | 0.00 |
| 12 x 10 | 730 | 6,924 | 4.37s | 0.80s | 134.49s | 8e-11 | 1,855 | 752 | 3,651 | 0.00 |
| 8 x 14 | 896 | over the ceiling | 2.84s | 6.26s | refused | n/a | 5,460 | 1,964 | 4,727 | 0.00 |

The CHP and AIC columns are `hc`, the interval form. The schedule-wise column is `hl`
solving the identical hull the obvious way, and the price gap is the largest difference
between the two prices. They are the same answer: at 12 x 10, 730 arcs in place of 6,924
schedules, 4.37 seconds in place of 134.49, and prices apart by eight in the eleventh
decimal. At 8 x 14 the schedule-wise route will not start at all.

The convex hull price leaves less uplift than LMP in every row, as the theory requires.
The average incremental cost rows all round to zero make-whole at the default epsilon, but
the wider sweep below shows why neither that result nor the 38.4 million uplift should be
generalised from one market.

### Average incremental cost price against epsilon

Epsilon is the extra MW allowed above each restricted commitment block's cleared output.
Cleared cost per MWh is the integer clearing objective divided by total demand. The premium
is the demand-weighted average energy price minus that cleared cost. Capped spare MW is
total capped capacity less demand in the period with the highest price.

| Market | epsilon MW | Period prices ($/MWh) | Uplift ($) | Make-whole ($) | Cleared cost ($/MWh) | Load-weighted price premium ($/MWh) | Highest-price period / capped spare MW |
| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| ex3 | 1e-06 | 10.000, 10.000, 422.000 | 730.00 | 0.00 | 22.58 | 152.22 | 3 / 0.000001 |
| ex3 | 0.0001 | 10.000, 10.000, 421.988 | 729.97 | 0.00 | 22.58 | 152.21 | 3 / 0.000100 |
| ex3 | 0.001 | 10.000, 10.000, 421.883 | 729.71 | 0.00 | 22.58 | 152.17 | 3 / 0.001000 |
| ex3 | 0.1 | 10.000, 10.000, 410.769 | 701.92 | 0.00 | 22.58 | 147.72 | 3 / 0.100000 |
| ex3 | 1 | 10.000, 10.000, 338.571 | 521.43 | 0.00 | 22.58 | 118.84 | 3 / 1.000000 |
| ex3 | 10 | 10.000, 10.000, 276.000 | 365.00 | 0.00 | 22.58 | 93.82 | 3 / 5.000000 |
| 8 x 6, seed 7 | 1e-06 | 74.724, 36.850, 56.210, 65.113, 58.745, 36.850 | 686.11 | 0.00 | 30.40 | 24.84 | 1 / 486.715002 |
| 8 x 6, seed 7 | 0.0001 | 74.724, 36.850, 56.210, 65.113, 58.745, 36.850 | 686.11 | 0.00 | 30.40 | 24.84 | 1 / 486.715200 |
| 8 x 6, seed 7 | 0.001 | 74.724, 36.850, 56.210, 65.113, 58.745, 36.850 | 686.11 | 0.02 | 30.40 | 24.84 | 1 / 486.717000 |
| 8 x 6, seed 7 | 0.1 | 74.704, 36.850, 56.210, 65.113, 58.729, 36.850 | 685.75 | 2.14 | 30.40 | 24.84 | 1 / 486.915000 |
| 8 x 6, seed 7 | 1 | 74.529, 36.850, 56.210, 65.113, 58.589, 36.850 | 682.58 | 21.10 | 30.40 | 24.79 | 1 / 488.715000 |
| 8 x 6, seed 7 | 10 | 73.699, 36.850, 56.210, 65.113, 57.357, 36.850 | 658.72 | 151.97 | 30.40 | 24.45 | 1 / 506.715000 |
| 10 x 8, seed 7 | 1e-06 | 84.020, 40.440, 40.440, 52.880, 55.564, 82,085.019, 46.387, 31.520 | 38,447,063.94 | 0.00 | 30.53 | 12,219.15 | 6 / 0.000001 |
| 10 x 8, seed 7 | 1e-05 | 84.020, 40.440, 40.440, 52.880, 55.564, 82,221.562, 46.370, 31.520 | 38,511,081.04 | 0.00 | 30.53 | 12,239.46 | 6 / 0.000010 |
| 10 x 8, seed 7 | 0.0001 | 84.020, 40.440, 40.440, 52.880, 55.564, 57,979.259, 49.360, 31.520 | 27,145,243.51 | 0.00 | 30.53 | 8,634.66 | 6 / 0.000100 |
| 10 x 8, seed 7 | 0.001 | 84.020, 40.440, 40.440, 52.880, 55.564, 57,979.206, 49.360, 31.520 | 27,145,218.58 | 0.01 | 30.53 | 8,634.66 | 6 / 0.001000 |
| 10 x 8, seed 7 | 0.0025 | 84.019, 40.440, 40.440, 52.880, 55.564, 57,978.079, 49.360, 31.520 | 27,144,689.94 | 0.03 | 30.53 | 8,634.49 | 6 / 0.002500 |
| 10 x 8, seed 7 | 0.00275 | 84.019, 40.440, 40.440, 52.880, 55.664, 67.146, 52.692, 31.520 | 1,559.91 | 0.08 | 30.53 | 22.76 | 1 / 747.982750 |
| 10 x 8, seed 7 | 0.005 | 84.018, 40.440, 40.440, 52.880, 61.048, 52.880, 52.693, 31.520 | 416.91 | 0.09 | 30.53 | 21.49 | 1 / 747.985000 |
| 10 x 8, seed 7 | 0.1 | 83.992, 40.440, 40.440, 52.880, 61.043, 52.880, 52.693, 31.520 | 416.46 | 1.87 | 30.53 | 21.49 | 1 / 748.080000 |
| 10 x 8, seed 7 | 1 | 83.751, 40.440, 40.440, 52.880, 60.989, 52.880, 52.693, 31.520 | 412.25 | 18.42 | 30.53 | 21.46 | 1 / 748.980000 |
| 10 x 8, seed 7 | 10 | 81.830, 40.440, 40.440, 52.880, 60.488, 52.880, 52.693, 31.520 | 377.90 | 159.98 | 30.53 | 21.20 | 1 / 757.980000 |

`ex3` is stable near $422/MWh through epsilon 0.001 and declines as the restriction
loosens. The 8 x 6 market is stable and has at least 486.7 MW spare in its highest-price
period. Near-zero headroom alone therefore does not make a price explode.

The 10 x 8 market has two high-price plateaus, then its period-six price falls from
$57,978.08 to $67.15 between epsilon 0.0025 and 0.00275. The feasible schedule set is the
same on both sides; only its output ceilings move. At the same point the highest-price
period shifts from period 6, with only epsilon MW spare, to period 1, with 748 MW spare.
In this market the blow-up coincides with depleted capped headroom, while its size and
discontinuity indicate a change of face in the fixed-cost convex envelope rather than a
simple inverse-epsilon rule.

The 1e-6 row is numerically thin: the compact and schedule-wise hulls put period six in the
same high-price regime but differ by $64.48/MWh. At 1e-5 they agree within $0.0002/MWh at
about $82,221.56/MWh. The table reports the compact solve as measured, not cents of
mathematical precision at the solver tolerance.

The default epsilon was also measured on 15 independently seeded 10 x 8 markets. "At
epsilon headroom" means capped spare MW is no more than 1.1e-6.

| Seeds | Peak price >$1,000/MWh: count (uplift range, $) | Peak price <=$1,000/MWh: count (uplift range, $) | Highest-price period at epsilon headroom | Make-whole below $0.001 | Largest make-whole ($) |
| ---: | --- | --- | ---: | ---: | ---: |
| 15 | 3 (32,759,768.79-38,447,063.94) | 12 (283.70-14,585.92) | 6 | 14 | 10.38 |

The 38.4 million result is one of three extreme markets, not the typical outcome. Six peak
periods have only epsilon MW spare, but only three have a four- or five-digit price, so
depleted headroom is not sufficient. Fourteen markets leave less than $0.001 make-whole.
In the fifteenth, the restriction makes its targeted block whole but creates a $10.38 loss
on another commitment block. That is outside Proposition 3's stated guarantee and is why
the repository no longer says the rule always removes all make-whole.

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

The last full verification on 2026-09-15 passed 236 tests, the complete Ruff and dependency
checks, and every benchmark row including the 2,082,896-row pit linear program.
