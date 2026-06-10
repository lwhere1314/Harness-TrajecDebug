# Kimi Code TB2.1 Meta-Harness Sweep

Date: 2026-06-10

Harness: Harbor / Terminal-Bench 2.1 proxy tasks, using
`harbor_adapters.kimi_code_host_agent:KimiCodeHostAgent`.

Model: `kimi-for-coding`.

Prior-failure source: `claude-code + kimi-k2.6` failed cases from
`tb21-kimi-k26-local-019e737a-colima16g-proxy`.

## Status

This is a preliminary reproduction snapshot. The lightweight diagnosis archive
is included under `raw-logs/` and tracked through Git LFS. The full Harbor raw
log archive was prepared locally as
`raw-logs/harbor-runs-kimicode-tb21-sweep-20260610.tar.zst` and can be added as
a follow-up LFS commit; it is intentionally left out of this quick PR because it
is about 438 MB.

The additional `headless-terminal` probe logs are included as
`raw-logs/headless-terminal-kimicode-20260610.tar.zst`.

Completed task families so far:

- `openssl-selfsigned-cert`: without Meta-Harness failed, with Meta-Harness passed.
- `sanitize-git-repo`: without Meta-Harness failed, with Meta-Harness passed.
- `kv-store-grpc`: without Meta-Harness failed, with Meta-Harness passed.
- `torch-tensor-parallelism`: without Meta-Harness failed, with Meta-Harness passed.
- `query-optimize`: mixed; `without-stop` passed once, `with-stop` had one missing-artifact failure and one pass. Repetition was stopped to publish this PR.
- `headless-terminal`: without Meta-Harness failed, and with Meta-Harness also
  failed in the full no-stop run. This is the first current
  Meta-Harness-unsolved candidate in this Kimi Code sweep.

## Evaluation

Each run used Harbor reward files and verifier stdout from the official task
tests. See `runs.csv` for the run-level reward/error table and `summary.json`
for the structured summary.

## Trajectory Notes

Meta-Harness injected a prior-failure repair brief plus, when enabled, an
environment snapshot. The strongest trajectory diffs observed:

- `openssl-selfsigned-cert`: with Meta-Harness avoided undeclared Python
  `cryptography` dependency and used verifier-compatible certificate checks.
- `sanitize-git-repo`: with Meta-Harness preserved commit identity and replaced
  nested escaped fake-token occurrences rather than rewriting history.
- `kv-store-grpc`: with Meta-Harness addressed localhost gRPC proxy bypass and
  used a post-upload script for container-side setup.
- `torch-tensor-parallelism`: with Meta-Harness implemented distributed
  gather/reduce behavior instead of returning only local shards.
- `query-optimize`: both variants found the candidate-only top-synset join at
  least once; current evidence is not yet a stable Meta-Harness win.
- `headless-terminal`: without Meta-Harness produced a standard-library PTY
  implementation that passed 6/7 tests but left localhost requests routed through
  the proxy (`503`). With Meta-Harness, the trajectory did use the proxy
  environment snapshot and prior failure signal: it set `NO_PROXY`/`no_proxy`
  and added a post-upload `pip install pexpect`. The final implementation still
  failed, but the failure shifted to interaction semantics: `vim` timed out
  while waiting for a shell prompt, and the background HTTP server was not
  reachable directly (`ConnectionRefusedError`). Current evidence: Meta-Harness
  repaired the proxy diagnosis but did not solve the task.

## Current Negative Candidate

`headless-terminal` is a clean candidate for the next "Meta-Harness cannot yet
solve it" bucket:

- Prior Claude Code + Kimi K2.6 failed with `503 != 200` on the background
  localhost HTTP check.
- Kimi Code without Meta-Harness reproduced the same failure with reward `0.0`.
- Kimi Code with Meta-Harness, run without the early stop artifact, also had
  reward `0.0`. It acted on the Meta-Harness hint but traded the proxy failure
  for prompt/interactive-process failures.
- A with-stop run is retained in `runs.csv` as diagnostic only because
  `stop_after_path=headless_terminal.py` cut the run before dependency setup.
