#!/usr/bin/env bash
set -euo pipefail

ROUTE="route-a"
TASK="cancel-async-tasks"
MODEL="kimi-k2.6"
ENDPOINT_PROFILE="seed-agent-plan"
JOBS_DIR="artifacts/meta_harness_dual_route/runs"
ATTEMPTS="1"
CONCURRENCY="1"
ROUTE_A_MAX_TOKENS="${ROUTE_A_MAX_TOKENS:-8192}"
FORCE_BUILD="true"
DELETE="true"
HOST_PROXY_URL="${HOST_PROXY_URL:-http://127.0.0.1:1082}"
CONTAINER_PROXY_URL="${CONTAINER_PROXY_URL:-http://host.docker.internal:1082}"
DEBUG="true"
DRY_RUN="0"

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_meta_harness_dual_route_canary.sh [options]

Options:
  --route NAME              route-a, claude-adaptation, route-b, or both. Default: route-a.
  --task NAME_OR_PATH       TB2.1 proxy task name or local path. Default: cancel-async-tasks.
  --model NAME              Target model. Default: kimi-k2.6.
  --endpoint-profile NAME   Endpoint profile. Default: seed-agent-plan.
  --jobs-dir PATH           Output jobs dir. Default: artifacts/meta_harness_dual_route/runs.
  --attempts N              Attempts per route. Default: 1.
  --concurrency N           Harbor trial concurrency. Default: 1.
  --route-a-max-tokens N    Terminus2 max output tokens. Default: 8192.
  --host-proxy-url URL      Host proxy for model endpoint. Default: http://127.0.0.1:1082.
  --container-proxy-url URL Container proxy passed to Claude Code. Default: http://host.docker.internal:1082.
  --no-force-build          Use task prebuilt image instead of proxy-patched Dockerfile.
  --no-delete               Keep Harbor containers/images after the trial.
  --quiet                   Omit Harbor --debug.
  --dry-run                 Print commands without running.
  -h, --help                Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --route) ROUTE="$2"; shift 2 ;;
    --task) TASK="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --endpoint-profile) ENDPOINT_PROFILE="$2"; shift 2 ;;
    --jobs-dir) JOBS_DIR="$2"; shift 2 ;;
    --attempts) ATTEMPTS="$2"; shift 2 ;;
    --concurrency) CONCURRENCY="$2"; shift 2 ;;
    --route-a-max-tokens) ROUTE_A_MAX_TOKENS="$2"; shift 2 ;;
    --host-proxy-url) HOST_PROXY_URL="$2"; shift 2 ;;
    --container-proxy-url) CONTAINER_PROXY_URL="$2"; shift 2 ;;
    --no-force-build) FORCE_BUILD="false"; shift ;;
    --no-delete) DELETE="false"; shift ;;
    --quiet) DEBUG="false"; shift ;;
    --dry-run) DRY_RUN="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$ROUTE" in
  route-a|claude-adaptation|route-b|both) ;;
  *) echo "--route must be route-a, claude-adaptation, route-b, or both" >&2; exit 2 ;;
esac
if [[ "$ROUTE" == "route-b" ]]; then
  echo "warning: --route route-b is a legacy alias for --route claude-adaptation; it is not upstream Meta-Harness" >&2
  ROUTE="claude-adaptation"
fi

source ~/.bashrc >/dev/null 2>&1 || true
source scripts/lib_endpoint_profile.sh
apply_endpoint_profile "$ENDPOINT_PROFILE"

if [[ -n "$HOST_PROXY_URL" ]]; then
  export HTTP_PROXY="$HOST_PROXY_URL"
  export HTTPS_PROXY="$HOST_PROXY_URL"
  export ALL_PROXY="$HOST_PROXY_URL"
  export http_proxy="$HOST_PROXY_URL"
  export https_proxy="$HOST_PROXY_URL"
  export all_proxy="$HOST_PROXY_URL"
fi
if [[ -n "$CONTAINER_PROXY_URL" ]]; then
  export META_HARNESS_CONTAINER_PROXY_URL="$CONTAINER_PROXY_URL"
fi

export DOCKER_HOST="${DOCKER_HOST:-unix:///Users/hugo/.colima/tb21-harbor/docker.sock}"
export HARBOR_CLAUDE_CODE_BINARY="${HARBOR_CLAUDE_CODE_BINARY:-/Users/hugo/Desktop/super-refactor/harbor/cache/claude-code/claude-linux-arm64}"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"

TASK_PATH="$TASK"
if [[ "$TASK" != /* && "$TASK" != .* && ! -d "$TASK" ]]; then
  TASK_PATH="/Users/hugo/Desktop/super-refactor/harbor/datasets/terminal-bench-2.1-proxy/tasks/$TASK"
fi
if [[ ! -d "$TASK_PATH" ]]; then
  echo "Task path does not exist: $TASK_PATH" >&2
  exit 2
fi

mkdir -p "$JOBS_DIR/_meta"
PREFLIGHT_JSON="$JOBS_DIR/_meta/preflight-${ENDPOINT_PROFILE}-${MODEL//\//-}.json"
if ! scripts/check_model_endpoint.py \
  --endpoint-profile "$ENDPOINT_PROFILE" \
  --model "$MODEL" \
  --timeout-sec 30 > "$PREFLIGHT_JSON"; then
  echo "Endpoint preflight failed; see $PREFLIGHT_JSON" >&2
  cat "$PREFLIGHT_JSON" >&2
  exit 3
fi

HARBOR_BIN="/opt/miniconda3/envs/terminal-bench/bin/harbor"
COMMON_ARGS=(
  run
  --jobs-dir "$JOBS_DIR"
  --n-attempts "$ATTEMPTS"
  -n "$CONCURRENCY"
  --path "$TASK_PATH"
)
if [[ "$FORCE_BUILD" == "true" ]]; then
  COMMON_ARGS+=(--force-build)
else
  COMMON_ARGS+=(--no-force-build)
fi
if [[ "$DEBUG" == "true" ]]; then
  COMMON_ARGS+=(--debug)
fi
if [[ "$DELETE" == "false" ]]; then
  COMMON_ARGS+=(--no-delete)
fi

run_route_a() {
  local timestamp job_name route_model
  timestamp="$(date +%Y%m%dT%H%M%S)"
  job_name="mh-route-a-terminus2-${TASK##*/}-${MODEL//\//-}-${timestamp}"
  route_model="$MODEL"
  if [[ "$route_model" != */* ]]; then
    route_model="anthropic/$route_model"
  fi
  local cmd=(
    "$HARBOR_BIN" "${COMMON_ARGS[@]}"
    --job-name "$job_name"
    --agent-import-path meta_harness_dual_route.agents.route_a_terminus_general_review:AgentHarness
    --model "$route_model"
    --ak "api_base=$ANTHROPIC_BASE_URL"
    --ak temperature=0.2
    --ak record_terminal_session=false
    --ak "llm_kwargs={\"max_tokens\":${ROUTE_A_MAX_TOKENS}}"
  )
  printf 'route=route-a job=%s import_path=%s model=%s\n' \
    "$job_name" \
    "meta_harness_dual_route.agents.route_a_terminus_general_review:AgentHarness" \
    "$route_model" | tee "$JOBS_DIR/_meta/$job_name.invocation.txt"
  printf '%q ' "${cmd[@]}" | tee -a "$JOBS_DIR/_meta/$job_name.invocation.txt"
  printf '\n' | tee -a "$JOBS_DIR/_meta/$job_name.invocation.txt"
  if [[ "$DRY_RUN" != "1" ]]; then
    "${cmd[@]}"
  fi
}

run_claude_adaptation() {
  local timestamp job_name
  timestamp="$(date +%Y%m%dT%H%M%S)"
  job_name="mh-claude-adaptation-${TASK##*/}-${MODEL//\//-}-${timestamp}"
  local cmd=(
    "$HARBOR_BIN" "${COMMON_ARGS[@]}"
    --job-name "$job_name"
    --agent-import-path meta_harness_dual_route.agents.claude_code_generic_review_adaptation:AgentHarness
    --model "$MODEL"
  )
  printf 'route=claude-adaptation job=%s import_path=%s model=%s note=%s\n' \
    "$job_name" \
    "meta_harness_dual_route.agents.claude_code_generic_review_adaptation:AgentHarness" \
    "$MODEL" \
    "diagnostic-not-upstream-meta-harness" | tee "$JOBS_DIR/_meta/$job_name.invocation.txt"
  printf '%q ' "${cmd[@]}" | tee -a "$JOBS_DIR/_meta/$job_name.invocation.txt"
  printf '\n' | tee -a "$JOBS_DIR/_meta/$job_name.invocation.txt"
  if [[ "$DRY_RUN" != "1" ]]; then
    "${cmd[@]}"
  fi
}

case "$ROUTE" in
  route-a) run_route_a ;;
  claude-adaptation) run_claude_adaptation ;;
  both)
    run_route_a
    run_claude_adaptation
    ;;
esac
