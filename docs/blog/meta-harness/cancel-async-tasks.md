# Case Study: Meta-Harness on `cancel-async-tasks`

This is the cleanest short example for a failure-informed repair prompt, but it
is not a faithful reproduction of the upstream Meta-Harness Terminal-Bench
skill. The prior failure exposed a specific behavioral edge: cancellation after
only the first `max_concurrent` tasks have started. Our prompt carried that
failure into the Kimi Code run, and the trajectory shifted from a generic
semaphore solution to a cancellation-aware worker design.

Raw logs for this case are under
[`../raw_logs/meta-harness/harbor_runs/`](../raw_logs/meta-harness/harbor_runs/).

## Task

The task asks the agent to create `/app/run.py` with:

```python
async run_tasks(tasks: list[Callable[[], Awaitable[None]]], max_concurrent: int) -> None
```

Passing requires more than bounded concurrency. The official verifier sends a
SIGINT while only the first two tasks should have started, then checks that those
two running tasks are cancelled and their cleanup code executes.

## Conditions

| Condition | Trial | Result |
| --- | --- | --- |
| Claude Code + `kimi-k2.6` baseline | `cancel-async-tasks__pdHm6Ub` | reward `0.0`; 5 passed / 1 failed |
| Kimi Code without Meta-Harness | 4 trials under `without-metaharness-4x` | `0/4` passed |
| Kimi Code with Meta-Harness | 4 trials under `with-metaharness-4x` | `4/4` passed |

The counted Meta-Harness trial is `cancel-async-tasks__UmqeHfc`.

## What Failed Before

The original Claude Code run passed the basic concurrency tests but failed
`test_tasks_cancel_above_max_concurrent`. The verifier expected two cleanup
lines after SIGINT, but got none:
[`test-stdout.txt` L190-L196](../raw_logs/meta-harness/harbor_runs/tb21-cancel-async-tasks-claude-code-k6/cancel-async-tasks__pdHm6Ub/verifier/test-stdout.txt#L190-L196).

The same failure appears in the structured verifier output:
[`ctrf.json` L64-L72](../raw_logs/meta-harness/harbor_runs/tb21-cancel-async-tasks-claude-code-k6/cancel-async-tasks__pdHm6Ub/verifier/ctrf.json#L64-L72).

The Kimi Code no-Meta-Harness reproduction repeated that failure pattern. For
example, `cancel-async-tasks__e6T4eog` failed the same test with 5 passed / 1
failed:
[`ctrf.json` L9-L10](../raw_logs/meta-harness/harbor_runs/tb21-cancel-async-tasks-kimicode-4x/without-metaharness-4x/cancel-async-tasks__e6T4eog/verifier/ctrf.json#L9-L10),
[`ctrf.json` L64-L72](../raw_logs/meta-harness/harbor_runs/tb21-cancel-async-tasks-kimicode-4x/without-metaharness-4x/cancel-async-tasks__e6T4eog/verifier/ctrf.json#L64-L72).

## What Meta-Harness Added

Our Meta-Harness-inspired adapter injected a prior-failure brief into the Kimi
Code prompt. The brief named the failing test, the exact
`n_tasks=3, max_concurrent=2` scenario, the expected stdout, and the failure
interpretation:
[`prompt.txt` L20-L46](../raw_logs/meta-harness/harbor_runs/tb21-cancel-async-tasks-kimicode-4x/with-metaharness-4x/cancel-async-tasks__UmqeHfc/agent/prompt.txt#L20-L46).

The important change was not merely "more context." It was process context: the
agent was told that creating one wrapper task per input and relying on
`asyncio.gather` can leave semaphore-blocked wrappers in the wrong cancellation
state. The repair direction was to start only up to `max_concurrent` workers,
cancel those workers, and await them during cleanup.

That is materially different from the upstream
`meta-harness-terminal-bench-2` skill. The upstream skill asks the proposer to
read many failed and successful trajectories, implement a new general-purpose
`AgentHarness` Python scaffold, and write `pending_eval.json` for the outer
benchmark loop. It also forbids task-specific hints and task names in the
candidate agent. In this `cancel-async-tasks` run, by contrast, the next agent
was directly told the task-specific failed test and failure interpretation. So
the causal claim here is only: structured prior-failure feedback can repair this
task for Kimi Code. It is not evidence that the original Meta-Harness skill
would discover a general harness change that improves this task without
task-specific information.

## Trajectory Shift

| Without Meta-Harness | With Meta-Harness |
| --- | --- |
| Recreates a reasonable semaphore/gather implementation. It passes normal concurrency checks but misses the SIGINT cleanup edge. | Starts from the failed verifier edge and implements cancellation as explicit runner state. The generated `run.py` handles below/at/above max-concurrent cancellation. |

The generated passing artifact is preserved here:
[`run.py`](../raw_logs/meta-harness/harbor_runs/tb21-cancel-async-tasks-kimicode-4x/with-metaharness-4x/cancel-async-tasks__UmqeHfc/agent/host-workspace/run.py).

## Verifier Result

The counted Meta-Harness trial passed all six official tests:
[`ctrf.json` L9-L10](../raw_logs/meta-harness/harbor_runs/tb21-cancel-async-tasks-kimicode-4x/with-metaharness-4x/cancel-async-tasks__UmqeHfc/verifier/ctrf.json#L9-L10),
including `test_tasks_cancel_above_max_concurrent`:
[`ctrf.json` L64-L65](../raw_logs/meta-harness/harbor_runs/tb21-cancel-async-tasks-kimicode-4x/with-metaharness-4x/cancel-async-tasks__UmqeHfc/verifier/ctrf.json#L64-L65).

The stdout summary shows the same result:
[`test-stdout.txt` L152-L158](../raw_logs/meta-harness/harbor_runs/tb21-cancel-async-tasks-kimicode-4x/with-metaharness-4x/cancel-async-tasks__UmqeHfc/verifier/test-stdout.txt#L152-L158).

## Takeaway

This is a strong interview example for recovery from structured verifier
feedback: a previous failure became a concrete repair target, and the target
changed the agent's search trajectory. It should not be described as a faithful
upstream Meta-Harness reproduction. The measured effect is a reproducible
`0/4 -> 4/4` shift under Kimi Code on this task when the agent is given
task-specific failure feedback.
