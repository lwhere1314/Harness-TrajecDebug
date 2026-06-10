#!/usr/bin/env bash
set -euo pipefail

PACK_DIR="runs/harbor_icl_baseline"
TASK=""
CONTEXT_VARIANT="debug_action"
TRIGGER="ask_user_question"
JOBS_DIR=""
SETUP_TIMEOUT="1200"
AGENT_TIMEOUT="120"
VERIFIER_TIMEOUT="300"
FORCE_BUILD=1
CLEAN_EXISTING=1
DELETE_EXISTING=0
DRY_RUN=0
HARBOR_BIN="${HARBOR_BIN:-/opt/miniconda3/envs/terminal-bench/bin/harbor}"

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_harbor_runtime_smoke.sh --task TASK [options]

Purpose:
  Run a no-model Harbor smoke test for runtime ICL mechanics. The agent
  simulates a live controller trigger such as AskUserQuestion, records the
  injected context decision, materializes the Debug-Action artifact in Docker,
  and lets the official verifier run. This is mechanism evidence, not a model
  reward datapoint.

Options:
  --pack-dir DIR          ICL pack. Default: runs/harbor_icl_baseline
  --task NAME             Task name, e.g. gcode-to-text
  --context-variant NAME  Teacher card to materialize. Default: debug_action
  --trigger NAME          ask_user_question, WebSearch, WebFetch, or dependency_install.
                          Default: ask_user_question
  --jobs-dir DIR          Harbor output directory. Default: <pack-dir>/harbor_runs_runtime_smoke
  --setup-timeout SEC     Agent setup timeout. Default: 1200
  --agent-timeout SEC     Agent execution timeout. Default: 120
  --verifier-timeout SEC  Official verifier timeout. Default: 300
  --no-force-build        Reuse cached image when possible
  --keep-existing         Do not archive an existing job directory before running
  --delete-existing       Delete an existing job directory instead of archiving
  --dry-run               Print generated Harbor config and exit
  -h, --help              Show help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack-dir) PACK_DIR="$2"; shift 2 ;;
    --task) TASK="$2"; shift 2 ;;
    --context-variant) CONTEXT_VARIANT="$2"; shift 2 ;;
    --trigger) TRIGGER="$2"; shift 2 ;;
    --jobs-dir) JOBS_DIR="$2"; shift 2 ;;
    --setup-timeout) SETUP_TIMEOUT="$2"; shift 2 ;;
    --agent-timeout) AGENT_TIMEOUT="$2"; shift 2 ;;
    --verifier-timeout) VERIFIER_TIMEOUT="$2"; shift 2 ;;
    --no-force-build) FORCE_BUILD=0; shift ;;
    --keep-existing) CLEAN_EXISTING=0; shift ;;
    --delete-existing) DELETE_EXISTING=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$TASK" ]]; then
  echo "--task is required" >&2
  usage >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -z "$JOBS_DIR" ]]; then
  JOBS_DIR="$PACK_DIR/harbor_runs_runtime_smoke"
fi

TASK_DIR="$PACK_DIR/task_variants/no_icl/$TASK"
CONTEXT_PATH="$PACK_DIR/teacher_cards/$TASK/${CONTEXT_VARIANT}.md"

if [[ ! -d "$TASK_DIR" ]]; then
  echo "Missing no_icl task variant: $TASK_DIR" >&2
  exit 1
fi

if [[ ! -f "$CONTEXT_PATH" ]]; then
  echo "Missing context card: $CONTEXT_PATH" >&2
  exit 1
fi

SAFE_CONTEXT="${CONTEXT_VARIANT//\//-}"
SAFE_CONTEXT="${SAFE_CONTEXT//./-}"
SAFE_TRIGGER="${TRIGGER//\//-}"
SAFE_TRIGGER="${SAFE_TRIGGER//./-}"
JOB_NAME="htd-runtime-smoke-${SAFE_TRIGGER}-${SAFE_CONTEXT}-${TASK}"
CONFIG_PATH="/private/tmp/${JOB_NAME}.json"
if [[ "$DRY_RUN" == "1" ]]; then
  LOG_FILE="/private/tmp/${JOB_NAME}.dry-run.log"
else
  LOG_FILE="$JOBS_DIR/$JOB_NAME/runner.log"
fi

if [[ -e "$JOBS_DIR/$JOB_NAME" ]]; then
  if [[ "$DRY_RUN" == "1" ]]; then
    :
  elif [[ "$CLEAN_EXISTING" == "1" ]]; then
    if [[ "$DELETE_EXISTING" == "1" ]]; then
      rm -rf "$JOBS_DIR/$JOB_NAME"
    else
      ARCHIVE_DIR="$JOBS_DIR/_archived"
      ARCHIVE_STAMP="$(date +%Y%m%dT%H%M%S)"
      ARCHIVE_PATH="$ARCHIVE_DIR/${JOB_NAME}-${ARCHIVE_STAMP}"
      mkdir -p "$ARCHIVE_DIR"
      mv "$JOBS_DIR/$JOB_NAME" "$ARCHIVE_PATH"
      echo "Archived existing job dir to: $ARCHIVE_PATH"
    fi
  fi
fi

mkdir -p "$(dirname "$LOG_FILE")"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python3 - "$CONFIG_PATH" "$JOB_NAME" "$JOBS_DIR" "$SETUP_TIMEOUT" "$AGENT_TIMEOUT" "$VERIFIER_TIMEOUT" "$TASK_DIR" "$CONTEXT_PATH" "$TRIGGER" "$FORCE_BUILD" <<'PY'
import json
import sys
from pathlib import Path

(
    config_path,
    job_name,
    jobs_dir,
    setup_timeout,
    agent_timeout,
    verifier_timeout,
    task_dir,
    context_path,
    trigger,
    force_build,
) = sys.argv[1:]

config = {
    "job_name": job_name,
    "jobs_dir": jobs_dir,
    "n_attempts": 1,
    "orchestrator": {
        "type": "local",
        "n_concurrent_trials": 1,
    },
    "environment": {
        "type": "docker",
        "force_build": force_build == "1",
    },
    "verifier": {
        "override_timeout_sec": float(verifier_timeout),
    },
    "agents": [
        {
            "import_path": "harness_trajecdebug.experiments.runtime_injection_smoke_agent:RuntimeInjectionSmokeAgent",
            "model_name": "none",
            "override_setup_timeout_sec": float(setup_timeout),
            "override_timeout_sec": float(agent_timeout),
            "kwargs": {
                "context_path": str(Path(context_path).resolve()),
                "trigger": trigger,
            },
        }
    ],
    "tasks": [{"path": task_dir}],
}

Path(config_path).write_text(json.dumps(config, indent=2), encoding="utf-8")
PY

exec > >(tee -a "$LOG_FILE") 2>&1

echo "Harbor: $HARBOR_BIN"
echo "Task: $TASK_DIR"
echo "Context: $CONTEXT_PATH"
echo "Trigger: $TRIGGER"
echo "Job: $JOB_NAME"
echo "Config: $CONFIG_PATH"
echo "Runner log: $LOG_FILE"
echo "Agent: RuntimeInjectionSmokeAgent"
echo "Verifier timeout: ${VERIFIER_TIMEOUT}s"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "Dry run: not launching Harbor."
  cat "$CONFIG_PATH"
  exit 0
fi

"$HARBOR_BIN" run --config "$CONFIG_PATH"
