#!/usr/bin/env bash
set -euo pipefail

PACK_DIR="runs/harbor_icl_baseline"
MODEL="${MODEL:-kimi-k2.6}"
CONTEXT_VARIANT="debug_action"
TASKS=("gcode-to-text")
TRIGGERS=("ask_user_question" "WebSearch")
BUILD_PACK=1
RUN_CHEAP_CLOSURE=1
RUN_ARTIFACT_VERIFIER=1
RUN_RUNTIME_SMOKE=1
SETUP_TIMEOUT="1200"
AGENT_TIMEOUT="120"
VERIFIER_TIMEOUT="300"
NO_FORCE_BUILD=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_daily_icl_mechanism.sh [options]

Purpose:
  Daily-safe no-model canary for interactive ICL mechanics. It rebuilds the
  selected task cards, checks Debug-Action artifact closure, runs a deterministic
  artifact materialization agent through Harbor + the official verifier, runs
  runtime-injection smoke agents for selected trigger points, then refreshes the
  aggregate/readiness reports.

This script proves that the Harness-TrajecDebug context cards, runtime hook
decisions, Docker artifact materialization, and official verifier path are
healthy. It does not prove model reward improvement; use run_daily_icl_canary.sh
or run_icl_matrix_canaries.sh with --run once the model endpoint is available.

Options:
  --pack-dir DIR              ICL pack. Default: runs/harbor_icl_baseline
  --task NAME                 Task to include. May repeat. Default: gcode-to-text
  --model NAME                Model label used when rebuilding cards. Default:
                              $MODEL or kimi-k2.6
  --context-variant NAME      Teacher card. Default: debug_action
  --trigger NAME              Runtime trigger to smoke. May repeat. Default:
                              ask_user_question and WebSearch
  --setup-timeout SEC         Harbor setup timeout. Default: 1200
  --agent-timeout SEC         No-model agent timeout. Default: 120
  --verifier-timeout SEC      Official verifier timeout. Default: 300
  --no-build-pack             Skip rebuilding task cards/variants
  --skip-cheap-closure        Skip local heredoc/task-specific closure check
  --skip-artifact-verifier    Skip no-model artifact + official verifier run
  --skip-runtime-smoke        Skip runtime injection smoke runs
  --no-force-build            Reuse cached Harbor images when possible
  -h, --help                  Show help.
USAGE
}

TASKS_SET=0
TRIGGERS_SET=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack-dir) PACK_DIR="$2"; shift 2 ;;
    --task)
      if [[ "$TASKS_SET" == "0" ]]; then
        TASKS=()
        TASKS_SET=1
      fi
      TASKS+=("$2")
      shift 2
      ;;
    --model) MODEL="$2"; shift 2 ;;
    --context-variant) CONTEXT_VARIANT="$2"; shift 2 ;;
    --trigger)
      if [[ "$TRIGGERS_SET" == "0" ]]; then
        TRIGGERS=()
        TRIGGERS_SET=1
      fi
      TRIGGERS+=("$2")
      shift 2
      ;;
    --setup-timeout) SETUP_TIMEOUT="$2"; shift 2 ;;
    --agent-timeout) AGENT_TIMEOUT="$2"; shift 2 ;;
    --verifier-timeout) VERIFIER_TIMEOUT="$2"; shift 2 ;;
    --no-build-pack) BUILD_PACK=0; shift ;;
    --skip-cheap-closure) RUN_CHEAP_CLOSURE=0; shift ;;
    --skip-artifact-verifier) RUN_ARTIFACT_VERIFIER=0; shift ;;
    --skip-runtime-smoke) RUN_RUNTIME_SMOKE=0; shift ;;
    --no-force-build) NO_FORCE_BUILD=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ${#TASKS[@]} -eq 0 ]]; then
  echo "At least one --task is required" >&2
  exit 2
fi
if [[ ${#TRIGGERS[@]} -eq 0 && "$RUN_RUNTIME_SMOKE" == "1" ]]; then
  echo "At least one --trigger is required unless --skip-runtime-smoke is set" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

echo "== Harness-TrajecDebug Daily Mechanism Canary =="
echo "Pack dir: $PACK_DIR"
echo "Model label: $MODEL"
echo "Context variant: $CONTEXT_VARIANT"
echo "Tasks:"
printf '  - %s\n' "${TASKS[@]}"
if [[ "$RUN_RUNTIME_SMOKE" == "1" ]]; then
  echo "Runtime triggers:"
  printf '  - %s\n' "${TRIGGERS[@]}"
fi
echo "Verifier timeout: ${VERIFIER_TIMEOUT}s"

if [[ "$BUILD_PACK" == "1" ]]; then
  echo
  echo "== Rebuilding selected task cards =="
  BUILD_ARGS=(--output-dir "$PACK_DIR" --model "$MODEL" --max-context-chars 12000)
  for task in "${TASKS[@]}"; do
    BUILD_ARGS+=(--target-task "$task")
  done
  python3 scripts/build_harbor_icl_baseline.py "${BUILD_ARGS[@]}"
fi

if [[ "$RUN_CHEAP_CLOSURE" == "1" ]]; then
  echo
  echo "== Cheap Debug-Action closure =="
  CLOSURE_ARGS=(--pack-dir "$PACK_DIR" --context-variant "$CONTEXT_VARIANT")
  for task in "${TASKS[@]}"; do
    CLOSURE_ARGS+=(--task "$task")
  done
  scripts/check_debug_action_closure.py "${CLOSURE_ARGS[@]}"
fi

COMMON_HARBOR_ARGS=(
  --pack-dir "$PACK_DIR"
  --context-variant "$CONTEXT_VARIANT"
  --setup-timeout "$SETUP_TIMEOUT"
  --agent-timeout "$AGENT_TIMEOUT"
  --verifier-timeout "$VERIFIER_TIMEOUT"
)
if [[ "$NO_FORCE_BUILD" == "1" ]]; then
  COMMON_HARBOR_ARGS+=(--no-force-build)
fi

if [[ "$RUN_ARTIFACT_VERIFIER" == "1" ]]; then
  echo
  echo "== Official verifier artifact-closure smoke =="
  for task in "${TASKS[@]}"; do
    scripts/run_harbor_artifact_closure.sh \
      --task "$task" \
      "${COMMON_HARBOR_ARGS[@]}"
  done
fi

if [[ "$RUN_RUNTIME_SMOKE" == "1" ]]; then
  echo
  echo "== Runtime injection smoke =="
  for task in "${TASKS[@]}"; do
    for trigger in "${TRIGGERS[@]}"; do
      scripts/run_harbor_runtime_smoke.sh \
        --task "$task" \
        --trigger "$trigger" \
        "${COMMON_HARBOR_ARGS[@]}"
    done
  done
fi

echo
echo "== Refresh aggregate/readiness =="
scripts/aggregate_icl_results.py --pack-dir "$PACK_DIR" > "$PACK_DIR/daily_mechanism_aggregate.stdout.json"
scripts/report_icl_readiness.py --pack-dir "$PACK_DIR" > "$PACK_DIR/daily_mechanism_readiness.stdout.json"
cat "$PACK_DIR/icl_readiness.md"
