# Case Study: Terminal-Bench 3 `cli-2ph-simplex`

This case study records a Terminal-Bench 3 repair experiment where an
interactive ICL card was not enough, but a verifier-guided MCTS-like search
found an actionable critical error step and expanded it into a reward-1 repair
path.

## Task

Task: `cli-2ph-simplex`

Harness: Harbor / Terminal-Bench 3

Agent route: Claude Code through the Seed Agent Plan endpoint

Configured model label: `claude-opus-4-7`

Provider stream model observed in Claude Code logs:
`doubao-seed-2-0-code-preview-260215`

The task requires a globally callable `/app/lp_solve` command that implements a
two-phase simplex solver for maximization LPs. The verifier checks the final
tableau, pivot-log semantics, shortest continuation after required initial
pivots, report formatting, exception behavior, and infeasible best-effort
output.

## Baseline Runs

| Condition | Job | Reward | Verifier footprint | Raw evidence |
| --- | --- | ---: | --- | --- |
| No TD | `tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-seed-plan-20260629` | `0.0` | `50 failed, 53 passed` | [`trajectory`](../blog/raw_logs/blog_raw_logs/terminal_bench_3_cli_simplex/harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-seed-plan-20260629/cli-2ph-simplex__PiTA9w7/agent/trajectory.json), [`transcript`](../blog/raw_logs/blog_raw_logs/terminal_bench_3_cli_simplex/harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-seed-plan-20260629/cli-2ph-simplex__PiTA9w7/agent/claude-code.txt), [`verifier`](../blog/raw_logs/blog_raw_logs/terminal_bench_3_cli_simplex/harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-seed-plan-20260629/cli-2ph-simplex__PiTA9w7/verifier/test-stdout.txt) |
| First interactive TD card | `tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701` | `0.0` | `63 failed, 40 passed` | [`trajectory`](../blog/raw_logs/blog_raw_logs/terminal_bench_3_cli_simplex/harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/agent/trajectory.json), [`transcript`](../blog/raw_logs/blog_raw_logs/terminal_bench_3_cli_simplex/harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/agent/claude-code.txt), [`TD hint`](../blog/raw_logs/blog_raw_logs/terminal_bench_3_cli_simplex/harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/agent/interactive_icl_hint.txt), [`verifier`](../blog/raw_logs/blog_raw_logs/terminal_bench_3_cli_simplex/harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/verifier/test-stdout.txt) |

The first TD card injected successfully. The trial transcript contained one
`harness_trajecdebug_interactive_icl_injected` marker, so the failure was not an
injection failure. The card was simply too broad: it named Phase 1 / Phase 2,
negative RHS normalization, pivot replay, and report formatting, but did not
name the first wrong state transition.

This is exactly the boundary between a broad diagnosis and an actionable
Debug-Action card.

## Raw Evidence Bundle

The sanitized raw trajectory bundle is published at
[`docs/blog/raw_logs/blog_raw_logs/terminal_bench_3_cli_simplex/`](../blog/raw_logs/blog_raw_logs/terminal_bench_3_cli_simplex/README.md).
It includes the original Harbor `trajectory.json` files, Claude Code
transcripts, verifier output, result/config files, the injected TD hint, and
checksums for the copied evidence.

## Search Method

The follow-up search treated the failed submission as a local search state.

State:

```text
patched source tree + verifier failure set + targeted probe results
```

Action:

```text
one concrete repair step, such as changing Phase 1 objective construction,
pivoting out artificial basics, fixing parser behavior, or replacing a local
pivot heuristic with a global shortest-path search
```

Evaluation:

```text
run targeted probes, then run pytest against tests/test_outputs.py
```

Selection:

```text
keep branches that reduce verifier failures or move the failure frontier to a
later, narrower requirement
```

This is MCTS-like rather than a full generic MCTS engine: the expansion actions
were proposed by manual trace review and verifier deltas, but each branch was
scored mechanically by the official tests.

## Search Trace

The final searched state was:

```text
/data/harbor/td_artifacts/cli_mcts_search/states/s4_global_shortest
```

When that state was mounted as `/app`, the official verifier tests passed:

```text
103 passed in 4.69s
```

| Search state | Action | Verifier footprint |
| --- | --- | --- |
| `s0_baseline` | failed first TD artifact | `63 failed, 40 passed` |
| `s1_phase1_sign` | fix artificial objective sign | `12 failed, 91 passed` |
| `s2_artificial_cleanup` | pivot zero-valued artificial basics out before dropping artificial columns | `7 failed, 96 passed` |
| `s3_protocol_best_effort` | fix Decimal rounding, literal traceback behavior, and infeasible best-effort output | `2 failed, 101 passed` |
| `s4_global_shortest` | search globally over Phase 1 plus Phase 2 pivot count | `103 passed` when mounted as `/app` |

The intermediate `s3` count included a host-only `/app/lp_solve` preservation
failure caused by running outside the task container. Mounting the searched state
as `/app` closed that artifact gap.

## Critical Error Step 1: Phase 1 Objective Sign

The first high-impact critical step was in
`simplex/tableau.py::build_initial_tableau`.

The failed submission initialized artificial-variable coefficients in the Phase
1 objective row as `-1.0`. The verifier/reference construction uses `+1.0` for
artificial variables and then canonicalizes the objective with the
artificial-basic rows.

Minimal failing probe:

```text
maximize x1 + 5*x2
subject to:
  x1 + 2*x2 <= 40
  2*x1 + x2 >= 39
  x1 + x2 = 20
```

Expected objective: `24.0`

Failed behavior: the solver raised `Exception: Unbounded`.

Trace evidence:

```text
initial Phase 1 objective with wrong sign:
[Z=1, x1=3, x2=2, s2=-1, RHS=59]
```

Because the Phase 1 row had the wrong sign, the solver saw a negative reduced
cost in the surplus column and treated the auxiliary problem as unbounded before
finding a feasible basis.

Changing only this sign made the minimal probe return `24.0`, made
`fractional_primal_from_mixed_basis` return `11.0`, and improved the full
verifier footprint from `63 failed, 40 passed` to `12 failed, 91 passed`.

This is a concrete critical error step: one state transition explains a large
part of the verifier failure surface.

## Critical Error Step 2: Artificial Basic Cleanup

After Phase 1, an artificial variable can remain basic with value zero. The
failed solver dropped artificial columns directly. That can leave a row without
a valid basic variable, so Phase 2 starts from a broken basis and later ratio
tests can move into an infeasible solution.

Concrete probe: `bounded_fuzz_2`

Before cleanup, the Phase 2 start objective was already correct at `-9.0`, but
the solver pivoted to `-3.0`, which did not encode a feasible optimum.

Repair action:

```text
Before removing artificial columns, pivot every zero-valued artificial basic out
using a non-artificial nonzero column. Treat this as an algebraic cleanup step,
not as a logged simplex optimization pivot.
```

This moved the verifier footprint to `7 failed, 96 passed`.

## Critical Error Step 3: Protocol Failures

The remaining broad failures were not simplex search failures.

They were protocol mismatches:

- Report rounding used float arithmetic. `math.floor(n * 100 + 0.5)` is wrong
  for values such as `1.005`, `-1.005`, and `-2.995`.
- Malformed Python literals were parsed by `argparse type=...`, so they produced
  argparse usage text instead of a Python traceback.
- Infeasible Phase 1 cases were still allowed to enter Phase 2 or raise
  `Unbounded`, even though the task requires best-effort tableau output for
  infeasible inputs.

Repair actions:

```text
Use Decimal(str(value)).quantize(Decimal("0.01"), ROUND_HALF_UP).
Parse literals inside the main try block after parse_args().
If Phase 1 terminates with nonzero auxiliary objective, return the last
best-effort tableau instead of entering Phase 2.
```

This moved the verifier footprint to `2 failed, 101 passed`.

## Critical Error Step 4: Global Pivot-Count Search

The last true verifier failure was `raw_row_4` in the initial-pivot shortest
continuation tests.

The failed solver minimized pivots in two local stages:

```text
minimal_pivot_path(phase1)
then
minimal_pivot_path(phase2)
```

The task requires the shortest total logged path across the Phase 1 continuation
and the Phase 2 continuation together.

For row 4, the required prefix was:

```text
x1/R3
```

Local path emitted four pivots:

```text
x1/R3 -> x3/R5 -> x2/R4 -> Phase 2 s4/R4
```

The global shortest path emits three pivots, all in Phase 1:

```text
x1/R3 -> x3/R5 -> s4/R4
```

After the unlogged Phase 1 to Phase 2 handoff, the tableau is already optimal.

Repair action:

```text
Run BFS/MCTS-style search over states (phase, tableau, basis). Phase 1 valid
simplex pivots and Phase 2 valid simplex pivots are logged actions. The Phase 1
to Phase 2 handoff is a zero-cost transition. Return the first path that reaches
a Phase 2 optimal tableau.
```

This closed the last true verifier failure.

## Why This Was More Robust

The first TD card failed because it compressed the failure into a topic list.
The search loop was more robust because it required every proposed repair step
to produce a verifier delta.

The useful pattern was:

```text
failure surface
  -> smallest reproducible failing probe
  -> first wrong state transition
  -> one repair action
  -> verifier delta
  -> next narrowed failure surface
```

The case also shows why critical-step extraction should not stop at the first
reward-0 diagnosis. One repair can expose the next critical layer. Here, the
first critical step explained most failures, but reward 1 required a sequence of
four localized repairs.

## Artifacts

Baseline no-TD run:

```text
/data/harbor/jobs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-seed-plan-20260629
```

First interactive TD run:

```text
/data/harbor/jobs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701
```

Reward-1 searched state:

```text
/data/harbor/td_artifacts/cli_mcts_search/states/s4_global_shortest
```

Reward-1 path card:

```text
/data/harbor/td_artifacts/repair_briefs/tb3-cli-2ph-simplex-mcts-reward1-path.md
```

Published raw evidence bundle:

[`docs/blog/raw_logs/blog_raw_logs/terminal_bench_3_cli_simplex/`](../blog/raw_logs/blog_raw_logs/terminal_bench_3_cli_simplex/README.md)

## Limitations

This was a Codex-in-the-loop search, not yet a fully automated critical-step
extractor. The verifier scoring and branch evaluation were mechanical, but the
candidate repair actions were still proposed by human/Codex trace review.

For the next version, the automation target is to make action proposal more
systematic:

```text
verifier failure cluster
  -> minimal probe generator
  -> state-transition differ
  -> candidate Debug-Action card
  -> isolated verifier rollout
```

That would turn this case study from a manual MCTS-like repair search into a
repeatable Harness-TrajecDebug pipeline.
