---
name: trajectorydebug
description: Diagnose Harbor, Terminal-Bench, Claude Code, Codex, or Kimi Code agent trajectories with Harness-TrajecDebug; use for critical-step localization, Debug-Action card selection, no-TD versus with-TD comparison, runtime ICL canaries, and ATIF viewer export.
type: prompt
whenToUse: When the user asks to debug a terminal-agent trajectory, explain a failed run, compare harness/framework results, select or inject a trajectory-debug card, or make Claude Code, Codex, and Kimi Code use Harness-TrajecDebug.
---

# TrajectoryDebug Agent Skill

Use Harness-TrajecDebug as the evidence layer for terminal-agent runs. The
goal is not to guess from final reward alone. Always preserve or reconstruct:

- task id and harness/model,
- raw trajectory or session stream,
- verifier stdout/stderr and reward file,
- artifact paths and closure checks,
- diagnosis JSON, Debug-Action card, and rerun summary.

## First Choice Commands

Prefer the repository CLI. From the Harness-TrajecDebug repo:

```bash
harness-trajdebug diagnose --trace TRACE_JSON --run-id RUN_ID --output DIAGNOSIS_JSON
harness-trajdebug harbor-import --run HARBOR_RUN --output-dir artifacts/normalized-harbor --diagnose
harness-trajdebug atif-viewer-export --run HARBOR_RUN --viewer-root ATIF_VIEWER_ROOT --diagnose
```

If this skill is loaded from the plugin directory, the helper script may also
be available:

```bash
plugins/harness-trajdebug-agent/scripts/htd-agent doctor
plugins/harness-trajdebug-agent/scripts/htd-agent diagnose --trace TRACE_JSON --run-id RUN_ID
plugins/harness-trajdebug-agent/scripts/htd-agent harbor-import --run HARBOR_RUN --output-dir artifacts/normalized-harbor --diagnose
```

If the helper path is unavailable, call `harness-trajdebug` directly. If the
CLI is missing, run `python3 -m pip install -e .` from the repo root.

## Diagnosis Workflow

1. Find the run material: Harbor run directory, ATIF `trajectory.json`, Codex
   JSONL stream, Kimi wire/session record, or a normalized trace JSON.
2. Join the agent trace with verifier output whenever possible. For Harbor,
   prefer `harbor-import --diagnose` over direct JSONL diagnosis.
3. Read the diagnosis fields: `outcome`, `final_failure`,
   `failure_patterns`, `critical_step`, and `repair_hint`.
4. Explain the result with concrete evidence. Do not claim a pattern unless
   there is a verifier footprint and trace evidence.
5. For reruns, choose the smallest context intervention that matches the
   diagnosis: `debug_action` first, then `td_full`, then `raw_trace`; use
   `outcome_only` only as a baseline.

## Runtime ICL Workflow

Use this when the user asks to repair a failed task, run a canary, or compare
no-TD against with-TD.

1. Keep task, model, harness, image, timeout, verifier, and endpoint profile
   fixed across conditions.
2. For broad sweeps, prefer `prelude` injection because it is batch-friendly.
3. For case studies, prefer `sdk_live` or `hooks_live` so the card lands at a
   concrete boundary such as first decisive `Bash`, schema inspection, compile
   loop, package install, long training command, or artifact promotion.
4. Record injected card path, character count, injection mode, trigger, reward,
   verifier output, and artifact closure.
5. Separate infrastructure-invalid rows from model/verifier failures.

Common entry points:

```bash
scripts/build_icl_task_matrix.py
scripts/build_joint_failure_matrix.py
scripts/run_daily_icl_mechanism.sh --task TASK --context-variant debug_action --verifier-timeout 300
scripts/run_daily_icl_canary.sh --task TASK --model kimi-k2.6 --endpoint-profile auto --inject-mode sdk_live --context-variant debug_action
```

Read `experiments/harbor_icl_baseline/README.md` for the full baseline suite
and `experiments/harbor_icl_baseline/fairness_protocol.md` before making claims
against Meta-Harness-style changed-harness baselines.

## Report Shape

End with a compact, evidence-linked summary:

```text
task:
harness/model:
baseline:
with-TD:
failure pattern:
critical step:
card/injection:
verifier evidence:
artifact closure:
validity:
next action:
```

If comparing with Meta-Harness, keep the distinction explicit:
Meta-Harness changes/searches harness workflow; Harness-TrajecDebug keeps the
task harness/verifier fixed and changes selected runtime context or diagnostic
evidence.
