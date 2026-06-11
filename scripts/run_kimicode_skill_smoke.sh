#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIMI_CODE_ROOT="${KIMI_CODE_ROOT:-$REPO_ROOT/kimi-code}"
NODE24_BIN="${NODE24_BIN:-/Users/hugo/.nvm/versions/node/v24.16.0/bin}"
KIMI_CODE_HOME="${KIMI_CODE_HOME:-$REPO_ROOT/runs/kimi_code_smoke/home}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-stream-json}"

if [[ -f "$HOME/.bashrc" ]]; then
  # shellcheck source=/dev/null
  set +u
  source "$HOME/.bashrc"
  set -u
fi

: "${SEED_CODING_PLAN_BASE_URL:?Set SEED_CODING_PLAN_BASE_URL or source ~/.bashrc}"
: "${SEED_CODING_PLAN_API_KEY:?Set SEED_CODING_PLAN_API_KEY or source ~/.bashrc}"

export KIMI_CODE_HOME
export KIMI_MODEL_NAME="${KIMI_MODEL_NAME:-kimi-k2.6}"
export KIMI_MODEL_PROVIDER_TYPE="${KIMI_MODEL_PROVIDER_TYPE:-anthropic}"
export KIMI_MODEL_BASE_URL="${KIMI_MODEL_BASE_URL:-$SEED_CODING_PLAN_BASE_URL}"
export KIMI_MODEL_API_KEY="${KIMI_MODEL_API_KEY:-$SEED_CODING_PLAN_API_KEY}"
export KIMI_MODEL_MAX_CONTEXT_SIZE="${KIMI_MODEL_MAX_CONTEXT_SIZE:-262144}"
export KIMI_MODEL_MAX_OUTPUT_SIZE="${KIMI_MODEL_MAX_OUTPUT_SIZE:-4096}"
export KIMI_MODEL_CAPABILITIES="${KIMI_MODEL_CAPABILITIES:-tool_use}"

if [[ ! -x "$NODE24_BIN/node" ]]; then
  echo "Node 24 not found at $NODE24_BIN/node; set NODE24_BIN=/path/to/node24/bin" >&2
  exit 127
fi
if [[ ! -x "$KIMI_CODE_ROOT/node_modules/.bin/tsx" ]]; then
  echo "Kimi Code dev dependencies not found under $KIMI_CODE_ROOT" >&2
  echo "Run pnpm install in the Kimi Code checkout, or set KIMI_CODE_ROOT." >&2
  exit 127
fi

mkdir -p "$KIMI_CODE_HOME"
export PATH="$NODE24_BIN:$PATH"

PROMPT="${1:-/harness-runtime-icl Run exactly this command from the Harness-TrajecDebug repo root: plugins/harness-trajdebug-agent/scripts/htd-agent doctor. Do not modify files. Summarize whether the plugin wrapper, project skills, and SEED endpoint variables are available.}"

cd "$REPO_ROOT"
exec "$KIMI_CODE_ROOT/node_modules/.bin/tsx" \
  --tsconfig "$KIMI_CODE_ROOT/apps/kimi-code/tsconfig.json" \
  --import "$KIMI_CODE_ROOT/build/register-raw-text-loader.mjs" \
  "$KIMI_CODE_ROOT/apps/kimi-code/src/main.ts" \
  -p "$PROMPT" \
  --output-format "$OUTPUT_FORMAT"
