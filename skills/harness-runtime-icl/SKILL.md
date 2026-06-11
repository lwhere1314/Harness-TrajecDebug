---
name: harness-runtime-icl
description: Run Harness-TrajecDebug runtime in-context-learning injection for Harbor or Terminal-Bench tasks. Use when a user asks to run or design Debug-Action cards, td_full/prelude/sdk_live/hooks_live injection, Claude Code plus Kimi experiments, no-TD versus with-TD comparisons, or to separate ICL context selection from Meta-Harness workflow changes.
---

# Harness Runtime ICL

Use this skill to run or design Harness-TrajecDebug runtime in-context-learning
experiments. The core job is to turn prior trajectory evidence into bounded,
task-matched context, inject it at the right point in an agent run, and preserve
enough raw evidence to compare no-TD and with-TD fairly.

## Decision Tree

1. If the user wants a full sweep or exact pass-rate number, use batch-compatible
   `prelude` injection first. It is slower than pure no-TD, but avoids live SDK
   overhead and is resumable.
2. If the user wants a case study, a failed-case repair, or proof that the hint
   changed the key path, use `sdk_live` or `hooks_live` so the Debug-Action card
   arrives at a concrete tool boundary such as first risky `Bash`.
3. If the goal is data selection for small-model ICL, compare at least these
   conditions on the same task/model/harness/environment: `no_icl`,
   `outcome_only`, `raw_trace` or `prompt_filtered`, and `debug_action` or
   `td_full`.
4. If the user compares against Meta-Harness, keep the claim separate:
   Meta-Harness changes or searches harness/workflow; Harness-TrajecDebug keeps
   the task harness/verifier fixed and changes selected runtime context.

## Inputs And Outputs

Minimum inputs:

- Task id and harness family, for example `cancel-async-tasks`, `query-optimize`,
  Harbor, or Terminal-Bench 2.1.
- Target agent/model and endpoint profile, for example Claude Code plus
  Kimi-k2.6.
- A no-TD baseline run or known failing trace.
- A context card source, usually
  `runs/harbor_icl_baseline/teacher_cards/<task>/td_full.md`, a Debug-Action
  card, or a human/Codex-in-the-loop critical-step note.

Required outputs:

- Agent trace, Claude Code session stream, verifier output, reward file, copied
  `/app` artifacts, and controller logs if live injection is used.
- A small summary with task, model, injection mode, context variant, reward,
  artifact closure, injection trigger, and whether the row is valid or
  infrastructure-invalid.
- For blog/report claims, preserve raw logs and link line-level evidence.

## Card Selection

Prefer cards in this order:

1. `debug_action`: a task-matched card with a concrete next action, verified
   artifact path or patch, closure check, and stop rule.
2. `td_full`: reference-state-commitment diagnosis, failure pattern, and repair
   route distilled from a trajectory.
3. `raw_trace`: full or summarized teacher trace only when a compact action card
   is unavailable.
4. `outcome_only`: use as a baseline, not as the main method.

Before injection, check that the card matches the current task contract,
artifact path, verifier semantics, and environment. If it includes a ready
artifact route, make the first recommended action cheap and concrete:
materialize the artifact, run the narrow verifier or closure check, then stop
instead of recomputing the whole solution.

For V1, be explicit about automation boundaries. Reward-1 teacher cards can be
collected mostly with scripts because the verifier gives an executable positive
label. Failed-run critical cards are still human/Codex-in-the-loop unless the
project has an explicit LLM judge or rule-based extractor wired into the run.
Do not imply that critical-step extraction is fully automatic when it was
written from manual trace review.

## Injection Modes

Use `prelude` for full TB2.1 sweeps and first-pass comparisons. It injects the
card before the agent starts, is batch-compatible, and works with the wrapper:

```bash
python3 scripts/run_tb21_full_td_batch.py \
  --run-name tb21-kimi-k26-with-td-YYYYMMDD \
  --context-variant td_full \
  --inject-mode prelude \
  --model kimi-k2.6 \
  --min-concurrency 1 \
  --max-concurrency 1
```

Use `sdk_live` or `hooks_live` for runtime repair evidence. The canonical
pattern from the query-optimize case is:

```text
agent reads task files
agent requests first decisive Bash inspection
PreToolUse fires with already_injected=false
Debug-Action card is attached through additionalContext
tool result returns
next reasoning starts from the card and teacher artifact
```

A good live trigger is the earliest boundary after the agent has enough task
context and before it commits to an expensive or wrong route. Common triggers
are first schema inspection, first compile/test loop, first package install,
first long training command, or first artifact promotion. The trigger should
prevent route selection drift, not merely comment on a failure after it happens.

## Running Baselines

Use no-TD and with-TD runs with the same task list, model, endpoint, image,
timeouts, and artifact export settings. For a single task:

```bash
python3 scripts/run_tb21_full_td_batch.py \
  --task TASK_ID \
  --run-name tb21-kimi-k26-with-td-canary \
  --context-variant td_full \
  --inject-mode prelude \
  --model kimi-k2.6 \
  --force-rerun
```

For Harbor case studies, prefer the existing Harbor runner and
`harness_trajecdebug.experiments.dynamic_icl_agent:DynamicIclClaudeCode`.
Inspect the current repository scripts before inventing a new runner.

## Slow-Run Triage

Before blaming the model, check infrastructure:

- Architecture: an amd64 image needs `claude-linux-x64`; an arm64 image needs
  `claude-linux-arm64`. A wrong binary can look like an agent failure.
- Build versus run: if task setup is slow, pre-pull or reuse official prebuilt
  images and mark build timeouts as infrastructure-invalid until rerun.
- QEMU: avoid accidental emulation for full sweeps; it can cause
  agentRunTimeout and misleading failures.
- Heavy tasks: ML training, Caffe builds, C4 reshards, and large compiles may
  dominate wall time. Run them sequentially, preserve logs, and resume instead
  of restarting the whole sweep.
- Stale runs: kill only targeted old screens/processes. Avoid broad kill
  patterns that also match monitoring commands.

## Evidence Checklist

For each claimed improvement, collect:

- no-TD reward and failure footprint.
- with-TD reward and verifier output.
- injected card path and character count.
- injection mode and trigger, such as `PreToolUse:Bash`.
- session lines showing the injection arrived before the route choice.
- artifact closure evidence, for example `/app/sol.sql` or `/app/model.bin`.
- a note on whether the card was script-derived, reward-1 teacher-derived, or
  human/Codex-in-the-loop failed-run diagnosis.

Report exact counts only after parsing `result_summary.reward` or verifier
reward files, not just the top-level state row. Some batch state files do not
store reward at the top level.
