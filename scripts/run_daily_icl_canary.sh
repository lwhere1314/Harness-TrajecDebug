#!/usr/bin/env bash
set -euo pipefail

PACK_DIR="runs/harbor_icl_baseline"
TASK="count-dataset-tokens"
MODEL="${MODEL:-kimi-k2.6}"
CONTEXT_VARIANT="debug_action"
INJECT_MODE="continue_after"
ENDPOINT_PROFILE="${HTD_ENDPOINT_PROFILE:-auto}"
JOBS_DIR=""
PREFLIGHT_TIMEOUT="20"
RUN_HARBOR=0
SKIP_PREFLIGHT=0
FORCE_RUN=0
FIRST_TURN_TIMEOUT="75"
VERIFIER_TIMEOUT="600"
SDK_LIVE_INTERCEPT_TOOLS=("WebSearch" "WebFetch")

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_daily_icl_canary.sh [options]

Purpose:
  Daily-safe canary for runtime ICL baselines. It checks the model endpoint,
  replays the live controller against synthetic trigger events, and only runs
  Harbor when explicitly requested with --run.

Options:
  --pack-dir DIR              ICL pack. Default: runs/harbor_icl_baseline
  --task NAME                 Task canary. Default: count-dataset-tokens
  --model NAME                Model name. Default: $MODEL or kimi-k2.6
  --context-variant NAME      Teacher card. Default: debug_action
  --inject-mode MODE          tool, prelude, continue_after, sdk_live, or hooks_live.
                              Default: continue_after
  --endpoint-profile NAME     Endpoint profile: auto, anthropic,
                              seed-coding-plan, token-plan, ark, dashscope,
                              or kimi. Default: auto
  --jobs-dir DIR              Harbor output dir. Default: <pack-dir>/harbor_runs
  --first-turn-timeout SEC    continue_after first-turn timeout. Default: 75
  --verifier-timeout SEC      Official verifier timeout. Default: 600
  --sdk-live-intercept-tool NAME
                              sdk_live intercept tool. May repeat.
                              Default: WebSearch and WebFetch
  --preflight-timeout SEC     Endpoint preflight timeout. Default: 20
  --skip-preflight            Do not check the endpoint.
  --force-run                 Run Harbor even when preflight fails.
  --run                       Actually launch Harbor. Without --run this only
                              performs preflight + replay checks.
  -h, --help                  Show help.

Environment:
  auto uses ANTHROPIC_* first, then SEED_CODING_PLAN_*, then TOKEN_PLAN_*.
  Explicit profiles read SEED_CODING_PLAN_*, TOKEN_PLAN_*, ARK_*,
  DASHSCOPE_*, KIMI_*, or ANTHROPIC_* variables.

This script never prints API keys. Keep credentials in the shell environment,
~/.bashrc, Keychain, or another local secret store.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack-dir) PACK_DIR="$2"; shift 2 ;;
    --task) TASK="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --context-variant) CONTEXT_VARIANT="$2"; shift 2 ;;
    --inject-mode) INJECT_MODE="$2"; shift 2 ;;
    --endpoint-profile) ENDPOINT_PROFILE="$2"; shift 2 ;;
    --jobs-dir) JOBS_DIR="$2"; shift 2 ;;
    --first-turn-timeout) FIRST_TURN_TIMEOUT="$2"; shift 2 ;;
    --verifier-timeout) VERIFIER_TIMEOUT="$2"; shift 2 ;;
    --sdk-live-intercept-tool)
      if [[ ${#SDK_LIVE_INTERCEPT_TOOLS[@]} -eq 2 && "${SDK_LIVE_INTERCEPT_TOOLS[0]}" == "WebSearch" && "${SDK_LIVE_INTERCEPT_TOOLS[1]}" == "WebFetch" ]]; then
        SDK_LIVE_INTERCEPT_TOOLS=()
      fi
      SDK_LIVE_INTERCEPT_TOOLS+=("$2")
      shift 2
      ;;
    --preflight-timeout) PREFLIGHT_TIMEOUT="$2"; shift 2 ;;
    --skip-preflight) SKIP_PREFLIGHT=1; shift ;;
    --force-run) FORCE_RUN=1; shift ;;
    --run) RUN_HARBOR=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$INJECT_MODE" != "tool" && "$INJECT_MODE" != "prelude" && "$INJECT_MODE" != "continue_after" && "$INJECT_MODE" != "sdk_live" && "$INJECT_MODE" != "hooks_live" ]]; then
  echo "--inject-mode must be tool, prelude, continue_after, sdk_live, or hooks_live" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -f "$HOME/.bashrc" ]]; then
  set +u
  # shellcheck disable=SC1090
  source "$HOME/.bashrc"
  set -u
fi

# shellcheck disable=SC1091
source "$REPO_ROOT/scripts/lib_endpoint_profile.sh"
apply_endpoint_profile "$ENDPOINT_PROFILE"

if [[ -z "$JOBS_DIR" ]]; then
  if [[ "$INJECT_MODE" == "sdk_live" ]]; then
    JOBS_DIR="$PACK_DIR/harbor_runs_sdk_live"
  else
    JOBS_DIR="$PACK_DIR/harbor_runs"
  fi
fi

SAFE_MODEL="${MODEL//\//-}"
SAFE_MODEL="${SAFE_MODEL//./-}"
SAFE_CONTEXT="${CONTEXT_VARIANT//\//-}"
SAFE_CONTEXT="${SAFE_CONTEXT//./-}"
JOB_NAME="htd-dynamic-icl-${INJECT_MODE}-${SAFE_CONTEXT}-${TASK}-${SAFE_MODEL}"
CONTEXT_PATH="$PACK_DIR/teacher_cards/$TASK/$CONTEXT_VARIANT.md"
CANARY_DIR="$PACK_DIR/daily_canary/$JOB_NAME"
mkdir -p "$CANARY_DIR"

echo "== Harness-TrajecDebug Daily ICL Canary =="
echo "Task: $TASK"
echo "Model: $MODEL"
echo "Inject mode: $INJECT_MODE"
echo "Endpoint profile: $ENDPOINT_PROFILE"
echo "Context: $CONTEXT_PATH"
echo "Jobs dir: $JOBS_DIR"
echo "Canary dir: $CANARY_DIR"
echo "Verifier timeout: ${VERIFIER_TIMEOUT}s"

if [[ ! -f "$CONTEXT_PATH" ]]; then
  echo "Missing context card: $CONTEXT_PATH" >&2
  exit 1
fi

PREFLIGHT_OK=1
if [[ "$SKIP_PREFLIGHT" == "0" ]]; then
  echo
  echo "== Endpoint preflight =="
  if scripts/check_model_endpoint.py \
    --endpoint-profile "$ENDPOINT_PROFILE" \
    --model "$MODEL" \
    --timeout-sec "$PREFLIGHT_TIMEOUT" \
    --allow-fail > "$CANARY_DIR/preflight.json"; then
    cat "$CANARY_DIR/preflight.json"
  fi
  PREFLIGHT_OK=$(python3 - "$CANARY_DIR/preflight.json" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text())
print(0 if data.get("ok") else 1)
PY
)
else
  echo
  echo "== Endpoint preflight skipped =="
  PREFLIGHT_OK=0
fi

echo
echo "== Live-controller replay =="
WEB_REPLAY_ARGS=()
for tool in "${SDK_LIVE_INTERCEPT_TOOLS[@]}"; do
  WEB_REPLAY_ARGS+=(--intercept-tool "$tool")
done
if [[ "$INJECT_MODE" == "hooks_live" ]]; then
  scripts/replay_live_icl_hook.py \
    --context-path "$CONTEXT_PATH" \
    --session-start \
    > "$CANARY_DIR/replay-session-start.json"
  scripts/replay_live_icl_hook.py \
    --context-path "$CONTEXT_PATH" \
    --tool-name WebSearch \
    --tool-input-json '{"query":"daily canary trigger"}' \
    --state-path "$CANARY_DIR/replay-websearch-state.json" \
    --event-log "$CANARY_DIR/replay-websearch-events.jsonl" \
    "${WEB_REPLAY_ARGS[@]}" > "$CANARY_DIR/replay-websearch.json"
  scripts/replay_live_icl_hook.py \
    --context-path "$CONTEXT_PATH" \
    --tool-name AskUserQuestion \
    --tool-input-json '{"questions":[{"question":"Which artifact should I close?","options":[{"label":"/app/answer.txt"}]}]}' \
    --state-path "$CANARY_DIR/replay-ask-user-question-state.json" \
    --event-log "$CANARY_DIR/replay-ask-user-question-events.jsonl" \
    > "$CANARY_DIR/replay-ask-user-question.json"
else
  scripts/replay_live_icl_controller.py \
    --context-path "$CONTEXT_PATH" \
    --mode pre_tool_use \
    --tool-name WebSearch \
    --tool-input-json '{"query":"daily canary trigger"}' \
    "${WEB_REPLAY_ARGS[@]}" > "$CANARY_DIR/replay-websearch.json"
  scripts/replay_live_icl_controller.py \
    --context-path "$CONTEXT_PATH" \
    --mode can_use_tool \
    --tool-name AskUserQuestion \
    --tool-input-json '{"questions":[{"question":"Which artifact should I close?","options":[{"label":"/app/answer.txt"}]}]}' \
    > "$CANARY_DIR/replay-ask-user-question.json"
fi
python3 - "$CANARY_DIR/replay-websearch.json" "$CANARY_DIR/replay-ask-user-question.json" <<'PY'
import json
import sys
from pathlib import Path
for path in map(Path, sys.argv[1:]):
    data = json.loads(path.read_text())
    print(json.dumps({
        "file": str(path),
        "reason": data.get("reason"),
        "injected": data.get("injected"),
        "event_types": [event.get("type") for event in data.get("events", [])],
    }, ensure_ascii=False))
PY

if [[ "$RUN_HARBOR" == "0" ]]; then
  echo
  echo "Not launching Harbor because --run was not provided."
  if [[ "$PREFLIGHT_OK" != "0" ]]; then
    echo "Readiness: blocked by endpoint preflight. Fix credentials/quota before daily model runs."
  else
    echo "Readiness: preflight + replay passed. Add --run to launch the canary."
  fi
  exit 0
fi

if [[ "$PREFLIGHT_OK" != "0" && "$FORCE_RUN" != "1" ]]; then
  echo "Preflight failed; refusing to launch Harbor. Use --force-run to override." >&2
  exit 1
fi

echo
echo "== Harbor canary run =="
RUN_ARGS=(
  --pack-dir "$PACK_DIR"
  --task "$TASK"
  --model "$MODEL"
  --jobs-dir "$JOBS_DIR"
  --context-variant "$CONTEXT_VARIANT"
  --inject-mode "$INJECT_MODE"
  --endpoint-profile "$ENDPOINT_PROFILE"
  --first-turn-timeout "$FIRST_TURN_TIMEOUT"
  --verifier-timeout "$VERIFIER_TIMEOUT"
)
if [[ "$INJECT_MODE" == "sdk_live" ]]; then
  for tool in "${SDK_LIVE_INTERCEPT_TOOLS[@]}"; do
    RUN_ARGS+=(--sdk-live-intercept-tool "$tool")
  done
fi
scripts/run_harbor_dynamic_icl.sh "${RUN_ARGS[@]}"

echo
echo "== Canary summary =="
JOB_DIR="$JOBS_DIR/$JOB_NAME"
if [[ ! -d "$JOB_DIR" ]]; then
  echo "Missing job dir after run: $JOB_DIR" >&2
  exit 1
fi

TRIAL_DIR=$(find "$JOB_DIR" -mindepth 1 -maxdepth 1 -type d -name "${TASK}__*" -print | sort | tail -1)
if [[ -z "${TRIAL_DIR:-}" ]]; then
  echo "No trial directory found under $JOB_DIR" >&2
  exit 1
fi

if [[ "$INJECT_MODE" == "sdk_live" ]]; then
  scripts/summarize_sdk_live_trial.py \
    "$TRIAL_DIR" \
    --output "$TRIAL_DIR/sdk-live-summary.json"
else
  python3 - "$TRIAL_DIR" <<'PY'
import json
import sys
from pathlib import Path
trial = Path(sys.argv[1])
result = json.loads((trial / "result.json").read_text())
reward = result.get("verifier_result", {}).get("rewards", {}).get("reward")
summary = {
    "trial_dir": str(trial),
    "reward": reward,
    "exception_info": result.get("exception_info"),
    "agent_tokens": result.get("agent_result", {}),
}
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY
fi
