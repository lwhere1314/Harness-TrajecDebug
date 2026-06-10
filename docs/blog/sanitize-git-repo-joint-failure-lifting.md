# Case Study: Lifting a Joint Failure on `sanitize-git-repo`

This case study documents a stronger Harness-TrajecDebug runtime-ICL result than
the earlier `query-optimize` mechanism canary.

Here, both historical runs failed:

- Codex + GPT-5.5: reward `0.0`
- Claude Code + Kimi-k2.6: reward `0.0`

Harness-TrajecDebug compared the two failed trajectories, identified the
critical action boundary, synthesized a Debug-Action hint from the failure
footprints, and injected that hint into a new Claude Code + Kimi-k2.6 run. The
rerun passed the official Harbor verifier with reward `1.0`.

This is the "left foot steps on right foot" pattern: two failed traces can still
contain enough complementary process evidence to produce a repair hint.

## Task

`sanitize-git-repo` asks the agent to sanitize the `/app/dclm` repository by
replacing API keys and tokens with placeholders, while avoiding unrelated file
changes.

The verifier checks three things:

1. secret-like values are removed from the contaminated files;
2. the contaminated files exactly match the expected sanitized versions;
3. no files other than the known contaminated files were changed relative to the
   original reference commit.

This makes the task a useful trace-diagnosis case. A model can over-solve by
rewriting git history, or under-solve by missing a token embedded inside a large
JSON string.

## Historical Failures

Harness-TrajecDebug first built a joint-failure matrix from local historical
runs:

```bash
scripts/build_joint_failure_matrix.py
```

The generated matrix found `sanitize-git-repo` as a high-suitability joint
failure:

| Run | Reward | Verifier footprint |
| --- | ---: | --- |
| Claude Code + Kimi-k2.6 | `0.0` | failed `test_removal_of_secret_information` and `test_correct_replacement_of_secret_information` |
| Codex + GPT-5.5 | `0.0` | failed `test_no_other_files_changed` |

The two failures are complementary:

- Kimi-k2.6 preserved the no-extra-files constraint, but missed a second
  HuggingFace-token occurrence embedded inside the JSON metadata diff.
- Codex + GPT-5.5 removed the obvious secrets, but rewrote or garbage-collected
  repository history, so the verifier could not resolve the original reference
  commit for the "no other files changed" check.

## Critical Step

The critical commitment is the task framing:

> This is not a history-purge task. It is a bounded working-tree edit task.

The correct action boundary is:

- edit only the known contaminated files;
- replace every secret-shaped value, including lowercase copies and values
  embedded in JSON strings;
- preserve the original git object graph and reference commit;
- do not run history-mutating commands such as `git filter-branch`,
  `git filter-repo`, `git rebase`, `git gc`, `git prune`, or deleting `.git`.

That is the HTD signal: not "here is the answer", but "this is the decision
boundary that both failed traces got wrong in different ways."

## Runtime Injection

The successful rerun used the existing `sdk_live` runtime injection path:

```bash
TB21_TASKS=/Volumes/SSD/terminal-bench-harbor/harbor/datasets/terminal-bench-2.1/tasks

mkdir -p runs/harbor_icl_baseline/task_variants/no_icl
rm -rf runs/harbor_icl_baseline/task_variants/no_icl/sanitize-git-repo
cp -R "$TB21_TASKS/sanitize-git-repo" \
  runs/harbor_icl_baseline/task_variants/no_icl/sanitize-git-repo

mkdir -p runs/harbor_icl_baseline/teacher_cards/sanitize-git-repo
cp experiments/harbor_icl_baseline/joint_failure_cards/sanitize-git-repo-debug-action.md \
  runs/harbor_icl_baseline/teacher_cards/sanitize-git-repo/debug_action.md
```

```bash
scripts/run_harbor_dynamic_icl.sh \
  --task sanitize-git-repo \
  --model kimi-k2.6 \
  --context-variant debug_action \
  --inject-mode sdk_live \
  --endpoint-profile ark \
  --sdk-live-intercept-tool Bash \
  --jobs-dir runs/harbor_icl_baseline/harbor_runs_joint_failure \
  --agent-timeout 900 \
  --verifier-timeout 900
```

The original task instruction was not edited. Harness-TrajecDebug started Claude
Code normally, watched tool-use events through the Claude Agent SDK, and injected
the Debug-Action card at the first Bash boundary:

```text
PreToolUse(Bash)
command = "ls -la /app"
channel = "PreToolUse.additionalContext"
injection_count = 1
```

This is an intentionally early decision point. It happens before the agent
commits to a search strategy, so the hint can constrain the whole repair path.

## What Changed

After the injected hint, Claude Code + Kimi-k2.6 did the bounded repair:

- searched for AWS, GitHub, and HuggingFace token patterns;
- edited exactly the three contaminated files;
- covered the second HuggingFace-token occurrence inside the JSON diff string;
- checked that only the contaminated files appeared in `git diff --name-only`;
- did not rewrite history or delete git metadata.

The run summary:

```text
tool_event_count = 8
injection_count = 1
injection_reasons = ["Bash"]
api_retry_count = 0
agent_return_code = 0
```

The official verifier passed:

```text
3 passed
reward = 1.0
```

The successful trial is:

```text
runs/harbor_icl_baseline/harbor_runs_joint_failure/
  htd-dynamic-icl-sdk_live-debug_action-sanitize-git-repo-kimi-k2-6/
    sanitize-git-repo__JPnpGsH
```

## Why This Matters

This result is stronger than a teacher-success replay:

- the historical Codex + GPT-5.5 run did not pass;
- the historical Claude Code + Kimi-k2.6 run did not pass;
- the repair hint came from comparing failure footprints and locating the
  critical commitment boundary;
- the new runtime-injected run passed.

So the useful data object is not simply a successful trace. It can also be a
pair of failed traces whose errors are complementary. Harness-TrajecDebug turns
that pair into a process-aware repair hint.

That supports the project thesis:

> Debug-Trajectory selected examples can be useful because they encode the
> process decision that changes the trajectory, not just the final outcome.

## Current Limitation

This is still a same-task repair run, so it should be reported as a strong
mechanism result rather than held-out generalization. The next experiment is to
use this joint-failure selection strategy across a set of held-out Harbor-style
tasks and compare it against outcome-only and prompt-filtered selection.
