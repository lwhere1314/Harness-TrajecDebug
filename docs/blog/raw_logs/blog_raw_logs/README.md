# Query-Optimize Runtime Debug-Action Raw Logs

This directory contains the raw evidence bundle for
[`query-optimize-runtime-debug-action.md`](../../query-optimize-runtime-debug-action.md).
It is a focused copy of the local Harbor / Claude Code artifacts used to write
the blog post, preserving the three controlled query-optimize runs and the
runtime Debug-Action material injected through the Claude Agent SDK path.

## Evidence Map

| Blog condition | Trial directory | Reward | Key evidence |
| --- | --- | ---: | --- |
| `no_icl` | [`harbor_runs_query_baseline/htd-icl-no_icl-query-optimize-kimi-k2-6/query-optimize__cTzLSZp`](harbor_runs_query_baseline/htd-icl-no_icl-query-optimize-kimi-k2-6/query-optimize__cTzLSZp) | `0.0` | [`result.json`](harbor_runs_query_baseline/htd-icl-no_icl-query-optimize-kimi-k2-6/query-optimize__cTzLSZp/result.json), [`agent/trajectory.json`](harbor_runs_query_baseline/htd-icl-no_icl-query-optimize-kimi-k2-6/query-optimize__cTzLSZp/agent/trajectory.json), [`verifier/test-stdout.txt`](harbor_runs_query_baseline/htd-icl-no_icl-query-optimize-kimi-k2-6/query-optimize__cTzLSZp/verifier/test-stdout.txt) |
| `outcome_only + sdk_live` | [`harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-outcome_only-query-optimize-kimi-k2-6/query-optimize__R8AokaA`](harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-outcome_only-query-optimize-kimi-k2-6/query-optimize__R8AokaA) | `0.0` | [`sdk-live-summary.json`](harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-outcome_only-query-optimize-kimi-k2-6/query-optimize__R8AokaA/sdk-live-summary.json), [`agent/sdk-live-events.jsonl`](harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-outcome_only-query-optimize-kimi-k2-6/query-optimize__R8AokaA/agent/sdk-live-events.jsonl), [`agent/sessions/projects/-app/6c66263d-0bc3-4157-bab4-a8d789de2a50.jsonl`](harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-outcome_only-query-optimize-kimi-k2-6/query-optimize__R8AokaA/agent/sessions/projects/-app/6c66263d-0bc3-4157-bab4-a8d789de2a50.jsonl) |
| `debug_action + sdk_live` | [`harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq`](harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq) | `1.0` | [`sdk-live-summary.json`](harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/sdk-live-summary.json), [`agent/sdk-live-events.jsonl`](harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/agent/sdk-live-events.jsonl), [`agent/dynamic_context.md`](harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/agent/dynamic_context.md), [`agent/trajectory.json`](harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/agent/trajectory.json), [`verifier/test-stdout.txt`](harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/verifier/test-stdout.txt) |

## Directory Layout

- [`harbor_runs_query_baseline/`](harbor_runs_query_baseline/) preserves the
  three local Harbor trial directories cited by the blog post. Each trial keeps
  `result.json`, `agent/`, `verifier/`, `runner.log`, and related config files.
- [`teacher_cards/query-optimize/`](teacher_cards/query-optimize/) preserves the
  teacher-derived cards used by the experiment. The injected Debug-Action card
  is [`debug_action.md`](teacher_cards/query-optimize/debug_action.md).
- [`task_variants/no_icl/query-optimize/`](task_variants/no_icl/query-optimize/)
  preserves the task contract, original slow SQL query, verifier script, and
  golden SQL used by the canary.
- [`prompts/`](prompts/) preserves the generated prompt variants for the same
  task.
- [`checksums.sha256`](checksums.sha256) records SHA-256 checksums for all files
  in this evidence bundle.

## Runtime Injection Evidence

The successful run's SDK event log shows the live insertion point:

- `pre_tool_use` on `Bash` for `sqlite3 /app/oewn.sqlite ".schema"`;
- `live_injection` through `PreToolUse.additionalContext`;
- `injection_count = 1` in
  [`sdk-live-summary.json`](harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/sdk-live-summary.json).

The exact text injected into the run is preserved in
[`agent/dynamic_context.md`](harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/agent/dynamic_context.md)
and mirrors
[`teacher_cards/query-optimize/debug_action.md`](teacher_cards/query-optimize/debug_action.md).
