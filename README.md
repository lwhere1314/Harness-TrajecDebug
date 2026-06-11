# Harness-TrajecDebug

Harness-TrajecDebug is a trace diagnosis and trajectory-selection framework for
terminal agents. It turns raw pass/fail benchmark runs into process-level
records: reference objects, observed state, decision evidence, failure patterns,
critical steps, repair hints, and ICL data-quality signals.

The project is intentionally conservative. It only emits a failure pattern when
there is concrete trace evidence and a final verifier footprint.

The product direction is a harness-agnostic plugin layer, not a replacement
harness. Harbor, Terminal-Bench, Meta-Harness-style runners, Claude Code, Codex,
and Kimi Code should be able to call the same TrajectoryDebug interface to run
experiments, preserve raw traces, diagnose failures, select or synthesize
Debug-Action cards, rerun with runtime ICL, and export a reproducible evidence
bundle.

## Contents

- A reusable diagnosis core for terminal-agent traces under
  `src/harness_trajecdebug/`.
- A CLI for local diagnosis, Harbor task discovery, Harbor run import, harness
  inventory, and ATIF viewer export.
- Cross-agent skill/plugin shims under `plugins/harness-trajdebug-agent/`,
  `.claude/skills/`, `.agents/skills/`, and `.kimi-code/skills/` so Claude
  Code, Codex, and Kimi Code can invoke the same workflows.
- Minimal normalized examples under `examples/traces/` and
  `examples/diagnoses/`.
- Research notes under `docs/`, including the framework, failure taxonomy,
  integrations, roadmap, Meta-Harness comparison, and blog-style case studies.
- ICL baseline experiments under `experiments/harbor_icl_baseline/`.
- Raw experiment material and run archives under `harbor/runs/`, `runs/`,
  `artifacts/`, `docs/blog/raw_logs/`, and `docs/case-studies/` when present
  locally.
- A lightweight Vercel demo in `index.html`, `styles.css`, `app.js`, and
  `api/diagnose.py`.

## Quick Start

Install the package in editable mode:

```bash
python3 -m pip install -e .
```

Run the bundled near-miss diagnosis:

```bash
harness-trajdebug diagnose \
  --trace examples/traces/train-fasttext-kimi-k26-minimal.json \
  --run-id train-fasttext-kimi-k26-minimal \
  --output examples/diagnoses/train-fasttext-kimi-k26-diagnosis.json
```

Run the passing example:

```bash
harness-trajdebug diagnose \
  --trace examples/traces/cancel-async-tasks-passed-minimal.json \
  --run-id cancel-async-tasks-passed-minimal \
  --output examples/diagnoses/cancel-async-tasks-diagnosis.json
```

The longer command alias `harness-trajecdebug` is also available.

## How It Works

Harness-TrajecDebug reads the same trace through three views:

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

The first target application is ICL data selection for smaller terminal agents.
Instead of feeding small models random successful traces or outcome-only traces,
the framework selects trajectories with reusable process signal:

- successful traces with verifier-aligned artifact closure,
- near-miss traces with clear critical-step evidence,
- contrastive traces where a bad branch and a repairable decision are visible,
- traces that demonstrate planning, validation, recovery, and state checking.

SFT, preference learning, process rewards, and RL curricula are later downstream
uses. The current milestone is a reliable trace-to-ICL-example pipeline.

## Documentation Map

| File | What it is for |
| --- | --- |
| `docs/framework.md` | Reference/state/commitment workflow and ICL selection logic. |
| `docs/failure-taxonomy.md` | Failure routing tree, pattern definitions, and repair levers. |
| `docs/integrations.md` | Codex, Claude Code, Kimi-Code, Harbor, and ATIF viewer adapters. |
| `docs/trajectorydebug-hint-and-icl-flow.md` | TD hint-generation and runtime ICL injection diagrams. |
| `docs/related-work-metaharness.md` | Positioning against Meta-Harness and proposed comparison experiments. |
| `docs/roadmap.md` | Current progress, planned experiments, and longer-term training uses. |
| `docs/closed-loop-case-summary.md` | Current closed-loop case summary. |
| `docs/candidate-search-status.md` | Accepted/rejected candidate status and endpoint notes. |
| `AGENT_MIGRATION_RUNBOOK.md` | End-to-end server migration and Harbor -> diagnosis -> repair -> viewer workflow. |

Blog-style case studies:

- `docs/blog/trajectorydebug-algorithm-flow.md`
- `docs/blog/query-optimize-runtime-debug-action.md`
- `docs/blog/sanitize-git-repo-joint-failure-lifting.md`
- `docs/blog/filter-js-from-html-clean-preservation.md`
- `docs/blog/raman-fitting-axis-critical-step.md`
- `docs/blog/pytorch-model-recovery-forward-api-critical-step.md`

Raw and generated research material is intentionally kept outside the core
package:

- `harbor/runs/` contains small checked-in Harbor run examples.
- `docs/blog/raw_logs/blog_raw_logs/` contains blog-facing raw trace bundles,
  prompts, teacher cards, task variants, checksums, and Harbor run logs.
- `docs/case-studies/` contains case-study reports and reproducibility
  material.
- `artifacts/harbor-runs/` and `runs/harbor_icl_baseline/` are local result
  pools used for sweeps and canaries when present.
- `artifacts/kimi-session-records-usage-20260611/` contains archived Kimi wire
  records and token-usage manifests when present locally.

## Meta-Harness Relationship

This repository follows the same high-level bet as
[Meta-Harness](https://github.com/stanford-iris-lab/meta-harness): final reward
is too sparse, and raw execution traces contain useful signal. The optimization
layer is different.

| Dimension | Meta-Harness | Harness-TrajecDebug |
| --- | --- | --- |
| Main objective | Search for better harness code | Select better trajectory data for ICL |
| Unit optimized | Candidate harness implementation | Trace, trace segment, or contrastive pair |
| Primary output | New task-specific harness | Diagnosed trace record and data-quality signal |
| Intervention time | Before and during the next run | After a run, before future ICL runs |
| Trace use | Proposer reads raw history to write harness code | Diagnosis labels critical steps and reusable examples |

The projects are complementary. Meta-Harness can discover a harness-level
intervention, such as deterministic environment bootstrapping.
Harness-TrajecDebug can turn the resulting traces into labeled examples or use
its diagnostic labels as a compact index for future harness search.

## Current Mechanism Results

The current runtime-ICL canaries show that process-aware Debug-Trajectory cards
can repair failures that outcome-only context does not fix.

On `query-optimize`, Claude Code + `kimi-k2.6` produced a semantically correct
SQL rewrite that still failed the official runtime gate. A same-task controlled
canary compared:

| Condition | Runtime injection | Result |
| --- | --- | --- |
| `no_icl` | none | reward `0.0`; solution slower than the official golden query |
| `outcome_only + sdk_live` | teacher outcome summary only | reward `0.0`; injection happened, but the agent rebuilt the insufficient route |
| `debug_action + sdk_live` | Debug-Trajectory repair card with `/app/sol.sql` | reward `1.0`; the agent materialized the teacher artifact and passed 6/6 verifier tests |

The stronger current signal is joint-failure lifting: failed traces can still be
useful ICL data when their process evidence identifies the critical decision
boundary.

| Task | Context source | Historical Codex + GPT-5.5 | Historical Claude Code + Kimi-k2.6 | HTD runtime rerun |
| --- | --- | ---: | ---: | ---: |
| `sanitize-git-repo` | oracle-grounded critical step | reward `0.0` | reward `0.0` | reward `1.0`, `3/3` tests passed |
| `sanitize-git-repo` | oracle-free joint-failure diagnosis | reward `0.0` | reward `0.0` | reward `1.0`, `3/3` tests passed |
| `filter-js-from-html` | oracle-grounded critical step | reward `0.0` | reward `0.0` | reward `1.0`, `2/2` tests passed |
| `filter-js-from-html` | oracle-free shared-failure diagnosis | reward `0.0` | reward `0.0` | reward `1.0`, `2/2` tests passed |

This is not yet the final held-out generalization claim. It is a mechanism
check showing that critical-step examples can correct interactive reruns, while
the benchmark work moves toward held-out task matrices.

## Current Experiment Material

| Material | Location | Notes |
| --- | --- | --- |
| ICL baseline design and runner scripts | `experiments/harbor_icl_baseline/` | Includes the fairness protocol for comparing against Meta-Harness-style changed-harness baselines. |
| Query-optimize raw-log bundle | `docs/blog/raw_logs/blog_raw_logs/` | Contains prompts, teacher cards, task variants, raw Harbor runs, and checksums. |
| Meta-Harness-style Harbor comparison | `harbor/runs/` | `cancel-async-tasks` has a small 4x comparison: with Meta-Harness-style injection passed 4/4, without it passed 0/4. |
| Kimi-Code Terminal-Bench sweep | `artifacts/harbor-runs/` | Local sweep result pool with `with-metaharness` and `without-metaharness` variants when present. |
| Raw Kimi agent sessions | `artifacts/kimi-session-records-usage-20260611/` | Archived `wire.jsonl` session records plus token summaries when present locally. |

These are early engineering artifacts, not a paper-ready benchmark claim. They
are useful because they preserve prompts, trajectories, verifier output, reward
files, and failure footprints for later diagnosis and ICL selection.

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
  --run /Volumes/SSD/terminal-bench-harbor/harbor/runs/tb21-train-fasttext-claude-code-kimi-k26 \
  --output-dir artifacts/normalized-harbor \
  --diagnose
```

Export a Harbor run into the local ATIF trajectory viewer:

```bash
harness-trajdebug atif-viewer-export \
  --run /path/to/harbor/runs/swebenchpro-fix-ansible-invalid-hosts-claude-code-kimi-k26 \
  --viewer-root /Users/hugo/Documents/terminal-bench-3.0-PR/ATIF-trajectory-viewer \
  --label swebenchpro-fix-ansible-invalid-hosts-claude-code-kimi-k26 \
  --diagnose
```

For a new server, start with:

```bash
bash scripts/preflight.sh
```

Then follow `AGENT_MIGRATION_RUNBOOK.md` for the full migration, Harbor run,
diagnosis, repair, and viewer-export workflow.

## Harbor ICL Baseline

The baseline suite compares random/outcome-only/raw-trace/prompt-filtered
selection against Harness-TrajecDebug debug cards and runtime injection. The
full design lives in `experiments/harbor_icl_baseline/README.md`; the fairness
boundary lives in `experiments/harbor_icl_baseline/fairness_protocol.md`.

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
- initial unit tests and GitHub CI.

Next milestones:

- broader adapters for common harness trace formats,
- Harbor-compatible dataset adapters beyond Terminal-Bench, such as SWE-bench Pro,
- Harness x Model experiment runner,
- ICL data selection benchmark against random, outcome-only, prompt-filtered,
  and raw-trace retrieval baselines.
