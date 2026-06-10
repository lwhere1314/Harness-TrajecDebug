#!/usr/bin/env bash
set -euo pipefail

PACK_DIR="runs/harbor_icl_baseline"
MATRIX_JSON=""
MODEL="${MODEL:-kimi-k2.6}"
CONTEXT_VARIANT="debug_action"
INJECT_MODE="continue_after"
ENDPOINT_PROFILE="${HTD_ENDPOINT_PROFILE:-auto}"
LIMIT="3"
TASK_FILTERS=()
INCLUDE_SMOKE_PASSED=0
REQUIRE_ARTIFACT=1
BUILD_PACK=1
RUN_HARBOR=0
FORCE_RUN=0
PREFLIGHT_TIMEOUT="20"
FIRST_TURN_TIMEOUT="75"
VERIFIER_TIMEOUT="600"
JOBS_DIR=""
SDK_LIVE_INTERCEPT_TOOLS=("WebSearch" "WebFetch")
BATCH_DIR=""

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_icl_matrix_canaries.sh [options]

Purpose:
  Select Kimi-k2.6 failed / Codex+GPT-5.5 passed tasks from the task matrix,
  replay runtime ICL trigger points for each selected task, and optionally run
  Harbor canaries sequentially.

Options:
  --pack-dir DIR              ICL pack. Default: runs/harbor_icl_baseline
  --matrix-json PATH          Candidate matrix. Default: <pack-dir>/task_matrix.json
  --model NAME                Model name. Default: $MODEL or kimi-k2.6
  --context-variant NAME      Teacher card. Default: debug_action
  --inject-mode MODE          tool, prelude, continue_after, sdk_live, or hooks_live.
                              Default: continue_after
  --endpoint-profile NAME     Endpoint profile: auto, anthropic, token-plan,
                              ark, dashscope, or kimi. Default: auto
  --limit N                   Number of matrix tasks to select. Default: 3
  --task NAME                 Run this task from the matrix. May repeat.
  --include-smoke-passed      Include tasks already marked with a smoke_note.
  --allow-missing-artifact    Do not require captured teacher artifacts.
  --no-build-pack             Do not rebuild selected task cards/variants.
  --jobs-dir DIR              Harbor output dir. Default follows run_daily script.
  --batch-dir DIR             Matrix batch output directory. Default:
                              <pack-dir>/matrix_canary/<timestamp>-<model>-<mode>
  --first-turn-timeout SEC    continue_after first-turn timeout. Default: 75
  --verifier-timeout SEC      Official verifier timeout. Default: 600
  --sdk-live-intercept-tool NAME
                              sdk_live intercept tool. May repeat.
                              Default: WebSearch and WebFetch
  --preflight-timeout SEC     Endpoint preflight timeout. Default: 20
  --force-run                 Run Harbor even when endpoint preflight fails.
  --run                       Actually launch Harbor canaries. Without --run this
                              performs selection + preflight + replay only.
  -h, --help                  Show help.

Environment:
  auto uses ANTHROPIC_* first, then TOKEN_PLAN_*. Explicit profiles read:
  TOKEN_PLAN_*, ARK_*, DASHSCOPE_*, KIMI_*, or ANTHROPIC_* variables.

This script never prints API keys.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack-dir) PACK_DIR="$2"; shift 2 ;;
    --matrix-json) MATRIX_JSON="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --context-variant) CONTEXT_VARIANT="$2"; shift 2 ;;
    --inject-mode) INJECT_MODE="$2"; shift 2 ;;
    --endpoint-profile) ENDPOINT_PROFILE="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --task) TASK_FILTERS+=("$2"); shift 2 ;;
    --include-smoke-passed) INCLUDE_SMOKE_PASSED=1; shift ;;
    --allow-missing-artifact) REQUIRE_ARTIFACT=0; shift ;;
    --no-build-pack) BUILD_PACK=0; shift ;;
    --jobs-dir) JOBS_DIR="$2"; shift 2 ;;
    --batch-dir) BATCH_DIR="$2"; shift 2 ;;
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

if [[ -z "$MATRIX_JSON" ]]; then
  MATRIX_JSON="$PACK_DIR/task_matrix.json"
fi

if [[ ! -f "$MATRIX_JSON" ]]; then
  echo "Missing matrix JSON: $MATRIX_JSON" >&2
  echo "Build it first with scripts/build_icl_task_matrix.py" >&2
  exit 1
fi

if [[ -f "$HOME/.bashrc" ]]; then
  set +u
  # shellcheck disable=SC1090
  source "$HOME/.bashrc"
  set -u
fi

# shellcheck disable=SC1091
source "$REPO_ROOT/scripts/lib_endpoint_profile.sh"
apply_endpoint_profile "$ENDPOINT_PROFILE"

SAFE_MODEL="${MODEL//\//-}"
SAFE_MODEL="${SAFE_MODEL//./-}"
if [[ -z "$BATCH_DIR" ]]; then
  BATCH_DIR="$PACK_DIR/matrix_canary/$(date +%Y%m%dT%H%M%S)-${SAFE_MODEL}-${INJECT_MODE}"
fi
mkdir -p "$BATCH_DIR"

if [[ -z "$JOBS_DIR" ]]; then
  if [[ "$INJECT_MODE" == "sdk_live" ]]; then
    EFFECTIVE_JOBS_DIR="$PACK_DIR/harbor_runs_sdk_live"
  else
    EFFECTIVE_JOBS_DIR="$PACK_DIR/harbor_runs"
  fi
else
  EFFECTIVE_JOBS_DIR="$JOBS_DIR"
fi

TASKS_FILE="$BATCH_DIR/tasks.txt"
TASK_ARGS_FILE="$BATCH_DIR/task-args.txt"
SELECT_ARGS=("$MATRIX_JSON" "$LIMIT" "$INCLUDE_SMOKE_PASSED" "$REQUIRE_ARTIFACT")
if [[ ${#TASK_FILTERS[@]} -gt 0 ]]; then
  SELECT_ARGS+=("${TASK_FILTERS[@]}")
fi
python3 - "${SELECT_ARGS[@]}" > "$TASKS_FILE" <<'PY'
import json
import sys
from pathlib import Path

matrix_path = Path(sys.argv[1])
limit = int(sys.argv[2])
include_smoke = sys.argv[3] == "1"
require_artifact = sys.argv[4] == "1"
filters = set(sys.argv[5:])
data = json.loads(matrix_path.read_text())
selected = []
for candidate in data.get("candidates", []):
    task = candidate.get("task")
    if filters and task not in filters:
        continue
    if not include_smoke and candidate.get("smoke_note"):
        continue
    if require_artifact and not candidate.get("teacher_artifacts"):
        continue
    selected.append(task)
    if not filters and len(selected) >= limit:
        break
for task in selected:
    print(task)
PY

if [[ ! -s "$TASKS_FILE" ]]; then
  echo "No matrix tasks selected. Try --include-smoke-passed or --allow-missing-artifact." >&2
  exit 1
fi

python3 - "$TASKS_FILE" > "$TASK_ARGS_FILE" <<'PY'
import sys
from pathlib import Path
for task in Path(sys.argv[1]).read_text().splitlines():
    task = task.strip()
    if task:
        print(f"--target-task {task}")
PY

echo "== Harness-TrajecDebug Matrix Canary Batch =="
echo "Matrix: $MATRIX_JSON"
echo "Pack dir: $PACK_DIR"
echo "Model: $MODEL"
echo "Inject mode: $INJECT_MODE"
echo "Endpoint profile: $ENDPOINT_PROFILE"
echo "Context variant: $CONTEXT_VARIANT"
echo "Batch dir: $BATCH_DIR"
echo "Jobs dir: $EFFECTIVE_JOBS_DIR"
echo "Verifier timeout: ${VERIFIER_TIMEOUT}s"
echo "Selected tasks:"
sed 's/^/  - /' "$TASKS_FILE"

python3 - "$BATCH_DIR/config.json" "$PACK_DIR" "$MATRIX_JSON" "$MODEL" "$CONTEXT_VARIANT" "$INJECT_MODE" "$ENDPOINT_PROFILE" "$EFFECTIVE_JOBS_DIR" "$FIRST_TURN_TIMEOUT" "$VERIFIER_TIMEOUT" "${SDK_LIVE_INTERCEPT_TOOLS[@]}" <<'PY'
import json
import sys
from pathlib import Path

(
    output,
    pack_dir,
    matrix_json,
    model,
    context_variant,
    inject_mode,
    endpoint_profile,
    jobs_dir,
    first_turn_timeout,
    verifier_timeout,
    *intercept_tools,
) = sys.argv[1:]

Path(output).write_text(
    json.dumps(
        {
            "pack_dir": pack_dir,
            "matrix_json": matrix_json,
            "model": model,
            "context_variant": context_variant,
            "inject_mode": inject_mode,
            "endpoint_profile": endpoint_profile,
            "jobs_dir": jobs_dir,
            "first_turn_timeout": int(float(first_turn_timeout)),
            "verifier_timeout": int(float(verifier_timeout)),
            "sdk_live_intercept_tools": intercept_tools,
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY

if [[ "$BUILD_PACK" == "1" ]]; then
  echo
  echo "== Building selected task pack =="
  BUILD_ARGS=(--output-dir "$PACK_DIR" --model "$MODEL" --max-context-chars 12000)
  while read -r target_arg task_name; do
    [[ -n "${target_arg:-}" && -n "${task_name:-}" ]] || continue
    BUILD_ARGS+=("$target_arg" "$task_name")
  done < "$TASK_ARGS_FILE"
  python3 scripts/build_harbor_icl_baseline.py "${BUILD_ARGS[@]}" > "$BATCH_DIR/build-pack.json"
  echo "Build output: $BATCH_DIR/build-pack.json"
fi

echo
echo "== Endpoint preflight =="
scripts/check_model_endpoint.py \
  --endpoint-profile "$ENDPOINT_PROFILE" \
  --model "$MODEL" \
  --timeout-sec "$PREFLIGHT_TIMEOUT" \
  --allow-fail > "$BATCH_DIR/preflight.json"
cat "$BATCH_DIR/preflight.json"
PREFLIGHT_OK=$(python3 - "$BATCH_DIR/preflight.json" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text())
print(0 if data.get("ok") else 1)
PY
)

echo
echo "== Replay selected tasks =="
REPLAY_SUMMARY="$BATCH_DIR/replay-summary.jsonl"
: > "$REPLAY_SUMMARY"
WEB_REPLAY_ARGS=()
for tool in "${SDK_LIVE_INTERCEPT_TOOLS[@]}"; do
  WEB_REPLAY_ARGS+=(--intercept-tool "$tool")
done
while read -r task; do
  [[ -n "$task" ]] || continue
  context_path="$PACK_DIR/teacher_cards/$task/$CONTEXT_VARIANT.md"
  if [[ ! -f "$context_path" ]]; then
    echo "Missing context card for $task: $context_path" >&2
    exit 1
  fi
  task_dir="$BATCH_DIR/replay/$task"
  mkdir -p "$task_dir"
  if [[ "$INJECT_MODE" == "hooks_live" ]]; then
    scripts/replay_live_icl_hook.py \
      --context-path "$context_path" \
      --session-start \
      > "$task_dir/session-start.json"
    scripts/replay_live_icl_hook.py \
      --context-path "$context_path" \
      --tool-name WebSearch \
      --tool-input-json '{"query":"matrix canary trigger"}' \
      --state-path "$task_dir/websearch-state.json" \
      --event-log "$task_dir/websearch-events.jsonl" \
      "${WEB_REPLAY_ARGS[@]}" > "$task_dir/websearch.json"
    scripts/replay_live_icl_hook.py \
      --context-path "$context_path" \
      --tool-name AskUserQuestion \
      --tool-input-json '{"questions":[{"question":"Which artifact should I close?","options":[{"label":"/app/answer.txt"}]}]}' \
      --state-path "$task_dir/ask-user-question-state.json" \
      --event-log "$task_dir/ask-user-question-events.jsonl" \
      > "$task_dir/ask-user-question.json"
  else
    scripts/replay_live_icl_controller.py \
      --context-path "$context_path" \
      --mode pre_tool_use \
      --tool-name WebSearch \
      --tool-input-json '{"query":"matrix canary trigger"}' \
      "${WEB_REPLAY_ARGS[@]}" > "$task_dir/websearch.json"
    scripts/replay_live_icl_controller.py \
      --context-path "$context_path" \
      --mode can_use_tool \
      --tool-name AskUserQuestion \
      --tool-input-json '{"questions":[{"question":"Which artifact should I close?","options":[{"label":"/app/answer.txt"}]}]}' \
      > "$task_dir/ask-user-question.json"
  fi
  python3 - "$task" "$task_dir/websearch.json" "$task_dir/ask-user-question.json" >> "$REPLAY_SUMMARY" <<'PY'
import json
import sys
from pathlib import Path
task = sys.argv[1]
rows = []
for path in map(Path, sys.argv[2:]):
    data = json.loads(path.read_text())
    rows.append({
        "file": str(path),
        "reason": data.get("reason"),
        "injected": data.get("injected"),
        "event_types": [event.get("type") for event in data.get("events", [])],
    })
print(json.dumps({"task": task, "replays": rows}, ensure_ascii=False))
PY
done < "$TASKS_FILE"
cat "$REPLAY_SUMMARY"

if [[ "$RUN_HARBOR" == "0" ]]; then
  echo
  echo "== Matrix canary summary =="
  scripts/summarize_matrix_canary.py "$BATCH_DIR" --pack-dir "$PACK_DIR" > "$BATCH_DIR/summary.stdout.json"
  cat "$BATCH_DIR/summary.md"
  echo
  echo "Not launching Harbor because --run was not provided."
  if [[ "$PREFLIGHT_OK" != "0" ]]; then
    echo "Readiness: blocked by endpoint preflight. Replay artifacts are saved under $BATCH_DIR."
  else
    echo "Readiness: preflight + matrix replay passed. Add --run to launch selected canaries."
  fi
  exit 0
fi

if [[ "$PREFLIGHT_OK" != "0" && "$FORCE_RUN" != "1" ]]; then
  echo "Preflight failed; refusing to launch Harbor. Use --force-run to override." >&2
  exit 1
fi

echo
echo "== Launching Harbor canaries =="
while read -r task; do
  [[ -n "$task" ]] || continue
  args=(
    --pack-dir "$PACK_DIR"
    --task "$task"
    --model "$MODEL"
    --context-variant "$CONTEXT_VARIANT"
    --inject-mode "$INJECT_MODE"
    --endpoint-profile "$ENDPOINT_PROFILE"
    --first-turn-timeout "$FIRST_TURN_TIMEOUT"
    --verifier-timeout "$VERIFIER_TIMEOUT"
    --run
  )
  if [[ -n "$JOBS_DIR" ]]; then
    args+=(--jobs-dir "$JOBS_DIR")
  fi
  if [[ "$FORCE_RUN" == "1" ]]; then
    args+=(--force-run)
  fi
  if [[ "$INJECT_MODE" == "sdk_live" ]]; then
    for tool in "${SDK_LIVE_INTERCEPT_TOOLS[@]}"; do
      args+=(--sdk-live-intercept-tool "$tool")
    done
  fi
  scripts/run_daily_icl_canary.sh "${args[@]}" | tee "$BATCH_DIR/$task-run.log"
done < "$TASKS_FILE"

echo
echo "== Matrix canary summary =="
scripts/summarize_matrix_canary.py "$BATCH_DIR" --pack-dir "$PACK_DIR" > "$BATCH_DIR/summary.stdout.json"
cat "$BATCH_DIR/summary.md"
