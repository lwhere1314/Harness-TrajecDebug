#!/usr/bin/env bash
set -euo pipefail

PACK_DIR="runs/harbor_icl_baseline"
TASK=""
MODEL="${MODEL:-kimi-k2.6}"
JOBS_DIR=""
CONTEXT_VARIANT="debug_trajectory"
INJECT_MODE="tool"
ENDPOINT_PROFILE="${HTD_ENDPOINT_PROFILE:-auto}"
SDK_LIVE_INTERCEPT_TOOLS=""
SDK_LIVE_INSTALL_TIMEOUT="${SDK_LIVE_INSTALL_TIMEOUT:-900}"
SETUP_TIMEOUT="1200"
AGENT_TIMEOUT="900"
VERIFIER_TIMEOUT="600"
FIRST_TURN_TIMEOUT="75"
CLEAN_EXISTING=1
DELETE_EXISTING=0
FORCE_CONTEXT_CALL=1
FORCE_BUILD=1
DRY_RUN=0
PREFLIGHT=0
PREFLIGHT_TIMEOUT="20"
HARBOR_BIN="${HARBOR_BIN:-/opt/miniconda3/envs/terminal-bench/bin/harbor}"

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_harbor_dynamic_icl.sh --task TASK [options]

Options:
  --pack-dir DIR          Generated ICL pack. Default: runs/harbor_icl_baseline
  --task NAME             Task name, e.g. break-filter-js-from-html
  --model NAME            Model name passed to Claude Code. Default: $MODEL or kimi-k2.6
  --jobs-dir DIR          Harbor output directory. Default: <pack-dir>/harbor_runs
  --context-variant NAME  Teacher card to expose at runtime. Default: debug_trajectory
  --inject-mode MODE      Runtime injection mode: tool, prelude, continue_after,
                          sdk_live, or hooks_live. Default: tool
  --endpoint-profile NAME Endpoint profile: auto, anthropic, seed-coding-plan,
                          token-plan, ark, dashscope, or kimi. Default: auto
  --sdk-live-intercept-tool NAME
                          In sdk_live mode, inject context before this tool name. May repeat.
  --sdk-live-install-timeout SEC
                          In sdk_live mode, allow this many seconds for in-container
                          claude-agent-sdk installation. Default: 900
  --setup-timeout SEC     Agent setup timeout. Default: 1200
  --agent-timeout SEC     Agent execution timeout. Default: 900
  --verifier-timeout SEC  Official verifier timeout. Default: 600
  --first-turn-timeout SEC
                          Timeout for the first no-context turn in continue_after mode. Default: 75
  --no-force-context      Make htd-context optional instead of required once
  --no-force-build        Reuse the task docker_image / cached image when possible
  --keep-existing         Do not archive an existing job directory before running
  --delete-existing       Delete an existing job directory instead of archiving.
                          Avoid this unless you intentionally want to discard
                          prior trial evidence.
  --dry-run               Print the generated Harbor config and exit
  --preflight             Check the model endpoint before launching Harbor
  --preflight-timeout SEC Endpoint preflight timeout. Default: 20
  -h, --help              Show this help

Environment:
  auto uses ANTHROPIC_* first, then SEED_CODING_PLAN_*, then TOKEN_PLAN_*.
  Explicit profiles read SEED_CODING_PLAN_*, TOKEN_PLAN_*, ARK_*,
  DASHSCOPE_*, KIMI_*, or ANTHROPIC_* variables. The script also sets
  PYTHONPATH so Harbor can import the local DynamicIclClaudeCode agent.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack-dir) PACK_DIR="$2"; shift 2 ;;
    --task) TASK="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --jobs-dir) JOBS_DIR="$2"; shift 2 ;;
    --context-variant) CONTEXT_VARIANT="$2"; shift 2 ;;
    --inject-mode) INJECT_MODE="$2"; shift 2 ;;
    --endpoint-profile) ENDPOINT_PROFILE="$2"; shift 2 ;;
    --sdk-live-intercept-tool)
      SDK_LIVE_INTERCEPT_TOOLS="${SDK_LIVE_INTERCEPT_TOOLS}${SDK_LIVE_INTERCEPT_TOOLS:+,}$2"
      shift 2
      ;;
    --sdk-live-install-timeout) SDK_LIVE_INSTALL_TIMEOUT="$2"; shift 2 ;;
    --setup-timeout) SETUP_TIMEOUT="$2"; shift 2 ;;
    --agent-timeout) AGENT_TIMEOUT="$2"; shift 2 ;;
    --verifier-timeout) VERIFIER_TIMEOUT="$2"; shift 2 ;;
    --first-turn-timeout) FIRST_TURN_TIMEOUT="$2"; shift 2 ;;
    --no-force-context) FORCE_CONTEXT_CALL=0; shift ;;
    --no-force-build) FORCE_BUILD=0; shift ;;
    --keep-existing) CLEAN_EXISTING=0; shift ;;
    --delete-existing) DELETE_EXISTING=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --preflight) PREFLIGHT=1; shift ;;
    --preflight-timeout) PREFLIGHT_TIMEOUT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$TASK" ]]; then
  echo "--task is required" >&2
  usage >&2
  exit 2
fi

if [[ "$INJECT_MODE" != "tool" && "$INJECT_MODE" != "prelude" && "$INJECT_MODE" != "continue_after" && "$INJECT_MODE" != "sdk_live" && "$INJECT_MODE" != "hooks_live" ]]; then
  echo "--inject-mode must be 'tool', 'prelude', 'continue_after', 'sdk_live', or 'hooks_live'" >&2
  exit 2
fi

if [[ -f "$HOME/.bashrc" ]]; then
  set +u
  # shellcheck disable=SC1090
  source "$HOME/.bashrc"
  set -u
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$REPO_ROOT/scripts/lib_endpoint_profile.sh"
apply_endpoint_profile "$ENDPOINT_PROFILE"
export ANTHROPIC_MODEL="$MODEL"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="${CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:-1}"
export CLAUDE_CODE_AUTO_COMPACT_WINDOW="${CLAUDE_CODE_AUTO_COMPACT_WINDOW:-262144}"

if [[ "$DRY_RUN" != "1" && ( -z "${ANTHROPIC_BASE_URL:-}" || -z "${ANTHROPIC_API_KEY:-}" ) ]]; then
  echo "Missing model API credentials for endpoint profile '$ENDPOINT_PROFILE'." >&2
  exit 1
fi

if [[ -z "$JOBS_DIR" ]]; then
  JOBS_DIR="$PACK_DIR/harbor_runs"
fi

TASK_DIR="$PACK_DIR/task_variants/no_icl/$TASK"
CONTEXT_PATH="$PACK_DIR/teacher_cards/$TASK/${CONTEXT_VARIANT}.md"

if [[ ! -d "$TASK_DIR" ]]; then
  echo "Missing no_icl task variant: $TASK_DIR" >&2
  echo "Build it first with scripts/build_harbor_icl_baseline.py --target-task $TASK" >&2
  exit 1
fi

if [[ ! -f "$CONTEXT_PATH" ]]; then
  echo "Missing runtime context card: $CONTEXT_PATH" >&2
  exit 1
fi

mkdir -p "$JOBS_DIR"

SAFE_MODEL="${MODEL//\//-}"
SAFE_MODEL="${SAFE_MODEL//./-}"
SAFE_CONTEXT="${CONTEXT_VARIANT//\//-}"
SAFE_CONTEXT="${SAFE_CONTEXT//./-}"
JOB_NAME="htd-dynamic-icl-${INJECT_MODE}-${SAFE_CONTEXT}-${TASK}-${SAFE_MODEL}"
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

python3 - "$CONFIG_PATH" "$JOB_NAME" "$JOBS_DIR" "$MODEL" "$ENDPOINT_PROFILE" "$SETUP_TIMEOUT" "$AGENT_TIMEOUT" "$VERIFIER_TIMEOUT" "$TASK_DIR" "$CONTEXT_PATH" "$FORCE_CONTEXT_CALL" "$FORCE_BUILD" "$INJECT_MODE" "$FIRST_TURN_TIMEOUT" "$SDK_LIVE_INTERCEPT_TOOLS" "$SDK_LIVE_INSTALL_TIMEOUT" <<'PY'
import json
import sys
from pathlib import Path

(
    config_path,
    job_name,
    jobs_dir,
    model,
    endpoint_profile,
    setup_timeout,
    agent_timeout,
    verifier_timeout,
    task_dir,
    context_path,
    force_context_call,
    force_build,
    inject_mode,
    first_turn_timeout,
    sdk_live_intercept_tools,
    sdk_live_install_timeout,
) = sys.argv[1:]

config = {
    "job_name": job_name,
    "jobs_dir": jobs_dir,
    "endpoint_profile": endpoint_profile,
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
            "import_path": "harness_trajecdebug.experiments.dynamic_icl_agent:DynamicIclClaudeCode",
            "model_name": model,
            "override_setup_timeout_sec": float(setup_timeout),
            "override_timeout_sec": float(agent_timeout),
            "kwargs": {
                "context_path": str(Path(context_path).resolve()),
                "force_context_call": force_context_call == "1",
                "inject_mode": inject_mode,
                "endpoint_profile": endpoint_profile,
                "first_turn_timeout_sec": int(float(first_turn_timeout)),
                "sdk_live_install_timeout_sec": int(float(sdk_live_install_timeout)),
                "sdk_live_intercept_tools": [
                    tool for tool in sdk_live_intercept_tools.split(",") if tool
                ],
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
echo "Inject mode: $INJECT_MODE"
echo "Endpoint profile: $ENDPOINT_PROFILE"
if [[ -n "$SDK_LIVE_INTERCEPT_TOOLS" ]]; then
  echo "SDK live intercept tools: $SDK_LIVE_INTERCEPT_TOOLS"
fi
if [[ "$INJECT_MODE" == "sdk_live" ]]; then
  echo "SDK live install timeout: $SDK_LIVE_INSTALL_TIMEOUT"
fi
echo "First-turn timeout: $FIRST_TURN_TIMEOUT"
echo "Verifier timeout: $VERIFIER_TIMEOUT"
echo "Job: $JOB_NAME"
echo "Config: $CONFIG_PATH"
echo "Runner log: $LOG_FILE"
echo "Agent: DynamicIclClaudeCode"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "Dry run: not launching Harbor."
  cat "$CONFIG_PATH"
  exit 0
fi

if [[ "$PREFLIGHT" == "1" ]]; then
  echo "Running model endpoint preflight..."
  python3 "$REPO_ROOT/scripts/check_model_endpoint.py" \
    --endpoint-profile "$ENDPOINT_PROFILE" \
    --model "$MODEL" \
    --timeout-sec "$PREFLIGHT_TIMEOUT"
fi

"$HARBOR_BIN" run --config "$CONFIG_PATH"
