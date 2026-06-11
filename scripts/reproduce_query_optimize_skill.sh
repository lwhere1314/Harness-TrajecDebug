#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TASK="query-optimize"
MODEL="${MODEL:-kimi-k2.6}"
ENDPOINT_PROFILE="${HTD_ENDPOINT_PROFILE:-seed-coding-plan}"
JOBS_DIR=""
RUN_ARGS=()
RUN_HARBOR=0
FIRST_TURN_TIMEOUT="90"
VERIFIER_TIMEOUT="600"
PREFLIGHT_TIMEOUT="20"
RUN_DEBUG_ACTION=1
RUN_OUTCOME_ONLY=1

usage() {
  cat <<'USAGE'
Usage:
  scripts/reproduce_query_optimize_skill.sh [options]

Purpose:
  One-command reproduction of the query-optimize runtime ICL canary described
  in docs/query-optimize-skill-repro-20260611.md.

Default behavior is safe: it performs endpoint preflight plus live-controller
replay only. Add --run to launch the Harbor task and spend model calls.

Options:
  --run                         Actually run Harbor. Without this, dry-run only.
  --model NAME                  Model name. Default: $MODEL or kimi-k2.6.
  --endpoint-profile NAME       auto, anthropic, seed-coding-plan, token-plan,
                                ark, dashscope, or kimi. Default:
                                $HTD_ENDPOINT_PROFILE or seed-coding-plan.
  --jobs-dir DIR                Output directory. Default:
                                runs/harbor_icl_baseline/harbor_runs_query_skill_repro_<timestamp>
  --debug-action-only           Run only debug_action + sdk_live.
  --outcome-only                Run only outcome_only + sdk_live.
  --first-turn-timeout SEC      First-turn timeout passed to the canary.
                                Default: 90.
  --verifier-timeout SEC        Verifier timeout. Default: 600.
  --preflight-timeout SEC       Endpoint preflight timeout. Default: 20.
  --force-run                   Pass through to the canary when preflight fails.
  --skip-preflight              Pass through to the canary.
  -h, --help                    Show help.

Required credentials:
  Set the variables for the selected endpoint profile. For example:

    export ARK_API_KEY=...
    export ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/coding
    scripts/reproduce_query_optimize_skill.sh --endpoint-profile ark --run

  Or:

    export SEED_CODING_PLAN_API_KEY=...
    export SEED_CODING_PLAN_BASE_URL=...
    scripts/reproduce_query_optimize_skill.sh --endpoint-profile seed-coding-plan --run

This wrapper never prints API keys.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run) RUN_HARBOR=1; shift ;;
    --model) MODEL="$2"; shift 2 ;;
    --endpoint-profile) ENDPOINT_PROFILE="$2"; shift 2 ;;
    --jobs-dir) JOBS_DIR="$2"; shift 2 ;;
    --debug-action-only) RUN_DEBUG_ACTION=1; RUN_OUTCOME_ONLY=0; shift ;;
    --outcome-only) RUN_DEBUG_ACTION=0; RUN_OUTCOME_ONLY=1; shift ;;
    --first-turn-timeout) FIRST_TURN_TIMEOUT="$2"; shift 2 ;;
    --verifier-timeout) VERIFIER_TIMEOUT="$2"; shift 2 ;;
    --preflight-timeout) PREFLIGHT_TIMEOUT="$2"; shift 2 ;;
    --force-run) RUN_ARGS+=(--force-run); shift ;;
    --skip-preflight) RUN_ARGS+=(--skip-preflight); shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$JOBS_DIR" ]]; then
  JOBS_DIR="runs/harbor_icl_baseline/harbor_runs_query_skill_repro_$(date +%Y%m%d_%H%M%S)"
fi

CANARY_BASE=(
  --task "$TASK"
  --model "$MODEL"
  --inject-mode sdk_live
  --sdk-live-intercept-tool Bash
  --endpoint-profile "$ENDPOINT_PROFILE"
  --jobs-dir "$JOBS_DIR"
  --first-turn-timeout "$FIRST_TURN_TIMEOUT"
  --verifier-timeout "$VERIFIER_TIMEOUT"
  --preflight-timeout "$PREFLIGHT_TIMEOUT"
)

if [[ "$RUN_HARBOR" == "1" ]]; then
  CANARY_BASE+=(--run)
fi

echo "== Harness-TrajecDebug query-optimize reproduction =="
echo "Task: $TASK"
echo "Model: $MODEL"
echo "Endpoint profile: $ENDPOINT_PROFILE"
echo "Jobs dir: $JOBS_DIR"
echo "Mode: $([[ "$RUN_HARBOR" == "1" ]] && echo run || echo dry-run)"
echo

run_variant() {
  local variant="$1"
  echo "== Variant: $variant + sdk_live =="
  scripts/run_daily_icl_canary.sh \
    "${CANARY_BASE[@]}" \
    "${RUN_ARGS[@]}" \
    --context-variant "$variant"
  echo
}

if [[ "$RUN_DEBUG_ACTION" == "1" ]]; then
  run_variant debug_action
fi

if [[ "$RUN_OUTCOME_ONLY" == "1" ]]; then
  run_variant outcome_only
fi

echo "== Raw logs =="
echo "$JOBS_DIR"

if [[ "$RUN_HARBOR" != "1" ]]; then
  echo
  echo "Dry-run complete. Add --run to launch the full Harbor reproduction."
  exit 0
fi

python3 - "$JOBS_DIR" <<'PY'
import json
import sys
from pathlib import Path

jobs = Path(sys.argv[1])
print()
print("== Result summary ==")
rows = []
for summary in sorted(jobs.glob("htd-dynamic-icl-sdk_live-*/*/sdk-live-summary.json")):
    data = json.loads(summary.read_text())
    job = summary.parents[1].name
    trial = summary.parent
    if "debug_action" in job:
        variant = "debug_action"
    elif "outcome_only" in job:
        variant = "outcome_only"
    else:
        variant = job
    rows.append({
        "variant": variant,
        "reward": data.get("reward"),
        "status": data.get("status"),
        "injections": data.get("injection_count"),
        "trial": str(trial),
    })

if not rows:
    print(f"No sdk-live-summary.json files found under {jobs}")
    sys.exit(0)

for row in rows:
    print(
        f"{row['variant']}: reward={row['reward']} "
        f"status={row['status']} injections={row['injections']}"
    )
    print(f"  {row['trial']}")
PY
