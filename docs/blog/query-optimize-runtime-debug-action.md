# Case Study: Runtime Debug-Action Injection on `query-optimize`

This case study documents the first end-to-end runtime ICL canary for
Harness-TrajecDebug. The key result is narrow but important: a Claude Code +
`kimi-k2.6` run that previously failed the `query-optimize` verifier was repaired
when a process-aware Debug-Action hint was injected at a live tool-use boundary.

This is a **same-task mechanism canary**, not the final held-out generalization
claim. It shows that the runtime injection path works and that a
Debug-Trajectory-derived action card can be more useful than outcome-only
context on the same failing task.

The raw logs and evidence files for this canary are preserved under
[`raw_logs/blog_raw_logs/`](raw_logs/blog_raw_logs/README.md), including the
three Harbor trial directories, Claude Code SDK event streams, structured
trajectories, verifier outputs, and the injected Debug-Action card.

## Task

`query-optimize` gives the agent an Open English Wordnet SQLite database at
`/app/oewn.sqlite` and a slow SQL query at `/app/my-sql-query.sql`. The agent
must write a single SQLite query to `/app/sol.sql`.

Passing the task requires more than matching the output. The official verifier
also compares runtime against a golden query:

- output equivalence must pass;
- the database must not be modified;
- `/app/sol.sql` must contain one valid SQL query;
- the solution must satisfy the runtime gate.

This makes the task a useful harness case: a model can understand the SQL
semantics and still fail because its optimization route is not fast enough.

## Baselines

We ran three controlled variants on Claude Code + `kimi-k2.6`:

| Condition | Runtime context | Result |
| --- | --- | --- |
| `no_icl` | none | reward `0.0`; output matched, but runtime gate failed |
| `outcome_only + sdk_live` | teacher task name + reward summary | reward `0.0`; context injected, but the agent rebuilt an insufficient window-function route |
| `debug_action + sdk_live` | Debug-Action repair card with a verified `/app/sol.sql` artifact | reward `1.0`; the agent materialized the teacher artifact and passed 6/6 verifier tests |

The important contrast is not simply "injection versus no injection." The
`outcome_only` run also received runtime context through `sdk_live`, but the
context only said that a teacher run had passed. It did not contain the
process/action information needed to change the route.

## Where The Hint Was Injected

The successful `debug_action + sdk_live` run did not prepend the teacher trace
to `instruction.md`. Instead, Harness-TrajecDebug used the Claude Agent SDK to
watch Claude Code tool-use events and inject context only when the agent entered
a relevant decision point.

The event sequence was:

| Step | Event | What happened |
| --- | --- | --- |
| 1 | `Read("/app/my-sql-query.sql")` | Claude Code inspected the slow query. No context was injected. |
| 2 | `PreToolUse(Bash)` | Claude Code prepared to inspect the database schema with `sqlite3 /app/oewn.sqlite ".schema"`. |
| 3 | `live_injection` | Harness-TrajecDebug injected the Debug-Action card through `PreToolUse.additionalContext`. |
| 4 | `Bash(".schema")` | Claude Code continued the schema inspection with the injected hint now in context. |
| 5 | `Bash(".indexes")` | Claude Code did one cheap check for indexes. |
| 6 | `Bash("cat > /app/sol.sql ...")` | Claude Code materialized the verified teacher SQL artifact. |
| 7 | `Read("/app/sol.sql")` | Claude Code performed artifact closure. |
| 8 | official verifier | Harbor ran the verifier and returned reward `1.0`. |

The exact injection point was the first Bash schema-inspection call:

```bash
sqlite3 /app/oewn.sqlite ".schema"
```

Harness-TrajecDebug intercepted this as:

```text
PreToolUse(Bash)
reason = "Bash"
channel = "PreToolUse.additionalContext"
injection_count = 1
```

That moment matters because it is where the agent moves from "understand the
task" into "commit to an engineering search route." Injecting there gives the
model a chance to avoid re-discovering a merely adequate SQL rewrite and instead
use the verified compact artifact route.

## Raw Evidence For The Injection Point

The claim above is not inferred from the final solution alone. It is visible in
two raw logs preserved in the evidence bundle:

- SDK event stream:
  [`agent/sdk-live-events.jsonl`](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/agent/sdk-live-events.jsonl)
- Claude Code native session stream:
  [`agent/sessions/projects/-app/7ae21fa8-7488-49ad-8605-1effb41d7068.jsonl`](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/agent/sessions/projects/-app/7ae21fa8-7488-49ad-8605-1effb41d7068.jsonl)

The SDK event stream shows the exact order:

| Raw line | Event | Evidence |
| --- | --- | --- |
| [`sdk-live-events.jsonl` L9](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/agent/sdk-live-events.jsonl#L9) | `sdk_message` | Claude Code requests `Bash_1` with `sqlite3 /app/oewn.sqlite ".schema"`. |
| [`sdk-live-events.jsonl` L10](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/agent/sdk-live-events.jsonl#L10) | `pre_tool_use` | The controller sees `tool_name="Bash"`, `reason="Bash"`, and `already_injected=false`. |
| [`sdk-live-events.jsonl` L11](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/agent/sdk-live-events.jsonl#L11) | `live_injection` | Harness-TrajecDebug injects `3694` characters through `PreToolUse.additionalContext`. |
| [`sdk-live-events.jsonl` L12](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/agent/sdk-live-events.jsonl#L12) | `sdk_message` | The `.schema` result returns after the injection event. |
| [`sdk-live-events.jsonl` L13](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/agent/sdk-live-events.jsonl#L13) | `sdk_message` | The next model reasoning explicitly starts from the Debug-Action card and the teacher artifact. |

The native Claude session stream shows the same boundary from Claude Code's
side:

| Raw line | Event | Evidence |
| --- | --- | --- |
| [`session.jsonl` L8](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/agent/sessions/projects/-app/7ae21fa8-7488-49ad-8605-1effb41d7068.jsonl#L8) | assistant `tool_use` | `Bash_1` is the `.schema` command. |
| [`session.jsonl` L9](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/agent/sessions/projects/-app/7ae21fa8-7488-49ad-8605-1effb41d7068.jsonl#L9) | `hook_additional_context` | The injected attachment is labeled `HARNESS-TRAJECDEBUG LIVE ICL INJECTION`, with `Trigger: Bash`, `hookName="PreToolUse:Bash"`, and `toolUseID="Bash_1"`. |
| [`session.jsonl` L10](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/agent/sessions/projects/-app/7ae21fa8-7488-49ad-8605-1effb41d7068.jsonl#L10) | user `tool_result` | The schema output is delivered after the injected attachment. |

The run summary records the aggregate controller state:
[`sdk-live-summary.json` L13-L17](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/sdk-live-summary.json#L13-L17)
reports `tool_event_count=5`, `injection_count=1`, and
`injection_reasons=["Bash"]`.

So the concrete sequence is:

```text
Read /app/my-sql-query.sql
agent requests: sqlite3 /app/oewn.sqlite ".schema"
PreToolUse(Bash) fires with already_injected=false
Debug-Action card is attached through PreToolUse.additionalContext
.schema output returns
next model reasoning starts from the teacher artifact
```

This establishes the timing: the card arrived before the model reasoned from the
schema result and before it chose a SQL rewrite strategy.

## Why The `.schema` Boundary Worked

The `.schema` command itself was not magic, and Harness-TrajecDebug did not add
that command to the prompt. Claude Code chose it as the natural next inspection
step. The controller used it as a trigger because it was the first Bash boundary
after the model had read the slow query and before it committed to an
optimization plan.

Before that boundary, Claude Code only knew the task contract and the slow SQL.
After the schema came back, it had enough database context to choose a concrete
route: inspect version support, build a CTE/window-function rewrite, test it,
time it, and write `/app/sol.sql`. In the failing runs, that route was sensible
but not fast enough for the official runtime gate.

The Debug-Action card arrived at the narrow gap between those two phases. It did
not merely say "a prior run passed." It gave the agent a task-matched repair
card with:

- the same task contract;
- a teacher outcome of `reward=1.0`;
- the verified artifact path `/app/sol.sql`;
- a concrete next action to materialize that artifact;
- guardrails to stop after cheap closure instead of doing full recomputation.

That is why the same insertion location had different outcomes depending on the
content. The `outcome_only + sdk_live` run was also injected at the first
`.schema` Bash boundary, but its injected context was only a short outcome
summary:
[`sdk-live-events.jsonl` L9-L11](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-outcome_only-query-optimize-kimi-k2-6/query-optimize__R8AokaA/agent/sdk-live-events.jsonl#L9-L11)
shows the same `.schema` request, `PreToolUse(Bash)`, and `live_injection`, but
with only `500` injected characters. It did not contain the artifact-producing
action, so the agent continued down the autonomous rewrite route and failed the
runtime gate.

## Trajectory Shift After Injection

The raw trajectories show three different paths after the same early task setup:

| Condition | Post-`.schema` trajectory | Verifier evidence |
| --- | --- | --- |
| `no_icl` | `Read` slow query, inspect `.schema`, check SQLite version, run and time the original query, write a `word_synset_counts` / `ROW_NUMBER()` rewrite to `/app/sol.sql`. | Runtime failed: golden median `0.3557s`, solution median `0.5464s` ([`test-stdout.txt` L914-L926](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-icl-no_icl-query-optimize-kimi-k2-6/query-optimize__cTzLSZp/verifier/test-stdout.txt#L914-L926)). |
| `outcome_only + sdk_live` | Injected at the same `.schema` Bash boundary, then continued with `.version`, `/tmp/opt_query.sql`, query-plan comparison, timing, and a `ROW_NUMBER()` rewrite. | Runtime failed: golden median `0.3597s`, solution median `0.4767s` ([`test-stdout.txt` L101-L113](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-outcome_only-query-optimize-kimi-k2-6/query-optimize__R8AokaA/verifier/test-stdout.txt#L101-L113)). |
| `debug_action + sdk_live` | Injected at `.schema`, then the next reasoning says the Debug-Action card suggests a verifier-passing teacher artifact; the agent checks `.indexes`, writes the artifact to `/app/sol.sql`, reads it back, and stops. | Runtime passed: golden median `0.3506s`, solution median `0.2331s`; `6 passed in 162.19s` ([`test-stdout.txt` L36-L47](raw_logs/blog_raw_logs/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/verifier/test-stdout.txt#L36-L47)). |

The cleanest interpretation is therefore:

```text
same early task setup
same first Bash schema boundary for both sdk_live variants
outcome-only context -> continues generic rewrite -> runtime fail
debug-action context -> materializes verified artifact -> runtime pass
```

## What The Debug-Action Card Changed

Without the Debug-Action card, `kimi-k2.6` tends to do the reasonable but
insufficient thing:

1. read the original correlated-subquery SQL;
2. inspect the SQLite schema;
3. rewrite the query using CTEs and window functions;
4. self-check output equivalence against the original query;
5. write `/app/sol.sql`.

That route is semantically valid but too slow for the official runtime gate.
In the `outcome_only + sdk_live` run, the solution median was about `0.477s`
against a golden median of about `0.360s`, so the verifier failed.

The Debug-Action card carried a different kind of signal:

- the task reference matched the current task;
- a teacher run had already passed the official verifier;
- the verified artifact path was `/app/sol.sql`;
- the next action was to materialize that artifact before doing expensive
  recomputation;
- the agent should stop after artifact closure and let the verifier grade it.

After receiving that hint, Claude Code wrote the teacher SQL directly to
`/app/sol.sql` and avoided the slower window-function route.

## Verifier Result

The official Harbor verifier passed:

```text
6 passed in 162.19s
reward = 1.0
```

The runtime comparison also passed with margin:

```text
golden median:   0.3506s
solution median: 0.2331s
speedup:         1.50x
```

This is the concrete repair:

```text
no_icl                      -> reward 0.0
outcome_only + sdk_live      -> reward 0.0
debug_action + sdk_live      -> reward 1.0
```

## Why This Matters

The case study supports the core Harness-TrajecDebug hypothesis:

> Process-aware trajectory examples can be better ICL data than examples chosen
> only by final outcome.

Outcome-only context told the agent that success was possible, but not where the
decision point was or what action should change. The Debug-Action card provided
the missing process signal: at the schema-inspection stage, do not rebuild a
generic SQL optimization from scratch; materialize the verifier-proven artifact
and close the task.

In other words, the value is not just "a bigger prompt." The value is selecting
the right trajectory fragment and delivering it at the moment when it can still
change the agent's search path.

## Current Limitations

- This is a same-task repair canary, so it can contain task-specific solution
  information.
- The final claim requires held-out Harbor-style tasks where Debug-Trajectory
  selected examples are transferred across tasks.
- `sdk_live` currently bootstraps Python/pip and installs `claude-agent-sdk`
  inside task containers when needed, so it is more invasive than `hooks_live`.
- Some SDK runs can emit non-fatal hook callback noise; summary tooling keeps
  those separate from verifier outcomes.

## Next Experiment

The next step is to turn this from a mechanism canary into a data-selection
experiment:

1. build a bank of strong-model teacher trajectories;
2. select examples using Debug-Trajectory process labels;
3. compare against outcome-only and prompt-filtered selectors under a fixed
   token budget;
4. inject examples during live Claude Code / Harbor runs;
5. evaluate on held-out Harbor-style tasks by pass rate and failure-pattern
   shift.

That is the stronger result we want: not just repairing one known case, but
showing that process-aware trajectory selection gives smaller agents better
in-context learning data.
