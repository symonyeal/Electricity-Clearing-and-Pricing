# Ultimate pit limit

Let $B$ be the blocks, $v_b$ the net value of block $b$, and $P(b)$ the blocks that
must be removed before $b$. The model is

$$
\begin{aligned}
\max_x \quad & \sum_{b\in B} v_b x_b \\
\text{s.t.}\quad & x_b \le x_p && b\in B,\ p\in P(b),\\
& x_b\in\{0,1\} && b\in B.
\end{aligned}
$$

This is a maximum-closure problem. Picard's reduction solves it by one minimum cut.

| Function | Method | Role |
| --- | --- | --- |
| `mc` | OR-Tools maximum flow; exact integer capacities | Default |
| `mc_nx` | NetworkX minimum cut | Independent implementation of the reduction |
| `lp` | Linear programming relaxation | Independent formulation |
| `bf` | Enumeration of closed sets | Exact check for at most 20 blocks |

All routes use the same precedence array. Separate tests check arc direction, boundary
counts, closure, and economic nontriviality.

### External validation

The MineLib Newman1 fixture has 1,060 blocks and 3,922 precedence arcs. The model returns
26,086,899.025970 and the same 1,059 selected block IDs as the official solution. Its
rounded value is MineLib's 26,086,899. OR-Tools, NetworkX, and the LP agree. File hashes are
in [Sources](SOURCES.md#minelib-benchmark).
