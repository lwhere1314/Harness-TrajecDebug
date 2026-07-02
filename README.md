# Harness-TrajecDebug

Repository: <https://github.com/lwhere1314/Harness-TrajecDebug>

Harness-TrajecDebug is a harness-agnostic trajectory debugging layer for
terminal agents. It reads raw agent traces plus verifier output, localizes the
critical failure step, and turns that evidence into Debug-Action cards that can
be injected into future runs.

It is not another benchmark harness. Harbor, Terminal-Bench, Meta-Harness-style
runners, Claude Code, Codex, and Kimi Code keep owning task execution; this
project owns trace normalization, failure diagnosis, repair-card selection,
runtime injection, and evidence export.

## Start Here

| Need | Entry |
| --- | --- |
| See the end-to-end story | [`demo/README.md`](demo/README.md) |
| Run the compact demo | `HTD_DEMO_PAUSE=1 plugins/harness-trajdebug-agent/scripts/htd-agent demo query-optimize --recorded` |
| Use the agent SKILL | [`plugins/harness-trajdebug-agent/skills/trajectorydebug/SKILL.md`](plugins/harness-trajdebug-agent/skills/trajectorydebug/SKILL.md) |
| Run no-TD versus with-TD canaries | [`plugins/harness-trajdebug-agent/skills/harness-runtime-icl/SKILL.md`](plugins/harness-trajdebug-agent/skills/harness-runtime-icl/SKILL.md) |
| Install Claude/Codex/Kimi skill shims | [`docs/agent-plugin.md`](docs/agent-plugin.md) |
| Read case studies and evidence bundles | [`docs/case-studies/README.md`](docs/case-studies/README.md) |
| Understand the diagnosis model | [`docs/framework.md`](docs/framework.md) and [`docs/failure-taxonomy.md`](docs/failure-taxonomy.md) |

## What It Does

Harness-TrajecDebug follows one trace through a conservative evidence pipeline:

```text
trace + verifier output
  -> reference view
  -> state view
  -> commitment / decision evidence
  -> failure pattern
  -> critical step
  -> repair hint
  -> Debug-Action card / runtime ICL signal
```

The framework only emits a concrete failure pattern when the trace contains
process evidence and the final verifier footprint supports the diagnosis.

Current primary use cases:

- diagnose Harbor, Terminal-Bench, Claude Code, Codex, and Kimi Code runs,
- preserve raw traces, verifier logs, rewards, artifacts, and diagnosis JSON,
- generate or select Debug-Action cards from critical-step evidence,
- compare no-TD versus with-TD runtime ICL runs,
- export reproducible bundles for reports and case studies.

## Quick Demo

Install the package, then run the recorded `query-optimize` demo:

```bash
python3 -m pip install -e .
HTD_DEMO_PAUSE=1 plugins/harness-trajdebug-agent/scripts/htd-agent demo query-optimize --recorded
```

The demo shows:

```text
first agent run fails
-> Harness-TrajecDebug imports the trace
-> critical step is localized
-> a Debug-Action card is selected/generated
-> second run injects the card at PreToolUse(Bash)
-> verifier passes
```

For a live second attempt with a failure-derived card:

```bash
HTD_DEMO_PAUSE=1 HTD_DEMO_NO_FORCE_BUILD=1 HTD_DEMO_KEEP_ENVIRONMENT=1 \
  plugins/harness-trajdebug-agent/scripts/htd-agent demo query-optimize --live-fail-teacher
```

Recording notes, expected terminal output, Docker warm-run policy, and
agent-specific smoke checks are in [`demo/README.md`](demo/README.md).

## Agent Skill Entrances

The canonical skill source lives under the plugin package:

| Skill | Purpose |
| --- | --- |
| [`trajectorydebug`](plugins/harness-trajdebug-agent/skills/trajectorydebug/SKILL.md) | Diagnose existing runs, localize failures, review reward/verifier evidence, select next actions. |
| [`harness-runtime-icl`](plugins/harness-trajdebug-agent/skills/harness-runtime-icl/SKILL.md) | Run runtime ICL canaries and compare no-TD versus with-TD evidence. |

Install project-local shims for Claude Code, Codex, and Kimi Code:

```bash
python3 scripts/install_agent_plugin.py
```

Installed shim locations:

| Surface | Local entry |
| --- | --- |
| Claude Code | [`.claude/skills/trajectorydebug/SKILL.md`](.claude/skills/trajectorydebug/SKILL.md), [`.claude/skills/harness-runtime-icl/SKILL.md`](.claude/skills/harness-runtime-icl/SKILL.md) |
| Codex / agents | [`.agents/skills/trajectorydebug/SKILL.md`](.agents/skills/trajectorydebug/SKILL.md), [`.agents/skills/harness-runtime-icl/SKILL.md`](.agents/skills/harness-runtime-icl/SKILL.md) |
| Kimi Code | [`.kimi-code/skills/trajectorydebug/SKILL.md`](.kimi-code/skills/trajectorydebug/SKILL.md), [`.kimi-code/skills/harness-runtime-icl/SKILL.md`](.kimi-code/skills/harness-runtime-icl/SKILL.md) |
| Codex plugin source | [`plugins/harness-trajdebug-agent/.codex-plugin/plugin.json`](plugins/harness-trajdebug-agent/.codex-plugin/plugin.json) |
| Kimi plugin source | [`plugins/harness-trajdebug-agent/kimi.plugin.json`](plugins/harness-trajdebug-agent/kimi.plugin.json) |

Typical agent prompts:

```text
/trajectorydebug diagnose this Harbor run
/harness-runtime-icl run a no-TD versus with-TD canary
```

Full compatibility notes are in [`docs/agent-plugin.md`](docs/agent-plugin.md)
and [`docs/integrations.md`](docs/integrations.md).

## Case Studies

Use [`docs/case-studies/README.md`](docs/case-studies/README.md) as the case
study entry point. It links to the main reports, metrics, repair briefs, and
raw-log archives.

High-signal entries:

| Case | Entry |
| --- | --- |
| Query-optimize runtime Debug-Action card | [`docs/blog/query-optimize-runtime-debug-action.md`](docs/blog/query-optimize-runtime-debug-action.md) |
| Kimi Code TB2.1 Meta-Harness sweep | [`docs/case-studies/kimi-code-tb21-metaharness-sweep-2026-06-10/REPORT.md`](docs/case-studies/kimi-code-tb21-metaharness-sweep-2026-06-10/REPORT.md) |
| Cancel-async-tasks 4x reproduction | [`docs/case-studies/kimi-code-cancel-async-tasks-metaharness-2026-06-10/REPORT.md`](docs/case-studies/kimi-code-cancel-async-tasks-metaharness-2026-06-10/REPORT.md) |
| Joint-failure lifting examples | [`docs/blog/sanitize-git-repo-joint-failure-lifting.md`](docs/blog/sanitize-git-repo-joint-failure-lifting.md), [`docs/blog/filter-js-from-html-clean-preservation.md`](docs/blog/filter-js-from-html-clean-preservation.md) |
| Blog raw-log bundle | [`docs/blog/raw_logs/blog_raw_logs/README.md`](docs/blog/raw_logs/blog_raw_logs/README.md) |

## Repository Map

| Path | What lives there |
| --- | --- |
| [`src/harness_trajecdebug/`](src/harness_trajecdebug/) | Diagnosis core: parsing, adapters, failure patterns, critical-step selection. |
| [`plugins/harness-trajdebug-agent/`](plugins/harness-trajdebug-agent/) | Agent-facing plugin, skills, and `htd-agent` wrapper. |
| [`demo/`](demo/) | Top-level recorded and live demo workflow. |
| [`docs/`](docs/) | Framework docs, integrations, roadmap, case studies, and blog-style reports. |
| [`experiments/harbor_icl_baseline/`](experiments/harbor_icl_baseline/) | ICL baseline protocol and runners. |
| [`scripts/`](scripts/) | Experiment runners, preflight checks, closure checks, and batch utilities. |
| [`examples/`](examples/) | Minimal normalized traces and diagnosis outputs. |
| [`api/diagnose.py`](api/diagnose.py), [`index.html`](index.html), [`app.js`](app.js) | Lightweight Vercel demo surface. |

## CLI Quick Start

Run a bundled near-miss diagnosis:

```bash
harness-trajdebug diagnose \
  --trace examples/traces/train-fasttext-kimi-k26-minimal.json \
  --run-id train-fasttext-kimi-k26-minimal \
  --output examples/diagnoses/train-fasttext-kimi-k26-diagnosis.json
```

Import and diagnose a Harbor run:

```bash
harness-trajdebug harbor-import \
  --run /path/to/harbor/run \
  --output-dir artifacts/normalized-harbor \
  --diagnose
```

Run a runtime ICL canary through the wrapper:

```bash
plugins/harness-trajdebug-agent/scripts/htd-agent run-icl \
  --task TASK \
  --model kimi-k2.6 \
  --endpoint-profile auto \
  --context-variant debug_action \
  --inject-mode prelude \
  --dry-run
```

Check local agent/plugin readiness:

```bash
plugins/harness-trajdebug-agent/scripts/htd-agent doctor
```

## Documentation

| File | Use it for |
| --- | --- |
| [`docs/framework.md`](docs/framework.md) | Reference/state/commitment workflow and ICL selection logic. |
| [`docs/failure-taxonomy.md`](docs/failure-taxonomy.md) | Failure routing tree, pattern definitions, and repair levers. |
| [`docs/trajectorydebug-hint-and-icl-flow.md`](docs/trajectorydebug-hint-and-icl-flow.md) | TD hint generation and runtime ICL injection diagrams. |
| [`docs/interactive-icl-v1-implementation.md`](docs/interactive-icl-v1-implementation.md) | Interactive ICL implementation notes. |
| [`docs/related-work-metaharness.md`](docs/related-work-metaharness.md) | Positioning against Meta-Harness and proposed comparisons. |
| [`docs/roadmap.md`](docs/roadmap.md) | Current progress and planned experiments. |
| [`AGENT_MIGRATION_RUNBOOK.md`](AGENT_MIGRATION_RUNBOOK.md) | Server migration, Harbor run, diagnosis, repair, and viewer-export workflow. |

## Development

```bash
make test
make examples
python3 -m unittest discover -s tests
python3 -m py_compile src/harness_trajecdebug/*.py
```

Run or deploy the lightweight Vercel demo:

```bash
npx vercel --prod
curl https://your-deployment-url.vercel.app/api/diagnose?example=all
```
