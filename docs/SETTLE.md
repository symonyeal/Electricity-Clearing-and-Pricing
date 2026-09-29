# Storage in the clearing: value, settlement, and the mode cut

This study measures how cleared storage changes dispatch, congestion, prices, make-whole
payments, and settlement allocation under the repository's stated pricing rule.

[Joint clearing](JOINT.md) puts storage inside the market program; [Storage trading](TRADING.md)
values it against prices it does not move. `models/settle.py` asks what clearing it
changes: dispatch, price, congestion, make-whole, and who is paid. It reads joint's rows
and adds no market rule. `python run_settle.py` regenerates every table here.

## Setting

Three buses. Bus 0 holds A, 70 MW at 10/MWh. Bus 1 holds the load, 40, 40, 100 and 40 MW,
and two units: B, a peaker with a 10 MW floor, 50/MWh and a 600 start-up, and C, flexible
at 80/MWh. Bus 2 is an empty spur. Lines 0–1 and 1–2 have unit reactance. Without storage
the peak needs 30 MW beyond A, B serves it, and the clearing costs 4,000. At the price
that holds the integers, $(10,10,50,10)$, B loses its start-up: 600 of make-whole.

Every clearing here is an integer program with the thermal commitment integer, and every
price holds the clearing's integers and reads the balance duals, as `joint.lmp` does.
**That pricing rule is a market-design choice**, the repository's; every statement about
who is paid is conditional on it. The rest of this section is mathematics.

**Settlement identity.** At any price $\pi$ and any balanced dispatch,

$$
\underbrace{\sum_{b,t}\pi_{bt}d_{bt}}_{L}-z
=\sum_g r_g+\sum_j r^s_j+R,
\qquad R=\sum_{\ell,t}f_{\ell t}\,(\pi_{q(\ell)t}-\pi_{a(\ell)t}),
$$

where $z$ is the dispatch's cost, $r_g$ unit profit, $r^s_j$ storage profit, and $R$ the
congestion rent. `stl` computes $R$ twice: as the payment difference, and from flows
$f=(\theta_a-\theta_q)/x$ with $B\theta$ equal to the nodal injections, solved without the
clearing's angle columns. The two agree to $10^{-12}$ on every case, as they must for any
flows that balance the injections, at any price: the agreement checks the payments. The
prices are checked by complementary slackness. Every case's network is a tree, so the
limit's multiplier on a line is the price difference across it, which the tests find
nonzero only on a line at its limit. Each load-bus price also lies between the one-sided
derivatives of the held value in demand (BT Theorem 5.2), an interval that is a point in
every case but s1.

**The resource never needs make-whole under this rule.** With the modes held, the
re-dispatch is a linear program. Relaxing its balance rows at an optimal dual leaves each
resource minimising its own cost less its revenue, and the cleared schedule is such a
minimiser. Idling is feasible under any modes when $e_0=e_f$ or $e_f$ is free. Hence
the resource's profit at the held-integer price is its best over its held-mode polytope,
and it is non-negative. The tests check the equality on every case. Its profit can still
fall short of any fixed cost, which the clearing never sees.

**The mode cut.** Let $X$ be the resource's feasible set with binary modes, $H=\operatorname{conv}(X)$,
and $R$ the set with the modes relaxed and the cut $c/C+d/D\le1$ kept. Then
$X\subseteq H\subseteq R$, so every clearing satisfies $z_X\ge z_H\ge z_R$. `settle` builds
$H$ exactly, by Balas' union of the $2^T$ mode-pattern polytopes. Each pattern's polytope is
joint's own rows with the mode held.

*The cut is exact for profit above a threshold.* Let $h=\eta_c\eta_d$. If
$p_t\ge-k(1+h)/(1-h)$ in every period, then $\max_R p^\top(d-c)-k(c+d)=\max_X$. Proof: at
a period with $c_t,d_t>0$, lower $c_t$ by $\delta$ and $d_t$ by $h\delta$. The stored
energy is unchanged, so every energy row, bound and the cut still hold, and profit changes
by $\delta\,[p_t(1-h)+k(1+h)]\ge0$. Repeating removes every simultaneous pair without loss
and leaves a schedule of $X$. Below the threshold, the cut lets the resource destroy
energy for money. In a clearing that means absorbing a surplus the store has no room for.

## The seven cases

| Case | Resource | Network | What it isolates |
| --- | --- | --- | --- |
| s1 | 40 MWh, 30 MW at the load bus | no line binds | energy value with no congestion |
| s2 | the same, on the spur | spur limited to 15 MW | deliverability behind a line |
| s3 | the same, at A's bus | line 0–1 limited to 85 MW | a resource at the cheap bus |
| s4 | 20 MWh, 30 MW at the load bus | no line binds | the energy bound |
| s5 | 60 MWh, 15 MW at the load bus | line 0–1 limited to 70 MW | the power bound, behind a binding import |
| s6 | 20 MWh, 30 MW, 80% each way, empty | no line binds | the cut exact |
| s7 | the same, full | no line binds | the cut not exact |

s1–s5 are lossless and use the load above. s6 and s7 use two periods, 40 then 100 MW, and
an A that must stay above 45 MW or pay 2,000 to restart, so 5 MW of A's output in period 1
must be stored or A must stop.

### Value and settlement

| Case | Cost without | Cost with | Saved | Storage profit | Load pays, without | Load pays, with | Make-whole, without | Make-whole, with | Lost opportunity, with | Rent, without | Rent, with |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| s1 | 4,000 | 2,200 | 1,800 | 0 | 6,200 | 2,200 | 600 | 0 | 0 | 0 | 0 |
| s2 | 4,000 | 3,250 | 750 | 0 | 6,200 | 9,200 | 600 | 0 | 1,200 | 0 | 1,050 |
| s3 | 4,000 | 3,250 | 750 | 0 | 6,200 | 9,200 | 600 | 0 | 1,200 | 0 | 5,950 |
| s4 | 4,000 | 2,900 | 1,100 | 1,400 | 6,200 | 9,200 | 600 | 0 | 1,200 | 0 | 0 |
| s5 | 4,000 | 3,250 | 750 | 1,050 | 6,200 | 9,200 | 600 | 0 | 1,200 | 2,800 | 4,900 |
| s6 | 6,800 | 2,470 | 4,330 | 1,030 | 7,000 | 8,400 | 600 | 0 | 1,200 | 0 | 0 |
| s7 | 6,800 | 6,000 | 800 | 800 | 7,000 | 7,000 | 600 | 600 | 4,800 | 0 | 0 |

"Lost opportunity, with" is the units' and the resource's together; the resource's is zero
in every case.

### Prices at the load bus and the resource's bus

| Case | Bus | Without | With |
| --- | ---: | --- | --- |
| s1 | 1 | 10, 10, 50, 10 | 10, 10, 10, 10 |
| s2 | 1 | 10, 10, 50, 10 | 10, 10, 80, 10 |
| s2 | 2 | 10, 10, 50, 10 | 10, 10, 10, 10 |
| s3 | 0 | 10, 10, 50, 10 | 10, 10, 10, 10 |
| s3 | 1 | 10, 10, 50, 10 | 10, 10, 80, 10 |
| s4 | 1 | 10, 10, 50, 10 | 10, 10, 80, 10 |
| s5 | 1 | 10, 10, 50, 10 | 10, 10, 80, 10 |
| s6 | 1 | 50, 50 | 10, 80 |
| s7 | 1 | 50, 50 | 50, 50 |

**s1.** The resource charges 30 MWh from A off-peak and meets the peak itself, so B never
starts. Cost falls by 1,800 and the 600 of make-whole disappears. The resource earns
nothing at every optimal price, since it charges and discharges the same energy at one
price. That price is not determined: the optimal face lets the charging and peak periods
price anywhere in [10, 80]. The payment rule takes A's 10, and with it load's saving of
4,000.

**s2.** On the spur it delivers 15 MW, C serves the remaining 15, and B is not started.
The spur binds in both directions, so the spur bus prices at 10 throughout. The resource
earns nothing; the spur's 1,050 of rent is what its energy was worth at the load.

**s3.** At A's bus it fills the line: A and the resource send 85 MW at the peak. Bus 0 now
prices at 10 and bus 1 at C's 80. A loses the 2,800 it earned at a peak price of 50, the
resource earns nothing, and the rent is 5,950. The resource saved 750, and its bus's price
does not show it.

**s4.** The energy bound binds: 20 MWh covers 20 MW of the peak. C serves 10, B is not
started, and the peak price rises from B's 50 to C's 80. The resource earns 70 on each of
its 20 MWh, 1,400, more than the 1,100 it saved.

**s5.** The power bound binds at 15 MW and the import line binds without it. The resource
earns 1,050. Against bus 0 all of it is congestion value; against bus 1 all of it is
energy value:

| Case | Resource bus | Energy, ref 0 | Congestion, ref 0 | Energy, ref 1 | Congestion, ref 1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| s2 | 2 | 1,050 | −1,050 | 1,050 | −1,050 |
| s3 | 0 | 0 | 0 | 2,100 | −2,100 |
| s5 | 1 | 0 | 1,050 | 1,050 | 0 |

The split prices the resource's net injection at a reference bus and calls the remainder
congestion. It moves with the reference, and the total does not. The reference is a
convention, not a property of the resource.

### The three descriptions of the resource

| Case | $z_X$ | $z_H$ | $z_R$ | $z_X-z_H$ | $z_H-z_R$ | Price over R at bus 1 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| s1 | 2,200 | 2,200 | 2,200 | 0 | 0 | 10, 10, 10, 10 |
| s2 | 3,250 | 3,250 | 3,250 | 0 | 0 | 10, 10, 80, 10 |
| s3 | 3,250 | 3,250 | 3,250 | 0 | 0 | 10, 10, 80, 10 |
| s4 | 2,900 | 2,900 | 2,900 | 0 | 0 | 10, 10, 80, 10 |
| s5 | 3,250 | 3,250 | 3,250 | 0 | 0 | 10, 10, 80, 10 |
| s6 | 2,470 | 2,470 | 2,470 | 0 | 0 | 10, 80 |
| s7 | 6,000 | 6,000 | 2,270 | 0 | 3,730 | 0, 80 |

**s6.** The store starts empty and takes A's surplus by charging: 25 MW in period 1, of
which 16 MW comes back at the peak. No period needs charge and discharge together, and
the three descriptions agree.

**s7.** The store starts full. No schedule absorbs energy into a full store, and neither
does a mixture of schedules that each start full. So over X and over H, A stops in period
1, B serves 40 MW, and A restarts for the peak: 6,000. Over R the store charges 13.889 MW
and discharges 8.889 MW in the same period. That leaves it full, since
$0.8\times13.889=8.889/0.8$, and destroys 5 MWh as loss. A stays on, and the clearing
costs 2,270. The cut overstates the resource by 3,730, all of it the energy bound the cut
ignores; $H$ is not strictly between. Over R the surplus period prices at 0, which is the
threshold above at $k=0$: the only prices at which destroying energy is worth anything.

## Market design

s1's resource, three ways. Co-optimised, the market schedules it as above. Price-taking,
it schedules itself against the no-storage price $(10,10,50,10)$, expects 1,200, and the
market takes that schedule in full. As a curve, the same position is offered through
`market/bid.py`'s `curve` around that price: discharge slices at reservation prices, charge
slices at bids. The clearing accepts what a single price would. The offer replaces the
throughput cost in the objective, and the energy rows still hold.

| Design | Cost | Peak price | Storage profit | Load pays | Lost opportunity |
| --- | ---: | ---: | ---: | ---: | ---: |
| Co-optimised | 2,200 | 10 | 0 | 2,200 | 0 |
| Price-taking schedule, imposed in full | 2,200 | 10 | 0 | 2,200 | 0 |
| Curve, 1 step, spread 0 | 2,200 | 50 | 1,200 | 6,200 | 0 |
| Curve, 3 steps, spread 0.2 | 2,200 | 62 | 1,560 | 7,400 | 120 |
| Curve, 5 steps, spread 1 | 2,620 | 80 | 1,680 | 9,200 | 1,200 |

The price-taking schedule is the co-optimised one, and it earns nothing. The spread it
was built on is the spread its own injection removes. As a curve the resource sets the
price it is paid. At one step the peak prices at its 50 offer. At three steps the 60 slice
clears, and the last charged slice, bid at 8, adds 2 through the energy row: the peak
prices at 62. At five steps the slice offered at 100 is above C's 80 and does not clear;
C runs 6 MW, cost rises by 420, and the peak prices at 80. Welfare is read from true cost,
never from the objective, which carries bids.

## What the cases answer

1. **Lower cost, unpaid.** s1: the resource saves 1,800 and earns 0. Under a held-integer
   price the resource's profit is its best over its held modes. When its own flexibility
   sets the price, the spread it trades is zero at every optimal price. Any fixed cost it
   carries goes unrecovered. Load keeps the 4,000 only under the payment rule's choice.
2. **Congestion moves the value.** s2 and s3 save 750 each and earn nothing, because the
   saving reappears as rent on the line the resource fills. In s3 that line is the one A
   uses, and A's 2,800 moves into rent as well. The reverse, profit beyond value, needs a
   nonconvexity, not congestion: in s4 and s5 removing B moves the peak price from 50 to 80.
   With the integers fixed, the cost $z(y)$ of meeting demand given the resource's
   injection $y$ is convex, and its price is $-\nabla z(y)$. Hence
   $z(0)-z(y)\ge-\nabla z(y)^\top y$: what the resource saves is at least what it earns at
   the post-entry price. Only a change of commitment breaks that inequality.
3. **The cut's overstatement.** Zero whenever the store can absorb what the system asks,
   s1–s6. 3,730 of 6,000, 62%, in s7, where the energy bound binds and the system needs
   energy destroyed. At the resource's own profit the cut is exact above
   $-k(1+h)/(1-h)$, and it is never exact below it with a full store.
4. **Curves.** The same energy clears; who is paid changes. The resource earns 1,200 to
   1,680 instead of 0, and load pays 4,000 to 7,000 more. A wide spread withholds the top
   slice and costs 420 of welfare.
5. **Separation.** Each case moves one quantity, and each quantity has its own
   identity-backed number: energy and congestion value by reference bus (s5), the rent
   (s2, s3), make-whole (600 to 0 everywhere but s7), and lost opportunity. The last is
   B's 1,200 at the new peak price of 80 in s2–s6, and A's 4,800 in s7. The
   energy/congestion split is not unique; the other three are.

## Scope

No reserve, losses, or multi-day horizon. No ISO's tariff or settlement rule is
implemented: the curve is `market/bid.py`'s mechanism with its own parameters, not any
market's, and no NYISO rule is claimed. The held-integer price is the repository's
convention. A convex hull price for the joint feasible set remains open
([Open issues](ISSUES.md), item 3).
