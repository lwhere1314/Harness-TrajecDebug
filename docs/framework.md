# Framework

Harness-TrajecDebug uses three views of the same terminal-agent trace. These
views are used first for diagnosis and then for selecting trajectories that are
useful as in-context learning examples.

```mermaid
flowchart LR
  T["Trace JSON"] --> R["Reference view"]
  T --> S["State view"]
  T --> C["Commitment view"]

  R --> D["Trigger detection"]
  S --> D
  C --> D

  D --> F["Failure pattern"]
  F --> K["Critical step"]
  K --> H["Repair hint"]
  H --> Q["ICL data quality signal"]

  R -. "What must be true?" .-> D
  S -. "What is observed?" .-> D
  C -. "What did the agent decide?" .-> D
```

## Reference View

Reference view contains the task/verifier contract:

- final artifact path
- size or resource gate
- metric and threshold
- verifier semantics
- task-specific API contracts

## State View

State view contains observations reconstructed from the trace:

- command outputs
- artifact size and path
- metric values
- timeout, killed, or API errors
- final verifier output

## Commitment View

Commitment view contains agent decisions inferred from explicit messages or
action sequences:

- choosing a route
- trusting a local validation score
- promoting a final artifact
- committing to compression or another repair route

## Critical Step

A critical step is the earliest actionable point where:

- a decision or commitment is evidenced,
- it conflicts with a reference object or state observation,
- the conflict leaves a final verifier footprint,
- a local counterfactual repair would plausibly change the outcome.

## ICL Data Quality Signal

For the current project stage, diagnosis is used to decide whether a trace is a
good in-context learning example.

Useful examples include:

- passed traces with strong verifier-aligned closure,
- near misses with a clear critical step,
- contrastive traces where a bad route and a recoverable alternative are visible,
- traces that demonstrate state checking, validation, recovery, and artifact
  closure.

Weak examples include:

- pure tool loops,
- accidental successes with little reusable process signal,
- failures with diffuse root causes,
- traces whose local validation conflicts with the official verifier.
