# Interactive ICL V1 Implementation Details

This document is the implementation-level companion to
`docs/interactive-icl-swebenchpro.md`. It describes exactly how V1 constructs
and injects an ICL hint for SWE-bench Pro repair experiments.

## Scope

V1 is a single-repair-attempt algorithm:

1. Run a baseline agent on one SWE-bench Pro task.
2. If the baseline fails, prepare one repair hint from the failure artifacts.
3. Re-run the same task with an interactive driver.
4. Inject the repair hint once during the second run.
5. Let Harbor run the official verifier.

V1 does not do multi-round self-debugging. A failed ICL run is recorded as a
failed ICL run.

## Runtime Components

| Component | Path | Responsibility |
| --- | --- | --- |
| Baseline agent | `local_harbor_agents/claude_code_node20.py` | Stabilizes Claude Code execution in SWE-bench Pro containers by installing Node/npm through the container package manager. |
| ICL wrapper | `local_harbor_agents/claude_code_interactive_icl.py` | Prepares credentials, environment variables, the original instruction, the repair hint, and the interactive driver. |
| ICL driver | `local_harbor_agents/interactive_icl_driver.py` | Runs Claude Code in stream-json mode and injects one repair hint into stdin. |
| Benchmark runner | Harbor | Builds the task container, runs the agent, downloads artifacts, and runs the verifier. |

## Artifact Contract

The baseline and ICL runs communicate only through files. V1 treats Harbor's
trial directory as the stable data contract.

Baseline inputs for hint construction:

```text
<baseline-job>/<trial>/result.json
<baseline-job>/<trial>/verifier/test-stdout.txt
<baseline-job>/<trial>/verifier/output.json
<baseline-job>/<trial>/agent/claude-code.txt
<baseline-job>/<trial>/agent/trajectory.json
<baseline-job>/<trial>/config.json
```

ICL runtime files uploaded into the task container:

```text
/logs/agent/interactive_icl_driver.py
/logs/agent/interactive_icl_instruction.txt
/logs/agent/interactive_icl_hint.txt
/logs/agent/claude-code.txt
```

Verifier outputs after ICL:

```text
<icl-job>/<trial>/result.json
<icl-job>/<trial>/verifier/test-stdout.txt
<icl-job>/<trial>/verifier/output.json
```

## Hint Construction

V1 has two hint construction modes.

### Generic Hint

Generic mode is used when no task-specific diagnosis has been generated. The
fallback text is embedded in `ClaudeCodeInteractiveICL`:

```text
TrajecDebug interactive repair hint: inspect the previous verifier failure and
apply the smallest code change that makes the failing required test pass. Before
finishing, run the targeted failing test.
```

Generic hints are cheap and easy to run, but they do not tell the model what the
baseline patch got wrong.

### Diagnosis Hint

Diagnosis mode is the preferred V1 path. It is supplied through:

```text
HARNESS_TRAJECDEBUG_INTERACTIVE_ICL_HINT
```

The hint should be short and diagnostic. It should not replay the full
transcript. A good hint contains:

- the exact failing required test name,
- the relevant observed vs expected behavior,
- the baseline patch area,
- the most likely missing condition,
- negative guidance that prevents repeating the baseline mistake,
- the targeted test command to run before finishing.

Template:

```text
Baseline failed required test: <test name>.
The previous patch changed <file/function> but did not handle <missing case>.
Focus on <specific module/function>.
Avoid <bad direction from baseline>.
Run <targeted test command> before finishing.
```

Example:

```text
Baseline failed required test:
Mailbox.retries.test.tsx | should wait for all API actions to be finished before
loading elements.

The previous patch handled one request path but did not wait for all queued API
actions before rendering mailbox elements. Focus on the mailbox retry/loading
state transition, not on broad UI timing changes. Run the targeted mailbox retry
test before finishing.
```

## Injection Algorithm

The driver starts Claude Code with stream-json input and output:

```bash
claude \
  --verbose \
  --input-format=stream-json \
  --output-format=stream-json \
  --permission-mode=bypassPermissions \
  --print \
  --replay-user-messages
```

The original task instruction is sent first. The hint is sent later as a second
user message.

Pseudo-code:

```text
start claude process
send user_message(original_instruction)

injected = false
saw_progress = false
started_at = now()

for each stream_json line from claude:
    write line to stdout
    append line to /logs/agent/claude-code.txt

    payload = parse_json(line)
    if payload.type in {"assistant", "system"}:
        saw_progress = true

    if not injected and should_inject(payload, started_at, saw_progress):
        log injection marker
        send user_message(repair_hint)
        injected = true

    if payload.type == "result" and payload.terminal_reason == "completed":
        close stdin

return claude exit code
```

Injection trigger:

```text
should_inject(payload, started_at, saw_progress):
    if payload.type == "assistant":
        if assistant text contains one of:
            "Let me make the changes"
            "Now I have the exact file contents"
            "I need to"
            "I'll"
            return true

        if assistant content contains tool_use:
            return true

    if saw_progress and now() - started_at > 45 seconds:
        return true

    return false
```

The injection marker is written into the same transcript:

```json
{
  "type": "system",
  "subtype": "harness_trajecdebug_interactive_icl_injected",
  "timestamp": "..."
}
```

This marker lets later analysis distinguish normal Claude Code output from the
point where TrajecDebug intervened.

## Environment and Model Configuration

`ClaudeCodeInteractiveICL` forwards the Anthropic-compatible environment used by
the experiment runner:

```text
ANTHROPIC_API_KEY
ANTHROPIC_BASE_URL
ANTHROPIC_MODEL
ANTHROPIC_DEFAULT_SONNET_MODEL
ANTHROPIC_DEFAULT_OPUS_MODEL
ANTHROPIC_DEFAULT_HAIKU_MODEL
CLAUDE_CODE_SUBAGENT_MODEL
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
FORCE_AUTO_BACKGROUND_TASKS=1
ENABLE_BACKGROUND_TASKS=1
IS_SANDBOX=1
CLAUDE_CONFIG_DIR=/logs/agent/sessions
```

If `model_name` is set by Harbor, it becomes the Claude Code model and is also
used for the default Sonnet/Opus/Haiku aliases when a custom base URL is active.

## Running Baseline

Dataset-level baseline:

```bash
uvx harbor run \
  -d swebenchpro@1.0 \
  --agent-import-path local_harbor_agents.claude_code_node20:ClaudeCodeNode20 \
  -m kimi-k2.6 \
  --jobs-dir /home/admin/coding_agent_project/harbor_jobs \
  --job-name swebenchpro-n5-claude-code-node20-kimi-baseline-20260610 \
  --n-concurrent 1 \
  --n-tasks 5 \
  --artifact /logs/agent/claude-code.txt \
  --artifact /logs/agent/trajectory.json \
  --yes
```

Single local cached task baseline:

```bash
uvx harbor run \
  -p /home/admin/.cache/harbor/tasks/<cache-id>/<task-dir> \
  --agent-import-path local_harbor_agents.claude_code_node20:ClaudeCodeNode20 \
  -m kimi-k2.6 \
  --jobs-dir /home/admin/coding_agent_project/harbor_jobs \
  --job-name <job-name> \
  --n-concurrent 1 \
  --artifact /logs/agent/claude-code.txt \
  --artifact /logs/agent/trajectory.json \
  --yes
```

## Running ICL

Generic hint:

```bash
uvx harbor run \
  -p /home/admin/.cache/harbor/tasks/<cache-id>/<task-dir> \
  --agent-import-path local_harbor_agents.claude_code_interactive_icl:ClaudeCodeInteractiveICL \
  -m kimi-k2.6 \
  --jobs-dir /home/admin/coding_agent_project/harbor_jobs \
  --job-name <icl-job-name> \
  --n-concurrent 1 \
  --artifact /logs/agent/claude-code.txt \
  --artifact /logs/agent/trajectory.json \
  --yes
```

Diagnosis hint:

```bash
export HARNESS_TRAJECDEBUG_INTERACTIVE_ICL_HINT="$(cat repair-brief.txt)"

uvx harbor run \
  -p /home/admin/.cache/harbor/tasks/<cache-id>/<task-dir> \
  --agent-import-path local_harbor_agents.claude_code_interactive_icl:ClaudeCodeInteractiveICL \
  -m kimi-k2.6 \
  --jobs-dir /home/admin/coding_agent_project/harbor_jobs \
  --job-name <icl-job-name> \
  --n-concurrent 1 \
  --artifact /logs/agent/claude-code.txt \
  --artifact /logs/agent/trajectory.json \
  --yes
```

## Evaluation

V1 reports both instance-level and required-test-level metrics when available.

Instance-level:

```text
baseline_instance_accuracy = baseline_reward_1_count / baseline_completed_count
icl_instance_accuracy = icl_reward_1_count / icl_completed_count
```

Required-test-level:

```text
baseline_test_accuracy = baseline_required_tests_passed / baseline_required_tests
icl_test_accuracy = icl_required_tests_passed / icl_required_tests
```

Setup failures are not counted as model accuracy. For example, built-in
`claude-code` installer failures caused by `claude.ai/install.sh` returning 403
are runner failures, not SWE-bench Pro repair failures.

## Failure Modes

Common failure modes:

- invalid Claude credentials,
- missing Docker daemon access,
- unsupported package manager in the task image,
- Claude Code stream-json protocol changes,
- agent timeout after creating a correct patch,
- verifier timeout,
- generic hint too weak to change the model's repair path.

When a run times out after producing a patch, V1 still relies on Harbor verifier
output. If the verifier passes, the instance is counted as solved even if the
agent phase reports a timeout exception.

## V2 Direction

The next version should automate diagnosis hint construction:

```text
verifier failure + baseline transcript + patch diff + task instruction
    -> compact repair brief
    -> interactive ICL run
```

The target is a deterministic, structured repair brief generator that produces
short hints with enough task-specific detail to avoid repeating baseline
mistakes.
