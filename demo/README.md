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
HTD_DEMO_PAUSE=1 plugins/harness-trajdebug-agent/scripts/htd-agent demo query-optimize --recorded
```

Agent-friendly rehearsal, useful inside Claude Code:

```bash
cd Harness-TrajecDebug
HTD_DEMO_PAUSE=0 plugins/harness-trajdebug-agent/scripts/htd-agent demo query-optimize --recorded --compact
```

Live second run with the pass-teacher Debug-Action card:

```bash
cd Harness-TrajecDebug
HTD_DEMO_PAUSE=1 HTD_DEMO_NO_FORCE_BUILD=1 HTD_DEMO_KEEP_ENVIRONMENT=1 \
  plugins/harness-trajdebug-agent/scripts/htd-agent demo query-optimize --live
```

Recommended live recording: checked-in failed teacher evidence, then a real
second run with a failure-derived Debug-Action card:

```bash
cd Harness-TrajecDebug
HTD_DEMO_PAUSE=1 HTD_DEMO_NO_FORCE_BUILD=1 HTD_DEMO_KEEP_ENVIRONMENT=1 \
  plugins/harness-trajdebug-agent/scripts/htd-agent demo query-optimize --live-fail-teacher
```

Optional research/debug mode: full live fail-teacher run, including a fresh
first failure. This is slower and may be less recording-stable because a fresh
agent can time out, pass unexpectedly, or hit environment setup issues.

```bash
cd Harness-TrajecDebug
HTD_DEMO_PAUSE=1 HTD_DEMO_NO_FORCE_BUILD=1 HTD_DEMO_KEEP_ENVIRONMENT=1 \
  plugins/harness-trajdebug-agent/scripts/htd-agent demo query-optimize --live-full-fail-teacher
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

## Docker Warm-Run Policy

The live demo is intentionally configured to avoid cold Docker work during
recording:

```bash
HTD_DEMO_NO_FORCE_BUILD=1
HTD_DEMO_KEEP_ENVIRONMENT=1
HTD_DEMO_TAG_LOCAL_HB_PREBUILT=1
```

`HTD_DEMO_NO_FORCE_BUILD=1` tells Harbor to reuse the task `docker_image` or a
cached image instead of forcing a rebuild. This is the default for the demo.

`HTD_DEMO_KEEP_ENVIRONMENT=1` tells Harbor not to delete the task container at
the end of the run. Use it for recording so the warmed Python/pip/SDK state can
remain inspectable. For clean benchmark sweeps, leave it unset so each trial
starts from a clean task environment.

`HTD_DEMO_TAG_LOCAL_HB_PREBUILT=1` tells the demo to tag
`hb__query-optimize:latest` to the `docker_image` name in `task.toml` before the
no-force live run. This matters because Harbor uses `task.toml`'s prebuilt image
when `force_build=false`; the upstream `alexgshaw/query-optimize:20251031`
image is smaller but does not provide the Python/pip runtime needed by
`sdk_live`, while the locally built `hb__query-optimize:latest` image does.

Before recording a live run:

```bash
plugins/harness-trajdebug-agent/scripts/htd-agent doctor
scripts/run_harbor_dynamic_icl.sh \
  --pack-dir docs/blog/raw_logs/blog_raw_logs \
  --task query-optimize \
  --context-variant fail_debug_action \
  --inject-mode sdk_live \
  --model kimi-k2.6 \
  --endpoint-profile seed-coding-plan \
  --sdk-live-intercept-tool Bash \
  --dry-run \
  --no-force-build \
  --keep-environment \
  --tag-local-hb-prebuilt
```

The dry run should show:

```text
Force build: 0
Keep environment: 1
Tag local hb prebuilt: 1
"force_build": false
"delete": false
```

If a live run dies while installing Python/pip, during Docker build, or before
`claude_init: true`, classify it as a Harbor/Docker setup failure. It is not
evidence that the Debug-Action card or TrajectoryDebug algorithm failed.

Avoid running another long Harbor or Terminal-Bench job at the same time while
recording this demo. On small local Docker/Colima allocations, concurrent jobs
can make apt, pip, or verifier steps exit with a killed process.

## Claude Code Recording SOP

Open Claude Code from the repository root:

```bash
cd Harness-TrajecDebug
claude --model sonnet --permission-mode bypassPermissions
```

Paste this first for a safe rehearsal:

```text
/harness-runtime-icl
Do not edit files. Run exactly:
HTD_DEMO_PAUSE=0 plugins/harness-trajdebug-agent/scripts/htd-agent demo query-optimize --recorded --compact --out-dir /tmp/htd-claude-recorded
Report the first reward, diagnosis critical step, card closure, recorded with-TD reward, injection_count, and injection_reasons.
```

Then paste this for the live recording once Docker is warm:

```text
/harness-runtime-icl
Do not edit files. Run exactly:
HTD_DEMO_PAUSE=0 HTD_DEMO_NO_FORCE_BUILD=1 HTD_DEMO_KEEP_ENVIRONMENT=1 HTD_DEMO_TAG_LOCAL_HB_PREBUILT=1 plugins/harness-trajdebug-agent/scripts/htd-agent demo query-optimize --live-fail-teacher --compact
Report the first reward, card teacher outcome, live reward, injection_count, injection_reasons, and live trial directory.
```

If the live command fails, save the trial path and runner log shown on screen.
The important environment-failure signatures are `sdk_live Python/pip bootstrap
failed`, Docker build exit `-9`, missing `reward.txt`, or `claude_init: false`.

## Agent CLI Smoke Checks

The main recording should happen inside Claude Code. To show that the same
plugin entry point is usable from Kimi Code, run this headless smoke separately:

```bash
scripts/run_kimicode_skill_smoke.sh \
  'Use Bash to run: HTD_DEMO_PAUSE=0 plugins/harness-trajdebug-agent/scripts/htd-agent demo query-optimize --recorded --compact --out-dir /tmp/htd-kimi-recorded'
```

Run this from a real terminal or PTY. Expected evidence includes `kimi_rc: 0`,
`kimi_tool_calls: ['Bash']`, `critical_step`, `closure_passed`, recorded reward
`1`, and `injection_count: 1`.

Codex support is the current Codex app/thread skill path plus the detached
launcher for long Harbor jobs. For nested Codex CLI, use the explicit gate:

```bash
scripts/run_codex_skill_smoke.sh --echo
scripts/run_codex_skill_smoke.sh --recorded
```

Do not claim nested `codex exec` as working in the demo until `--echo` prints
`CODEX_EXEC_OK` and `--recorded` prints the compact recorded demo completion or
injection evidence.

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
failure-derived guidance: the teacher run failed, and the executable repair
action is synthesized from the failed runtime gate plus the critical-step
diagnosis rather than copied from a passing teacher trajectory.

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
closure: closure_passed
artifact: /app/sol.sql
check: query_optimize_single_statement=ok
check: query_optimize_select_only=ok
```

This is still a fail-teacher demo: the `Teacher outcome` line stays `reward=0.0`.
The point is that Harness-TrajecDebug turns the failed trace and verifier
footprint into a bounded repair action that the second agent can execute.

5. Run with runtime injection.

The live command underneath is:

```bash
scripts/run_harbor_dynamic_icl.sh \
  --pack-dir docs/blog/raw_logs/blog_raw_logs \
  --task query-optimize \
  --model kimi-k2.6 \
  --jobs-dir runs/demo-query-optimize-live-YYYYMMDDTHHMMSS \
  --context-variant fail_debug_action \
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
agent a copied passing trajectory; we are giving it a repair action synthesized
from the failed runtime gate and the critical-step diagnosis.
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
