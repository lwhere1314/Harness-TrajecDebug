# Control Note: `query-optimize`

`query-optimize` should not be presented as a clean Meta-Harness strategy win.
It is valuable precisely because it shows why the evaluation needs control runs:
the original Claude Code harness/model row failed, but Kimi Code passed the task
even without Meta-Harness.

Raw logs for this control are under
[`../raw_logs/meta-harness/harbor_runs/`](../raw_logs/meta-harness/harbor_runs/).

## Task

The task provides an OEWN SQLite database at `/app/oewn.sqlite` and a slow query
at `/app/my-sql-query.sql`. The agent must write a single SQLite query to
`/app/sol.sql` with identical output and runtime within `1.05x` of the golden
query.

## Conditions

| Condition | Trial | Result |
| --- | --- | --- |
| Claude Code + `kimi-k2.6` baseline | `query-optimize__qSVU2Yu` | reward `0.0`; runtime test failed |
| Kimi Code without Meta-Harness | `query-optimize__J3frX2U` | reward `1.0`; 6 passed |
| Kimi Code with Meta-Harness | `query-optimize__zDp5pa9` | reward `1.0`; 6 passed |

So the disciplined conclusion is:

```text
Claude Code harness/model row failed.
Kimi Code harness/model row succeeded.
This is not clean evidence that the Meta-Harness strategy caused the pass.
```

## What Failed In The Baseline

The Claude Code run produced a semantically correct query but failed the runtime
gate. The verifier records 5 passed / 1 failed:
[`ctrf.json` L9-L10](../raw_logs/meta-harness/harbor_runs/tb21-query-optimize-claude-code-k6/query-optimize__qSVU2Yu/verifier/ctrf.json#L9-L10).

The runtime failure was:

```text
golden median:   0.9276560420003079s
solution median: 1.203042084001936s
```

The raw verifier line is here:
[`test-stdout.txt` L94-L100](../raw_logs/meta-harness/harbor_runs/tb21-query-optimize-claude-code-k6/query-optimize__qSVU2Yu/verifier/test-stdout.txt#L94-L100).

## What The Kimi Code Controls Show

Kimi Code without Meta-Harness passed the same official verifier:
[`ctrf.json` L9-L10](../raw_logs/meta-harness/harbor_runs/tb21-queryopt-kimicode-without-metaharness-stop-20260610T171537/query-optimize__J3frX2U/verifier/ctrf.json#L9-L10).

Its runtime comparison was within threshold:
[`test-stdout.txt` L39-L53](../raw_logs/meta-harness/harbor_runs/tb21-queryopt-kimicode-without-metaharness-stop-20260610T171537/query-optimize__J3frX2U/verifier/test-stdout.txt#L39-L53).

Kimi Code with Meta-Harness also passed:
[`ctrf.json` L9-L10](../raw_logs/meta-harness/harbor_runs/tb21-queryopt-kimicode-with-metaharness-stop-r2-20260610T174611/query-optimize__zDp5pa9/verifier/ctrf.json#L9-L10),
[`test-stdout.txt` L39-L53](../raw_logs/meta-harness/harbor_runs/tb21-queryopt-kimicode-with-metaharness-stop-r2-20260610T174611/query-optimize__zDp5pa9/verifier/test-stdout.txt#L39-L53).

Both Kimi Code variants wrote compact candidate-filtered SQL artifacts:
[`without sol.sql`](../raw_logs/meta-harness/harbor_runs/tb21-queryopt-kimicode-without-metaharness-stop-20260610T171537/query-optimize__J3frX2U/agent/host-workspace/sol.sql),
[`with sol.sql`](../raw_logs/meta-harness/harbor_runs/tb21-queryopt-kimicode-with-metaharness-stop-r2-20260610T174611/query-optimize__zDp5pa9/agent/host-workspace/sol.sql).

The with-Meta-Harness prompt did include a prior-failure repair brief and runtime
numbers:
[`prompt.txt` L33-L90](../raw_logs/meta-harness/harbor_runs/tb21-queryopt-kimicode-with-metaharness-stop-r2-20260610T174611/query-optimize__zDp5pa9/agent/prompt.txt#L33-L90).
But the without-Meta-Harness control already found the same class of fix, so
this does not isolate Meta-Harness as the cause.

## Cost And Latency Use

This case is still useful for instrumentation and reporting. The paired metrics
row compares the original baseline against the Kimi Code + Meta-Harness run:

```text
baseline wall time:              1239.581s
Kimi Code + Meta-Harness wall:    597.660s
baseline total tokens:           672,413
Meta-Harness total tokens:        77,691
```

Use those numbers for cost/latency discussion, not as a causal pass-rate claim.
The more honest framing is:

> `query-optimize` helped validate the logging, metric, and control-run
> pipeline. It is a harness/model success for Kimi Code, not a clean
> Meta-Harness strategy success.
