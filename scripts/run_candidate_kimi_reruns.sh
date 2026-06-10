#!/usr/bin/env bash
set -euo pipefail

PACK_DIR="runs/harbor_icl_baseline"
MODEL="${MODEL:-kimi-k2.6}"
ENDPOINT_PROFILE="${HTD_ENDPOINT_PROFILE:-auto}"
INJECT_MODE="prelude"
SETUP_TIMEOUT="1200"
AGENT_TIMEOUT="1200"
VERIFIER_TIMEOUT="1200"
DRY_RUN=0
PREFLIGHT=1
PREFLIGHT_TIMEOUT="20"
NO_FORCE_BUILD=1
SUMMARIZE_AFTER=1
STOP_ON_ERROR=0
SUMMARY_MARKDOWN="docs/candidate-kimi-rerun-status.md"
SUMMARY_JSON="runs/harbor_icl_baseline/candidate_kimi_rerun_status.json"
TASKS=("make-mips-interpreter" "make-doom-for-mips")
CONTEXT_VARIANTS=("oracle_grounded" "debug_action")

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_candidate_kimi_reruns.sh [options]

Purpose:
  Run the accepted Codex + GPT-5.5 failure candidates through both
  Harness-TrajecDebug context methods:

    - oracle_grounded
    - debug_action

  The script preflights the model endpoint before launching any Harbor job. If
  the endpoint is quota-limited or missing credentials, it exits before starting
  a model run.

Options:
  --pack-dir DIR              ICL pack. Default: runs/harbor_icl_baseline
  --model NAME                Model name. Default: $MODEL or kimi-k2.6
  --endpoint-profile NAME     Endpoint profile. Default: $HTD_ENDPOINT_PROFILE or auto
  --inject-mode MODE          prelude, continue_after, hooks_live, sdk_live, or tool.
                              Default: prelude
  --task NAME                 Candidate task. May repeat. Replaces defaults.
  --context-variant NAME      Context variant. May repeat. Replaces defaults.
  --setup-timeout SEC         Agent setup timeout. Default: 1200
  --agent-timeout SEC         Agent execution timeout. Default: 1200
  --verifier-timeout SEC      Official verifier timeout. Default: 1200
  --preflight-timeout SEC     Endpoint preflight timeout. Default: 20
  --skip-preflight            Launch jobs without the upfront endpoint check
  --force-build               Force task image build instead of reusing cached image
  --summary-markdown PATH     Markdown status report path.
                              Default: docs/candidate-kimi-rerun-status.md
  --summary-json PATH         JSON status report path.
                              Default: runs/harbor_icl_baseline/candidate_kimi_rerun_status.json
  --no-summary                Do not regenerate the candidate status report after runs
  --stop-on-error             Stop the queue after the first failed Harbor run
  --dry-run                   Print the generated commands and validate files only
  -h, --help                  Show this help

Default task queue:
  make-mips-interpreter, make-doom-for-mips

Default context queue:
  oracle_grounded, debug_action
USAGE
}

TASKS_SET=0
VARIANTS_SET=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack-dir) PACK_DIR="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --endpoint-profile) ENDPOINT_PROFILE="$2"; shift 2 ;;
    --inject-mode) INJECT_MODE="$2"; shift 2 ;;
    --task)
      if [[ "$TASKS_SET" == "0" ]]; then
        TASKS=()
        TASKS_SET=1
      fi
      TASKS+=("$2")
      shift 2
      ;;
    --context-variant)
      if [[ "$VARIANTS_SET" == "0" ]]; then
        CONTEXT_VARIANTS=()
        VARIANTS_SET=1
      fi
      CONTEXT_VARIANTS+=("$2")
      shift 2
      ;;
    --setup-timeout) SETUP_TIMEOUT="$2"; shift 2 ;;
    --agent-timeout) AGENT_TIMEOUT="$2"; shift 2 ;;
    --verifier-timeout) VERIFIER_TIMEOUT="$2"; shift 2 ;;
    --preflight-timeout) PREFLIGHT_TIMEOUT="$2"; shift 2 ;;
    --skip-preflight) PREFLIGHT=0; shift ;;
    --force-build) NO_FORCE_BUILD=0; shift ;;
    --summary-markdown) SUMMARY_MARKDOWN="$2"; shift 2 ;;
    --summary-json) SUMMARY_JSON="$2"; shift 2 ;;
    --no-summary) SUMMARIZE_AFTER=0; shift ;;
    --stop-on-error) STOP_ON_ERROR=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ${#TASKS[@]} -eq 0 ]]; then
  echo "At least one --task is required" >&2
  exit 2
fi

if [[ ${#CONTEXT_VARIANTS[@]} -eq 0 ]]; then
  echo "At least one --context-variant is required" >&2
  exit 2
fi

case "$INJECT_MODE" in
  tool|prelude|continue_after|hooks_live|sdk_live) ;;
  *)
    echo "--inject-mode must be tool, prelude, continue_after, hooks_live, or sdk_live" >&2
    exit 2
    ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -f "$HOME/.bashrc" ]]; then
  set +u
  # shellcheck disable=SC1090
  source "$HOME/.bashrc"
  set -u
fi

variant_jobs_dir() {
  case "$1" in
    oracle_grounded) echo "$PACK_DIR/harbor_runs_oracle_grounded" ;;
    debug_action) echo "$PACK_DIR/harbor_runs_joint_failure" ;;
    *) echo "$PACK_DIR/harbor_runs_candidate" ;;
  esac
}

validate_queue() {
  local missing=0
  for task in "${TASKS[@]}"; do
    if [[ ! -d "$PACK_DIR/task_variants/no_icl/$task" ]]; then
      echo "Missing task variant: $PACK_DIR/task_variants/no_icl/$task" >&2
      missing=1
    fi
    for variant in "${CONTEXT_VARIANTS[@]}"; do
      if [[ ! -f "$PACK_DIR/teacher_cards/$task/$variant.md" ]]; then
        echo "Missing teacher card: $PACK_DIR/teacher_cards/$task/$variant.md" >&2
        missing=1
      fi
    done
  done
  if [[ "$missing" == "1" ]]; then
    exit 1
  fi
}

validate_queue

echo "== Harness-TrajecDebug candidate Kimi rerun queue =="
echo "Pack dir: $PACK_DIR"
echo "Model: $MODEL"
echo "Endpoint profile: $ENDPOINT_PROFILE"
echo "Inject mode: $INJECT_MODE"
echo "Preflight: $PREFLIGHT"
echo "Dry run: $DRY_RUN"
echo "Summarize after runs: $SUMMARIZE_AFTER"
echo "Tasks:"
printf '  - %s\n' "${TASKS[@]}"
echo "Context variants:"
printf '  - %s\n' "${CONTEXT_VARIANTS[@]}"

if [[ "$DRY_RUN" != "1" && "$PREFLIGHT" == "1" ]]; then
  echo
  echo "== Endpoint preflight =="
  if ! scripts/check_model_endpoint.py \
    --endpoint-profile "$ENDPOINT_PROFILE" \
    --model "$MODEL" \
    --timeout "$PREFLIGHT_TIMEOUT"; then
    echo
    echo "Endpoint preflight failed; no Harbor reruns were launched." >&2
    exit 75
  fi
fi

RUN_FAILURES=0
for task in "${TASKS[@]}"; do
  for variant in "${CONTEXT_VARIANTS[@]}"; do
    jobs_dir="$(variant_jobs_dir "$variant")"
    cmd=(
      scripts/run_harbor_dynamic_icl.sh
      --pack-dir "$PACK_DIR"
      --jobs-dir "$jobs_dir"
      --model "$MODEL"
      --task "$task"
      --endpoint-profile "$ENDPOINT_PROFILE"
      --context-variant "$variant"
      --inject-mode "$INJECT_MODE"
      --setup-timeout "$SETUP_TIMEOUT"
      --agent-timeout "$AGENT_TIMEOUT"
      --verifier-timeout "$VERIFIER_TIMEOUT"
    )
    if [[ "$NO_FORCE_BUILD" == "1" ]]; then
      cmd+=(--no-force-build)
    fi

    echo
    echo "== Candidate: $task / $variant =="
    printf '%q ' "${cmd[@]}"
    echo

    if [[ "$DRY_RUN" == "1" ]]; then
      continue
    fi
    if "${cmd[@]}"; then
      echo "Candidate run finished: $task / $variant"
    else
      code=$?
      RUN_FAILURES=1
      echo "Candidate run failed with exit code $code: $task / $variant" >&2
      if [[ "$STOP_ON_ERROR" == "1" ]]; then
        exit "$code"
      fi
    fi
  done
done

if [[ "$DRY_RUN" != "1" && "$SUMMARIZE_AFTER" == "1" ]]; then
  summary_args=(
    scripts/summarize_candidate_kimi_reruns.py
    --pack-dir "$PACK_DIR"
    --model "$MODEL"
    --inject-mode "$INJECT_MODE"
    --markdown-output "$SUMMARY_MARKDOWN"
    --json-output "$SUMMARY_JSON"
  )
  for task in "${TASKS[@]}"; do
    summary_args+=(--task "$task")
  done
  for variant in "${CONTEXT_VARIANTS[@]}"; do
    summary_args+=(--context-variant "$variant")
  done

  echo
  echo "== Regenerating candidate rerun status =="
  printf '%q ' "${summary_args[@]}"
  echo
  "${summary_args[@]}"
fi

if [[ "$RUN_FAILURES" == "1" ]]; then
  exit 1
fi
