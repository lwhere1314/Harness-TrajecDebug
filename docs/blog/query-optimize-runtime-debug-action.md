# Case Study: Runtime Debug-Action Injection on `query-optimize`

This case study documents the first end-to-end runtime ICL canary for
Harness-TrajecDebug. The key result is narrow but important: a Claude Code +
`kimi-k2.6` run that previously failed the `query-optimize` verifier was repaired
when a process-aware Debug-Action hint was injected at a live tool-use boundary.

This is a **same-task mechanism canary**, not the final held-out generalization
claim. It shows that the runtime injection path works and that a
Debug-Trajectory-derived action card can be more useful than outcome-only
context on the same failing task.

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
