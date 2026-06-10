# Candidate Search Status

This note tracks the next Codex + GPT-5.5 failed cases for the
Harness-TrajecDebug closed-loop experiment.

Goal:

```text
historical Codex + GPT-5.5 reward = 0.0
+ HTD oracle-grounded card
+ HTD Debug-Action card
+ Claude Code + Kimi-k2.6 reruns for both cards
+ task verifier reward = 1.0
```

## Endpoint Status

As of 2026-06-10, new Kimi reruns cannot start from this checkout:

- `token-plan` preflight returns HTTP `429` with quota exhausted.
- `ark` profile has no `ARK_API_KEY` in the current environment.

Use this preflight before launching any new rerun:

```bash
source ~/.bashrc >/dev/null 2>&1 || true
scripts/check_model_endpoint.py --endpoint-profile auto --model kimi-k2.6
```

Do not report a model-method failure unless endpoint preflight succeeds and the
agent enters the Claude Code loop.

## Accepted Candidates

| Candidate | Historical Codex + GPT-5.5 failure | Card status | Sanity status | Next action |
| --- | --- | --- | --- | --- |
| `make-mips-interpreter` | `test_vm_execution` failed while frame existence and visual similarity passed; stdout only said `saved 1 frame(s)`. | Tracked `oracle_grounded` and `debug_action` cards. | Oracle sanity passed, verifier reward `1.0`. | Run Kimi-k2.6 with both cards when endpoint quota/credentials recover. |
| `make-doom-for-mips` | `test_vm_execution` failed while frame existence and visual similarity passed; trace evidence shows local smoke runs printed the target line, but the final handoff left stale `/tmp/frame.bmp`. | Tracked `oracle_grounded` and `debug_action` cards. | Oracle sanity was started but manually stopped during the long compile/verifier path; no reward result yet. | Re-run oracle sanity, then run Kimi-k2.6 with both cards when endpoint quota/credentials recover. |

`make-mips-interpreter` and `make-doom-for-mips` are sibling tasks, but they
exercise different process failures:

- `make-mips-interpreter`: output-contract miss. The VM produced the right
  frame but not the exact DOOM graphics-init stdout line.
- `make-doom-for-mips`: state-handoff miss. The VM could produce both frame and
  stdout in local checks, but stale `/tmp/frame.bmp` let the verifier kill the
  fresh process too early.

## Deprioritized Or Rejected Candidates

| Candidate | Decision | Reason |
| --- | --- | --- |
| `install-windows-3.11` | Deprioritized | QEMU-heavy, and the user flagged QEMU as a likely source of `agentRunTimeout`. Keep it for later only after a timeout-specific harness plan exists. |
| `mteb-leaderboard` | Rejected as primary evidence | Failure appears tied to a fixed leaderboard snapshot / fixed-answer target, which risks turning the card into answer leakage rather than process evaluation. |
| `nginx-request-logging` | Rejected as primary evidence | Historical Codex configuration looked plausible, but verifier requests were contaminated by local proxy routing, so the failure is infra/proxy noise rather than a clean agent-process error. |

## Resume Commands

Oracle sanity for `make-doom-for-mips`:

```bash
export DOCKER_HOST=unix:///Users/hugo/.colima/tb21-harbor/docker.sock
/Users/hugo/.codex/skills/terminal-bench-harbor-runner/scripts/run_terminal_bench_harbor.sh \
  --task runs/harbor_icl_baseline/task_variants/no_icl/make-doom-for-mips \
  --agent oracle \
  --job-name htd-oracle-sanity-make-doom-for-mips \
  --jobs-dir runs/harbor_icl_baseline/harbor_runs_sanity \
  --setup-timeout 1200 \
  --agent-timeout 1200 \
  --no-force-build
```

Kimi reruns for `make-mips-interpreter` once preflight is green:

```bash
scripts/run_harbor_dynamic_icl.sh \
  --pack-dir runs/harbor_icl_baseline \
  --jobs-dir runs/harbor_icl_baseline/harbor_runs_oracle_grounded \
  --model kimi-k2.6 \
  --task make-mips-interpreter \
  --endpoint-profile auto \
  --context-variant oracle_grounded \
  --inject-mode prelude \
  --agent-timeout 1200 \
  --verifier-timeout 1200 \
  --no-force-build

scripts/run_harbor_dynamic_icl.sh \
  --pack-dir runs/harbor_icl_baseline \
  --jobs-dir runs/harbor_icl_baseline/harbor_runs_joint_failure \
  --model kimi-k2.6 \
  --task make-mips-interpreter \
  --endpoint-profile auto \
  --context-variant debug_action \
  --inject-mode prelude \
  --agent-timeout 1200 \
  --verifier-timeout 1200 \
  --no-force-build
```

Use the same command shape for `make-doom-for-mips` after oracle sanity passes.
