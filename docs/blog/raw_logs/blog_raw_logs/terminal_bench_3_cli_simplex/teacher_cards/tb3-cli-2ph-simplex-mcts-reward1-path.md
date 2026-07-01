# MCTS-Style Reward-1 Repair Path: cli-2ph-simplex

Source state: failed with-TD artifact
`/data/harbor/jobs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/artifacts/app`.

Search result: the patched state
`/data/harbor/td_artifacts/cli_mcts_search/states/s4_global_shortest`
passes the official verifier tests when mounted as `/app`:

```text
103 passed in 4.69s
```

## Reward-Improving Step Sequence

### Step 1: Fix Phase 1 artificial objective sign

Critical error:
`simplex/tableau.py::build_initial_tableau` initialized artificial-variable
objective coefficients as `-1.0`. The verifier/reference construction uses
`+1.0`, then canonicalizes with the artificial-basic rows.

Effect:

- Minimal `ge_bound_respected` stopped raising `Unbounded` and returned `24.0`.
- `fractional_primal_from_mixed_basis` returned `11.0`.
- Full score improved from `63 failed / 40 passed` to `12 failed / 91 passed`.

### Step 2: Pivot zero-valued artificial basics out before removing columns

Critical error:
After Phase 1, artificial variables can remain basic with value zero. Dropping
artificial columns directly leaves rows without a valid basic variable, so Phase
2 ratio tests can move into infeasible territory.

Concrete failure:
`bounded_fuzz_2` had the correct Phase 2 start objective `-9.0`, but after
dropping an artificial-basic row incorrectly, the solver pivoted to objective
`-3.0`, which violates the original constraints.

Fix:
Before removing artificial columns, for each artificial basic row, perform an
unlogged algebraic pivot on a non-artificial nonzero column, preferring slack /
surplus columns when possible.

Effect:
Full score improved to `7 failed / 96 passed`; the remaining `/app` failure was
only a host-probe artifact.

### Step 3: Fix protocol-level failures

Required micro-steps:

- Use `Decimal(str(value)).quantize(Decimal("0.01"), ROUND_HALF_UP)` for report
  rounding. The float `math.floor(n * 100 + 0.5)` path is wrong for `1.005`,
  `-1.005`, `-2.995`, and negative zero.
- Parse Python literals after `argparse.parse_args()` inside the main `try`
  block, not with `argparse type=...`, so malformed literals emit a Python
  traceback and no partial outputs.
- If Phase 1 terminates with nonzero auxiliary objective, treat it as
  infeasible and return a best-effort last tableau instead of entering Phase 2
  or raising `Unbounded`.

Effect:
Full score improved to `2 failed / 101 passed`; the true remaining failure was
only raw pivot row 4 minimum-count.

### Step 4: Search globally over Phase 1 + Phase 2 pivot count

Critical error:
For `--initial_pivots`, the solver minimized Phase 1 and Phase 2 separately:
`minimal_pivot_path(phase1)` followed by `minimal_pivot_path(phase2)`. The task
requires the smallest total number of logged pivots across the whole
continuation.

Concrete row 4 evidence:

- Required prefix: `x1/R3`.
- Local path logged 4 pivots:
  `x1/R3`, `x3/R5`, `x2/R4`, then Phase 2 `s4/R4`.
- Global shortest path logs 3 pivots:
  `x1/R3`, `x3/R5`, `s4/R4`, all in Phase 1; after the unlogged Phase 2 handoff,
  the tableau is already optimal.

Fix:
Run BFS/MCTS-style search over states `(phase, tableau, basis)` where Phase 1
valid simplex pivots are actions, Phase 1 -> Phase 2 handoff is a zero-cost
transition, and Phase 2 valid simplex pivots are actions. Return the first path
that reaches a Phase 2 optimal tableau.

Effect:
With `/app` pointed to the final searched state:

```text
103 passed in 4.69s
```

## Candidate Debug-Action Summary

The next live ICL card should not say “implement two-phase simplex” broadly. It
should instruct the agent to apply the four steps above in order, running the
minimal probes after Step 1 and Step 2, then `pytest -q /tests/test_outputs.py`.
