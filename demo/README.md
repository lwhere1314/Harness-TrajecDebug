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

Fast rehearsal with checked-in evidence:

```bash
cd Harness-TrajecDebug
HTD_DEMO_PAUSE=1 demo/query-optimize-trace-to-card.sh --recorded
```

Live second run with the pass-teacher Debug-Action card:

```bash
cd Harness-TrajecDebug
HTD_DEMO_PAUSE=1 demo/query-optimize-trace-to-card.sh --live
```

Live second run with a failure-derived teacher card:

```bash
cd Harness-TrajecDebug
HTD_DEMO_PAUSE=1 demo/query-optimize-trace-to-card.sh --live-fail-teacher
```

Full live fail-teacher run, including a fresh first failure:

```bash
cd Harness-TrajecDebug
HTD_DEMO_PAUSE=1 demo/query-optimize-trace-to-card.sh --live-full-fail-teacher
```

The four modes are:

| Mode | First failure | Teacher/card source | Second run |
| --- | --- | --- | --- |
| `--recorded` | Checked-in failed run | Checked-in pass-teacher card | Checked-in passing run |
| `--live` | Checked-in failed run | Checked-in pass-teacher card | Real `sdk_live` rerun |
| `--live-fail-teacher` | Checked-in failed run | Reward-0 failure-derived card | Real `sdk_live` rerun |
| `--live-full-fail-teacher` | Fresh no-ICL Harbor run | Freshly generated reward-0 card after diagnosis | Real `sdk_live` rerun |

For live modes, the script defaults to the current repository root. If your
machine needs long Harbor processes to run from a separate mirror, set
`HTD_DEMO_LIVE_ROOT=/path/to/repo-mirror`. The mirror must contain the current
demo script, helper scripts, task variants, and teacher cards. For
`--live-full-fail-teacher`, set
`HARBOR_RUNNER=/path/to/run_terminal_bench_harbor.sh` unless your local default
runner path already exists. The script sources `~/.bashrc` internally for
endpoint-profile checks and live runners.

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

Pass-teacher card path:

```text
docs/blog/raw_logs/blog_raw_logs/teacher_cards/query-optimize/debug_action.md
```

Checked-in fail-teacher card path:

```text
docs/blog/raw_logs/blog_raw_logs/teacher_cards/query-optimize/fail_debug_action.md
```

In `--live-full-fail-teacher`, the script generates a fresh temporary card
under `runs/.../runtime_pack/teacher_cards/query-optimize/fail_debug_action_live.md`
from that run's failed trial and diagnosis.

For the fail-teacher demo, point at `Teacher outcome: reward=0.0`. This card is
failure-derived guidance; it intentionally does not copy a passing `/app/sol.sql`
artifact.

4. Check that the card is executable.

Expected on screen for the pass-teacher card:

```text
closure: closure_passed
artifact: /app/sol.sql
check: query_optimize_single_statement=ok
check: query_optimize_select_only=ok
```

Expected on screen for the fail-teacher card:

```text
closure: closure_unavailable
check: card_has_artifact_heredoc=fail
```

That failure is expected because the teacher is reward-0 data, not a copied
passing artifact. The second run still receives the card as repair guidance.

5. Run with runtime injection.

The live command underneath is:

```bash
scripts/run_harbor_dynamic_icl.sh \
  --pack-dir docs/blog/raw_logs/blog_raw_logs \
  --task query-optimize \
  --model kimi-k2.6 \
  --jobs-dir runs/demo-query-optimize-live-YYYYMMDDTHHMMSS \
  --context-variant debug_action \
  --inject-mode sdk_live \
  --endpoint-profile seed-coding-plan \
  --sdk-live-intercept-tool Bash
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

Fail-teacher card:

```text
Here the teacher is deliberately a failed trajectory. We are not giving the
agent a copied passing solution; we are giving it the critical-step diagnosis
and the repair route extracted from reward-0 evidence.
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
