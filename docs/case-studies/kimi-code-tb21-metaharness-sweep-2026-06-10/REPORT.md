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

Additional exploratory search logs for `largest-eigenval` and
`chess-best-move` are included as
`raw-logs/exploratory-unsolved-search-kimicode-20260610.tar.zst`. These runs
are retained for trajectory analysis only and are explicitly excluded from the
valid reward comparison because they timed out or were interrupted before a
clean without/with pair was available.

Completed task families so far:

- `openssl-selfsigned-cert`: without Meta-Harness failed, with Meta-Harness passed.
- `sanitize-git-repo`: without Meta-Harness failed, with Meta-Harness passed.
- `kv-store-grpc`: without Meta-Harness failed, with Meta-Harness passed.
- `torch-tensor-parallelism`: without Meta-Harness failed, with Meta-Harness passed.
- `query-optimize`: mixed; `without-stop` passed once, `with-stop` had one missing-artifact failure and one pass. Repetition was stopped to publish this PR.
- `headless-terminal`: without Meta-Harness failed, and with Meta-Harness also
  failed in the full no-stop run. This is the first current
  Meta-Harness-unsolved candidate in this Kimi Code sweep.
- `largest-eigenval`: selected as the next K2.6 failure candidate, but the
  Kimi Code exploratory run did not write a candidate file before it was
  stopped; no reward comparison was recorded.
- `chess-best-move`: selected as a short clean K2.6 failure candidate. The
  without run did not write `move.txt` before being stopped. The with
  Meta-Harness run received a repair brief that named both expected moves, but
  the trajectory went into image-analysis scripts and timed out without
  creating `/app/move.txt`; verifier reward was `0.0` with
  `AgentTimeoutError`. This is useful trajectory evidence, but not a clean
  reward comparison.

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
- `chess-best-move`: Meta-Harness supplied the missing-move feedback directly
  (`e2e4` and `g2g4`), plus an environment snapshot showing only
  `chess_board.png` in `/app`. Kimi Code nevertheless wrote a sequence of
  helper scripts (`analyze_board*.py`, `find_position*.py`) and never created
  `move.txt` before timeout. The trajectory diff is therefore not a solution
  improvement; it is evidence that prior-failure feedback was present but not
  followed.

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

## Continuing Search Notes

After opening the PR, I continued scanning K2.6 reward-0 cases:

- `largest-eigenval`: prior K2.6 failed speedup tests on sizes 5, 7, and 9
  after leaving the implementation equivalent to `np.linalg.eig`. The
  exploratory Kimi Code run stayed in agent execution without writing a new
  `eigen.py`; it was stopped before verifier execution and is not counted.
- `chess-best-move`: prior K2.6 was a clean verifier failure, writing only
  `e2e4` where the verifier expected both `e2e4` and `g2g4`. A Meta-Harness
  repair brief included that exact feedback. The with Meta-Harness run still
  timed out after writing only analysis scripts and no `move.txt`, so it is a
  trajectory-only negative signal rather than a completed valid pair.
