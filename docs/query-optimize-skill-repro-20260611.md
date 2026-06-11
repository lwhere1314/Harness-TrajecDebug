# Query-Optimize Skill Reproduction

Date: 2026-06-11

This run used the local `harness-runtime-icl` skill to reproduce the
`query-optimize` runtime injection case with Claude Code + `kimi-k2.6`.

## Setup

Both canaries used the same task, model, endpoint profile, runtime injection
mode, and injection trigger:

```bash
scripts/run_daily_icl_canary.sh \
  --task query-optimize \
  --model kimi-k2.6 \
  --inject-mode sdk_live \
  --sdk-live-intercept-tool Bash \
  --endpoint-profile seed-coding-plan \
  --jobs-dir runs/harbor_icl_baseline/harbor_runs_query_skill_repro_20260611 \
  --first-turn-timeout 90 \
  --verifier-timeout 600 \
  --run
```

The only experimental variable was the context card:

- `debug_action`
- `outcome_only`

## Results

| Condition | Injection evidence | Outcome |
| --- | --- | --- |
| `debug_action + sdk_live` | `PreToolUse(Bash)` before `sqlite3 /app/oewn.sqlite ".schema"`; injected `3694` chars | `reward=1.0`, verifier `6/6 passed` |
| `outcome_only + sdk_live` | Same `PreToolUse(Bash)` boundary; injected `500` chars | `reward=0.0`; agent timed out and verifier showed runtime failure |

## Key Evidence

### Debug-Action

Trial:

```text
runs/harbor_icl_baseline/harbor_runs_query_skill_repro_20260611/
  htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/
  query-optimize__ckWBP4p/
```

`agent/sdk-live-events.jsonl`:

```text
L10 pre_tool_use tool_name=Bash command='sqlite3 /app/oewn.sqlite ".schema"'
L11 live_injection channel=PreToolUse.additionalContext reason=Bash chars=3694
```

Behavioral shift:

```text
The next reasoning step says the Debug-Action card provides a teacher artifact.
The agent writes /app/sol.sql, performs a cheap closure check, and stops.
```

Verifier:

```text
solution median_s = 0.2984631059998719
golden median_s   = 0.4194624380006644
speedup           = 1.4054080037646075
6 passed in 258.10s
```

Summary:

```json
{
  "status": "passed",
  "reward": 1.0,
  "injection_count": 1,
  "injection_reasons": ["Bash"]
}
```

### Outcome-Only

Trial:

```text
runs/harbor_icl_baseline/harbor_runs_query_skill_repro_20260611/
  htd-dynamic-icl-sdk_live-outcome_only-query-optimize-kimi-k2-6/
  query-optimize__M7sannx/
```

`agent/sdk-live-events.jsonl`:

```text
L10 pre_tool_use tool_name=Bash command='sqlite3 /app/oewn.sqlite ".schema"'
L11 live_injection channel=PreToolUse.additionalContext reason=Bash chars=500
```

Behavioral shift:

```text
The agent does not materialize a teacher artifact. It continues autonomous SQL
search, writes its own CTE/window-function rewrite, runs extended self-tests,
and hits the agent timeout.
```

Verifier:

```text
solution median_s = 0.557494131000567
golden median_s   = 0.38911285099948145
speedup           = 0.697967618602761
1 failed, 5 passed in 399.13s
```

Summary:

```json
{
  "status": "injected_but_failed_verifier",
  "reward": 0.0,
  "injection_count": 1,
  "injection_reasons": ["Bash"],
  "exception_type": "AgentTimeoutError"
}
```

## Takeaway

This reproduces the blog claim: the injection point alone is not sufficient.
Both runs injected at the same first decisive Bash boundary, but only the
Debug-Action card supplied a concrete artifact-producing next action and stop
rule. The outcome-only card carried the same teacher reward signal without the
process/action information, so the agent drifted into a slow autonomous
optimization route.
