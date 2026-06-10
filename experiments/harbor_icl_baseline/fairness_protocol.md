# Fairness Protocol: ICL Injection vs Meta-Harness-Style Harness Search

This note fixes the experimental boundary for Harness-TrajecDebug's first ICL
baseline.

## Core Claim

The claim is not:

> We can beat any harness optimizer.

The claim is:

> Under the same target harness and model, Debug-Trajectory selected examples
> are better in-context learning inputs than examples selected by final outcome
> only, raw-log transfer, random retrieval, or free-form LLM filtering.

This means the primary comparison group must hold the **runtime harness fixed**.

## What We Are Testing

Harness-TrajecDebug acts before the task run:

```text
teacher traces
  -> diagnosis / selection / compression
  -> ICL context inserted into copied instruction.md
  -> same target agent, same harness, same verifier
```

The changed variable is the **context shown to the target model**, not the
agent loop or verifier.

## Instruction.md Injection

For Harbor / Terminal-Bench tasks, the baseline injects context by copying the
task directory and editing only the copied `instruction.md`.

Invariant across variants:

- same source task,
- same `task.toml`,
- same Docker image,
- same tests,
- same verifier,
- same agent binary,
- same model endpoint,
- same timeout,
- same job runner.

Changed variable:

- the ICL block appended to `instruction.md`.

Prompt shape:

```text
<original instruction.md>

----- BEGIN ICL BASELINE CONTEXT: <variant> -----
This block is in-context learning context from a previous teacher run, not an
additional task requirement...

<selected teacher example>
----- END ICL BASELINE CONTEXT: <variant> -----

Now solve the current task in the live environment and close the required
artifact.
```

This isolates the question:

> Does this form of trace injection change the target model's behavior?

## Primary Baselines

These are fair because they modify only ICL context.

| Name | Injected context | Tests |
| --- | --- | --- |
| `no_icl` | original instruction only | baseline target performance |
| `random_success` | random passing teacher trace | whether any successful trace helps |
| `outcome_only` | task name + reward / verifier summary | pass/fail-only selection |
| `raw_trace` | compressed event log under same context budget | direct trace transfer |
| `prompt_filtered` | LLM-selected snippets under same context budget | prompt-only trace filtering |
| `debug_trajectory` | reference/state/commitment card + evidence | Harness-TrajecDebug method |

For the current MVP, the implemented variants are `no_icl`, `outcome_only`,
`raw_trace`, and `debug_trajectory`. The script enforces a fixed injected
payload budget via `--max-context-chars`.

## Same-Task vs Held-Out

Same-task injection is useful, but it is not the final proof.

| Setting | Teacher example | What it proves | Risk |
| --- | --- | --- | --- |
| Same-task repair | GPT-5.5 trace from the same task Kimi failed | target model can reuse teacher process when the relevant strategy is visible | solution leakage |
| Leave-one-task-out | teacher examples from other tasks only | cross-task transfer from selected process examples | weaker effect, better scientific claim |
| Held-out task family | teacher examples from other Harbor families | general trace-to-skill transfer | requires more tasks |

Report same-task results as a smoke test or upper-bound replay condition. Report
held-out results as the main evidence for example-selection quality.

## Is Meta-Harness A Fair Baseline?

Not for the primary ICL-selection claim.

Meta-Harness optimizes **harness code** around a fixed base model. The paper
describes harnesses as code deciding what to store, retrieve, and show while the
model works, and the released repo describes the method as automated search over
task-specific model harnesses. Its Terminal-Bench artifact also injects an
environment snapshot before the agent loop starts, saving early exploration
turns.

That is a different intervention:

```text
Meta-Harness:
  prior traces / scores / code
    -> proposer writes new harness code
    -> changed agent scaffold
    -> evaluation

Harness-TrajecDebug ICL:
  prior traces
    -> selected/compressed example
    -> unchanged agent scaffold
    -> evaluation
```

So using Meta-Harness as a direct baseline would conflate two variables:

1. better trace use,
2. changed runtime harness.

If Meta-Harness wins, we would not know whether the win came from better
trajectory information or from stronger environment bootstrapping, memory,
planner/executor scaffolding, prompt templates, or tool policy.

## How To Compare With Meta-Harness Fairly

Use a two-tier comparison.

### Tier 1: Fair ICL Selector Baselines

Hold runtime harness fixed and vary only injected context:

```text
Claude Code + kimi-for-coding + Harbor task
  no_icl
  outcome_only
  raw_trace
  prompt_filtered
  debug_trajectory
```

This tier answers the project's main claim.

### Tier 2: System-Level Harness Engineering Baselines

Allow the harness to change:

```text
same model + same task split + same evaluation budget
  fixed Claude Code harness
  Meta-Harness-like environment snapshot harness
  Meta-Harness discovered scaffold, if runnable
  Harness-TrajecDebug ICL on fixed harness
  optional: Harness-TrajecDebug labels supplied to harness search
```

This tier answers a different question:

> Is data-side ICL selection competitive with, or complementary to,
> harness-code optimization?

Report it as system-level comparison or upper bound, not as the primary
example-selection baseline.

## Minimum Fairness Checklist

For ICL-selection experiments:

- Use the same target model and endpoint, preferably `kimi-for-coding` on the
  Kimi Code Claude Code endpoint when testing Kimi Code.
- Use the same harness and agent binary.
- Use identical copied task directories except for `instruction.md`.
- Use held-out target tasks for the main claim.
- Do not include a target task's own teacher trace in held-out ICL.
- Fix injected context budget.
- Fix number of teacher examples.
- Freeze any LLM prompt-filter selection prompt before evaluation.
- Report API failures and quota failures separately from model failures.

For Meta-Harness-style comparisons:

- Separate "changed harness" results from "changed ICL context" results.
- Use the same train/test task split.
- Count harness-search compute separately from target-task inference compute.
- Prevent verifier/test/oracle leakage into the runtime agent.
- Report both final pass rate and failure-pattern shift.

## Practical Recommendation

Use this ordering:

1. Run `cancel-async-tasks` same-task smoke test to validate that
   `instruction.md` injection works end to end.
2. Expand to 5-10 Kimi-failed tasks with same-task repair to measure whether
   teacher traces can be consumed.
3. Move to leave-one-task-out ICL selection for the main claim.
4. Add a Meta-Harness-like environment-snapshot scaffold as a system-level
   comparator, clearly labeled as a changed-harness baseline.
5. Later, test whether Harness-TrajecDebug labels improve Meta-Harness itself.

## Sources Checked

- [Meta-Harness paper](https://arxiv.org/abs/2603.28052): describes
  Meta-Harness as an outer-loop system that searches over harness code and gives
  the proposer access to source code, scores, and execution traces.
- [Meta-Harness repository](https://github.com/stanford-iris-lab/meta-harness):
  describes the framework as automated search over task-specific model
  harnesses and includes a Terminal-Bench scaffold-evolution reference example.
- [Meta-Harness Terminal-Bench artifact](https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact):
  documents the Terminal-Bench 2 harness artifact and its environment snapshot
  method before the agent loop.
- [Kimi Code overview](https://www.kimi.com/code/docs/en/): documents the
  Anthropic-compatible endpoint, the `kimi-for-coding` model ID, and quota/rate
  limits.
- [Kimi Code third-party agents guide](https://www.kimi.com/code/docs/en/third-party-tools/other-coding-agents.html):
  documents third-party coding-agent setup and the OpenAI-compatible
  `kimi-for-coding` configuration used by tools such as Roo Code.
