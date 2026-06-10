# Kimi Code TB2.1 Meta-Harness Sweep

Date: 2026-06-10

Harness: Harbor / Terminal-Bench 2.1 proxy tasks, using
`harbor_adapters.kimi_code_host_agent:KimiCodeHostAgent`.

Model: `kimi-for-coding`.

Prior-failure source: `claude-code + kimi-k2.6` failed cases from
`tb21-kimi-k26-local-019e737a-colima16g-proxy`.

## Status

This is a reproduction snapshot. The lightweight diagnosis archive and Harbor
raw log archives are included under `raw-logs/` and tracked through Git LFS,
including `raw-logs/harbor-runs-kimicode-tb21-sweep-20260610.tar.zst`.

The additional `headless-terminal` probe logs are included as
`raw-logs/headless-terminal-kimicode-20260610.tar.zst`.

Additional exploratory search logs for `largest-eigenval` and
`chess-best-move` are included as
`raw-logs/exploratory-unsolved-search-kimicode-20260610.tar.zst`. These runs
are retained for trajectory analysis only and are explicitly excluded from the
valid reward comparison because they timed out or were interrupted before a
clean without/with pair was available.

Additional `break-filter-js-from-html` probe logs are included as
`raw-logs/break-filter-js-from-html-kimicode-20260610.tar.zst`. These runs are
also trajectory-only: the without run wrote `/app/out.html` but verifier failed
while creating the local ChromeDriver session with `503 Service Unavailable`;
the with Meta-Harness run timed out without writing `/app/out.html`.

Additional `configure-git-webserver` probe logs are included as
`raw-logs/configure-git-webserver-kimicode-20260610.tar.zst`. This is a valid
with Meta-Harness verifier failure: the timeout-upload path preserved a
post-upload script, the git push/deploy path ran, but the webserver check still
returned HTTP `503`.

Additional queue-run logs for `count-dataset-tokens`, `dna-insert`,
`filter-js-from-html`, and `gcode-to-text` are included as
`raw-logs/metaharness-queue-batch1-kimicode-20260610.tar.zst`.

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
- `break-filter-js-from-html`: selected from the K2.6 clean reward-0 pool. The
  Kimi Code without run wrote a meta-refresh/data-URL payload but the verifier
  failed before evaluating it because Selenium/ChromeDriver returned proxy
  `503`. The with Meta-Harness run had environment and prior-failure context
  injected, but timed out without creating `out.html`.
- `configure-git-webserver`: selected from the K2.6 clean reward-0 pool. The
  with Meta-Harness run generated a `.kimi-post-upload.sh` that installed git,
  nginx, and sshd, created `/git/server`, and installed a post-receive hook.
  Harbor timed the agent out, but `upload_on_timeout=true` preserved the
  workspace and ran the verifier. The verifier still failed because the final
  `curl` returned HTTP `503`.
- `count-dataset-tokens`: selected from the K2.6 clean reward-0 pool. The
  prior verifier tail exposed the expected output `79586`. Kimi Code wrote a
  recomputation script and timed out, but `upload_on_timeout=true` preserved the
  workspace; the official verifier then passed with reward `1.0`.
- `dna-insert`: selected from the K2.6 clean reward-0 pool. Kimi Code wrote
  `primers.fasta`, but the official verifier still failed with reward `0.0`.
- `filter-js-from-html`: selected from the K2.6 clean reward-0 pool. The run
  completed with reward `0.0` after receiving the prior failure and environment
  snapshot.
- `gcode-to-text`: selected from the K2.6 clean reward-0 pool. Kimi Code timed
  out without a passing `out.txt`; the timeout-upload verifier path ran and
  returned reward `0.0`.

## Evaluation

Each run used Harbor reward files and verifier stdout from the official task
tests. See `runs.csv` for the run-level reward/error table and `summary.json`
for the structured summary.

## 89-Task Audit

`tb21_89_audit.csv` and `tb21_89_audit.json` reconstruct the current task-level
score from local Harbor `result.json` files.

Current auditable snapshot:

- without Meta-Harness baseline: `33/89` tasks have reward `1.0` in the
  `claude-code + kimi-k2.6` run root.
- with Meta-Harness-style Kimi Code context: `40/89` currently proven, i.e.
  `33 + 7`.
- current additional solved tasks: `cancel-async-tasks`, `kv-store-grpc`,
  `openssl-selfsigned-cert`, `query-optimize`, `sanitize-git-repo`,
  `torch-tensor-parallelism`, and `count-dataset-tokens`.
- baseline invalid/missing-rerun bucket: `build-pov-ray`, `crack-7z-hash`,
  `db-wal-recovery`, `extract-elf`, `gpt2-codegolf`, `install-windows-3.11`,
  `make-doom-for-mips`, `make-mips-interpreter`, and `reshard-c4-data`.
- baseline failure bucket still requiring Meta-Harness traversal or confirmation:
  47 tasks, of which 7 now have observed with Meta-Harness failures
  (`break-filter-js-from-html`, `chess-best-move`, `configure-git-webserver`,
  `dna-insert`, `filter-js-from-html`, `gcode-to-text`, and
  `headless-terminal`).

This is not yet the final requested number. The final report must first rerun
the invalid baseline bucket and finish Meta-Harness traversal over the remaining
baseline failures, then regenerate the audit from raw logs.

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
- `break-filter-js-from-html`: without Meta-Harness eventually wrote an
  `out.html` payload, but the verifier hit the same class of local proxy/browser
  automation problem as other ChromeDriver/Selenium tasks before evaluating the
  payload. With Meta-Harness, the prompt included the proxy-only environment
  snapshot and prior failure details, but the trajectory regressed to a timeout
  with no `out.html` artifact.
- `configure-git-webserver`: Meta-Harness feedback correctly pointed at the
  previous HTTP `503` failure and the generated post-upload script set up the
  git and nginx pieces. The trajectory improved over the prior K2.6 failure
  because the verifier's git push/deploy completed, but the final webserver
  request still returned `503`, so the task remains unsolved.
- `count-dataset-tokens`: Meta-Harness exposed the prior assertion directly:
  the K2.6 baseline wrote `79566` while the official test expected `79586`.
  Kimi Code did not simply write the known value; it created a tokenizer-based
  recomputation script and then timed out. The timeout-upload path preserved the
  resulting workspace, and the official verifier passed. This is counted as a
  Meta-Harness win, with the important caveat that the successful upload
  happened after agent timeout.
- `dna-insert`: Meta-Harness supplied prior failure context and the run wrote a
  new `primers.fasta`, but the final verifier reward stayed `0.0`.
- `filter-js-from-html`: Meta-Harness supplied prior failure and proxy
  environment context, but the produced result still failed official tests.
- `gcode-to-text`: Meta-Harness supplied prior verifier output showing the
  earlier dependency/proxy failure, but Kimi Code did not reach a passing
  `out.txt` before timeout; the verifier ran after upload and returned reward
  `0.0`.

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
- `break-filter-js-from-html`: prior K2.6 was a clean verifier failure because
  `/app/out.html` was missing. The Kimi Code without run produced `out.html`,
  but the verifier failed while creating ChromeDriver (`503 Service
  Unavailable`), so no payload assertion was reached. The with Meta-Harness run
  timed out before creating `out.html`.
- `configure-git-webserver`: prior K2.6 failed with HTTP `503` and git-repo
  errors. The with Meta-Harness run fixed the git push/deploy path but still
  returned HTTP `503` on the webserver check.
- `count-dataset-tokens`: prior K2.6 failed by 20 tokens (`79566` vs expected
  `79586`). The with Meta-Harness run passed after timeout-upload, adding one
  new task to the current `m` count.
- `dna-insert`, `filter-js-from-html`, and `gcode-to-text`: all have raw
  with-Meta-Harness verifier results and remain reward-0 observed failures.
