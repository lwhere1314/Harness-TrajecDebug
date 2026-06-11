#!/usr/bin/env bash
set -euo pipefail

if [[ -f "$HOME/.bashrc" ]]; then
  # shellcheck source=/dev/null
  set +u
  source "$HOME/.bashrc"
  set -u
fi

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'USAGE'
Usage:
  scripts/run_query_optimize_sdk_live_repro.sh [JOBS_DIR] [CONTEXT_VARIANT]

Runs the query-optimize sdk_live reproduction with kimi-k2.6 through the SEED
endpoint profile. JOBS_DIR defaults to runs/harbor_icl_repro_seed.
CONTEXT_VARIANT defaults to debug_action; use fail_debug_action for the
reward-0 teacher-card demo.
USAGE
  exit 0
fi

JOBS_DIR="${1:-runs/harbor_icl_repro_seed}"
CONTEXT_VARIANT="${2:-debug_action}"
NO_FORCE_BUILD="${HTD_NO_FORCE_BUILD:-1}"
KEEP_ENVIRONMENT="${HTD_KEEP_ENVIRONMENT:-0}"

args=(
  scripts/run_harbor_dynamic_icl.sh
  --pack-dir docs/blog/raw_logs/blog_raw_logs
  --task query-optimize
  --model kimi-k2.6
  --jobs-dir "$JOBS_DIR"
  --context-variant "$CONTEXT_VARIANT"
  --inject-mode sdk_live
  --endpoint-profile seed-coding-plan
  --sdk-live-intercept-tool Bash
  --sdk-live-install-timeout 900
  --setup-timeout 1200
  --agent-timeout 1800
  --verifier-timeout 600
)

if [[ "$NO_FORCE_BUILD" == "1" ]]; then
  args+=(--no-force-build)
fi

if [[ "$KEEP_ENVIRONMENT" == "1" ]]; then
  args+=(--keep-environment)
fi

exec "${args[@]}"
