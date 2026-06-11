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

The `cancel-async-tasks` 4x with/without reproduction raw records are retained
in the sibling case-study folder
`docs/case-studies/kimi-code-cancel-async-tasks-metaharness-2026-06-10/raw/`;
the current sweep audit and metrics reference those raw result files rather
than duplicating them into this folder.

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

Additional `write-compressor` queue-run logs are included as
`raw-logs/write-compressor-kimicode-20260610.tar.zst`.

Additional `mteb-leaderboard` diagnostic logs are included as
`raw-logs/mteb-leaderboard-kimicode-20260610.tar.zst`. This run is not counted:
Kimi Code left the workspace empty, the adapter raised `FileNotFoundError`, and
the verifier did not run.

Additional `raman-fitting` queue-run logs are included as
`raw-logs/raman-fitting-kimicode-20260610.tar.zst`.

Additional `feal-differential-cryptanalysis` queue-run logs are included as
`raw-logs/feal-differential-cryptanalysis-kimicode-20260610.tar.zst`.

Additional `largest-eigenval` queue-run logs are included as
`raw-logs/largest-eigenval-kimicode-20260611.tar.zst`.

Additional `git-leak-recovery` diagnostic logs are included as
`raw-logs/git-leak-recovery-kimicode-20260611.tar.zst`. This run is not
counted: Kimi Code recovered the secret and cleaned the git unreachable objects,
but the official verifier exited before writing `reward.txt`, so Harbor raised
`RewardFileNotFoundError`.

Additional partial `video-processing` logs are included as
`raw-logs/video-processing-partial-kimicode-20260611.tar.zst`. These runs are
not counted: both ended before `jump_analyzer.py` or `result.json` was produced.

Additional `video-processing` SIGTERM diagnostic logs are included as
`raw-logs/video-processing-sigterm-kimicode-20260611.tar.zst`. This run is not
counted: Kimi Code analyzed the example video and wrote debug frame artifacts,
but the Harbor process exited with return code `-15` before `jump_analyzer.py`
or any verifier `result.json` was produced.

Additional `adaptive-rejection-sampler` diagnostic logs are included as
`raw-logs/adaptive-rejection-sampler-invalid-kimicode-20260611.tar.zst`. This
run is not counted: Kimi Code wrote `ars.R`, but Harbor's outer agent timeout
fired before the adapter could upload the workspace and run the verifier, so the
result has no verifier reward.

Additional `pypi-server` queue-run and diagnostic logs are included as
`raw-logs/pypi-server-kimicode-20260611.tar.zst`. The counted with
Meta-Harness result is a valid verifier failure with reward `0.0`: Kimi Code
built `vectorops` wheel/sdist artifacts and started a package server, but the
official `pip install vectorops==0.1.0` check still found no available version.
Two later repair probes are retained only as diagnostics because they failed
before a clean verifier result.

Additional Kimi Code session usage records are included as
`raw-logs/kimi-session-wire-usage-20260611.tar.zst`. This archive contains the
22 Kimi session `wire.jsonl`/`state.json` records used to backfill token usage
from `usage.record` events.

Completed task families so far:

- `cancel-async-tasks`: separate 4x reproduction. Without Meta-Harness failed
  4/4 on `test_tasks_cancel_above_max_concurrent`; with Meta-Harness passed
  4/4 after the injected previous failure steered the implementation toward
  broad cancellation handling.
- `openssl-selfsigned-cert`: without Meta-Harness failed, with Meta-Harness passed.
- `sanitize-git-repo`: without Meta-Harness failed, with Meta-Harness passed.
- `kv-store-grpc`: without Meta-Harness failed, with Meta-Harness passed.
- `torch-tensor-parallelism`: without Meta-Harness failed, with Meta-Harness passed.
- `query-optimize`: mixed; `without-stop` passed once, `with-stop` had one missing-artifact failure and one pass. Repetition was stopped to publish this PR.
- `headless-terminal`: without Meta-Harness failed, and with Meta-Harness also
  failed in the full no-stop run. This is the first current
  Meta-Harness-unsolved candidate in this Kimi Code sweep.
- `largest-eigenval`: selected from the K2.6 failure pool. The formal
  with Meta-Harness queue run timed out without changing `eigen.py`; the
  timeout-upload verifier path still ran and returned reward `0.0`.
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
- `feal-differential-cryptanalysis`: selected from the K2.6 clean reward-0
  pool. Kimi Code used the injected prior failure and environment context,
  wrote `attack.py`, the adapter stopped on `stop_after_path=attack.py`, and
  the official verifier passed with reward `1.0`.
- `dna-insert`: selected from the K2.6 clean reward-0 pool. Kimi Code wrote
  `primers.fasta`, but the official verifier still failed with reward `0.0`.
- `filter-js-from-html`: selected from the K2.6 clean reward-0 pool. The run
  completed with reward `0.0` after receiving the prior failure and environment
  snapshot.
- `gcode-to-text`: selected from the K2.6 clean reward-0 pool. Kimi Code timed
  out without a passing `out.txt`; the timeout-upload verifier path ran and
  returned reward `0.0`.
- `write-compressor`: selected from the K2.6 timeout-failure pool. The runner
  used `stop_after_path=data.comp`, but the artifact never appeared. The
  timeout-upload verifier path ran and returned reward `0.0`.
- `mteb-leaderboard`: diagnostic only. The prior failure was a verifier setup
  proxy failure. The with Meta-Harness run left the workspace empty, so no
  verifier reward was produced and the task is excluded from the current score.
- `raman-fitting`: selected from the K2.6 clean reward-0 pool. The with
  Meta-Harness run produced a valid verifier result with reward `0.0`.
- `git-leak-recovery`: diagnostic only. The with Meta-Harness run recovered
  `secret[lost_and_found_in_git]` and cleaned reflog/unreachable git objects,
  but the verifier failed before writing a reward file.
- `video-processing`: partial diagnostic only. Two with Meta-Harness attempts
  started video analysis and wrote exploratory scripts/images, but neither
  produced final `jump_analyzer.py` or a Harbor `result.json`.
- `video-processing` SIGTERM retry: partial diagnostic only. The retry used the
  prior verifier feedback and a stop condition for `jump_analyzer.py`; it
  generated debug frame artifacts and Kimi session wire usage, then exited with
  return code `-15` before writing the final script or verifier result.
- `adaptive-rejection-sampler`: diagnostic only. The run wrote `ars.R`, but the
  adapter timeout was set too close to the task-level Harbor timeout, so Harbor
  produced `AgentTimeoutError` before workspace upload/verifier execution.
- `pypi-server`: selected from the K2.6 clean reward-0 pool. The first queue
  attempt wrote package files but ended before a result. The counted queue run
  built uploadable artifacts and launched the server, but the official verifier
  still failed to discover `vectorops==0.1.0`, so it is a valid reward-0
  observed failure. Two follow-up repair probes are archived as diagnostics.

## Evaluation

Each run used Harbor reward files and verifier stdout from the official task
tests. See `runs.csv` for the run-level reward/error table and `summary.json`
for the structured summary.

`metrics.csv`, `metrics.json`, `metrics_task_pairs.csv`,
`metrics_task_pairs.json`, and `metrics_summary.json` extract token and latency
metrics from the same raw `result.json` files. Token fields are direct Harbor
`agent_result` values when present. For Kimi Code rows, Harbor currently leaves
those fields null, so the metrics script falls back to the local Kimi session
`wire.jsonl` `usage.record` events archived in
`raw-logs/kimi-session-wire-usage-20260611.tar.zst`.

Token coverage is now 78/89 rows for the `claude-code + kimi-k2.6` baseline and
22/22 rows for the current with Meta-Harness Kimi Code subset. On the 22 paired
rows, mean total `input+output` tokens moved from `893,998.909` to
`778,325.818` (`-115,673.091`), while mean cache-adjusted
`input-cache+output` tokens moved from `32,005.273` to `52,426.182`
(`+20,420.909`). The median paired deltas are `+10,980.000` total tokens and
`+18,824.000` cache-adjusted tokens. The interpretation is therefore mixed:
with Meta-Harness is lower on mean total tokens in this paired subset, but
higher on uncached/cache-adjusted tokens.

Current latency summary for the same paired subset: baseline mean wall time is
`3,474.376` seconds and with Meta-Harness mean wall time is `615.379` seconds
(`-2,858.997`). The corresponding medians are `972.452` seconds and
`638.580` seconds, with median paired wall-time delta `-294.089` seconds. This
latency comparison is not a controlled full-suite conclusion yet because the
with Meta-Harness set is still a targeted recovery subset and mixes passes,
failures, timeout-upload recoveries, and verifier-invalid diagnostics.

## 89-Task Audit

`tb21_89_audit.csv` and `tb21_89_audit.json` reconstruct the current task-level
score from local Harbor `result.json` files.

Current auditable snapshot:

- without Meta-Harness baseline: `33/89` tasks have reward `1.0` in the
  `claude-code + kimi-k2.6` run root.
- with Meta-Harness-style Kimi Code context: `41/89` currently proven, i.e.
  `33 + 8`.
- current additional solved tasks: `cancel-async-tasks`, `kv-store-grpc`,
  `openssl-selfsigned-cert`, `query-optimize`, `sanitize-git-repo`,
  `torch-tensor-parallelism`, `count-dataset-tokens`, and
  `feal-differential-cryptanalysis`.
- baseline invalid/missing-rerun bucket: `build-pov-ray`, `crack-7z-hash`,
  `db-wal-recovery`, `extract-elf`, `gpt2-codegolf`, `install-windows-3.11`,
  `make-doom-for-mips`, `make-mips-interpreter`, and `reshard-c4-data`.
- baseline failure bucket still requiring Meta-Harness traversal or confirmation:
  47 tasks, of which 11 now have observed with Meta-Harness failures
  (`break-filter-js-from-html`, `chess-best-move`, `configure-git-webserver`,
  `dna-insert`, `filter-js-from-html`, `gcode-to-text`, `headless-terminal`,
  `largest-eigenval`, `pypi-server`, `raman-fitting`, and
  `write-compressor`).

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
- `feal-differential-cryptanalysis`: Meta-Harness supplied the previous setup
  failure plus an environment snapshot. Kimi Code read `feal.py`, derived a
  deterministic differential characteristic, tested the 16-bit-derived
  `key[5]` candidates, and wrote `attack.py`. The adapter stopped after the
  target artifact stabilized, uploaded the workspace, and the verifier passed.
- `dna-insert`: Meta-Harness supplied prior failure context and the run wrote a
  new `primers.fasta`, but the final verifier reward stayed `0.0`.
- `filter-js-from-html`: Meta-Harness supplied prior failure and proxy
  environment context, but the produced result still failed official tests.
- `gcode-to-text`: Meta-Harness supplied prior verifier output showing the
  earlier dependency/proxy failure, but Kimi Code did not reach a passing
  `out.txt` before timeout; the verifier ran after upload and returned reward
  `0.0`.
- `write-compressor`: Meta-Harness supplied the prior missing-`data.comp`
  failure and the runner told the adapter to stop as soon as `data.comp`
  existed. Kimi Code never created that artifact, so the run timed out and the
  verifier again failed on the missing compressed file.
- `mteb-leaderboard`: Meta-Harness supplied task and proxy context, but Kimi
  Code produced no files at all. The failure occurred before upload/verifier and
  is tracked only as diagnostic raw evidence.
- `raman-fitting`: Meta-Harness supplied the prior verifier setup failure and
  environment snapshot. Kimi Code ran against the provided `graphene.dat` but
  the final `results.json` did not pass the official checks; this is a valid
  reward-0 verifier failure.
- `largest-eigenval`: Meta-Harness supplied the prior speedup failure, including
  failing sizes 5, 7, and 9 from the K2.6 run. The formal queue run entered
  Kimi Code but did not modify `eigen.py` before the 900-second agent timeout.
  The timeout-upload verifier still executed and failed speedup checks on sizes
  3 and 10, so this is a valid reward-0 verifier failure.
- `git-leak-recovery`: Meta-Harness supplied the prior verifier network/setup
  failure plus an environment snapshot showing a minimal image with no Python,
  pip, or uv. Kimi Code recovered the secret from the unreachable commit,
  wrote `/app/secret.txt`, expired reflogs, removed `ORIG_HEAD`, and ran
  aggressive GC so `git fsck --unreachable --no-reflogs` returned cleanly.
  The official verifier then failed before creating a reward file, so this
  remains diagnostic rather than a counted pass.
- `pypi-server`: Meta-Harness supplied the prior package-index failure and
  environment context. The counted run improved the trajectory from "nothing
  installable" to concrete `vectorops` package artifacts plus a running server,
  but it did not expose the package through an index shape that the official
  pip verifier accepted. Follow-up repair briefs tried a static PEP 503-style
  index and explicit setuptools package discovery; those probes are useful
  trajectory evidence but not counted because they failed before a clean
  verifier result.

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
  after leaving the implementation equivalent to `np.linalg.eig`. A later
  formal with Meta-Harness queue run also left `eigen.py` unchanged, timed out,
  and produced a valid verifier reward of `0.0`; it is now counted in the
  observed failure bucket.
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
- `feal-differential-cryptanalysis`: prior K2.6 failed during verifier setup.
  The with Meta-Harness run wrote a differential attack and passed after the
  `attack.py` stop artifact upload, adding one new task to the current `m`
  count.
- `dna-insert`, `filter-js-from-html`, and `gcode-to-text`: all have raw
  with-Meta-Harness verifier results and remain reward-0 observed failures.
- `write-compressor`: has a raw with-Meta-Harness verifier result and remains
  a reward-0 observed failure; it also validates the new queue runner
  `--stop-after-path` option.
- `mteb-leaderboard`: diagnostic-only run; `stop_after_path=result.txt` never
  triggered and no verifier reward exists.
- `raman-fitting`: has a raw with-Meta-Harness verifier result and remains a
  reward-0 observed failure.
- `largest-eigenval`: has a raw with-Meta-Harness verifier result and remains a
  reward-0 observed failure.
- `git-leak-recovery`: has raw with-Meta-Harness logs and a strong trajectory
  improvement, but Harbor raised `RewardFileNotFoundError`; it is retained as
  diagnostic evidence only.
- `video-processing`: the prior failure showed an off-by-few-frame takeoff
  estimate (`55` vs `[50,54]`, and `225` vs `[219,223]`). Meta-Harness injected
  this exact signal, and Kimi Code began frame-difference exploration, but both
  original attempts plus the SIGTERM retry ended before producing final
  `jump_analyzer.py`; these logs are retained only as partial infrastructure
  diagnostics.
- `pypi-server`: the counted with Meta-Harness queue run is a valid reward-0
  verifier failure. It built `vectorops` wheel/sdist artifacts and launched a
  server, but the official pip check still saw no `vectorops==0.1.0` versions.
  Two later repair probes are archived as diagnostics only.
