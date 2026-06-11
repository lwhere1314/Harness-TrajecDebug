# Demo: Trace To Debug-Action Card

This demo shows one Terminal-Bench / Harbor task end to end:

```text
first agent run fails
-> Harness-TrajecDebug imports the trace
-> critical step is localized
-> a Debug-Action card is selected/generated from task-matched evidence
-> second run injects the card at PreToolUse(Bash)
-> verifier passes
```

The recommended task is `query-optimize` because the failure is easy to explain:
the first agent creates a semantically correct SQLite query, but it is slower
than the official golden query and fails the runtime gate.

## Recording Shape

Use one terminal window with large font. Keep secrets out of view.

Fast rehearsal:

```bash
cd /Users/hugo/Projects/Harness-TrajecDebug
HTD_DEMO_PAUSE=1 scripts/demo_query_optimize_trace_to_card.sh --recorded
```

Live rerun:

```bash
cd /Users/hugo/Projects/Harness-TrajecDebug
HTD_DEMO_PAUSE=1 scripts/demo_query_optimize_trace_to_card.sh --live
```

For the live rerun, the script defaults to
`/Users/hugo/Documents/Harness-TrajecDebug` as `HTD_DEMO_LIVE_ROOT`, because
that mirror is safer for long Harbor processes on this machine. At the live
injection scene, the wrapper hands off to a helper under that mirror so the
long Harbor process is launched from the safe path. The script sources
`~/.bashrc` internally for endpoint-profile checks and the live runner.

## Scenes

1. Show the task and failed verifier.

The first run is `no_icl`, model `kimi-k2.6`, task `query-optimize`.
Expected on screen:

```text
reward.txt -> 0
5 passed, 1 failed
solution median slower than golden median
```

2. Import the terminal-agent trace.

Command shown by the script:

```bash
plugins/harness-trajdebug-agent/scripts/htd-agent harbor-import \
  --run docs/blog/raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-icl-no_icl-query-optimize-kimi-k2-6/query-optimize__cTzLSZp \
  --output-dir runs/demo-query-optimize-trace-to-card/diagnosis \
  --diagnose
```

Expected on screen:

```text
outcome: failed
final_failure: final artifact failed verifier validation
critical_step: pattern=budget debt loop
```

3. Show the Debug-Action card.

Card path:

```text
docs/blog/raw_logs/blog_raw_logs/teacher_cards/query-optimize/debug_action.md
```

Key thing to point at: the card contains a concrete next action that writes
`/app/sol.sql`, plus guardrails saying to stop after the artifact exists and let
the official verifier grade it.

4. Check that the card is executable.

Expected on screen:

```text
closure: closure_passed
artifact: /app/sol.sql
check: query_optimize_single_statement=ok
check: query_optimize_select_only=ok
```

5. Run with runtime injection.

The live command underneath is:

```bash
scripts/run_query_optimize_sdk_live_repro.sh runs/demo-query-optimize-live-YYYYMMDDTHHMMSS
```

Expected evidence:

```text
sdk_install: missing,starting,finished
claude_init: true
injection_count: 1
injection_reasons: ["Bash"]
reward: 1.0
6 passed
```

## Suggested Narration

Start:

```text
Same task, same model, same verifier. The first terminal agent run fails.
Not because the SQL is wrong, but because the artifact is too slow for the
official runtime gate.
```

Diagnosis:

```text
Harness-TrajecDebug reads the raw terminal-agent trace and the verifier output.
It does not just look at reward. It localizes the point where the agent commits
to a route that is semantically correct but accumulates runtime debt.
```

Card:

```text
The critical-step evidence becomes a Debug-Action card: concrete next action,
artifact path, closure check, and stop rule.
```

Injection:

```text
On the second run, the card is not pasted into the initial prompt. It is injected
at the first decisive Bash boundary, right after the agent has read the task and
before it commits to another expensive route.
```

Result:

```text
Same task, same verifier, same model family. The runtime card changes the
trajectory, writes the right artifact, and the official verifier passes.
```
