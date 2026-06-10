# Kimi Code Meta-Harness-Style Reproduction on `cancel-async-tasks`

Date: 2026-06-10

This folder contains a project-local case study for a baseline reproduction inspired by the Meta-Harness Terminal-Bench artifact. The immediate goal is to build a concrete understanding of why Meta-Harness-style context can fix this task; the next research step is to traverse failed Claude Code + Kimi K2.6 cases and look for tasks that this style of Meta-Harness intervention still cannot solve.

- Meta-Harness repo: https://github.com/stanford-iris-lab/meta-harness
- Terminal-Bench 2 artifact: https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact

Important scope note: this is not a full reproduction of the official Meta-Harness outer-loop harness search. It is a controlled A/B reproduction of the two pieces that were directly applicable to this Harbor task:

- deterministic task-container environment bootstrap injected into the prompt
- prior verifier failure feedback injected into the next candidate prompt

## Harness And Model

Harness:

- Harbor custom agent import path: `harbor_adapters.kimi_code_host_agent:KimiCodeHostAgent`
- Copied harness source: `kimi_code_host_agent.py`
- The harness runs local Kimi Code in headless prompt mode on the host, asks it to write exactly one `run.py` in a host workspace, uploads that file to `/app/run.py`, then lets Harbor run the verifier.
- Kimi Code version observed by Harbor agent info: `0.13.0`

Model:

- Kimi Code model argument: `--model kimi-for-coding`
- Config alias added locally: `[models."kimi-for-coding"]`, pointing at provider `managed:kimi-code` and model `kimi-for-coding`
- Node used for the Kimi Code subprocess: `/Users/hugo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`

Task:

- Harbor task: `cancel-async-tasks`
- Local task path: `/Users/hugo/.cache/harbor/tasks/5pwPaf92MGZBJjvqnuBn9d/cancel-async-tasks`
- Required solution: implement `async run_tasks(tasks, max_concurrent)` in `/app/run.py`, with correct cleanup behavior under KeyboardInterrupt/SIGINT.

## Evaluation Method

Each condition was run with the same Harbor task, same custom harness, same model, same Node path, and same Kimi Code root.

- `without-metaharness`: no environment snapshot, no prior verifier feedback
- `with-metaharness`: environment snapshot enabled and prior verifier failure feedback injected
- Attempts per condition: 4
- Concurrency: 1
- Harbor verifier: task-provided `/tests/test.sh`
- Reward: Harbor `reward` from each trial result
- Unit tests in verifier: 6 pytest tests

Exact commands are in `commands.sh`.

## Results

| Condition | Trials | Errors | Mean Reward | Reward Distribution |
| --- | ---: | ---: | ---: | --- |
| without Meta-Harness-style context | 4 | 0 | 0.000 | 4 x reward 0.0 |
| with Meta-Harness-style context | 4 | 0 | 1.000 | 4 x reward 1.0 |

Top-level raw results:

- `raw/without-metaharness-4x/result.json`
- `raw/with-metaharness-4x/result.json`

Machine-readable summaries:

- `summary.json`
- `trials.csv`

## Trial Summary

| Condition | Trial | Reward | Tests Passed | Tests Failed | Agent Seconds | Code Shape |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| without | `cancel-async-tasks__PKRUK5x` | 0.0 | 5 | 1 | 139.891 | semaphore, KeyboardInterrupt, gather |
| without | `cancel-async-tasks__XtjVRPK` | 0.0 | 5 | 1 | 221.714 | semaphore, gather |
| without | `cancel-async-tasks__c82NMkd` | 0.0 | 5 | 1 | 273.857 | semaphore, worker, gather |
| without | `cancel-async-tasks__e6T4eog` | 0.0 | 5 | 1 | 37.486 | semaphore, KeyboardInterrupt, gather |
| with | `cancel-async-tasks__THLazLx` | 1.0 | 6 | 0 | 184.321 | worker, BaseException, gather |
| with | `cancel-async-tasks__UmqeHfc` | 1.0 | 6 | 0 | 207.735 | worker, BaseException, gather |
| with | `cancel-async-tasks__kzDD3Dp` | 1.0 | 6 | 0 | 184.440 | queue, worker, BaseException, gather |
| with | `cancel-async-tasks__jevALeT` | 1.0 | 6 | 0 | 669.291 | worker, BaseException, gather |

Latency note: the with condition was more accurate but not faster in this sample. It had one long-tail model response, so wall time was higher. The measured claim supported here is reward/correctness improvement, not latency improvement.

## Trajectory Diff

Representative raw diffs:

- `diffs/prompt_without_vs_with.diff`
- `diffs/run_py_without_fail_vs_with_pass.diff`

### Prompt / Context Diff

Without Meta-Harness-style context, the prompt contained only:

- the Harbor task instruction
- the host target file path for `run.py`
- a request not to run tests

With Meta-Harness-style context, the prompt added:

- `[Environment Snapshot]`
- working directory `/app`
- `/app` listing
- Python version and package-manager availability
- previous verifier failure summary
- explicit interpretation of the failure: do not create all wrapper tasks up front behind a semaphore; start only up to `max_concurrent` workers; cancel and await active workers on `BaseException`

This mirrors the useful part of the Meta-Harness Terminal-Bench artifact: supply deterministic environment context and useful task-specific history before the model spends turns rediscovering or re-making the same mistake.

### Generated Code Diff

The without condition repeatedly generated semaphore/gather-shaped code. It usually created one wrapper task per input task up front and then tried to limit execution with a semaphore. That shape passed the simple concurrency tests but failed the SIGINT cleanup edge case.

The failing verifier was consistent across all 4 without trials:

- failed test: `test_tasks_cancel_above_max_concurrent`
- expected stdout: two `Task started.` lines and two `Cleaned up.` lines
- actual stdout: two `Task started.` lines and zero `Cleaned up.` lines

The with condition generated worker/queue or worker/iterator-shaped code. The key behavioral changes were:

- create only up to `max_concurrent` active worker tasks
- do not start the third task while two workers are active
- catch `BaseException`, not only `KeyboardInterrupt`
- cancel active workers and `await asyncio.gather(..., return_exceptions=True)` so task `finally` cleanup code runs before re-raising

All 4 with trials passed all 6 verifier tests.

## Conclusion

For this task and this Kimi Code setup, the conclusion is strongly supported:

- without Meta-Harness-style context: 0/4 pass, mean reward 0.000
- with Meta-Harness-style context: 4/4 pass, mean reward 1.000

The improvement came from trajectory/context quality, not from changing the model or verifier. The decisive trajectory diff is that prior verifier feedback steered Kimi Code away from the common semaphore/gather anti-pattern and toward a bounded-worker implementation that correctly awaits cancellation cleanup.

This is therefore a positive case study: the baseline method fails consistently, while the Meta-Harness-style context intervention solves the task consistently. It should be treated as a sanity check before searching for negative cases where Meta-Harness does not recover the failure.

## Raw Data Layout

- `raw/without-metaharness-4x/`: full Harbor job directory for the no-context condition
- `raw/with-metaharness-4x/`: full Harbor job directory for the Meta-Harness-style context condition
- `summary.json`: parsed top-level and per-trial metrics
- `trials.csv`: flat per-trial table
- `diffs/`: representative prompt and generated-code diffs
- `kimi_code_host_agent.py`: custom Harbor adapter used in the reproduction
- `cancel_async_tasks_previous_failure.txt`: prior verifier feedback injected in the with condition
- `commands.sh`: exact commands used to run both conditions
