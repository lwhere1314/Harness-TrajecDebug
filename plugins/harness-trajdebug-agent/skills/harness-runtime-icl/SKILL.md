---
name: harness-runtime-icl
description: Run Harness-TrajecDebug runtime in-context-learning injection for Harbor or Terminal-Bench tasks; use for Debug-Action cards, td_full/prelude/sdk_live/hooks_live injection, Claude Code plus Kimi experiments, no-TD versus with-TD comparisons, and Meta-Harness fairness boundaries.
type: prompt
whenToUse: When the user asks to run or design TD runtime ICL experiments, compare no-TD and with-TD runs, choose an injection mode, or preserve evidence for Harbor/Terminal-Bench canaries.
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

- task id and harness family, for example `cancel-async-tasks`,
  `query-optimize`, Harbor, or Terminal-Bench 2.1,
- target agent/model and endpoint profile, for example Claude Code plus
  Kimi-k2.6,
- a no-TD baseline run or known failing trace,
- a context card source, usually
  `runs/harbor_icl_baseline/teacher_cards/<task>/td_full.md`, a Debug-Action
  card, or a human/Codex-in-the-loop critical-step note.

Required outputs:

- agent trace, session stream, verifier output, reward file, copied `/app`
  artifacts, and controller logs if live injection is used,
- a small summary with task, model, injection mode, context variant, reward,
  artifact closure, injection trigger, and validity,
- for blog/report claims, raw logs and line-level evidence.

## Card Selection

Prefer cards in this order:

1. `debug_action`: concrete next action, verified artifact path or patch,
   closure check, and stop rule.
2. `td_full`: reference-state-commitment diagnosis, failure pattern, and repair
   route distilled from a trajectory.
3. `raw_trace`: full or summarized teacher trace only when a compact action card
   is unavailable.
4. `outcome_only`: baseline only, not the main method.

Before injection, check that the card matches the current task contract,
artifact path, verifier semantics, and environment. If it includes a ready
artifact route, make the first recommended action cheap and concrete:
materialize the artifact, run the narrow verifier or closure check, then stop
instead of recomputing the whole solution.

## Injection Modes

Use `prelude` for full TB2.1 sweeps and first-pass comparisons:

```bash
python3 scripts/run_tb21_full_td_batch.py \
  --run-name tb21-kimi-k26-with-td-YYYYMMDD \
  --context-variant td_full \
  --inject-mode prelude \
  --model kimi-k2.6 \
  --min-concurrency 1 \
  --max-concurrency 1
```

Use `sdk_live` or `hooks_live` for runtime repair evidence. A good live trigger
is the earliest boundary after the agent has enough task context and before it
commits to an expensive or wrong route.

For the `query-optimize` runtime Debug-Action case study, use the one-command
wrapper:

```bash
scripts/run_query_optimize_sdk_live_repro.sh runs/harbor_icl_repro_seed
```

It fixes the task, model, context variant, injection mode, SEED endpoint profile,
`PreToolUse:Bash` trigger, and live SDK timeouts used by the reproducible
canary.

When launching that long run from Codex CLI, prefer the detached launcher:

```bash
python3 scripts/launch_query_optimize_sdk_live_repro.py \
  runs/harbor_icl_repro_codex_launch
```

Codex's shell tool may clean up plain `nohup ... &` children after the tool call
returns. The detached launcher starts the Harbor runner in a new session and
writes a PID file plus a combined log path for monitoring.

## Runtime Environment Contract

Before claiming an `sdk_live` result, verify the runtime path separately from
the TD algorithm:

1. Run the local plugin doctor and endpoint preflight without printing secrets:

```bash
plugins/harness-trajdebug-agent/scripts/htd-agent doctor
bash -lc 'source ~/.bashrc; python3 scripts/check_model_endpoint.py \
  --endpoint-profile seed-coding-plan \
  --model kimi-k2.6 \
  --timeout-sec 20'
```

For Kimi Code prompt-mode smoke tests against the same SEED endpoint, use the
env-model bridge rather than editing `~/.kimi-code/config.toml`:

```bash
scripts/run_kimicode_skill_smoke.sh
```

That script maps `SEED_CODING_PLAN_BASE_URL` and `SEED_CODING_PLAN_API_KEY` to
Kimi Code's `KIMI_MODEL_BASE_URL` and `KIMI_MODEL_API_KEY`, sets
`KIMI_MODEL_PROVIDER_TYPE=anthropic`, and runs `kimi-k2.6` through the local
Kimi Code dev CLI from the repository root so project skills are discoverable.

For Codex prompt-mode runs, keep the compatibility boundary explicit:

- Supported tested path: Codex skill -> detached launcher -> Harness wrapper ->
  Claude Code SDK `sdk_live` -> `kimi-k2.6` through the SEED
  Anthropic-compatible endpoint.
- Do not treat direct `codex exec -m kimi-k2.6` as supported unless the endpoint
  exposes an OpenAI Responses-compatible wire API. A local smoke test accepted
  the custom provider config but failed during streaming before completion.

2. Treat `sdk_live` as requiring a Python-capable target container. The live
   SDK runner must be able to execute `python3 -m pip --version` before it
   starts Claude Code. If the task image lacks Python or pip, prebuild or
   prewarm the task image, or use `prelude` for batch evidence until the live
   image is prepared.
3. Pin the SDK dependency set used inside the target container. The known-good
   baseline is:

```text
claude-agent-sdk==0.1.43
mcp>=1.27.2
httpx==0.28.1
httpcore==1.0.9
```

4. For cold task images, pass a long enough SDK install timeout and agent
   timeout, for example `--sdk-live-install-timeout 900 --agent-timeout 1800`.
   The install timeout covers the in-container `claude-agent-sdk` install; the
   agent timeout must still leave room for Claude Code and verifier setup.
5. If the target container has flaky PyPI access, use a prebuilt wheelhouse or
   image layer rather than relying on live `pip install`. Do not classify
   failures such as missing Python, pip resolver backtracking, old `mcp`
   imports, or package download timeouts as TD algorithm failures.
6. For `sdk_live` evidence, preserve `sdk-live-events.jsonl`,
   `sdk-install.log`, `agent/command-*/stdout.txt`, and the Harbor runner log.
   A valid live run should show SDK setup, Claude Code init, at least one
   injection event, and verifier output in the same trial directory.

If these conditions are not met, report the run as an environment/setup failure
and either fix the image/dependency path or switch to `prelude`/`tool` mode for
the immediate experiment.

## Evidence Checklist

For each claimed improvement, collect:

- no-TD reward and failure footprint,
- with-TD reward and verifier output,
- injected card path and character count,
- injection mode and trigger, such as `PreToolUse:Bash`,
- session lines showing the injection arrived before the route choice,
- artifact closure evidence, for example `/app/sol.sql` or `/app/model.bin`,
- whether the card was script-derived, reward-1 teacher-derived, or
  human/Codex-in-the-loop failed-run diagnosis.
