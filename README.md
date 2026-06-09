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
comparison with Meta-Harness.

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
