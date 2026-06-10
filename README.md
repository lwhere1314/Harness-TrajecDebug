# Harness-TrajecDebug

Harness-TrajecDebug is an explainable trace diagnosis and data selection
framework for terminal-agent in-context learning. It turns raw pass/fail
benchmark trajectories into process-level records with reference objects, state
events, decision evidence, failure patterns, a critical step, and a repair hint.

The project is intentionally conservative: it only emits failure patterns when
there is concrete trace evidence and a final verifier footprint.

See [docs/failure-taxonomy.md](docs/failure-taxonomy.md) for the taxonomy diagram
and [docs/framework.md](docs/framework.md) for the reference/state/commitment
workflow. See [docs/roadmap.md](docs/roadmap.md) for the current progress,
to-do list, and planned Harbor experiments. See
[docs/related-work-metaharness.md](docs/related-work-metaharness.md) for a
comparison with Meta-Harness. See
[experiments/harbor_icl_baseline/README.md](experiments/harbor_icl_baseline/README.md)
for the first Kimi ICL baseline design and runner scripts, and
[experiments/harbor_icl_baseline/fairness_protocol.md](experiments/harbor_icl_baseline/fairness_protocol.md)
for the fairness boundary against Meta-Harness-style changed-harness baselines.

## Project Positioning

The first target application is **ICL data selection** for smaller terminal
agents. Instead of feeding small models random successful traces or traces chosen
only by final outcome, Harness-TrajecDebug selects trajectories based on the
process signal inside the trace:

- successful traces with verifier-aligned artifact closure,
- near-miss traces with clear critical-step evidence,
- contrastive traces where a bad branch and a repairable decision are visible,
- traces that demonstrate useful planning, validation, recovery, and state
  checking behavior.

SFT, RL, and preference-learning pipelines are future downstream applications.
The immediate goal is to build a reliable trace-to-ICL-example pipeline first.

## Current Mechanism Result

The first runtime-ICL canary is now working end to end on Harbor /
Terminal-Bench-style tasks. On `query-optimize`, Claude Code + `kimi-k2.6`
previously produced a semantically correct SQL rewrite that still failed the
official runtime gate. Harness-TrajecDebug reruns the same agent through
`sdk_live`, watches Claude Code tool events with the Python Agent SDK, and
injects a selected prior-trace hint at the first relevant `Bash` step.

In the controlled same-task canary:

| Condition | Runtime injection | Result |
| --- | --- | --- |
| `no_icl` | none | reward `0.0`; solution slower than the official golden query |
| `outcome_only + sdk_live` | teacher outcome summary only | reward `0.0`; injection happened, but the agent rebuilt the insufficient route |
| `debug_action + sdk_live` | Debug-Trajectory repair card with `/app/sol.sql` | reward `1.0`; the agent materialized the teacher artifact and passed 6/6 verifier tests |

This is not yet the final held-out generalization claim. It is a mechanism
check showing that process-aware Debug-Trajectory examples can correct a
previously failing interactive run, while outcome-only context does not provide
enough guidance on the same case.

## Why This Exists

Benchmark reward is useful for ranking agents, but it is too sparse for
improving harnesses. A failed terminal-agent run can fail because of verifier
misalignment, a thin validation margin, a tool/API loop, missing artifact
closure, or a bad search strategy. Those all look like reward `0`.

Harness-TrajecDebug adds the missing process layer:

```text
trace + verifier output
  -> reference view
  -> state view
  -> commitment / decision evidence
  -> failure pattern
  -> critical step
  -> repair hint
  -> ICL data quality signal
```

The core research question is:

> Can process-aware trajectory selection produce better ICL examples for small
> terminal agents than prompt-based LLM filtering or outcome-only filtering?

## Install

```bash
cd /path/to/Harness-TrajecDebug
python3 -m pip install -e .
```

No runtime dependencies are required.

## Quick Start

Run the built-in train-fasttext example:

```bash
harness-trajdebug diagnose \
  --trace examples/traces/train-fasttext-kimi-k26-minimal.json \
  --run-id train-fasttext-kimi-k26-minimal \
  --output examples/diagnoses/train-fasttext-kimi-k26-diagnosis.json
```

Run the passing cancel-async-tasks example:

```bash
harness-trajdebug diagnose \
  --trace examples/traces/cancel-async-tasks-passed-minimal.json \
  --run-id cancel-async-tasks-passed-minimal \
  --output examples/diagnoses/cancel-async-tasks-diagnosis.json
```

The command alias `harness-trajecdebug` is also available.

## Vercel Demo

This repository also includes a lightweight Vercel demo:

- `index.html`, `styles.css`, and `app.js` render the web interface.
- `api/diagnose.py` runs the same Python diagnosis engine on bundled examples.

Deploy it with:

```bash
npx vercel --prod
```

Then verify the cloud API:

```bash
curl https://your-deployment-url.vercel.app/api/diagnose?example=all
```

## Example Output

For the train-fasttext near miss, the prototype produces:

```json
{
  "task_family": "train-fasttext",
  "outcome": "failed",
  "final_failure": "final verifier P@1=0.617 < threshold 0.62",
  "failure_patterns": [
    {"name": "thin-margin promotion"},
    {"name": "compact-frontier search gap"}
  ],
  "critical_step": {
    "pattern": "thin-margin promotion",
    "step_index": 8,
    "evidence": "P@1 0.621"
  }
}
```

## Trace Input Schema

The minimal input is a JSON object:

```json
{
  "steps": [
    {
      "index": 0,
      "role": "user",
      "text": "Task prompt",
      "observation": "Optional tool output"
    }
  ],
  "verifierLog": "Final verifier stdout/stderr"
}
```

The parser also understands simple `toolCalls`, `reasoning`, and nested string
fields from common trace viewers.

## Development

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests
python3 -m py_compile src/harness_trajecdebug/*.py
```

Or use:

```bash
make test
make examples
```

## Harbor ICL Baseline

Build the task matrix from historical local runs. This identifies Kimi-k2.6
failed/unresolved tasks where Codex+GPT-5.5 teacher reward is `1.0`:

```bash
scripts/build_icl_task_matrix.py
```

The matrix is written to `runs/harbor_icl_baseline/task_matrix.json` and
`runs/harbor_icl_baseline/task_matrix.md`.

Replay the next matrix canaries without launching Harbor:

```bash
scripts/run_icl_matrix_canaries.sh \
  --limit 2 \
  --model kimi-k2.6 \
  --endpoint-profile auto \
  --inject-mode continue_after \
  --context-variant debug_action
```

When endpoint preflight is healthy, add `--run` to run those canaries
sequentially.

Each matrix canary batch writes `summary.json` and `summary.md` under
`runs/harbor_icl_baseline/matrix_canary/<batch>/`, separating replay readiness
from actual Harbor reward. This keeps endpoint/quota failures distinct from
method or verifier failures.

Run the full runtime-ICL baseline suite for one task without model calls:

```bash
scripts/run_icl_baseline_suite.sh \
  --task gcode-to-text \
  --model kimi-k2.6 \
  --endpoint-profile auto \
  --inject-mode continue_after \
  --verifier-timeout 600
```

This replays `outcome_only`, `raw_trace`, `prompt_filtered`,
`debug_trajectory`, and `debug_action` under the same runtime injection mode.
When endpoint preflight is healthy, add `--run` to launch the same suite through
Harbor sequentially.

Aggregate static, runtime, SDK-live, and matrix canary outcomes after every
daily batch:

```bash
scripts/aggregate_icl_results.py --pack-dir runs/harbor_icl_baseline
scripts/report_icl_readiness.py --pack-dir runs/harbor_icl_baseline
```

The aggregate report writes `baseline_results.json` and `baseline_results.md`.
The readiness report writes `icl_readiness.json` and `icl_readiness.md`.
Only real verifier outcomes such as `passed` and `failed_verifier` enter mean
reward. Infrastructure states such as `preflight_blocked`, `model_rate_limited`,
`missing_result`, `infrastructure_error`, `verifier_dependency_failure`, and
`verifier_timeout_after_materialization` remain visible but are excluded from
pass-rate comparison.

Runtime runs preserve evidence by default: if a job directory already exists,
`scripts/run_harbor_dynamic_icl.sh` moves it to `<jobs-dir>/_archived/` before
launching a new real run. `--dry-run` is non-destructive and writes its log to
`/private/tmp`.

Before spending model calls, verify that same-task Debug-Action cards can
materialize the intended artifact:

```bash
scripts/check_debug_action_closure.py \
  --pack-dir runs/harbor_icl_baseline \
  --task query-optimize \
  --task break-filter-js-from-html \
  --task gcode-to-text
```

This writes `artifact_closure/debug_action_closure.json` and `.md`, and the
aggregate report includes these rows as non-model artifact evidence. They do
not enter verifier reward averages.

For a stronger no-model check, run the Debug-Action artifact through Harbor's
official verifier:

```bash
scripts/run_harbor_artifact_closure.sh \
  --task gcode-to-text \
  --context-variant debug_action \
  --verifier-timeout 180
```

These rows appear as `harbor_artifact_closure`. They are useful for separating
artifact validity from model behavior, but verifier setup/network failures are
still classified separately from model failures. Use `--verifier-timeout` for
daily canaries so slow official tests cannot block the whole batch.

To verify the runtime injection controller itself without calling a model
endpoint, run a no-model Harbor smoke test. This simulates an `AskUserQuestion`
trigger, records the injected context decision, materializes the Debug-Action
artifact in Docker, and then runs the official verifier:

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

These rows appear as `harbor_runtime_smoke`. They prove the mechanism path, not
Kimi model quality.

For the current daily-safe check, run the mechanism canary. It does not call a
model endpoint; it rebuilds the selected card, runs local artifact closure,
runs the Debug-Action artifact through Harbor's official verifier, smokes both
`AskUserQuestion` and `WebSearch` runtime injection paths, and refreshes
`baseline_results.*` plus `icl_readiness.*`:

```bash
scripts/run_daily_icl_mechanism.sh \
  --task gcode-to-text \
  --context-variant debug_action \
  --verifier-timeout 300
```

Promote the daily job from `daily_mechanism_canary_only` to model reward
benchmarking only when endpoint preflight is healthy and the readiness report
has no verifier blockers for the selected task set. Until then, mechanism smoke
rows are evidence that runtime injection works, not evidence that Kimi improved.

Build a same-task trace-assisted repair pack from local GPT-5.5 teacher runs:

```bash
python3 scripts/build_harbor_icl_baseline.py \
  --output-dir runs/harbor_icl_baseline \
  --model kimi-for-coding \
  --max-context-chars 12000
```

Run one Kimi-K2.5 condition through the Token Plan / Claude Code route:

```bash
scripts/run_harbor_icl_variants.sh \
  --pack-dir runs/harbor_icl_baseline \
  --model kimi-for-coding \
  --task cancel-async-tasks \
  --variant debug_trajectory \
  --kimi-code
```

Use `--dry-run` first to inspect the Harbor command without calling the model
API.

Run the daily-safe runtime ICL canary. Without `--run`, this checks endpoint
health and replays live-controller triggers without launching Harbor:

```bash
scripts/run_daily_icl_canary.sh \
  --task count-dataset-tokens \
  --model kimi-k2.6 \
  --endpoint-profile auto \
  --inject-mode sdk_live \
  --context-variant debug_action \
  --verifier-timeout 600
```

Add `--run` only after the preflight is healthy.

Use `--endpoint-profile ark`, `--endpoint-profile dashscope`, or
`--endpoint-profile kimi` to switch Anthropic-compatible providers without
changing the ICL condition. These profiles read `ARK_API_KEY`,
`DASHSCOPE_API_KEY`, or `KIMI_API_KEY` from the local shell and never write
secrets into run configs. `auto` keeps the current behavior: `ANTHROPIC_*`
first, then `TOKEN_PLAN_*`.

Run the runtime controller-style baseline without editing `instruction.md`:

```bash
scripts/run_harbor_dynamic_icl.sh \
  --pack-dir runs/harbor_icl_baseline \
  --model kimi-k2.6 \
  --task count-dataset-tokens \
  --endpoint-profile auto \
  --context-variant debug_action \
  --inject-mode continue_after \
  --first-turn-timeout 75 \
  --verifier-timeout 600
```

Run the Claude Code native hook mode when you want the injection to happen
inside the ordinary CLI run, before matching tool calls. This mode writes a
temporary Claude settings file, installs a `PreToolUse` command hook, passes
`--settings` plus `--include-hook-events` to Claude Code, and injects context
when Claude reaches `AskUserQuestion`, `WebSearch`, `WebFetch`, or a dependency
install command:

```bash
scripts/run_harbor_dynamic_icl.sh \
  --pack-dir runs/harbor_icl_baseline \
  --model kimi-k2.6 \
  --task gcode-to-text \
  --endpoint-profile auto \
  --context-variant debug_action \
  --inject-mode hooks_live \
  --verifier-timeout 600 \
  --dry-run
```

Run the experimental same-process SDK live-intercept mode:

```bash
scripts/check_model_endpoint.py --model kimi-k2.6

scripts/run_harbor_dynamic_icl.sh \
  --pack-dir runs/harbor_icl_baseline \
  --model kimi-k2.6 \
  --task count-dataset-tokens \
  --context-variant debug_action \
  --inject-mode sdk_live \
  --sdk-live-intercept-tool WebSearch \
  --sdk-live-intercept-tool WebFetch \
  --preflight
```

Summarize an `sdk_live` trial after it finishes:

```bash
scripts/summarize_sdk_live_trial.py \
  runs/harbor_icl_baseline/harbor_runs_sdk_live/<job>/<trial> \
  --output runs/harbor_icl_baseline/harbor_runs_sdk_live/<job>/<trial>/sdk-live-summary.json
```

Replay the controller decision against a saved first-turn log:

```bash
PYTHONPATH=src scripts/replay_runtime_controller.py \
  --log-path runs/harbor_icl_baseline/harbor_runs/<job>/<trial>/agent/claude-code-first.txt \
  --context-path runs/harbor_icl_baseline/teacher_cards/<task>/debug_action.md \
  --output-path /tmp/htd-controller-real.json \
  --artifact-root /tmp/htd-empty-app
```

## Current Scope

Implemented failure patterns:

- `thin-margin promotion`
- `validation mismatch`
- `compact-frontier search gap`
- `accuracy objective gap`
- `final artifact validation`
- `tool/API loop`
- `budget debt loop`
- `no critical failure detected`

Current implementation:

- rule-based reference/state/commitment parser,
- failure taxonomy and critical-step selector,
- bundled train-fasttext and cancel-async-tasks examples,
- Vercel demo API that runs diagnosis on example traces,
- initial GitHub CI.

Next milestones:

- adapters for common harness trace formats,
- Harbor-style task support,
- Harness x Model experiment runner,
- ICL data selection benchmark against prompt-based and outcome-only baselines.
