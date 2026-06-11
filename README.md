# Harness-TrajecDebug

Harness-TrajecDebug is a harness-agnostic trajectory debugging layer for
terminal agents. It reads raw agent traces plus verifier output, localizes the
critical failure step, emits repair evidence, and turns that evidence into
runtime Debug-Action cards that can be injected into future agent runs.

The product direction is not "another benchmark harness." The goal is a plugin
interface that Harbor, Terminal-Bench, Meta-Harness-style runners, Claude Code,
Codex, and Kimi Code can call to:

- run or import experiments,
- preserve raw traces and verifier footprints,
- diagnose failures into critical-step evidence,
- select or synthesize Debug-Action cards,
- rerun with runtime ICL injection,
- export reproducible evidence bundles.

## Demo

The fastest way to understand the project is the top-level demo:

```bash
cd Harness-TrajecDebug
HTD_DEMO_PAUSE=1 demo/query-optimize-trace-to-card.sh --recorded
```

This shows the complete story on one Terminal-Bench / Harbor task:

```text
first agent run fails
-> Harness-TrajecDebug imports the trace
-> critical step is localized
-> a Debug-Action card is selected/generated
-> second run injects the card at PreToolUse(Bash)
-> verifier passes
```

For a real rerun of the second attempt:

```bash
HTD_DEMO_PAUSE=1 demo/query-optimize-trace-to-card.sh --live
```

For a fail-teacher demo where the injected card is derived from reward-0 data,
use one of:

```bash
# Uses checked-in failed teacher evidence, then runs the second attempt live.
HTD_DEMO_PAUSE=1 demo/query-optimize-trace-to-card.sh --live-fail-teacher

# Runs a fresh first failure, generates a fail-teacher card, then reruns live.
HTD_DEMO_PAUSE=1 demo/query-optimize-trace-to-card.sh --live-full-fail-teacher
```

The demo material lives in [`demo/`](demo/):

| File | Purpose |
| --- | --- |
| [`demo/README.md`](demo/README.md) | Recording SOP, scene-by-scene narration, expected terminal output. |
| [`demo/query-optimize-trace-to-card.sh`](demo/query-optimize-trace-to-card.sh) | One-command recorded, live, fail-teacher, and full-live demo runner. |

Expected evidence from the demo:

| Stage | Evidence |
| --- | --- |
| First run | `reward=0`, `5 passed, 1 failed`, runtime gate fails |
| Diagnosis | `critical_step: pattern=budget debt loop` |
| Pass-teacher card check | `closure: closure_passed`, artifact `/app/sol.sql` |
| Fail-teacher card check | `Teacher outcome: reward=0.0`, no copied passing artifact; `closure_unavailable` is expected |
| Runtime injection | `injection_count: 1`, `injection_reasons: ['Bash']` |
| Second run | `reward=1.0`, `6 passed` |

## Repository Map

| Path | What lives there |
| --- | --- |
| [`src/harness_trajecdebug/`](src/harness_trajecdebug/) | Diagnosis core: trace parsing, reference/state extraction, failure patterns, critical-step selection. |
| [`plugins/harness-trajdebug-agent/`](plugins/harness-trajdebug-agent/) | Agent-facing plugin and skills used by Claude Code, Codex, and Kimi Code. |
| [`.claude/skills/`](.claude/skills/), [`.agents/skills/`](.agents/skills/), [`.kimi-code/skills/`](.kimi-code/skills/) | Installed skill shims for the three CLI surfaces. |
| [`demo/`](demo/) | Top-level demo and recording SOP. |
| [`docs/`](docs/) | Framework notes, failure taxonomy, integrations, roadmap, related work, and case-study writeups. |
| [`docs/blog/`](docs/blog/) | Blog-style case studies and raw-log explanations. |
| [`docs/blog/raw_logs/`](docs/blog/raw_logs/) | Blog-facing raw trace bundles, prompts, teacher cards, task variants, Harbor runs, and checksums. |
| [`docs/case-studies/`](docs/case-studies/) | Reproducibility reports, raw experiment archives, metrics, and task-pair summaries. |
| [`experiments/harbor_icl_baseline/`](experiments/harbor_icl_baseline/) | ICL baseline protocol and runners. |
| [`scripts/`](scripts/) | Experiment runners, endpoint checks, closure checks, summarizers, and batch utilities. |
| [`examples/`](examples/) | Minimal normalized traces and diagnoses. |
| [`api/diagnose.py`](api/diagnose.py), [`index.html`](index.html), [`app.js`](app.js) | Lightweight Vercel demo surface. |

## Quick Start

Install the package in editable mode:

```bash
python3 -m pip install -e .
```

Run a bundled near-miss diagnosis:

```bash
harness-trajdebug diagnose \
  --trace examples/traces/train-fasttext-kimi-k26-minimal.json \
  --run-id train-fasttext-kimi-k26-minimal \
  --output examples/diagnoses/train-fasttext-kimi-k26-diagnosis.json
```

Run a passing example:

```bash
harness-trajdebug diagnose \
  --trace examples/traces/cancel-async-tasks-passed-minimal.json \
  --run-id cancel-async-tasks-passed-minimal \
  --output examples/diagnoses/cancel-async-tasks-diagnosis.json
```

The longer command alias `harness-trajecdebug` is also available.

## How It Works

Harness-TrajecDebug reads one trace through three complementary views:

```text
trace + verifier output
  -> reference view
  -> state view
  -> commitment / decision evidence
  -> failure pattern
  -> critical step
  -> repair hint
  -> Debug-Action card / ICL data-quality signal
```

The framework is intentionally conservative: it only emits a failure pattern
when the trace has concrete process evidence and the final verifier footprint
supports the diagnosis.

The first target application is ICL data selection for terminal agents. Instead
of feeding small models random successful traces or outcome-only summaries, the
framework selects trajectories with reusable process signal:

- successful traces with verifier-aligned artifact closure,
- near-miss traces with clear critical-step evidence,
- contrastive traces where a bad branch and a repairable decision are visible,
- traces that demonstrate planning, validation, recovery, and state checking.

SFT, preference learning, process rewards, and RL curricula are downstream
uses. The current milestone is a reliable trace-to-ICL-example and
trace-to-Debug-Action-card pipeline.

## Agent Plugin Surface

The current plugin path is:

```text
agent CLI
  -> skill / plugin shim
  -> Harness-TrajecDebug CLI
  -> trace import / diagnosis / card selection
  -> runtime injection runner
```

Supported or exercised surfaces:

| Surface | Current role |
| --- | --- |
| Claude Code | Can run the `trajectorydebug` / `harness-runtime-icl` skills and execute sdk-live injection. |
| Codex | Can call the same skill wrapper and launch the Harness-TrajecDebug runtime path. |
| Kimi Code | Can load the local skill shim and trigger the same reproduction workflow. |
| Harbor / Terminal-Bench | Provides task environments, official verifier output, and raw run directories. |

See [`docs/agent-plugin.md`](docs/agent-plugin.md) and
[`docs/integrations.md`](docs/integrations.md) for installation and adapter
details.

## Documentation Map

| File | Use it for |
| --- | --- |
| [`docs/framework.md`](docs/framework.md) | Reference/state/commitment workflow and ICL selection logic. |
| [`docs/failure-taxonomy.md`](docs/failure-taxonomy.md) | Failure routing tree, pattern definitions, and repair levers. |
| [`docs/integrations.md`](docs/integrations.md) | Codex, Claude Code, Kimi Code, Harbor, and ATIF viewer adapters. |
| [`docs/trajectorydebug-hint-and-icl-flow.md`](docs/trajectorydebug-hint-and-icl-flow.md) | TD hint generation and runtime ICL injection diagrams. |
| [`docs/related-work-metaharness.md`](docs/related-work-metaharness.md) | Positioning against Meta-Harness and proposed comparisons. |
| [`docs/roadmap.md`](docs/roadmap.md) | Current progress and planned experiments. |
| [`docs/closed-loop-case-summary.md`](docs/closed-loop-case-summary.md) | Closed-loop case summary. |
| [`docs/candidate-search-status.md`](docs/candidate-search-status.md) | Accepted/rejected candidate status and endpoint notes. |
| [`AGENT_MIGRATION_RUNBOOK.md`](AGENT_MIGRATION_RUNBOOK.md) | Server migration, Harbor run, diagnosis, repair, and viewer-export workflow. |

Blog-style case studies:

- [`docs/blog/trajectorydebug-algorithm-flow.md`](docs/blog/trajectorydebug-algorithm-flow.md)
- [`docs/blog/query-optimize-runtime-debug-action.md`](docs/blog/query-optimize-runtime-debug-action.md)
- [`docs/blog/sanitize-git-repo-joint-failure-lifting.md`](docs/blog/sanitize-git-repo-joint-failure-lifting.md)
- [`docs/blog/filter-js-from-html-clean-preservation.md`](docs/blog/filter-js-from-html-clean-preservation.md)
- [`docs/blog/raman-fitting-axis-critical-step.md`](docs/blog/raman-fitting-axis-critical-step.md)
- [`docs/blog/pytorch-model-recovery-forward-api-critical-step.md`](docs/blog/pytorch-model-recovery-forward-api-critical-step.md)

## Current Mechanism Results

The current runtime-ICL canaries show that process-aware Debug-Action cards can
repair failures that outcome-only context does not fix.

On `query-optimize`, Claude Code + `kimi-k2.6` produced a semantically correct
SQL rewrite that still failed the official runtime gate. A same-task controlled
canary compared:

| Condition | Runtime injection | Result |
| --- | --- | --- |
| `no_icl` | none | reward `0.0`; solution slower than the official golden query |
| `outcome_only + sdk_live` | teacher outcome summary only | reward `0.0`; injection happened, but the agent rebuilt the insufficient route |
| `debug_action + sdk_live` | Debug-Action repair card with `/app/sol.sql` | reward `1.0`; the agent materialized the artifact and passed 6/6 verifier tests |

The stronger current signal is joint-failure lifting: failed traces can still be
useful ICL data when their process evidence identifies the critical decision
boundary.

| Task | Context source | Historical Codex + GPT-5.5 | Historical Claude Code + Kimi-k2.6 | HTD runtime rerun |
| --- | --- | ---: | ---: | ---: |
| `sanitize-git-repo` | oracle-grounded critical step | reward `0.0` | reward `0.0` | reward `1.0`, `3/3` tests passed |
| `sanitize-git-repo` | oracle-free joint-failure diagnosis | reward `0.0` | reward `0.0` | reward `1.0`, `3/3` tests passed |
| `filter-js-from-html` | oracle-grounded critical step | reward `0.0` | reward `0.0` | reward `1.0`, `2/2` tests passed |
| `filter-js-from-html` | oracle-free shared-failure diagnosis | reward `0.0` | reward `0.0` | reward `1.0`, `2/2` tests passed |

These are mechanism checks, not final held-out generalization claims. The
benchmark work is moving toward held-out task matrices.

## Experiment Material

| Material | Location | Notes |
| --- | --- | --- |
| ICL baseline design and runner scripts | [`experiments/harbor_icl_baseline/`](experiments/harbor_icl_baseline/) | Fairness protocol for comparing against random, raw-trace, outcome-only, prompt-filtered, and Meta-Harness-style baselines. |
| Query-optimize raw-log bundle | [`docs/blog/raw_logs/blog_raw_logs/`](docs/blog/raw_logs/blog_raw_logs/) | Prompts, teacher cards, task variants, raw Harbor runs, and checksums. |
| Meta-Harness-style Harbor comparison | `harbor/runs/` and [`docs/blog/raw_logs/meta-harness/`](docs/blog/raw_logs/meta-harness/) | Includes small changed-harness and injection comparisons when present. |
| Kimi-Code Terminal-Bench sweep | [`docs/case-studies/kimi-code-tb21-metaharness-sweep-2026-06-10/`](docs/case-studies/kimi-code-tb21-metaharness-sweep-2026-06-10/) | Reports, metrics, raw-log archives, and repair briefs. |
| Raw Kimi agent sessions | `artifacts/kimi-session-records-usage-20260611/` | Archived wire records plus token summaries when present locally. |

Raw and generated research material is intentionally kept outside the core
package so the reusable library remains small while the evidence remains
auditable.

## Harbor And Harness Workflows

List locally discoverable harnesses:

```bash
harness-trajdebug harnesses
```

List Harbor-compatible tasks:

```bash
harness-trajdebug harbor-tasks \
  --root /Volumes/SSD/terminal-bench-harbor/harbor/datasets/terminal-bench-2.1-proxy/tasks \
  --limit 5
```

Import and diagnose a Harbor run:

```bash
harness-trajdebug harbor-import \
  --run /path/to/harbor/run \
  --output-dir artifacts/normalized-harbor \
  --diagnose
```

Export a Harbor run into the local ATIF trajectory viewer:

```bash
harness-trajdebug atif-viewer-export \
  --run /path/to/harbor/run \
  --viewer-root /path/to/ATIF-trajectory-viewer \
  --label example-run \
  --diagnose
```

For a new server, start with:

```bash
bash scripts/preflight.sh
```

Then follow [`AGENT_MIGRATION_RUNBOOK.md`](AGENT_MIGRATION_RUNBOOK.md) for the
full migration, Harbor run, diagnosis, repair, and viewer-export workflow.

## Harbor ICL Baseline

The baseline suite compares random, outcome-only, raw-trace, prompt-filtered,
and Harness-TrajecDebug debug-card context variants. The full design lives in
[`experiments/harbor_icl_baseline/README.md`](experiments/harbor_icl_baseline/README.md);
the fairness boundary lives in
[`experiments/harbor_icl_baseline/fairness_protocol.md`](experiments/harbor_icl_baseline/fairness_protocol.md).

Common entry points:

```bash
scripts/build_icl_task_matrix.py
scripts/build_joint_failure_matrix.py
scripts/run_daily_icl_mechanism.sh \
  --task gcode-to-text \
  --context-variant debug_action \
  --verifier-timeout 300
```

Daily canaries separate mechanism health from model quality. No-model checks
exercise artifact closure and runtime injection paths; real model reward
benchmarking should wait until endpoint preflight and verifier readiness are
healthy.

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

The parser also understands simple `toolCalls`, `reasoning`, nested string
fields from common trace viewers, ATIF `trajectory.json`, and Codex-style JSONL
streams when imported through the Harbor adapter.

## Development

Run the test suite:

```bash
make test
make examples
```

Or run the underlying checks directly:

```bash
python3 -m unittest discover -s tests
python3 -m py_compile src/harness_trajecdebug/*.py
```

Run the Vercel demo locally or deploy it with:

```bash
npx vercel --prod
```

Then verify the cloud API:

```bash
curl https://your-deployment-url.vercel.app/api/diagnose?example=all
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

Implemented capabilities:

- rule-based reference/state/commitment parser,
- failure taxonomy and critical-step selector,
- harness inventory for Codex, Claude Code, and Kimi routes,
- Harbor-compatible task discovery,
- Harbor run import for Claude Code ATIF traces and Codex JSONL traces,
- ATIF trajectory viewer local-bundle export for Harbor runs,
- bundled train-fasttext and cancel-async-tasks examples,
- Vercel demo API that runs diagnosis on example traces,
- runtime ICL smoke tests and closure checks.

Next milestones:

- broader adapters for common harness trace formats,
- Harbor-compatible dataset adapters beyond Terminal-Bench, such as SWE-bench Pro,
- reusable plugin packaging for third-party harnesses,
- held-out ICL data selection benchmark against random, outcome-only,
  prompt-filtered, and raw-trace retrieval baselines.
