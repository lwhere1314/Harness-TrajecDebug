# Agent Migration Runbook

This file is an executable handoff for an agent that must migrate and run the
current Harness-TrajecDebug workflow on another server.

The target workflow is:

```text
choose harness
  -> run Harbor task or dataset
  -> normalize trajectory through Harness-TrajecDebug
  -> find critical step and repair hint
  -> run a repair/improvement pass with Claude Code SDK/runner and Codex SDK/runner
  -> export every run to the ATIF trajectory viewer
```

## Non-Negotiables

- Never write API keys into repo files, markdown files, run manifests, shell
  history, or final reports. Keep secrets in the process environment or a
  server-side secret store.
- Do not delete existing Harbor runs, cached datasets, viewer bundles, or user
  worktrees unless the owner explicitly asks.
- Keep all server-specific paths configurable through environment variables.
- Preserve every failed run. Failed traces are useful input for
  Harness-TrajecDebug.
- Record the exact commands, run paths, rewards, diagnosis files, and viewer
  bundle ids in the final report.

## One-Command Preflight

After cloning Harness-TrajecDebug, run this first:

```bash
cd "$HTD_ROOT"
bash scripts/preflight.sh
```

The script detects the current host without printing secret values. It checks
Python, Node/npm, Harbor, Docker, jq, rsync, the ATIF viewer checkout, Seed
environment variables, optional Codex auth, Claude Code binary hints, and the
Harness-TrajecDebug harness inventory.

If it prints `[FAIL]`, fix those blockers before running Harbor. `[WARN]` items
are usually model- or server-specific choices, such as `CODEX_MODEL`.

## Expected Repositories

Set these variables first. Replace the remote URLs with the server owner's
actual remotes.

```bash
export HTD_ROOT="${HTD_ROOT:-$HOME/projects/Harness-TrajecDebug}"
export HTD_REMOTE="${HTD_REMOTE:-REPLACE_WITH_HARNESS_TRAJECDEBUG_REMOTE}"

export ATIF_VIEWER_ROOT="${ATIF_VIEWER_ROOT:-$HOME/projects/ATIF-trajectory-viewer}"
export ATIF_VIEWER_REMOTE="${ATIF_VIEWER_REMOTE:-REPLACE_WITH_ATIF_VIEWER_REMOTE}"

export HARBOR_ROOT="${HARBOR_ROOT:-$HOME/harbor}"
export HARBOR_RUNS_DIR="${HARBOR_RUNS_DIR:-$HARBOR_ROOT/runs}"
export HARBOR_DATASETS_DIR="${HARBOR_DATASETS_DIR:-$HARBOR_ROOT/datasets}"
```

Clone or update the repos:

```bash
mkdir -p "$(dirname "$HTD_ROOT")" "$(dirname "$ATIF_VIEWER_ROOT")"

if [ ! -d "$HTD_ROOT/.git" ]; then
  git clone "$HTD_REMOTE" "$HTD_ROOT"
else
  git -C "$HTD_ROOT" pull --ff-only
fi

if [ ! -d "$ATIF_VIEWER_ROOT/.git" ]; then
  git clone "$ATIF_VIEWER_REMOTE" "$ATIF_VIEWER_ROOT"
else
  git -C "$ATIF_VIEWER_ROOT" pull --ff-only
fi
```

If the migration source is a local machine rather than a remote repository, use
`rsync -a --exclude .git --exclude node_modules --exclude .venv` from the source
machine, then initialize the target repo as needed. Do not rsync secret files.

## Install Harness-TrajecDebug

Use Python 3.10 or newer.

```bash
cd "$HTD_ROOT"
python3 -m pip install -e .
make check
```

If the shell cannot find `harness-trajdebug` after editable install, use
`PYTHONPATH=src python3 -m harness_trajecdebug.cli` as a drop-in replacement.

Expected result:

- unit tests pass
- bundled example diagnoses run
- `py_compile` passes

If `make check` is unavailable, run:

```bash
python3 -m unittest discover -s tests
python3 -m py_compile src/harness_trajecdebug/*.py
```

## Install And Verify The ATIF Viewer

```bash
cd "$ATIF_VIEWER_ROOT"
npm install
npm run lint
npm run build
```

Expected result:

- `npm run lint` passes
- `npm run build` passes

The viewer is a static Vite app. For manual inspection:

```bash
cd "$ATIF_VIEWER_ROOT"
npm run dev -- --host 0.0.0.0 --port "${ATIF_VIEWER_PORT:-5173}"
```

## Locate Harbor

Prefer the local terminal-bench conda Harbor binary if it exists, otherwise use
the first `harbor` on PATH.

```bash
if [ -x /opt/miniconda3/envs/terminal-bench/bin/harbor ]; then
  export HARBOR_CLI=/opt/miniconda3/envs/terminal-bench/bin/harbor
else
  export HARBOR_CLI="$(command -v harbor)"
fi

test -n "$HARBOR_CLI"
"$HARBOR_CLI" --version
mkdir -p "$HARBOR_RUNS_DIR" "$HARBOR_DATASETS_DIR"
```

For Docker-backed Harbor runs, also verify Docker:

```bash
docker version
docker info
```

If the server uses a custom Docker socket, export `DOCKER_HOST` before running
Harbor.

## Configure Model Credentials

For Kimi through an Anthropic-compatible Claude Code route, map the Seed
variables into the names Claude Code expects.

```bash
set +x
test -n "$SEED_CODING_PLAN_BASE_URL"
test -n "$SEED_CODING_PLAN_API_KEY"

export ANTHROPIC_BASE_URL="$SEED_CODING_PLAN_BASE_URL"
export ANTHROPIC_API_KEY="$SEED_CODING_PLAN_API_KEY"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
set -x
```

If the task image is `linux/amd64`, use an x86_64 Claude Code binary. On Apple
Silicon or ARM servers this is a common failure mode.

```bash
if [ -n "${HARBOR_CLAUDE_CODE_BINARY:-}" ]; then
  file "$HARBOR_CLAUDE_CODE_BINARY"
fi
```

For Codex SDK/runner, configure the OpenAI/Codex credentials required by that
server. Do not print the values.

```bash
set +x
test -n "${OPENAI_API_KEY:-}" || true
set -x
```

## Discover Available Harnesses

```bash
cd "$HTD_ROOT"
harness-trajdebug harnesses --ssd-root "${SSD_ROOT:-/Volumes/SSD}" \
  | tee artifacts-harnesses.json
```

Interpretation:

- `claude-code` available means Harbor can usually produce ATIF
  `agent/trajectory.json`.
- `kimi-code` may appear as a Kimi model route through Claude Code even when a
  standalone `kimi-code` executable is not installed.
- `codex` available means Codex host/Harbor traces can usually be normalized as
  JSONL.

If a desired harness is missing, install it or set its binary path before
continuing.

## Choose A Harbor Task

The pipeline supports registry-backed datasets such as `swebenchpro@1.0` and
local Harbor-compatible task directories.

Registry task example:

```bash
export DATASET="${DATASET:-swebenchpro@1.0}"
export TASK_NAME="${TASK_NAME:-instance_ansible__ansible-cd473dfb2fdbc97acf3293c134b21cbbcfa89ec3-vba6da65a0f3baefda7a058ebbd0a8dcafb8512f5}"
export MODEL="${MODEL:-kimi-k2.6}"
```

Local task example:

```bash
export TASK_PATH="${TASK_PATH:-$HARBOR_DATASETS_DIR/terminal-bench-2.1-proxy/tasks/train-fasttext}"
harness-trajdebug harbor-tasks --root "$(dirname "$TASK_PATH")" --limit 5
```

For a local dataset directory, set `LOCAL_DATASET_PATH` and `TASK_NAME`:

```bash
export LOCAL_DATASET_PATH="${LOCAL_DATASET_PATH:-$HARBOR_DATASETS_DIR/terminal-bench-2.1-proxy/tasks}"
export TASK_NAME="${TASK_NAME:-train-fasttext}"
```

## Run Baseline Harbor Trial

Use a stable job name. Keep it lowercase and filesystem-safe.

```bash
export HARNESS="${HARNESS:-claude-code}"
export TASK_LABEL="${TASK_NAME:-$(basename "${TASK_PATH:-task}")}"
export SOURCE_LABEL="${DATASET%%@*}"
if [ -z "$SOURCE_LABEL" ]; then
  SOURCE_LABEL="$(basename "${LOCAL_DATASET_PATH:-${TASK_PATH:-local-task}}")"
fi
export JOB_NAME="${JOB_NAME:-${SOURCE_LABEL}-${TASK_LABEL}-${HARNESS}-${MODEL}-baseline}"
export JOB_NAME="$(printf '%s' "$JOB_NAME" | tr '/:@ ' '----')"
```

Registry-backed run:

```bash
"$HARBOR_CLI" run \
  -d "$DATASET" \
  -t "$TASK_NAME" \
  -a "$HARNESS" \
  -m "$MODEL" \
  --jobs-dir "$HARBOR_RUNS_DIR" \
  --job-name "$JOB_NAME" \
  --n-concurrent 1 \
  --export-traces \
  --export-verifier-metadata
```

Single local task run:

```bash
"$HARBOR_CLI" run \
  -p "$TASK_PATH" \
  -a "$HARNESS" \
  -m "$MODEL" \
  --jobs-dir "$HARBOR_RUNS_DIR" \
  --job-name "$JOB_NAME" \
  --n-concurrent 1 \
  --export-traces \
  --export-verifier-metadata
```

Local dataset run with task filter:

```bash
"$HARBOR_CLI" run \
  -p "$LOCAL_DATASET_PATH" \
  -t "$TASK_NAME" \
  -a "$HARNESS" \
  -m "$MODEL" \
  --jobs-dir "$HARBOR_RUNS_DIR" \
  --job-name "$JOB_NAME" \
  --n-concurrent 1 \
  --export-traces \
  --export-verifier-metadata
```

After completion:

```bash
export BASELINE_RUN="$HARBOR_RUNS_DIR/$JOB_NAME"
find "$BASELINE_RUN" -maxdepth 3 -type f \
  \( -name result.json -o -name trajectory.json -o -name codex-exec.jsonl -o -name reward.txt \) \
  -print
```

## Normalize And Diagnose

```bash
cd "$HTD_ROOT"
export DIAG_DIR="$HTD_ROOT/artifacts/diagnoses/$JOB_NAME"
mkdir -p "$DIAG_DIR"

harness-trajdebug harbor-import \
  --run "$BASELINE_RUN" \
  --output-dir "$DIAG_DIR" \
  --diagnose
```

Extract the critical step and repair hint:

```bash
export DIAGNOSIS_JSON="$(find "$DIAG_DIR/diagnoses" -type f -name '*-diagnosis.json' | head -1)"
test -f "$DIAGNOSIS_JSON"

jq '{
  run_id,
  task_family,
  outcome,
  final_failure,
  failure_patterns,
  critical_step,
  repair_hint
}' "$DIAGNOSIS_JSON"
```

The diagnosis is acceptable only when:

- `outcome` is present
- `final_failure` is present for failed runs
- `critical_step` is either a concrete step object or the run truly has no
  detectable critical failure
- `repair_hint` is present for failed runs

## Build A Repair Brief

Create a compact brief that can be injected into a second pass. This file must
not include secrets.

```bash
export REPAIR_BRIEF="$DIAG_DIR/repair-brief.md"

python3 - "$DIAGNOSIS_JSON" "$REPAIR_BRIEF" <<'PY'
import json
import sys
from pathlib import Path

diagnosis = json.loads(Path(sys.argv[1]).read_text())
target = Path(sys.argv[2])

critical = diagnosis.get("critical_step") or {}
patterns = diagnosis.get("failure_patterns") or []

lines = [
    "# Repair Brief",
    "",
    f"Outcome: {diagnosis.get('outcome')}",
    f"Task family: {diagnosis.get('task_family')}",
    f"Final failure: {diagnosis.get('final_failure')}",
    "",
    "## Critical Step",
    json.dumps(critical, ensure_ascii=False, indent=2),
    "",
    "## Failure Patterns",
    json.dumps(patterns, ensure_ascii=False, indent=2),
    "",
    "## Repair Hint",
    diagnosis.get("repair_hint") or "No repair hint emitted.",
    "",
    "## Instruction For The Next Agent",
    "Use this brief as process feedback. Do not blindly patch around tests.",
    "Reproduce the failure, inspect the implicated step, implement the smallest",
    "task-correct fix, and run the official or closest available verifier.",
]

target.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(target)
PY
```

## Create A Context-Learning Task Copy

For registry-backed tasks, get the local task path from the Harbor trial
`result.json`.

```bash
export TRIAL_RESULT="$(find "$BASELINE_RUN" -mindepth 2 -maxdepth 2 -name result.json | head -1)"
export SOURCE_TASK_PATH="$(jq -r '.config.task.path // empty' "$TRIAL_RESULT")"

if [ -z "$SOURCE_TASK_PATH" ] || [ ! -d "$SOURCE_TASK_PATH" ]; then
  echo "Could not infer SOURCE_TASK_PATH from $TRIAL_RESULT"
  echo "Search Harbor cache/datasets for the task and export SOURCE_TASK_PATH manually."
  exit 2
fi
```

Copy the task and prepend the repair brief to `instruction.md`.

```bash
export IMPROVE_TASK="$HTD_ROOT/artifacts/improvement-tasks/$JOB_NAME/$TASK_NAME"
mkdir -p "$(dirname "$IMPROVE_TASK")"
rsync -a --delete "$SOURCE_TASK_PATH/" "$IMPROVE_TASK/"

python3 - "$IMPROVE_TASK/instruction.md" "$REPAIR_BRIEF" <<'PY'
import sys
from pathlib import Path

instruction = Path(sys.argv[1])
brief = Path(sys.argv[2]).read_text(encoding="utf-8")
original = instruction.read_text(encoding="utf-8")

marker = "<!-- harness-trajecdebug-repair-brief -->"
if marker not in original:
    instruction.write_text(
        marker + "\n" +
        brief + "\n\n" +
        "# Original Task Instruction\n\n" +
        original,
        encoding="utf-8",
    )
print(instruction)
PY
```

This is the portable fallback when Harbor does not expose an agent prompt
injection knob. If the target server already has an official Claude Code SDK or
Codex SDK wrapper that can add context without mutating the task copy, prefer
that wrapper and keep the same `REPAIR_BRIEF`.

## Run Claude Code Improvement Pass

Prefer the server's Claude Code SDK wrapper if it exists. If not, use the Harbor
`claude-code` runner, which is the current supported path and produces ATIF
traces.

```bash
export CLAUDE_IMPROVE_JOB="${JOB_NAME}-repair-claude-code-${MODEL}"
export CLAUDE_IMPROVE_JOB="$(printf '%s' "$CLAUDE_IMPROVE_JOB" | tr '/:@ ' '----')"
export CLAUDE_IMPROVE_RUN="$HARBOR_RUNS_DIR/$CLAUDE_IMPROVE_JOB"

"$HARBOR_CLI" run \
  -p "$IMPROVE_TASK" \
  -a claude-code \
  -m "$MODEL" \
  --jobs-dir "$HARBOR_RUNS_DIR" \
  --job-name "$CLAUDE_IMPROVE_JOB" \
  --n-concurrent 1 \
  --export-traces \
  --export-verifier-metadata
```

Then diagnose it:

```bash
export CLAUDE_DIAG_DIR="$HTD_ROOT/artifacts/diagnoses/$CLAUDE_IMPROVE_JOB"
harness-trajdebug harbor-import \
  --run "$CLAUDE_IMPROVE_RUN" \
  --output-dir "$CLAUDE_DIAG_DIR" \
  --diagnose
```

## Run Codex Improvement Pass

Prefer the server's Codex SDK wrapper if it exists. If not, use Harbor's `codex`
agent when available. The expected trace is usually `agent/codex-exec.jsonl`,
which Harness-TrajecDebug can normalize.

```bash
: "${CODEX_MODEL:?Set CODEX_MODEL for the target server before running Codex.}"
export CODEX_IMPROVE_JOB="${JOB_NAME}-repair-codex-${CODEX_MODEL}"
export CODEX_IMPROVE_JOB="$(printf '%s' "$CODEX_IMPROVE_JOB" | tr '/:@ ' '----')"
export CODEX_IMPROVE_RUN="$HARBOR_RUNS_DIR/$CODEX_IMPROVE_JOB"

"$HARBOR_CLI" run \
  -p "$IMPROVE_TASK" \
  -a codex \
  -m "$CODEX_MODEL" \
  --jobs-dir "$HARBOR_RUNS_DIR" \
  --job-name "$CODEX_IMPROVE_JOB" \
  --n-concurrent 1 \
  --export-traces \
  --export-verifier-metadata
```

Then diagnose it:

```bash
export CODEX_DIAG_DIR="$HTD_ROOT/artifacts/diagnoses/$CODEX_IMPROVE_JOB"
harness-trajdebug harbor-import \
  --run "$CODEX_IMPROVE_RUN" \
  --output-dir "$CODEX_DIAG_DIR" \
  --diagnose
```

If the Codex run fails because the Harbor Codex agent is not installed, record
the failure and run the server's Codex SDK/CLI directly against a disposable
workspace created from `$IMPROVE_TASK`. Export its session JSONL as
`agent/codex-exec.jsonl` under a Harbor-like trial directory, then run
`harness-trajdebug harbor-import` on that directory.

## Compare Baseline And Improvement Runs

```bash
python3 - "$BASELINE_RUN" "$CLAUDE_IMPROVE_RUN" "$CODEX_IMPROVE_RUN" <<'PY'
import json
import sys
from pathlib import Path

def trial_results(run_root):
    root = Path(run_root)
    rows = []
    for result_path in sorted(root.glob("*/result.json")):
        try:
            result = json.loads(result_path.read_text())
        except Exception as exc:
            rows.append((result_path, "read-error", str(exc)))
            continue
        verifier = result.get("verifier_result") or {}
        rewards = verifier.get("rewards") or {}
        reward = rewards.get("reward")
        if reward is None:
            reward_path = result_path.parent / "verifier" / "reward.txt"
            reward = reward_path.read_text().strip() if reward_path.exists() else None
        rows.append((result_path.parent.name, reward, result.get("error")))
    return rows

for run_root in sys.argv[1:]:
    print(f"\n## {run_root}")
    for name, reward, error in trial_results(run_root):
        print(f"{name}\treward={reward}\terror={error}")
PY
```

The improvement is considered useful if any of these improve:

- verifier reward
- required tests passed
- final failure becomes narrower or more actionable
- critical step moves later in the trajectory after a real fix attempt
- the repair hint becomes more specific after the second pass

## Export Runs To ATIF Viewer

Export the baseline and every improvement run.

```bash
cd "$HTD_ROOT"

harness-trajdebug atif-viewer-export \
  --run "$BASELINE_RUN" \
  --viewer-root "$ATIF_VIEWER_ROOT" \
  --label "$JOB_NAME-baseline" \
  --diagnose

harness-trajdebug atif-viewer-export \
  --run "$CLAUDE_IMPROVE_RUN" \
  --viewer-root "$ATIF_VIEWER_ROOT" \
  --label "$CLAUDE_IMPROVE_JOB" \
  --diagnose

harness-trajdebug atif-viewer-export \
  --run "$CODEX_IMPROVE_RUN" \
  --viewer-root "$ATIF_VIEWER_ROOT" \
  --label "$CODEX_IMPROVE_JOB" \
  --diagnose
```

Verify the viewer index:

```bash
harness-trajdebug atif-viewer-info --viewer-root "$ATIF_VIEWER_ROOT"

cd "$ATIF_VIEWER_ROOT"
npm run lint
npm run build
npm run dev -- --host 0.0.0.0 --port "${ATIF_VIEWER_PORT:-5173}"
```

The exported files live under:

```text
$ATIF_VIEWER_ROOT/public/local/local-bundles.json
$ATIF_VIEWER_ROOT/public/local/runs/<bundle-id>/viewer-bundle.json
$ATIF_VIEWER_ROOT/public/local/runs/<bundle-id>/payloads/*.json
$ATIF_VIEWER_ROOT/public/local/runs/<bundle-id>/normalized/*.json
$ATIF_VIEWER_ROOT/public/local/runs/<bundle-id>/diagnoses/*-diagnosis.json
```

## Final Report Template

The executing agent must finish with this report:

```text
Migration status:
- Harness-TrajecDebug commit/path:
- ATIF viewer commit/path:
- Harbor CLI/version:
- Docker host:

Harness inventory:
- claude-code:
- kimi-code route:
- codex:

Task:
- dataset/path:
- task name:

Baseline:
- run path:
- reward:
- diagnosis:
- critical step:
- repair hint:

Claude Code repair pass:
- run path:
- reward:
- diagnosis:
- changed vs baseline:

Codex repair pass:
- run path:
- reward:
- diagnosis:
- changed vs baseline:

Viewer:
- local index:
- bundle ids:
- dev URL:

Validation:
- Harness-TrajecDebug tests:
- viewer lint:
- viewer build:

Open issues:
- missing SDKs:
- failed installs:
- verifier/task problems:
```

## Troubleshooting Notes

- `RewardFileNotFoundError`: preserve the run, inspect verifier stdout/stderr,
  and treat the failure as a task/verifier failure. Do not discard the trace.
- Missing `agent/trajectory.json`: check whether the harness emitted
  `agent/codex-exec.jsonl` or `agent/local_codex_sessions/*.jsonl`.
- SWE-bench Pro task aliases: Harbor registry task names are often long
  `instance_*` ids. If a short alias fails, search downloaded/cache task
  metadata and use the real registry task name.
- Claude binary architecture: if the task image is `linux/amd64`, use an x86_64
  Claude Code binary. An ARM binary inside an amd64 container fails before the
  agent starts.
- Network errors to Anthropic-compatible endpoints: verify proxy settings,
  DNS, and that `ANTHROPIC_BASE_URL` and `ANTHROPIC_API_KEY` are present in the
  environment visible to Harbor containers.
- Viewer public data: the exporter redacts key-like fields and clips large
  payloads, but still inspect generated bundles before publishing them.
