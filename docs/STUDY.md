# Demand sensitivity

`ecp case 3 study` uses the two-generator input published on slide 13 of the
[2020 FERC presentation](https://www.ferc.gov/sites/default/files/2020-06/W2-1_Chen_et_al.pdf).
The source table specifies both units' capacities, costs and ramps and demand
(95, 100, 130) MW. Those inputs are retained in `cases/3.json`; omitted minimum times
are one hour and units initially rest, as in the existing benchmark convention.
These are published illustrative parameters, not observations from an operating market.

This source fits the price-formation question and implemented feasible set. The
[PGLib-UC benchmarks](https://github.com/power-grid-lib/pglib-uc) provide larger public
cases, but include reserve requirements, piecewise production costs, renewable time
series and downtime-dependent startup costs. Importing them while discarding those
features would answer a different question. Observed demand and LMP series alone also
do not identify private offers or reconstruct commitment and uplift. The current study
therefore deepens the sourced small-system experiment.

The study scales every bus and period's demand by the same factor from 0.8 to 1.0.
Offers, unit limits, initial states and network remain fixed. It first evaluates five
equally spaced factors. Each additional solve bisects the interval with largest
width-weighted score: one plus ten for a commitment or solve-availability change,
plus the relative change in total LMP uplift (denominator at least one dollar).
There are 17 samples, sorted by scale. Ties select the later interval.

Each sample calls the ordinary clearing/pricing/settlement route. The output retains
the complete base market, model version, scaling factors, binary schedules, costs,
prices, bounds, gaps, price-selection quality and each unit's settlement. A failed
sample retains its typed error; it contributes no fabricated zero or incumbent.
The complete comparison requires successful payment minimisation, while individual
pricing routes expose weaker price-selection quality for callers to accept explicitly.

For the FERC input, the original endpoint reproduces cost 7,340 and total uplift near
1,690 under LMP and 365 under CHP. Lower demand does not make uplift monotone: sampled
CHP uplift falls to about 10 at scale 0.940625, then rises to about 795 at 0.94375 when
the optimal commitment changes. The adaptive search places additional samples around
that jump and another near scales 0.978125–0.98125. This connects fixed costs and
schedule changes to the price rule comparison.

The factors are modeled scenarios. The method learns where to sample from earlier
solves; it does not fit a forecasting model. A finite sample cannot certify every
transition, monotonicity or a globally optimal operating policy. Equal sampled
commitments may hide intermediate changes, and failure can reflect numerical or
price-selection issues as well as infeasibility. Bounds apply to each solved market,
not to the unsampled intervals.

The [retained run](results/ferc-study.json) contains all 17 successful samples from
version 0.4.0. Reproduce it with `cargo run --release --locked -- case 3 study`.
An independent calculation checked the source parameters, binary schedules, output
and ramp constraints, energy balances, costs, realized profits, uplift components,
CHP duality gaps and adaptive sample placements. This checks the reported finite
experiment; it does not establish behavior between samples.
