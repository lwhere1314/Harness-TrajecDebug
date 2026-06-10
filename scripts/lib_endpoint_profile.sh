#!/usr/bin/env bash

apply_endpoint_profile() {
  local profile="${1:-auto}"
  case "$profile" in
    auto)
      if [[ -n "${ANTHROPIC_BASE_URL:-}" || -n "${ANTHROPIC_API_KEY:-}" ]]; then
        export HTD_ENDPOINT_RESOLVED_PROFILE="anthropic"
      elif [[ -n "${SEED_CODING_PLAN_BASE_URL:-}" || -n "${SEED_CODING_PLAN_API_KEY:-}" ]]; then
        export HTD_ENDPOINT_RESOLVED_PROFILE="seed-coding-plan"
      elif [[ -n "${TOKEN_PLAN_BASE_URL:-}" || -n "${TOKEN_PLAN_API_KEY:-}" ]]; then
        export HTD_ENDPOINT_RESOLVED_PROFILE="token-plan"
      else
        export HTD_ENDPOINT_RESOLVED_PROFILE="auto"
      fi
      export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-${SEED_CODING_PLAN_BASE_URL:-${TOKEN_PLAN_BASE_URL:-}}}"
      export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-${SEED_CODING_PLAN_API_KEY:-${TOKEN_PLAN_API_KEY:-}}}"
      ;;
    anthropic)
      export HTD_ENDPOINT_RESOLVED_PROFILE="anthropic"
      export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-}"
      export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
      ;;
    token-plan|token_plan)
      export HTD_ENDPOINT_RESOLVED_PROFILE="token-plan"
      export ANTHROPIC_BASE_URL="${TOKEN_PLAN_BASE_URL:-}"
      export ANTHROPIC_API_KEY="${TOKEN_PLAN_API_KEY:-}"
      ;;
    seed-coding-plan|seed_coding_plan|seed)
      export HTD_ENDPOINT_RESOLVED_PROFILE="seed-coding-plan"
      export ANTHROPIC_BASE_URL="${SEED_CODING_PLAN_BASE_URL:-}"
      export ANTHROPIC_API_KEY="${SEED_CODING_PLAN_API_KEY:-}"
      ;;
    ark)
      export HTD_ENDPOINT_RESOLVED_PROFILE="ark"
      export ANTHROPIC_BASE_URL="${ARK_BASE_URL:-https://ark.cn-beijing.volces.com/api/coding}"
      export ANTHROPIC_API_KEY="${ARK_API_KEY:-}"
      ;;
    dashscope)
      export HTD_ENDPOINT_RESOLVED_PROFILE="dashscope"
      export ANTHROPIC_BASE_URL="${DASHSCOPE_BASE_URL:-https://coding.dashscope.aliyuncs.com/apps/anthropic}"
      export ANTHROPIC_API_KEY="${DASHSCOPE_API_KEY:-}"
      ;;
    kimi|kimi-code|kimi_code)
      export HTD_ENDPOINT_RESOLVED_PROFILE="kimi"
      export ANTHROPIC_BASE_URL="${KIMI_BASE_URL:-https://api.kimi.com/coding/}"
      export ANTHROPIC_API_KEY="${KIMI_API_KEY:-${MOONSHOT_API_KEY:-}}"
      ;;
    *)
      echo "Unknown endpoint profile: $profile" >&2
      return 2
      ;;
  esac
  export HTD_ENDPOINT_PROFILE="$profile"
}
