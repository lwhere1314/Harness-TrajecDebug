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
  scripts/run_query_optimize_sdk_live_repro.sh [JOBS_DIR]

Runs the query-optimize debug_action + sdk_live reproduction with kimi-k2.6
through the SEED endpoint profile. JOBS_DIR defaults to runs/harbor_icl_repro_seed.
USAGE
  exit 0
fi

JOBS_DIR="${1:-runs/harbor_icl_repro_seed}"

exec scripts/run_harbor_dynamic_icl.sh \
  --pack-dir docs/blog/raw_logs/blog_raw_logs \
  --task query-optimize \
  --model kimi-k2.6 \
  --jobs-dir "$JOBS_DIR" \
  --context-variant debug_action \
  --inject-mode sdk_live \
  --endpoint-profile seed-coding-plan \
  --sdk-live-intercept-tool Bash \
  --sdk-live-install-timeout 900 \
  --setup-timeout 1200 \
  --agent-timeout 1800 \
  --verifier-timeout 600
