# Query Optimize ARM64 Canary - 2026-06-17

## Scope

Task: Terminal-Bench 2.1 `query-optimize`, run from a local ARM64 task copy at
`experiments/meta_harness_dual_route/tasks/query-optimize-arm64`.

Headline result: this canary reproduces the upstream-shaped Meta-Harness effect
for the Terminus2 route, but it also shows that the current Claude Code
adaptation is not a correct Meta-Harness implementation.

Model endpoint: Seed Agent Plan Anthropic-compatible route, configured through
`SEED_AGENT_PLAN_ANTHROPIC_BASE_URL` / `SEED_AGENT_PLAN_BASE_URL` and
`SEED_AGENT_PLAN_API_KEY`.

Target model: `kimi-k2.6`.

The ARM64 task copy keeps the task contract, input SQL, golden SQL, and pytest
verifier logic from the Terminal-Bench 2.1 proxy task. The local changes are
limited to image/build plumbing so the task runs natively on this Apple Silicon
machine instead of under QEMU:

- Docker image name changed to `mh-dual-route-query-optimize-arm64:latest`.
- The image is built as `linux/arm64`.
- `curl`, `sqlite3`, and `uv` are preinstalled in the task environment.
- `tests/test.sh` only skips reinstalling tools that already exist; the pytest
  verifier and `tests/test_outputs.py` are unchanged.

QEMU attempts against the original `linux/amd64` image are excluded from the
main table because they mixed task behavior with emulation and binary-arch
confounds. The valid comparison below uses the local ARM64 task image for all
four runs.

## Routes

Baseline: matched Claude Code infra control.

- Agent import path:
  `meta_harness_dual_route.agents.route_b_claudecode_infra_control:AgentHarness`
- Inner harness: Claude Code.
- Claude Code version: `2.1.157`.
- Model: `kimi-k2.6`.
- No generic Meta-Harness review prompt.

Route B: Claude Code adaptation.

- Agent import path:
  `meta_harness_dual_route.agents.route_b_claudecode_general_review:AgentHarness`
- Inner harness: Claude Code.
- Claude Code version: `2.1.157`.
- Model: `kimi-k2.6`.
- Adds only the generic reliability review prompt. It does not include the task
  name, verifier test names, prior failure diagnoses, or task-specific hints.

Pure Terminus2 baseline: direct Terminus2 control.

- Harbor agent: `terminus-2`.
- Model passed to Terminus2: `anthropic/kimi-k2.6`.
- No generic Meta-Harness review prompt or wrapper.

Route A: upstream-shaped Terminal-Bench route.

- Agent import path:
  `meta_harness_dual_route.agents.route_a_terminus_general_review:AgentHarness`
- Inner harness: Terminus2.
- Model passed to Terminus2: `anthropic/kimi-k2.6`.
- Adds the same generic reliability review in the Terminus2 wrapper.

## Evaluation

The official verifier runs `tests/test_outputs.py` and writes reward to
`verifier/reward.txt`. A passing solution must:

- Match the original query output exactly.
- Avoid modifying the SQLite database.
- Contain one valid SQL `SELECT` query in `/app/sol.sql`.
- Stay small enough for the solution-size check.
- Meet the runtime threshold:
  `solution_median <= 1.05 * golden_median`, using 5 alternating timed
  iterations after warm-up.

## Raw Logs

All valid ARM64 run logs are copied under
`experiments/meta_harness_dual_route/raw_logs/`:

- Baseline:
  `mh-baseline-claudecode-infra-query-optimize-arm64-kimi-k2.6-20260617T151244-samecc-arm64`
- Route B:
  `mh-route-b-claudecode-query-optimize-arm64-kimi-k2.6-20260617T161528-samecc-arm64`
- Pure Terminus2 baseline:
  `mh-baseline-terminus2-query-optimize-arm64-kimi-k2.6-20260617T185528`
- Route A:
  `mh-route-a-terminus2-query-optimize-arm64-kimi-k2.6-20260617T163609`

Each directory includes the Harbor `config.json`, `result.json`, `job.log`,
trial `result.json`, `agent/trajectory.json`, verifier stdout, CTRF output, and
`verifier/reward.txt`. Claude Code runs also include `agent/claude-code.txt`;
the Terminus2 runs include per-episode prompts/responses and
`agent/terminus_2.pane`.

Secret hygiene: no API keys are committed. Terminus2 `api_key_sha256` fields in
the copied debug logs are redacted to `redacted-sha256`.

## Results

| Condition | Reward | Pytest | Agent | Total | Verifier | Input tokens | Output tokens | Runtime median |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Baseline Claude Code infra control | 1.0 | 6/6 | 9m04.8s | 17m11.5s | 7m54.4s | 696058 | 13866 | golden 0.9017s, sol 0.9161s |
| Route B Claude Code + generic review | 0.0 | 5/6 | 10m07.3s | 17m39.1s | 7m19.4s | 1134890 | 20698 | golden 0.8958s, sol 1.1890s |
| Pure Terminus2 baseline | 0.0 | 5/6 | 13m22.0s | 21m38.1s | 7m31.3s | 201422 | 21922 | golden 0.9099s, sol 1.3648s |
| Route A Terminus2 + generic review | 1.0 | 6/6 | 10m08.5s | 18m38.2s | 8m02.3s | 84951 | 8239 | golden 0.9064s, sol 0.9052s |

Notes:

- The baseline was slow mostly because `query-optimize` is intrinsically a
  long-verifier task: the original query takes about 2m40s to 2m50s on ARM, the
  agent runs at least one original-vs-solution self-check, and the verifier
  repeats golden/solution timing for 5 iterations.
- Route B consumed 63.0% more input tokens and 49.3% more output tokens than
  the Claude Code baseline. Agent wall time increased by about 62.5 seconds
  (+11.5%). The task reward regressed from 1.0 to 0.0 because the selected SQL
  was correct but missed the runtime threshold.
- Pure Terminus2 failed the same runtime gate that Route B failed, while still
  passing all correctness and format checks. Its reported token use was also
  higher than Route A Terminus2 + generic review: 201k vs 85k input tokens and
  21.9k vs 8.2k output tokens.
- Route A passed, but its token accounting is not directly comparable with
  Claude Code because Terminus2 reports model-call tokens differently. Compared
  with pure Terminus2, Route A used fewer reported tokens and less agent wall
  time in this run, but this is still a single canary and should not be treated
  as a stable aggregate result.

## Trajectory Diff

Baseline trajectory:

- Reads the original SQL, schema, indexes, and query plan.
- Identifies the expensive correlated scalar subqueries over `senses`.
- Times the original query and a candidate optimized query.
- Uses a two-stage rewrite:
  `word_stats -> synset_counts filtered by word_stats -> ranked_synsets`.
- Verifies output equality with `diff`.
- Writes `/app/sol.sql`.
- Passes the runtime verifier with solution median `0.9161s`, just within the
  `1.05 * golden` threshold.

Route B trajectory:

- Receives the same task plus only the generic reliability review prompt.
- Performs a broader analysis of schema, uniqueness, query plans, output diff,
  and alternative CTE shapes.
- Selects a shared `word_synset_stats` materialization that feeds both
  `word_stats` and `top_synsets`.
- The shell self-check reports the candidate as fast and output-identical, but
  the official verifier measures the solution median at `1.1890s`.
- Fails only `test_compare_golden_vs_solution_runtime`; correctness and format
  checks pass.
- Main effect: more validation and higher token/latency, but no task reward
  improvement on this SQL-performance task.

Pure Terminus2 baseline trajectory:

- Uses Terminus2 directly with `anthropic/kimi-k2.6` and no generic review
  wrapper.
- Starts the original query, interrupts it with `C-c`, then continues with
  schema inspection, cardinality checks, and sampled correctness checks.
- Chooses a shared materialized CTE shape:
  `word_sense_stats -> word_stats + ranked_synsets`.
- Runs sampled diffs, output checks, semicolon/comment checks, and solution file
  inspection.
- The official verifier confirms correctness and format, but the runtime median
  is too slow: solution `1.3648s` versus golden `0.9099s`.

Route A trajectory:

- Uses Terminus2 rather than Claude Code.
- Reads the same task input and query plan.
- Produces a candidate structurally close to the passing baseline:
  `word_stats -> synset_counts joined against word_stats -> top_synsets`.
- Runs multiple self-checks: optimized output, original output, `diff`, line
  counts, file-size checks, comment checks, and sample solution execution.
- Writes `/app/sol.sql`.
- Passes the runtime verifier with solution median `0.9052s`, slightly faster
  than the golden median in this run.

## Conclusion

This canary successfully reproduces a positive Meta-Harness effect for the
upstream-shaped Terminus2 route: pure Terminus2 + `kimi-k2.6` fails the runtime
gate, while Terminus2 + the generic Meta-Harness review wrapper passes.

It does not support a blanket claim that Meta-Harness improves `query-optimize`.
The result is route-specific:

- Claude Code control vs Route B: the matched Claude Code baseline already
  solves the task, while Route B's generic review increases token usage and
  fails the runtime threshold by choosing a slower correct SQL rewrite.
- Pure Terminus2 vs Route A: pure Terminus2 also fails the runtime threshold,
  while Terminus2 + the same generic review passes. In this single canary, the
  wrapper appears to move Terminus2 from the slower shared-materialization
  rewrite to the faster filtered `synset_counts` rewrite.

The interview-safe takeaway is narrow: this query-optimize example is not
evidence that Meta-Harness universally improves task success. It shows that the
same generic review can hurt the Claude Code trajectory but help the Terminus2
trajectory on a tight SQL-performance task, so harness changes must be evaluated
with reward, token cost, latency, raw logs, and trajectory diffs together.

Therefore Route B should be reported as an incorrect or incomplete Claude Code
adaptation attempt, not as the original Meta-Harness. The next implementation
step is to correct or rename Route B so the PR does not conflate it with the
upstream Terminal-Bench Meta-Harness protocol.
