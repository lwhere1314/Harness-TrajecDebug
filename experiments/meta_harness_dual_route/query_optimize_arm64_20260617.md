# Query Optimize ARM64 Canary - 2026-06-17

## Scope

Task: Terminal-Bench 2.1 `query-optimize`, run from a local ARM64 task copy at
`experiments/meta_harness_dual_route/tasks/query-optimize-arm64`.

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
three runs.

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
- Route A:
  `mh-route-a-terminus2-query-optimize-arm64-kimi-k2.6-20260617T163609`

Each directory includes the Harbor `config.json`, `result.json`, `job.log`,
trial `result.json`, `agent/trajectory.json`, verifier stdout, CTRF output, and
`verifier/reward.txt`. Claude Code runs also include `agent/claude-code.txt`;
the Terminus2 run includes per-episode prompts/responses and
`agent/terminus_2.pane`.

Secret hygiene: no API keys are committed. Terminus2 `api_key_sha256` fields in
the copied debug logs are redacted to `redacted-sha256`.

## Results

| Condition | Reward | Pytest | Agent | Total | Verifier | Input tokens | Output tokens | Runtime median |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Baseline Claude Code infra control | 1.0 | 6/6 | 9m04.8s | 17m11.5s | 7m54.4s | 696058 | 13866 | golden 0.9017s, sol 0.9161s |
| Route B Claude Code + generic review | 0.0 | 5/6 | 10m07.3s | 17m39.1s | 7m19.4s | 1134890 | 20698 | golden 0.8958s, sol 1.1890s |
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
- Route A passed, but its token accounting is not directly comparable with
  Claude Code because Terminus2 reports model-call tokens differently. Its
  agent wall time was similar to Route B, driven by 16 model episodes and
  repeated self-checks.

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

This canary does not support a blanket claim that Meta-Harness improves
`query-optimize`. With the same Claude Code version and `kimi-k2.6`, the
baseline already solves the task, while Route B's generic review increases token
usage and fails the runtime threshold by choosing a slower correct SQL rewrite.

Route A passes with Terminus2 and the same generic review, but it is a different
inner harness, so it should be reported separately from the Claude Code
baseline. The useful takeaway is narrower: the generic review can improve
coverage on reliability tasks such as `cancel-async-tasks`, but for tight
performance tasks it can increase checking overhead and still miss the fastest
acceptable implementation.
