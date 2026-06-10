# Related Work: Meta-Harness

This note compares Harness-TrajecDebug with
[Meta-Harness: End-to-End Optimization of Model Harnesses](https://arxiv.org/abs/2603.28052)
and the official repositories:

- [stanford-iris-lab/meta-harness](https://github.com/stanford-iris-lab/meta-harness)
- [stanford-iris-lab/meta-harness-tbench2-artifact](https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact)

## What Meta-Harness Does

Meta-Harness is an outer-loop system for **automated harness engineering**. It
searches over task-specific harness code around a fixed base model. A proposer
agent can inspect prior candidate harnesses, source code, scores, and execution
traces through a filesystem, then propose a new harness implementation.

The optimization target is the harness itself:

```text
prior harness code + scores + traces
  -> proposer agent
  -> new harness code
  -> benchmark evaluation
  -> repeat
```

The paper's central claim is that full execution traces are valuable because
scalar scores or summaries compress away the information needed for harness
engineering. This is strongly aligned with Harness-TrajecDebug's motivation.

## Insight From The Terminal-Bench Harness

The most concrete Terminal-Bench insight from Meta-Harness is not a larger
prompt or a new model. It is an initial environment injection. The optimized
Terminal-Bench artifact adds an environment bootstrap step before the agent loop
starts: the harness probes the sandbox for the working directory, `/app` file
listing, language/toolchain versions, package managers, and memory, then appends
that compact snapshot to the first prompt.

The relevant files are:

- [`meta-harness-tbench2-artifact/agent.py`](https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact/blob/main/agent.py), where `_gather_env_snapshot()` builds the snapshot and `_run_agent_loop()` injects it into the initial prompt.
- [`meta-harness/reference_examples/terminal_bench_2/agents/baseline_kira.py`](https://github.com/stanford-iris-lab/meta-harness/blob/main/reference_examples/terminal_bench_2/agents/baseline_kira.py), the Terminus-KIRA baseline that the artifact extends.
- [`meta-harness/reference_examples/text_classification/benchmark.py`](https://github.com/stanford-iris-lab/meta-harness/blob/main/reference_examples/text_classification/benchmark.py), which illustrates the benchmark sweep layer: candidate discovery, fixed model/dataset/seed settings, validation/test separation, saved memory, and frontier reporting.
- [`meta-harness/reference_examples/text_classification/meta_harness.py`](https://github.com/stanford-iris-lab/meta-harness/blob/main/reference_examples/text_classification/meta_harness.py), which illustrates the outer loop that asks a proposer agent to inspect prior files, scores, and traces, then write new candidate harness code.

The harness-level lesson is:

```text
Do not make the model spend its first turns rediscovering stable environment facts.
Probe them deterministically, then inject them before the first decision.
```

This is best understood as a trajectory-distribution intervention. The harness
does not solve the task, leak the answer, or update the model weights. Instead,
it removes low-value early uncertainty from the model's policy. Without the
bootstrap, a weaker terminal agent may spend the first few turns on `pwd`, `ls`,
`which python3`, package-manager checks, or even wrong assumptions about the
sandbox. With the bootstrap, the first model decision is conditioned on a true
environment snapshot, so the opening trajectory is less likely to drift.

In critical-step language, Meta-Harness is not primarily repairing a later
critical step after it appears. It is moving a recurring precondition out of the
model's free-form action space and into deterministic harness code. That
prevents some wrong or wasteful early commitments from being made in the first
place.

## What Harness-TrajecDebug Does

Harness-TrajecDebug is not currently trying to evolve harness code. Its first
goal is **trace-to-ICL-example selection** for smaller terminal agents.

The optimization target is the trajectory data bank:

```text
raw agent traces
  -> reference/state/commitment diagnosis
  -> failure taxonomy
  -> critical-step evidence
  -> trajectory quality score
  -> ICL example bank
```

The system asks:

> Which large-model trajectories are useful learning examples for a smaller
> terminal agent?

This is a different downstream objective from Meta-Harness.

## Key Differences

| Dimension | Meta-Harness | Harness-TrajecDebug |
| --- | --- | --- |
| Main objective | Search for better harness code | Select better trajectory data for ICL |
| Unit optimized | Candidate harness implementation | Candidate trace / trace segment / contrastive pair |
| Primary output | New task-specific harness | Diagnosed trace record + ICL data quality signal |
| Intervention time | Before and during the agent run | After the run, then before future ICL runs |
| Intervention mechanism | Modify harness code, prompt assembly, tool loop, or environment injection | Diagnose traces, localize critical steps, select/rewrite learning context |
| Feedback representation | Filesystem of prior code, scores, traces | Structured reference/state/commitment views |
| Credit assignment | Mostly delegated to proposer agent reading raw history | Explicit failure taxonomy + critical-step localization |
| Current downstream | Better benchmark pass rate via harness evolution | Better small-agent ICL examples on Harbor-style tasks |
| Baselines | hand-written harnesses, OpenEvolve, GEPA, TTT-Discover, scores-only/summary ablations | random traces, outcome-only filtering, prompt-filtered LLM selection |
| Role of raw traces | Input to proposer for writing new harness code | Input to data refinery for selecting teachable process examples |
| Model weights | Fixed base model during harness search | Small model initially unchanged; training left for later |
| Near-term experiment | evaluate discovered harness | evaluate ICL bank quality |

## Where We Are Similar

Both projects make the same important bet:

> Final reward is too sparse; raw execution traces contain the useful signal.

Meta-Harness shows this for harness code search. Harness-TrajecDebug tries to
show the same idea for ICL data selection.

Both also care about:

- long-horizon agent behavior,
- trace observability,
- harness effects beyond model weights,
- task-level verifier signals,
- interventions that shift trajectory quality without changing model weights,
- comparing harness/model combinations on Terminal-Bench or Harbor-style tasks.

## Where We Need To Be Different

To avoid becoming a smaller clone of Meta-Harness, Harness-TrajecDebug should
own a different layer:

### 1. Data selection, not harness evolution

Meta-Harness asks:

```text
What harness code should we run next?
```

Harness-TrajecDebug asks:

```text
Which trajectories should a small model study?
```

This makes our first deliverable an ICL example bank, not a better autonomous
agent scaffold.

### 2. Explicit process labels

Meta-Harness gives a strong proposer raw access to everything and lets it infer
failure causes. Harness-TrajecDebug should produce explicit, queryable labels:

- `thin-margin promotion`
- `validation mismatch`
- `compact-frontier search gap`
- `tool/API loop`
- `budget debt loop`
- `final artifact validation`
- `no critical failure detected`

These labels are the bridge from traces to ICL/SFT/RL data.

### 3. Harness compatibility and visualization

Meta-Harness optimizes inside a specific search setup. Harness-TrajecDebug should
serve as an adapter/observability layer across harnesses:

- Claude Code
- Codex
- Kimi-Code
- Harbor / Terminal-Bench
- auto-code-bench-style tasks

The output should be comparable across harnesses and models.

### 4. Small-model transfer

Meta-Harness demonstrates that changing the harness can improve a fixed model.
Harness-TrajecDebug should test whether process-aware trajectory selection can
improve a weaker model through ICL, before touching SFT or RL.

### 5. Different intervention layer

The two systems intervene at different layers of the same agent lifecycle:

```text
Meta-Harness:
  trace history -> better harness code -> next run starts differently

Harness-TrajecDebug:
  trace history -> diagnosed critical steps -> better ICL examples -> next model
  enters the run with better process priors
```

Meta-Harness acts on the harness boundary: it can change what the model sees,
which tools are available, how the loop handles completion, and what
deterministic probes happen before the first model call. Harness-TrajecDebug acts
on the trajectory bank: it decides which traces are worth teaching from, which
segments should be highlighted, and which critical decisions should become
contrastive examples for a smaller model.

These are complementary. A Harness-TrajecDebug label such as `tool/API loop`,
`budget debt loop`, or `final artifact validation` can suggest a future
harness-level intervention, while a Meta-Harness-discovered intervention such as
environment bootstrapping gives Harness-TrajecDebug a concrete pattern to encode
as a positive ICL example: inspect stable environment facts early, avoid
unnecessary exploratory turns, then spend the budget on task-specific validation.

## Proposed Experiments Against Meta-Harness-Inspired Baselines

Important fairness boundary: Meta-Harness should not be the primary baseline
for the ICL-selection claim because it changes the runtime harness. Use it as a
system-level harness-engineering comparator or upper bound. For the primary
claim, compare only methods that change the selected/injected ICL context while
holding the target harness fixed. The detailed protocol is in
[experiments/harbor_icl_baseline/fairness_protocol.md](../experiments/harbor_icl_baseline/fairness_protocol.md).

### Experiment 1: Trace Access vs Trace Diagnosis

Compare:

1. outcome-only trace selection,
2. LLM prompt-filtered trace selection,
3. raw-trace retrieval for ICL,
4. Harness-TrajecDebug diagnosis-based selection.

Question:

Does explicit failure taxonomy and critical-step localization beat simply giving
a large model the raw traces and asking it to choose examples?

### Experiment 2: Harness x Model x Harbor Tasks

Run a matrix:

```text
harnesses: Claude Code, Codex, Kimi-Code, Harbor baselines
models: frontier model, mid-size model, small target model
tasks: Harbor / Terminal-Bench / auto-code-bench-style tasks
```

Use strong-model traces to build ICL banks for the small model.

Compare:

- random examples,
- pass-only examples,
- prompt-filtered examples,
- Harness-TrajecDebug-selected examples.

Metrics:

- pass rate,
- verifier pass rate,
- tool-call count,
- token cost,
- recovery rate,
- artifact closure rate,
- failure pattern shift.

### Experiment 3: Complement With Meta-Harness

Harness-TrajecDebug can also be used as a preprocessing layer for Meta-Harness:

```text
raw trace history
  -> Harness-TrajecDebug labels and critical steps
  -> smaller, searchable diagnostic index
  -> Meta-Harness proposer reads structured failures
  -> new harness code
```

This would test whether explicit trace diagnosis improves or speeds up harness
evolution.

## Positioning Statement

Harness-TrajecDebug is complementary to Meta-Harness:

> Meta-Harness optimizes the code around a model. Harness-TrajecDebug optimizes
> which trajectories become learning context for another model.

In other words:

```text
Meta-Harness: traces -> better harness code
Harness-TrajecDebug: traces -> better ICL data
```

That distinction should stay central in the project positioning.
