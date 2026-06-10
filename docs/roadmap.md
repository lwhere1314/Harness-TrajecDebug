# Roadmap

Harness-TrajecDebug is currently positioned as a **trace-to-ICL-example
selection framework**. Training-time uses such as SFT, RL, DPO, or process reward
modeling are planned later; the first milestone is to prove that better
trajectory selection improves in-context learning for smaller terminal agents.

## Current Progress

- Built a rule-based diagnosis core that extracts reference, state, and
  commitment views from terminal-agent traces.
- Implemented an initial failure taxonomy:
  - `thin-margin promotion`
  - `validation mismatch`
  - `compact-frontier search gap`
  - `accuracy objective gap`
  - `final artifact validation`
  - `tool/API loop`
  - `budget debt loop`
  - `no critical failure detected`
- Added a CLI: `harness-trajdebug diagnose`.
- Added integration commands for:
  - local harness discovery across Codex, Claude Code, and Kimi routes,
  - Harbor-compatible task discovery,
  - Harbor run import from Claude Code ATIF traces and Codex JSONL traces.
- Added bundled examples for:
  - `train-fasttext` near miss,
  - `cancel-async-tasks` passed trajectory.
- Added unit tests and GitHub CI.
- Added a Vercel demo API that runs the diagnosis engine on example traces.

## Near-Term To-Do

### 1. Harness Compatibility

Build adapters for trace formats produced by common agent harnesses:

- Terminal-Bench / Harbor-style JSON traces (initial import path done),
- Claude Code / Codex / Kimi-Code terminal-agent traces (initial ATIF/JSONL path done),
- generic tool-call logs with `steps`, `toolCalls`, `observation`, and
  `verifierLog`,
- auto-code-bench-style coding task traces when available.

The adapter output should be a normalized run record:

```text
task spec
environment / sandbox metadata
agent messages
tool calls
observations
artifact states
verifier output
reward / pass-fail signal
```

### 2. Harbor Task Observability

Add first-class Harbor-style task support:

- parse task spec, tests, oracle/reference solution, and verifier output
  (initial task/trial scanner done),
- preserve container artifacts and command outputs,
- reconstruct artifact lifecycle and metric changes,
- expose task-level dashboards for comparing harnesses and models.

This should make Harbor tasks observable beyond final reward.

### 3. Harness x Model Experiment Matrix

Run the same Harbor task set across multiple harness/model combinations:

```text
Harnesses: Claude Code, Codex, Kimi-Code, custom terminal harness
Models: frontier models, mid-size models, small terminal-agent candidates
Tasks: Harbor / Terminal-Bench / auto-code-bench-style tasks
```

For every run, collect:

- pass/fail reward,
- verifier output,
- token and latency cost,
- tool-call count,
- failure pattern,
- critical step,
- trajectory quality score.

### 4. ICL Data Selection

Use Harness-TrajecDebug to select examples for small-model in-context learning.

Candidate data buckets:

- **Clean positives**: successful traces with strong artifact closure and
  verifier-aligned validation.
- **Hard negatives**: near-miss traces with clear critical-step evidence.
- **Contrastive pairs**: trajectories showing a bad commitment and a repairable
  alternative.
- **Recovery traces**: traces where the agent detects a local failure and
  recovers without terminal footprint.

Filtering rules should remove:

- noisy tool loops without reusable strategy,
- traces where local validation is not aligned with official verifier semantics,
- successes that pass by accident without useful process signal,
- failures whose root cause is too diffuse to teach a small model.

## Planned Experiments

### Experiment A: Diagnosis Validity

Question: Does the taxonomy match human judgment?

Dataset:

- sampled Harbor / Terminal-Bench / auto-code-bench-style traces,
- multiple harness/model combinations,
- both passed and failed runs.

Metrics:

- failure pattern classification agreement,
- critical-step localization accuracy,
- evidence quote quality,
- repair hint usefulness.

### Experiment B: ICL Selection Quality

Question: Does process-aware trace selection improve small-agent ICL?

Compare four ICL banks:

1. **Random trace bank**: randomly sampled trajectories.
2. **Outcome-only bank**: successful traces selected only by pass/fail.
3. **Prompt-filtered bank**: large model selects examples by reading traces and
   writing a free-form recommendation.
4. **Harness-TrajecDebug bank**: examples selected by failure taxonomy,
   critical-step evidence, verifier alignment, and trajectory quality score.

Evaluation:

- run the same small model on held-out Harbor tasks,
- measure task success rate, verifier pass rate, tool-call count, token cost,
  recovery rate, and artifact closure rate.

Hypothesis:

Harness-TrajecDebug-selected examples should outperform random, outcome-only,
and prompt-filtered baselines because they preserve process-level learning
signals rather than only final reward.

### Experiment C: Cross-Harness Generalization

Question: Do examples selected from one harness help another harness/model
combination?

Design:

- select ICL examples from high-quality traces generated by stronger models,
- use them to guide smaller models in a different harness,
- test whether critical-step and artifact-closure behavior transfers.

### Experiment D: Later Training Extensions

After the ICL pipeline is validated, the same selected records can be converted
into:

- SFT records,
- preference pairs,
- process reward labels,
- RL curriculum buckets.

These are intentionally later-stage goals. The immediate deliverable is a
working ICL data selection benchmark.

## Positioning Summary

Harness-TrajecDebug is not only a debugging UI. Its main role is to turn raw
agent trajectories into **teachable process data**:

```text
raw traces
  -> normalized harness records
  -> diagnosis and failure taxonomy
  -> critical-step evidence
  -> trajectory quality score
  -> ICL example bank for small terminal agents
```
