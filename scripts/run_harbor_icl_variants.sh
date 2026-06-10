#!/usr/bin/env bash
set -euo pipefail

PACK_DIR="runs/harbor_icl_baseline"
MODEL="${MODEL:-kimi-k2.5}"
TASK_FILTER=""
VARIANT_FILTER=""
JOBS_DIR=""
DRY_RUN=0
CLEAN_EXISTING=1
KIMI_CODE=0
FORCE_BUILD=1
RUNNER="${HARBOR_RUNNER:-/Users/hugo/.codex/skills/terminal-bench-harbor-runner/scripts/run_terminal_bench_harbor.sh}"

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_harbor_icl_variants.sh [options]

Options:
  --pack-dir DIR       Generated ICL pack. Default: runs/harbor_icl_baseline
  --model NAME         Model name passed to Claude Code. Default: $MODEL or kimi-k2.5
  --task NAME          Run only one task, e.g. cancel-async-tasks
  --variant NAME       Run only one variant: no_icl, outcome_only, raw_trace,
                       prompt_filtered, debug_trajectory, or debug_action
  --jobs-dir DIR       Harbor output directory. Default: <pack-dir>/harbor_runs
  --kimi-code          Use Kimi Code's Claude Code endpoint defaults
  --dry-run            Print commands without executing them
  --keep-existing      Do not remove an existing job directory before running
  --no-force-build     Reuse the task docker_image / cached image when possible
  -h, --help           Show this help

Environment:
  Kimi Code / Claude Code route:
    ANTHROPIC_API_KEY
    ANTHROPIC_BASE_URL defaults to https://api.kimi.com/coding/ with --kimi-code

  Token Plan route:
    TOKEN_PLAN_BASE_URL
    TOKEN_PLAN_API_KEY

  Also supported:
    ANTHROPIC_BASE_URL
    ANTHROPIC_API_KEY

  Optional:
    HARBOR_RUNNER      Path to run_terminal_bench_harbor.sh
    DOCKER_HOST        Docker socket for the Harbor environment
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack-dir) PACK_DIR="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --task) TASK_FILTER="$2"; shift 2 ;;
    --variant) VARIANT_FILTER="$2"; shift 2 ;;
    --jobs-dir) JOBS_DIR="$2"; shift 2 ;;
    --kimi-code) KIMI_CODE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --keep-existing) CLEAN_EXISTING=0; shift ;;
    --no-force-build) FORCE_BUILD=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! -d "$PACK_DIR/task_variants" ]]; then
  echo "Missing task variants under: $PACK_DIR/task_variants" >&2
  echo "Build them first with scripts/build_harbor_icl_baseline.py" >&2
  exit 1
fi

if [[ ! -x "$RUNNER" ]]; then
  echo "Harbor runner is not executable: $RUNNER" >&2
  exit 1
fi

if [[ -f "$HOME/.bashrc" ]]; then
  set +u
  # shellcheck disable=SC1090
  source "$HOME/.bashrc"
  set -u
fi

if [[ "$KIMI_CODE" == "1" ]]; then
  export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.kimi.com/coding/}"
fi

if [[ -z "${ANTHROPIC_BASE_URL:-${TOKEN_PLAN_BASE_URL:-}}" || -z "${ANTHROPIC_API_KEY:-${TOKEN_PLAN_API_KEY:-}}" ]]; then
  cat >&2 <<'MSG'
Missing model API credentials.
Set TOKEN_PLAN_BASE_URL/TOKEN_PLAN_API_KEY or ANTHROPIC_BASE_URL/ANTHROPIC_API_KEY.
MSG
  exit 1
fi

if [[ -z "$JOBS_DIR" ]]; then
  JOBS_DIR="$PACK_DIR/harbor_runs"
fi
mkdir -p "$JOBS_DIR"

export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="${CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:-1}"
export CLAUDE_CODE_AUTO_COMPACT_WINDOW="${CLAUDE_CODE_AUTO_COMPACT_WINDOW:-262144}"

run_one() {
  local variant="$1"
  local task="$2"
  local task_dir="$3"
  local safe_model="${MODEL//\//-}"
  safe_model="${safe_model//./-}"
  local job_name="htd-icl-${variant}-${task}-${safe_model}"

  local cmd=(
    "$RUNNER"
    --task "$task_dir"
    --agent claude-code
    --model "$MODEL"
    --job-name "$job_name"
    --jobs-dir "$JOBS_DIR"
    --setup-timeout 1200
    --agent-timeout 900
  )
  if [[ "$FORCE_BUILD" == "0" ]]; then
    cmd+=(--no-force-build)
  fi

  echo "=== variant=$variant task=$task model=$MODEL ==="
  printf '%q ' "${cmd[@]}"
  printf '\n'
  if [[ "$DRY_RUN" == "0" ]]; then
    if [[ "$CLEAN_EXISTING" == "1" ]]; then
      rm -rf "$JOBS_DIR/$job_name"
    fi
    "${cmd[@]}"
  fi
}

shopt -s nullglob
for variant_dir in "$PACK_DIR"/task_variants/*; do
  variant="$(basename "$variant_dir")"
  if [[ -n "$VARIANT_FILTER" && "$variant" != "$VARIANT_FILTER" ]]; then
    continue
  fi
  for task_dir in "$variant_dir"/*; do
    task="$(basename "$task_dir")"
    if [[ -n "$TASK_FILTER" && "$task" != "$TASK_FILTER" ]]; then
      continue
    fi
    run_one "$variant" "$task" "$task_dir"
  done
done
