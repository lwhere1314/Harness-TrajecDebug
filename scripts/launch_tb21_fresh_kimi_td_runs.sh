#!/usr/bin/env bash
set -euo pipefail

MODEL="${MODEL:-kimi-k2.6}"
ENDPOINT_PROFILE="${HTD_ENDPOINT_PROFILE:-seed-coding-plan}"
STAMP="${STAMP:-20260610}"
MIN_CONCURRENCY="${MIN_CONCURRENCY:-1}"
MAX_CONCURRENCY="${MAX_CONCURRENCY:-2}"
MAX_TASK_MEMORY_MB="${MAX_TASK_MEMORY_MB:-16384}"
LOW_DISK_GB="${LOW_DISK_GB:-35}"
PRUNE_CACHE_BELOW_GB="${PRUNE_CACHE_BELOW_GB:-45}"
HARBOR_RETRIES="${HARBOR_RETRIES:-1}"
NO_TD_RUN_NAME="${NO_TD_RUN_NAME:-tb21-kimi-k26-no-td-fresh-${STAMP}}"
WITH_TD_RUN_NAME="${WITH_TD_RUN_NAME:-tb21-kimi-k26-with-td-fresh-${STAMP}}"
WITH_TD_CONTEXT_VARIANT="${WITH_TD_CONTEXT_VARIANT:-td_full}"
WITH_TD_INJECT_MODE="${WITH_TD_INJECT_MODE:-prelude}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUPER_ROOT="/Users/hugo/Desktop/super-refactor"
HARBOR_BATCH="$SUPER_ROOT/harbor/scripts/run_tb21_kimi_k26_batch.py"
PYTHON="/opt/miniconda3/envs/terminal-bench/bin/python"

usage() {
  cat <<'USAGE'
Usage:
  scripts/launch_tb21_fresh_kimi_td_runs.sh [--dry-run]

Starts two detached screen sessions:
  1. full no-TD Claude Code + Kimi-k2.6 TB2.1 batch
  2. full with-TD DynamicIclClaudeCode + Kimi-k2.6 TB2.1 batch

Credentials are read from ~/.bashrc / environment. This script does not store
API keys. Default endpoint profile is seed-coding-plan.
USAGE
}

DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

cd "$REPO_ROOT"

scripts/prepare_tb21_full_td_pack.py --output-variant "$WITH_TD_CONTEXT_VARIANT" >/dev/null

set +u
source "$HOME/.bashrc" >/dev/null 2>&1 || true
set -u
source "$REPO_ROOT/scripts/lib_endpoint_profile.sh"
apply_endpoint_profile "$ENDPOINT_PROFILE"
if [[ -z "${ANTHROPIC_BASE_URL:-}" || -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "Missing credentials for endpoint profile '$ENDPOINT_PROFILE'." >&2
  exit 64
fi

export DOCKER_HOST="${DOCKER_HOST:-unix:///Users/hugo/.colima/tb21-harbor/docker.sock}"
export HARBOR_CLAUDE_CODE_BINARY="${HARBOR_CLAUDE_CODE_BINARY:-/Users/hugo/Desktop/super-refactor/harbor/cache/claude-code/claude-linux-arm64}"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="${CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:-1}"

NO_TD_SESSION="tb21-no-td-${STAMP}"
WITH_TD_SESSION="tb21-with-td-${STAMP}"

NO_TD_CMD=$(cat <<EOF
cd "$SUPER_ROOT"
set +u; source ~/.bashrc >/dev/null 2>&1 || true; set -u
export DOCKER_HOST="$DOCKER_HOST"
export HARBOR_CLAUDE_CODE_BINARY="$HARBOR_CLAUDE_CODE_BINARY"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
exec "$PYTHON" "$HARBOR_BATCH" \\
  --run-name "$NO_TD_RUN_NAME" \\
  --model "$MODEL" \\
  --min-concurrency "$MIN_CONCURRENCY" \\
  --max-concurrency "$MAX_CONCURRENCY" \\
  --max-task-memory-mb "$MAX_TASK_MEMORY_MB" \\
  --low-disk-gb "$LOW_DISK_GB" \\
  --prune-cache-below-gb "$PRUNE_CACHE_BELOW_GB" \\
  --harbor-retries "$HARBOR_RETRIES" \\
  --include-verifier-metadata \\
  --force-rerun \\
  --no-resume
EOF
)

WITH_TD_CMD=$(cat <<EOF
cd "$REPO_ROOT"
set +u; source ~/.bashrc >/dev/null 2>&1 || true; set -u
export DOCKER_HOST="$DOCKER_HOST"
export HARBOR_CLAUDE_CODE_BINARY="$HARBOR_CLAUDE_CODE_BINARY"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
exec "$PYTHON" "$REPO_ROOT/scripts/run_tb21_full_td_batch.py" \\
  --run-name "$WITH_TD_RUN_NAME" \\
  --model "$MODEL" \\
  --endpoint-profile "$ENDPOINT_PROFILE" \\
  --context-variant "$WITH_TD_CONTEXT_VARIANT" \\
  --inject-mode "$WITH_TD_INJECT_MODE" \\
  --min-concurrency "$MIN_CONCURRENCY" \\
  --max-concurrency "$MAX_CONCURRENCY" \\
  --max-task-memory-mb "$MAX_TASK_MEMORY_MB" \\
  --low-disk-gb "$LOW_DISK_GB" \\
  --prune-cache-below-gb "$PRUNE_CACHE_BELOW_GB" \\
  --harbor-retries "$HARBOR_RETRIES" \\
  --include-verifier-metadata \\
  --force-rerun \\
  --no-resume
EOF
)

echo "No-TD run:    $NO_TD_RUN_NAME"
echo "With-TD run:  $WITH_TD_RUN_NAME"
echo "Endpoint:     $ENDPOINT_PROFILE"
echo "Concurrency:  $MIN_CONCURRENCY-$MAX_CONCURRENCY"
echo "Sessions:     $NO_TD_SESSION, $WITH_TD_SESSION"
echo "Screen logs:  $REPO_ROOT/runs/${NO_TD_SESSION}.screen.log"
echo "              $REPO_ROOT/runs/${WITH_TD_SESSION}.screen.log"

if [[ "$DRY_RUN" == "1" ]]; then
  echo
  echo "== no-TD command =="
  echo "$NO_TD_CMD"
  echo
  echo "== with-TD command =="
  echo "$WITH_TD_CMD"
  exit 0
fi

mkdir -p "$REPO_ROOT/runs"
screen -dmS "$NO_TD_SESSION" bash -lc "$NO_TD_CMD > '$REPO_ROOT/runs/${NO_TD_SESSION}.screen.log' 2>&1"
screen -dmS "$WITH_TD_SESSION" bash -lc "$WITH_TD_CMD > '$REPO_ROOT/runs/${WITH_TD_SESSION}.screen.log' 2>&1"
screen -ls || true
