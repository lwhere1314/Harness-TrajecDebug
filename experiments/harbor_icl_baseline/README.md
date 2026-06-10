# Harbor ICL Baseline Design

This experiment asks a narrow first question:

> If Claude Code + Kimi-K2.5 previously failed a Harbor / Terminal-Bench task,
> can an in-context example extracted from a Codex + GPT-5.5 successful run help
> Kimi-K2.5 solve it on a rerun?

This is a useful first baseline, but it should be reported carefully.

See [fairness_protocol.md](fairness_protocol.md) for the explicit comparison
boundary between instruction-level ICL injection and Meta-Harness-style harness
code optimization.

## Scientific Status

Same-task teacher traces are a **trace-assisted repair smoke test**, not the
final generalization result. They may contain task-specific solution details, so
they measure whether Kimi-K2.5 can reuse a teacher trajectory when the relevant
solution pattern is visible.

Current smoke-test status:

- `cancel-async-tasks` + `debug_trajectory` context + Claude Code +
  `kimi-k2.6` on the Volces Ark coding endpoint passed on 2026-06-10.
- The successful Harbor trial is under
  `runs/harbor_icl_baseline/harbor_runs/htd-icl-debug_trajectory-cancel-async-tasks-kimi-k2-6/cancel-async-tasks__7rdwHjo`.
- Agent-side result: `n_input_tokens=221432`, `n_output_tokens=4328`.
- Verifier result: `reward=1.0`, `6 passed in 13.79s`.
- `query-optimize` now has a runtime `sdk_live` canary on the same Ark /
  `kimi-k2.6` endpoint:
  - B0 `no_icl`: `reward=0.0`; the solution was semantically correct but
    slower than the official golden query.
  - B1 `outcome_only + sdk_live`: `reward=0.0`; runtime context injected once
    on `Bash`, but only contained teacher outcome metadata, so the agent rebuilt
    the same insufficient window-function route.
  - B5 `debug_action + sdk_live`: `reward=1.0`; runtime context injected once
    on `Bash`, the agent materialized the teacher `/app/sol.sql`, and the
    official verifier passed.
- The successful `query-optimize` trial is under
  `runs/harbor_icl_baseline/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq`.
- This is still a same-task repair smoke test, but it is a useful mechanism
  check: runtime injection alone did not solve the task; the selected
  Debug-Action example did.

The stronger claim requires a held-out experiment:

> Debug-Trajectory selected examples improve Kimi-K2.5 on unseen Harbor-style
> tasks more than outcome-only selection or prompt-filtered selection under the
> same token budget.

## Research Questions

1. Can Kimi-K2.5 use successful GPT-5.5 traces as ICL examples at all?
2. Under a fixed context budget, does a Debug-Trajectory card beat raw logs?
3. Does process-aware selection beat outcome-only successful-example selection?
4. On held-out tasks, do selected examples change the failure pattern, not just
   final pass rate?

## Conditions

Use the same target model, harness, task set, timeout, Docker setup, and prompt
budget across all conditions.

| Condition | Input to Kimi-K2.5 | Purpose |
| --- | --- | --- |
| B0 `no_icl` | Original task instruction only | Base pass-rate floor |
| B1 `outcome_only` | Teacher task name + reward/verifier summary | Outcome-only selector baseline |
| B2 `raw_trace` | Compressed teacher event log | Direct log-transfer baseline |
| B3 `prompt_filtered` | Frozen generic filter over teacher artifact / verifier / command snippets | Prompt-filter baseline without HTD process labels |
| B4 `debug_trajectory` | Reference/state/commitment card + artifact/verification evidence | Harness-TrajecDebug method |
| B5 `debug_action` | Same-task Debug-Trajectory card distilled into recommended artifact action | Repair-smoke upper bound |

The current committed builder creates all six variants. B3 is implemented as a
deterministic prompt-filter approximation so it can run without another model
call; if an LLM judge is later used, freeze the judge prompt and report it as a
separate `prompt_filtered_llm` condition.

## Instruction.md Injection Protocol

For this baseline, trace/context injection is done only by editing a copied
task's `instruction.md`.

This is OK for a first Harbor baseline because Harbor treats `instruction.md` as
the task prompt shown to the agent. If we copy the task directory and edit only
the copy, then the sandbox, Docker image, tests, verifier, and artifact
contract stay unchanged.

The generated prompt has this shape:

```text
<original instruction.md>

----- BEGIN ICL BASELINE CONTEXT: <variant> -----
This block is in-context learning context from a previous teacher run, not an
additional task requirement...

<outcome-only card | raw trace card | Debug-Trajectory card>
----- END ICL BASELINE CONTEXT: <variant> -----

Now solve the current task in the live environment and close the required
artifact.
```

The control condition `no_icl` is just the original instruction copied into the
variant task directory.

Important constraints:

- Never edit the source task directory under the Terminal-Bench dataset.
- Keep every condition on the same task copy mechanism, timeout, verifier, and
  model endpoint.
- If a copied verifier needs an infrastructure-only patch, apply the same patch
  to every variant for that task and report it separately from model behavior.
- Treat same-task trace injection as a repair / replay smoke test. It can leak
  task-specific solution details, so it is not the final held-out
  generalization result.
- Use the same context budget when comparing `raw_trace`, `prompt_filtered`,
  and `debug_trajectory`.
- Compare Meta-Harness-style changed-harness runs separately from ICL-selection
  runs; they answer a system-level question, not the primary data-selection
  claim.

## Local Verifier Infrastructure Note

The first local `cancel-async-tasks` run was a false negative caused by verifier
infrastructure, not by the model's `/app/run.py`.

The copied task's original verifier path depended on `apt-get`, `curl`, and
`uvx`. In the local Harbor verifier container, `apt-get` attempted to use
`http://host.docker.internal:1082`, failed to connect to that proxy, then failed
to install `curl`; later `uvx` was not available either. As a result, the tests
did not run reliably.

The builder now patches copied pytest-only verifiers that use `apt/curl/uvx` by
installing `pytest` and `pytest-json-ctrf` with `python -m pip`, then running the
same `/tests/test_outputs.py` file and writing the same reward file. This is an
infrastructure patch, not a semantic verifier change. Disable it with
`--no-verifier-patch` when reproducing against an environment where the original
`apt/curl/uvx` path is stable.

For fairness, all ICL variants for a task should use the same copied verifier
patch during local experiments.

## Data Currently Used

Teacher runs already present on the SSD:

- `tb21-kimi-k25-failures-codex-gpt55-host-20260603Tbatch`: GPT-5.5 solved
  locally confirmed Kimi-K2.5 failures, including `cancel-async-tasks` and
  `query-optimize`.
- `tb21-k26-true-fails-codex-gpt55-host-20260603-clean4`: GPT-5.5 solved 30/40
  tasks from a Kimi-K2.6 strict true-fail set.

Initial target tasks:

- `cancel-async-tasks`
- `count-dataset-tokens`
- `query-optimize`
- `break-filter-js-from-html`

These are same-task repair tests because the teacher example is drawn from the
same task. For the paper-style claim, split by held-out tasks.

Generate the current candidate matrix with:

```bash
scripts/build_icl_task_matrix.py
```

The current matrix contains 30 Kimi-k2.6 failed/unresolved tasks where
Codex+GPT-5.5 teacher reward is `1.0`. After the already-tested
`cancel-async-tasks` and `count-dataset-tokens`, the next practical canaries are
`query-optimize`, `break-filter-js-from-html`, and `gcode-to-text` because they
have concrete teacher artifacts under `/app` that can be injected as
`debug_action` cards. `gcode-to-text` is the cleanest local verifier smoke case:
the Debug-Action artifact `/app/out.txt` passes the official Harbor verifier
with reward `1.0`.

Replay those next canaries as a batch:

```bash
scripts/run_icl_matrix_canaries.sh \
  --limit 2 \
  --model kimi-k2.6 \
  --endpoint-profile auto \
  --inject-mode continue_after \
  --context-variant debug_action \
  --verifier-timeout 600
```

This command selects tasks from `task_matrix.json`, rebuilds the selected
teacher cards and task variants, runs one endpoint preflight, and replays the
live-controller `WebSearch` / `AskUserQuestion` triggers for every selected
task. It only launches Harbor when `--run` is provided. Every batch also writes
`summary.json` and `summary.md`, so `preflight_blocked`, `not_run`,
`failed_verifier`, `passed`, and `model_rate_limited` are not collapsed into the
same bucket.

After each batch, aggregate the full experiment table:

```bash
scripts/aggregate_icl_results.py --pack-dir runs/harbor_icl_baseline
```

The aggregate files are written to `baseline_results.json` and
`baseline_results.md`. The mean reward only uses runs that reached the Harbor
verifier (`passed`, `failed_verifier`, or an explicit injected verifier
failure). Endpoint quota, missing `result.json`, SDK initialization, and Docker
errors stay in the table as infrastructure outcomes, but they are not evidence
for or against the ICL method.

Before launching a model run, check that the selected Debug-Action cards can
materialize their expected artifacts:

```bash
scripts/check_debug_action_closure.py \
  --pack-dir runs/harbor_icl_baseline \
  --task query-optimize \
  --task break-filter-js-from-html
```

This is a non-model closure check. For `query-optimize`, it validates the
materialized `/app/sol.sql` against cheap SQL guards from the verifier. For
`break-filter-js-from-html`, it validates the parser-differential artifact
shape and records that the full Chromium/Selenium verifier is still required.
The output is included in `baseline_results.md` as `artifact_closure` evidence
and is excluded from mean reward.

To run the same Debug-Action artifact through Harbor's official verifier
without calling a model endpoint:

```bash
scripts/run_harbor_artifact_closure.sh \
  --task break-filter-js-from-html \
  --context-variant debug_action \
  --no-force-build \
  --verifier-timeout 300
```

These runs appear as `harbor_artifact_closure`. Current local evidence:

- `gcode-to-text`: `/app/out.txt` materialized successfully and the official
  verifier passed (`reward=1.0`, 2 pytest tests passed). This is the current
  clean no-model proof that a Debug-Action card can close a Kimi-failed /
  Codex-passed task artifact through Harbor.
- `query-optimize`: `/app/sol.sql` materialized successfully and now passes the
  full Harbor verifier in the runtime `sdk_live + debug_action` run
  (`reward=1.0`, 6 pytest tests passed). The earlier daily-safe artifact
  closure timeout was a timeout-budget artifact, not a semantic failure.
- `break-filter-js-from-html`: `/app/out.html` materialized successfully, but
  verifier setup failed before browser validation because Debian package
  fetches resolved to `198.18.*`, `curl` was unavailable, and `uvx` could not
  be installed.

The remaining `break-filter-js-from-html` issue is classified as verifier
infrastructure/cost outcome, not as a model or Debug-Action artifact failure.

## Daily Promotion Rule

There are two daily levels:

1. **Mechanism canary**: safe to run now. It checks the Debug-Action card,
   runtime injection hook, Docker artifact materialization, and official
   verifier path without model calls.
2. **Model reward benchmark**: run only when endpoint preflight is healthy and
   the selected tasks have no verifier blockers in `icl_readiness.md`.

Current status is `daily_mechanism_canary_only`. The one-command mechanism
canary is:

```bash
scripts/run_daily_icl_mechanism.sh \
  --task gcode-to-text \
  --context-variant debug_action \
  --verifier-timeout 300
```

This default task is intentionally narrow: `gcode-to-text` is a Kimi-k2.6
failed / Codex+GPT-5.5 passed candidate with a concrete `/app/out.txt`
Debug-Action artifact, and the local official verifier has already passed it.
Use this job to catch regressions in the interactive ICL plumbing. Do not use
its no-model reward as evidence that Kimi improved.

Once a real endpoint passes preflight, move to:

```bash
scripts/run_icl_baseline_suite.sh \
  --task gcode-to-text \
  --model kimi-k2.6 \
  --endpoint-profile ark \
  --inject-mode continue_after \
  --verifier-timeout 600 \
  --run
```

The suite runs `outcome_only`, `raw_trace`, `prompt_filtered`,
`debug_trajectory`, and `debug_action` under the same model, endpoint,
injection mode, timeout, and verifier path. Compare these model reward rows
under a fixed context budget. The aggregate excludes `artifact_closure`,
`harbor_artifact_closure`, and `harbor_runtime_smoke` from mean reward so the
two daily levels do not get mixed.

For the most faithful version of “inject context while Claude Code is running,”
use `--inject-mode hooks_live`. This mode keeps the original task instruction
clean, passes a temporary `--settings` file to Claude Code, installs a
`PreToolUse` command hook, and injects prior-trace context before
`AskUserQuestion`, `WebSearch`, `WebFetch`, or dependency-install `Bash`
commands. It is closer to the desired production harness behavior than
`continue_after`; `sdk_live` remains useful as a same-process SDK probe.

## Build The ICL Pack

```bash
python3 scripts/build_harbor_icl_baseline.py \
  --output-dir runs/harbor_icl_baseline \
  --model kimi-for-coding \
  --max-context-chars 12000
```

The builder writes:

- `teacher_cards/<task>/debug_trajectory.md`
- `teacher_cards/<task>/debug_action.md`
- `teacher_cards/<task>/prompt_filtered.md`
- `teacher_cards/<task>/raw_trace.md`
- `teacher_cards/<task>/outcome_only.md`
- `prompts/<variant>/<task>.md`
- `task_variants/<variant>/<task>/instruction.md`
- `run_harbor_variants.sh`
- `manifest.json`

The task copies are generated under `runs/`, which is intentionally ignored by
git. By default, copied task verifiers are preserved exactly from the source
task. Use `--patch-verifier` only for explicitly marked local-infrastructure
experiments; patched verifiers should not be mixed into benchmark reward claims.

## Run Kimi-K2.5 Through The Token Plan / Claude Code Route

Set credentials outside the repo:

```bash
export TOKEN_PLAN_BASE_URL="https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic"
export TOKEN_PLAN_API_KEY="..."
export DOCKER_HOST="unix:///Users/hugo/.colima/tb21-harbor/docker.sock"
```

Runtime ICL scripts also support explicit Anthropic-compatible endpoint
profiles. Keep keys in the shell environment, not in config files:

```bash
export ARK_API_KEY="..."
scripts/run_daily_icl_canary.sh --endpoint-profile ark --model kimi-k2.6

export DASHSCOPE_API_KEY="..."
scripts/run_daily_icl_canary.sh --endpoint-profile dashscope --model kimi-k2.5
```

`ark` defaults to `https://ark.cn-beijing.volces.com/api/coding`;
`dashscope` defaults to `https://coding.dashscope.aliyuncs.com/apps/anthropic`;
`kimi` defaults to `https://api.kimi.com/coding/`. Override the default base
URLs with `ARK_BASE_URL`, `DASHSCOPE_BASE_URL`, or `KIMI_BASE_URL` when needed.
The endpoint profile is a run condition, not an ICL method variable.

Run a dry check first:

```bash
scripts/run_harbor_icl_variants.sh \
  --pack-dir runs/harbor_icl_baseline \
  --model kimi-k2.5 \
  --task cancel-async-tasks \
  --variant debug_trajectory \
  --dry-run
```

Then launch the actual baseline:

```bash
scripts/run_harbor_icl_variants.sh \
  --pack-dir runs/harbor_icl_baseline \
  --model kimi-k2.5 \
  --task cancel-async-tasks \
  --variant debug_trajectory
```

To run the full small baseline matrix:

```bash
scripts/run_harbor_icl_variants.sh \
  --pack-dir runs/harbor_icl_baseline \
  --model kimi-k2.5
```

For Kimi Code's official Claude Code endpoint, use:

```bash
export ANTHROPIC_BASE_URL="https://api.kimi.com/coding/"
export ANTHROPIC_API_KEY="..."

scripts/run_harbor_icl_variants.sh \
  --pack-dir runs/harbor_icl_baseline \
  --model kimi-for-coding \
  --task cancel-async-tasks \
  --variant debug_trajectory \
  --kimi-code
```

## Evaluation

Primary metric:

- verifier reward / pass rate

Secondary metrics:

- wall-clock time
- tool-call count
- artifact closure
- token cost when available
- failure-pattern shift from the original Kimi-K2.5 run

## Daily Baseline Readiness

Use the daily canary entry point before adding a result to the experiment table:

```bash
scripts/run_daily_icl_canary.sh \
  --task count-dataset-tokens \
  --model kimi-k2.6 \
  --inject-mode sdk_live \
  --context-variant debug_action \
  --verifier-timeout 600
```

The default command does not launch Harbor. It performs:

- endpoint preflight, so quota/auth failures are not misreported as verifier or
  method failures;
- synthetic live-controller replay for `WebSearch` and `AskUserQuestion`
  triggers;
- a clear readiness line telling whether `--run` is safe to use.

Only add `--run` when endpoint preflight is healthy. For `sdk_live`, only treat
a run as a method datapoint when `sdk-live-summary.json` shows Claude Code
entered the tool loop; `model_rate_limited`, `sdk_install_timeout`, and
`sdk_no_claude_init` are infrastructure outcomes.

Daily readiness has two tiers:

- mechanism canary: endpoint preflight, controller replay, cheap artifact
  closure, and bounded Harbor artifact-closure runs may run daily now;
- reward benchmark: only compare pass rates when the official verifier produces
  `passed` or `failed_verifier`. Statuses such as
  `verifier_dependency_failure` and `verifier_timeout_after_materialization`
  are useful diagnostics, but they are not model-quality datapoints.

After aggregating, generate the machine-readable gate:

```bash
scripts/aggregate_icl_results.py --pack-dir runs/harbor_icl_baseline
scripts/report_icl_readiness.py --pack-dir runs/harbor_icl_baseline
```

Current local decision is `daily_mechanism_canary_only`: controller replay and
artifact closure are ready for daily checks, but model endpoints and full
official verifiers are not yet ready for reward-table claims.

When model endpoints are blocked, use the no-model runtime smoke to verify the
Docker-side injection mechanism:

```bash
scripts/run_harbor_runtime_smoke.sh \
  --task gcode-to-text \
  --context-variant debug_action \
  --trigger ask_user_question \
  --verifier-timeout 180

scripts/run_harbor_runtime_smoke.sh \
  --task gcode-to-text \
  --context-variant debug_action \
  --trigger WebSearch \
  --verifier-timeout 180
```

The current `gcode-to-text` smokes record both `AskUserQuestion.updated_input`
and `PreToolUse.additionalContext` in `live-controller-events.jsonl`,
materialize `/app/out.txt`, and pass the official verifier with reward `1.0`.
This is mechanism evidence, not a Kimi pass-rate datapoint.

The static `instruction.md` injection baseline is ready for daily smoke tests:

1. Build or refresh the ICL pack from teacher traces.
2. Run `no_icl`, `outcome_only`, `raw_trace`, `debug_trajectory`, and optionally
   `debug_action` on the same target task/model/endpoint.
3. Record verifier reward, tokens, wall-clock time, and failure-pattern shift.
4. Treat same-task success as a replay smoke test, not as cross-task
   generalization evidence.

Runtime `prelude` injection is also ready for same-task repair smoke tests. It
does not edit `instruction.md`; the Harbor agent injects the selected card into
the Claude Code launch prompt at run time. This is the most reliable current
way to test whether a weaker model can reuse a teacher action/artifact.

Runtime `continue_after` injection is daily-ready as a controller-style smoke
test. It starts from the original instruction without ICL, observes the first
bounded turn, replays the controller decision against the saved stream-json log,
then injects the selected Debug card through `claude --continue` only when a
trigger or artifact gap is present.

Runtime `tool` injection is useful for instrumentation but is not daily-ready
as the main baseline. In two `count-dataset-tokens` attempts, Kimi either called
`htd-context` but still chose heavyweight recomputation, or skipped
`htd-context` and started with web/dataset tooling. This shows that prompt-only
tool-call policy is not a reliable injection controller.

Runtime `continue_after` injection is the first true controller-style baseline.
It starts Claude Code with the original instruction and no ICL, lets the first
turn run for a bounded window, parses the first-turn stream-json log for
triggers, checks whether expected artifacts are missing or mismatched, then
uses `claude --continue` to inject the selected Debug card into the same Claude
session before the official verifier runs.

The full interactive "inject ICL during the same live turn" baseline has an
experimental implementation through `sdk_live`. It now has a successful
`query-optimize` canary on Ark / `kimi-k2.6`, so it is eligible for controlled
same-task mechanism comparisons. Keep the following checks in the daily table so
infrastructure failures do not get mistaken for ICL failures:

- endpoint preflight returns `ok: true`;
- the SDK runner emits a Claude Code `init` event;
- `tool_event_count > 0`;
- `injection_count > 0` for an intended trigger such as `WebSearch`,
  `WebFetch`, dependency-install `Bash`, or `AskUserQuestion`;
- the verifier runs normally, regardless of pass/fail.

Before adding a daily result to the table, run the cheap controller replay
sanity checks:

```bash
PYTHONPATH=src scripts/replay_runtime_controller.py \
  --log-path runs/harbor_icl_baseline/harbor_runs/<job>/<trial>/agent/claude-code-first.txt \
  --context-path runs/harbor_icl_baseline/teacher_cards/<task>/debug_action.md \
  --output-path /tmp/htd-controller-real.json \
  --artifact-root /tmp/htd-empty-app
```

The replay should report actual tool-use triggers from the JSONL trace, not
strings that only appeared in a system tool list. For example, a real
`AskUserQuestion` tool call should produce `ask_user_question`, while a plain
text mention of the tool name should not.

For `sdk_live`, run an endpoint preflight first so quota or auth failures do
not get misreported as method failures:

```bash
scripts/check_model_endpoint.py --model kimi-k2.6
```

After an `sdk_live` trial, generate a status summary:

```bash
scripts/summarize_sdk_live_trial.py \
  runs/harbor_icl_baseline/harbor_runs_sdk_live/<job>/<trial> \
  --output runs/harbor_icl_baseline/harbor_runs_sdk_live/<job>/<trial>/sdk-live-summary.json
```

Only compare verifier reward across ICL methods when the summary status shows
the model actually entered the agent loop. Treat `model_rate_limited`,
`sdk_python_missing`, `sdk_install_timeout`, and `sdk_no_claude_init` as
infrastructure outcomes.

## Runtime ICL MVP

The repository now includes a first runtime-injection MVP:

- Agent import path:
  `harness_trajecdebug.experiments.dynamic_icl_agent:DynamicIclClaudeCode`
- Runner:
  `scripts/run_harbor_dynamic_icl.sh`
- Runtime context command inside the task container:
  `htd-context "brief question or current plan"`
- Runtime modes:
  - `tool`: install `htd-context` and rely on the agent to call it.
  - `prelude`: inject the selected card into the Claude Code launch prompt at
    run time without editing `instruction.md`.
  - `continue_after`: run a first no-context turn, detect triggers/artifact
    gaps, then inject the selected card with `claude --continue` before
    verifier execution.
  - `hooks_live`: keep the ordinary Claude Code CLI path, install a native
    `PreToolUse` command hook through Claude settings, and inject when the live
    run reaches `AskUserQuestion`, selected search/fetch tools, or costly
    dependency-install commands.
  - `sdk_live`: run Claude Code through the Python Agent SDK inside the task
    container and inject context via `PreToolUse.additionalContext` or
    `AskUserQuestion.updated_input`.

This differs from static `instruction.md` injection in one important way: the
full Debug-Trajectory card is not appended to the copied task instruction. In
`tool` mode, the initial prompt only tells Claude Code that a runtime context
command exists, and the teacher card enters the model context only if Claude
Code calls `htd-context`. Each call is logged to
`/logs/agent/htd-context-uses.jsonl`, which lets us verify the injection point.
In `prelude`, `continue_after`, and `hooks_live` modes, injection is controlled
by the Harbor agent wrapper instead of editing the task file.

Example:

```bash
python3 scripts/build_harbor_icl_baseline.py \
  --output-dir runs/harbor_icl_baseline \
  --target-task break-filter-js-from-html \
  --model kimi-k2.6

export ANTHROPIC_BASE_URL="..."
export ANTHROPIC_API_KEY="..."
export DOCKER_HOST="unix:///Users/hugo/.colima/tb21-harbor/docker.sock"

scripts/run_harbor_dynamic_icl.sh \
  --pack-dir runs/harbor_icl_baseline \
  --task break-filter-js-from-html \
  --model kimi-k2.6 \
  --endpoint-profile auto \
  --context-variant debug_action \
  --inject-mode continue_after \
  --first-turn-timeout 75 \
  --verifier-timeout 600
```

This MVP now has five layers:

- `tool`: logged but model-dependent context retrieval.
- `prelude`: reliable run-time prompt injection without editing the task file.
- `continue_after`: first-turn observation followed by `claude --continue`.
- `hooks_live`: Claude Code native `PreToolUse` command-hook injection while
  preserving the normal CLI execution path.
- `sdk_live`: true live interception using the Agent SDK's tool callbacks.

Runtime job names include both injection mode and context variant:

```text
htd-dynamic-icl-<inject_mode>-<context_variant>-<task>-<model>
```

This avoids overwriting `prelude`, `continue_after`, `hooks_live`, and
`sdk_live` results for the same task/model pair. Summaries still fall back to the older
`htd-dynamic-icl-<task>-<model>` name when reading historical smoke runs.
The dynamic runner now also archives any existing same-name job directory under
`<jobs-dir>/_archived/` before a real rerun. `--dry-run` is non-destructive and
does not write into the existing job directory.

`hooks_live` and `sdk_live` are the intended paths for a full `AskUserQuestion`
controller. Both can answer `AskUserQuestion` with Debug-Trajectory context and
can optionally inject context before `WebSearch`, `WebFetch`, or
dependency-install `Bash` calls. `hooks_live` uses Claude Code's command-hook
surface and can be replayed offline with `scripts/replay_live_icl_hook.py`.
`sdk_live` is still more invasive because it currently bootstraps Python/pip
when a task image lacks Python, installs `claude-agent-sdk` inside the task
container, and depends on model endpoint quota being available during the run.

Local coverage now includes both hook-bridge replay tests and fake-SDK
integration tests for the live paths: `PreToolUse.additionalContext` and
`AskUserQuestion.updated_input`. These tests prove the runner-to-controller
wiring and event logging without calling a model endpoint. They do not replace
a real Kimi canary because no actual model/tool loop is exercised.

Historical smoke notes and current filesystem evidence:

- Historical note: `count-dataset-tokens` + runtime `htd-context` + Claude Code +
  `kimi-k2.6` successfully called the runtime ICL channel on 2026-06-10.
- The call was logged at the following path during that run:
  `runs/harbor_icl_baseline/harbor_runs/htd-dynamic-icl-count-dataset-tokens-kimi-k2-6/count-dataset-tokens__cSMjiQ8/agent/htd-context-uses.jsonl`.
- The model received the Debug-Trajectory card, including the teacher artifact
  value, but then chose to independently install `pyarrow` and `transformers`.
  That pip install hung in the task container.
- The container was stopped manually, so Harbor reported
  `RewardFileNotFoundError`. This run proves the runtime injection channel
  works, but it is not a valid task-pass/fail measurement.
- Historical note: `count-dataset-tokens` + runtime `prelude` + `debug_action` + Claude Code +
  `kimi-k2.6` passed on 2026-06-10.
- Original historical Kimi-K2.6 trial:
  `/Volumes/SSD/terminal-bench-harbor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy/jobs/tb21-count-dataset-tokens-claude-code-k6/count-dataset-tokens__bMTDtbq`,
  verifier reward `0.0`; verifier expected `79586` but `/app/answer.txt`
  contained `79566`.
- Teacher Codex + GPT-5.5 run:
  `/Volumes/SSD/terminal-bench-harbor/harbor/runs/tb21-k26-true-fails-codex-gpt55-host-20260603-clean4/tasks/count-dataset-tokens`,
  reward `1.0`.
- Historical repair-smoke trial:
  `runs/harbor_icl_baseline/harbor_runs/htd-dynamic-icl-count-dataset-tokens-kimi-k2-6/count-dataset-tokens__xpViLdm`,
  verifier reward `1.0`, `1 passed in 0.01s`, agent tokens
  `n_input_tokens=124204`, `n_output_tokens=870`.
- Historical note: `count-dataset-tokens` + runtime `continue_after` + `debug_action` + Claude
  Code + `kimi-k2.6` also passed on 2026-06-10.
- In the first no-context turn, Kimi started with `WebSearch` / `WebFetch`
  instead of the teacher context. The controller then injected via
  `claude --continue` because `/app/answer.txt` was still missing and the
  first-turn trace contained web-tool usage.
- Historical controller-style trial:
  `runs/harbor_icl_baseline/harbor_runs/htd-dynamic-icl-count-dataset-tokens-kimi-k2-6/count-dataset-tokens__5VEAHhk`,
  verifier reward `1.0`, `1 passed in 0.01s`, agent tokens
  `n_input_tokens=204458`, `n_output_tokens=1876`.
  The controller decision was written to
  `agent/controller-decision.json`; the injected second turn was saved as
  `agent/claude-code-continue.txt`.
- Those three historical runtime trial directories are no longer present in
  the current filesystem snapshot, likely because earlier same-name dry-runs
  reused the job directory. They are therefore not counted in
  `baseline_results.md`. The dynamic runner now archives existing job
  directories and makes dry-runs non-destructive to prevent this evidence loss
  from recurring.
- `count-dataset-tokens` + runtime `sdk_live` + `debug_action` + Claude Code +
  `kimi-k2.6` was launched on 2026-06-10 as the first same-process live
  interception probe.
- Trial:
  `runs/harbor_icl_baseline/harbor_runs_sdk_live/htd-dynamic-icl-count-dataset-tokens-kimi-k2-6/count-dataset-tokens__B34mXiy`.
- Engineering result: the task container installed `claude-agent-sdk==0.1.43`,
  started Claude Code through the SDK, and emitted an SDK `init` event with
  `AskUserQuestion`, `WebSearch`, and `WebFetch` available.
- Model result: the run did not reach a tool-use trigger because the endpoint
  returned HTTP 429 / quota exhausted for all retries. `/app/answer.txt` was not
  created, so verifier reward was `0.0`; this is an API quota / infrastructure
  run, not evidence that `sdk_live` selection failed.
- Evidence files:
  `agent/sdk-live-events.jsonl`, `agent/sdk-install.log`, `agent/claude-code.txt`,
  `agent/command-1/return-code.txt`, and `sdk-live-summary.json`.

## Claim-Quality Experiment

For the stronger claim, avoid same-task leakage:

1. Build an example bank from GPT-5.5 successful traces on training tasks.
2. Select examples for a held-out Kimi-K2.5 failed task using:
   - random successful trace,
   - outcome-only top examples,
   - raw trace under the same token budget,
   - frozen prompt-filtered snippets, with an optional later
     `prompt_filtered_llm` judge condition,
   - Debug-Trajectory selected cards.
3. Keep token budget, number of examples, model, harness, timeout, and Docker
   image fixed.
4. Evaluate on held-out Harbor-style tasks and compare pass rate plus failure
   pattern shifts.
