#!/usr/bin/env bash
set -euo pipefail

PACK_DIR="runs/harbor_icl_baseline"
MATRIX_JSON=""
MODEL="${MODEL:-kimi-k2.6}"
INJECT_MODE="continue_after"
ENDPOINT_PROFILE="${HTD_ENDPOINT_PROFILE:-auto}"
LIMIT="1"
TASK_FILTERS=()
CONTEXT_VARIANTS=("outcome_only" "raw_trace" "prompt_filtered" "debug_trajectory" "debug_action")
INCLUDE_SMOKE_PASSED=0
REQUIRE_ARTIFACT=1
BUILD_PACK=1
RUN_HARBOR=0
FORCE_RUN=0
PREFLIGHT_TIMEOUT="20"
FIRST_TURN_TIMEOUT="75"
VERIFIER_TIMEOUT="600"
JOBS_DIR=""
SUITE_DIR=""
SDK_LIVE_INTERCEPT_TOOLS=("WebSearch" "WebFetch")

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_icl_baseline_suite.sh [options]

Purpose:
  Run the runtime-ICL baseline suite for the same task/model/endpoint across
  multiple context-selection methods. Without --run this performs endpoint
  preflight and live-controller replay only. With --run it launches Harbor for
  each context variant sequentially, using the same inject mode and verifier
  timeout.

Default context variants:
  outcome_only, raw_trace, prompt_filtered, debug_trajectory, debug_action

Options:
  --pack-dir DIR              ICL pack. Default: runs/harbor_icl_baseline
  --matrix-json PATH          Candidate matrix. Default: <pack-dir>/task_matrix.json
  --model NAME                Model name. Default: $MODEL or kimi-k2.6
  --inject-mode MODE          tool, prelude, continue_after, sdk_live, or hooks_live.
                              Default: continue_after
  --endpoint-profile NAME     Endpoint profile. Default: auto
  --limit N                   Number of matrix tasks to select when --task is
                              not passed. Default: 1
  --task NAME                 Run this task from the matrix. May repeat.
  --context-variant NAME      Context variant to include. May repeat. Passing
                              this option replaces the default variant list.
  --include-smoke-passed      Include tasks already marked with a smoke_note
  --allow-missing-artifact    Do not require captured teacher artifacts
  --no-build-pack             Do not rebuild selected task cards/variants
  --jobs-dir DIR              Harbor output dir. Default follows matrix runner
  --suite-dir DIR             Output directory for this suite. Default:
                              <pack-dir>/baseline_suites/<timestamp>-<model>-<mode>
  --first-turn-timeout SEC    continue_after first-turn timeout. Default: 75
  --verifier-timeout SEC      Official verifier timeout. Default: 600
  --sdk-live-intercept-tool NAME
                              sdk_live intercept tool. May repeat.
  --preflight-timeout SEC     Endpoint preflight timeout. Default: 20
  --force-run                 Run Harbor even when endpoint preflight fails
  --run                       Actually launch Harbor runs
  -h, --help                  Show help.
USAGE
}

VARIANTS_SET=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack-dir) PACK_DIR="$2"; shift 2 ;;
    --matrix-json) MATRIX_JSON="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --inject-mode) INJECT_MODE="$2"; shift 2 ;;
    --endpoint-profile) ENDPOINT_PROFILE="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --task) TASK_FILTERS+=("$2"); shift 2 ;;
    --context-variant)
      if [[ "$VARIANTS_SET" == "0" ]]; then
        CONTEXT_VARIANTS=()
        VARIANTS_SET=1
      fi
      CONTEXT_VARIANTS+=("$2")
      shift 2
      ;;
    --include-smoke-passed) INCLUDE_SMOKE_PASSED=1; shift ;;
    --allow-missing-artifact) REQUIRE_ARTIFACT=0; shift ;;
    --no-build-pack) BUILD_PACK=0; shift ;;
    --jobs-dir) JOBS_DIR="$2"; shift 2 ;;
    --suite-dir) SUITE_DIR="$2"; shift 2 ;;
    --first-turn-timeout) FIRST_TURN_TIMEOUT="$2"; shift 2 ;;
    --verifier-timeout) VERIFIER_TIMEOUT="$2"; shift 2 ;;
    --sdk-live-intercept-tool)
      if [[ ${#SDK_LIVE_INTERCEPT_TOOLS[@]} -eq 2 && "${SDK_LIVE_INTERCEPT_TOOLS[0]}" == "WebSearch" && "${SDK_LIVE_INTERCEPT_TOOLS[1]}" == "WebFetch" ]]; then
        SDK_LIVE_INTERCEPT_TOOLS=()
      fi
      SDK_LIVE_INTERCEPT_TOOLS+=("$2")
      shift 2
      ;;
    --preflight-timeout) PREFLIGHT_TIMEOUT="$2"; shift 2 ;;
    --force-run) FORCE_RUN=1; shift ;;
    --run) RUN_HARBOR=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ${#CONTEXT_VARIANTS[@]} -eq 0 ]]; then
  echo "At least one --context-variant is required" >&2
  exit 2
fi

if [[ "$INJECT_MODE" != "tool" && "$INJECT_MODE" != "prelude" && "$INJECT_MODE" != "continue_after" && "$INJECT_MODE" != "sdk_live" && "$INJECT_MODE" != "hooks_live" ]]; then
  echo "--inject-mode must be tool, prelude, continue_after, sdk_live, or hooks_live" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -z "$MATRIX_JSON" ]]; then
  MATRIX_JSON="$PACK_DIR/task_matrix.json"
fi

SAFE_MODEL="${MODEL//\//-}"
SAFE_MODEL="${SAFE_MODEL//./-}"
if [[ -z "$SUITE_DIR" ]]; then
  SUITE_DIR="$PACK_DIR/baseline_suites/$(date +%Y%m%dT%H%M%S)-${SAFE_MODEL}-${INJECT_MODE}"
fi
mkdir -p "$SUITE_DIR"

echo "== Harness-TrajecDebug Runtime ICL Baseline Suite =="
echo "Pack dir: $PACK_DIR"
echo "Matrix: $MATRIX_JSON"
echo "Model: $MODEL"
echo "Inject mode: $INJECT_MODE"
echo "Endpoint profile: $ENDPOINT_PROFILE"
echo "Suite dir: $SUITE_DIR"
echo "Context variants:"
printf '  - %s\n' "${CONTEXT_VARIANTS[@]}"
if [[ ${#TASK_FILTERS[@]} -gt 0 ]]; then
  echo "Task filters:"
  printf '  - %s\n' "${TASK_FILTERS[@]}"
else
  echo "Task selection limit: $LIMIT"
fi

python3 - "$SUITE_DIR/config.json" "$PACK_DIR" "$MATRIX_JSON" "$MODEL" "$INJECT_MODE" "$ENDPOINT_PROFILE" "$LIMIT" "$FIRST_TURN_TIMEOUT" "$VERIFIER_TIMEOUT" "$RUN_HARBOR" "$(IFS=,; echo "${SDK_LIVE_INTERCEPT_TOOLS[*]}")" "${CONTEXT_VARIANTS[@]}" <<'PY'
import json
import sys
from pathlib import Path

(
    output,
    pack_dir,
    matrix_json,
    model,
    inject_mode,
    endpoint_profile,
    limit,
    first_turn_timeout,
    verifier_timeout,
    run_harbor,
    intercept_tools_csv,
    *variants,
) = sys.argv[1:]
intercept_tools = [tool for tool in intercept_tools_csv.split(",") if tool]

Path(output).write_text(
    json.dumps(
        {
            "pack_dir": pack_dir,
            "matrix_json": matrix_json,
            "model": model,
            "inject_mode": inject_mode,
            "endpoint_profile": endpoint_profile,
            "limit": int(limit),
            "first_turn_timeout": int(float(first_turn_timeout)),
            "verifier_timeout": int(float(verifier_timeout)),
            "run_harbor": run_harbor == "1",
            "live_intercept_tools": intercept_tools,
            "context_variants": variants,
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY

SUMMARY_JSONL="$SUITE_DIR/variant-summaries.jsonl"
: > "$SUMMARY_JSONL"

for variant in "${CONTEXT_VARIANTS[@]}"; do
  echo
  echo "== Variant: $variant =="
  VARIANT_BATCH_DIR="$SUITE_DIR/$variant"
  mkdir -p "$VARIANT_BATCH_DIR"
  args=(
    --pack-dir "$PACK_DIR"
    --matrix-json "$MATRIX_JSON"
    --model "$MODEL"
    --inject-mode "$INJECT_MODE"
    --endpoint-profile "$ENDPOINT_PROFILE"
    --limit "$LIMIT"
    --context-variant "$variant"
    --batch-dir "$VARIANT_BATCH_DIR"
    --first-turn-timeout "$FIRST_TURN_TIMEOUT"
    --verifier-timeout "$VERIFIER_TIMEOUT"
    --preflight-timeout "$PREFLIGHT_TIMEOUT"
  )
  if [[ "$BUILD_PACK" == "0" ]]; then
    args+=(--no-build-pack)
  fi
  if [[ "$INCLUDE_SMOKE_PASSED" == "1" ]]; then
    args+=(--include-smoke-passed)
  fi
  if [[ "$REQUIRE_ARTIFACT" == "0" ]]; then
    args+=(--allow-missing-artifact)
  fi
  if [[ "$RUN_HARBOR" == "1" ]]; then
    args+=(--run)
  fi
  if [[ "$FORCE_RUN" == "1" ]]; then
    args+=(--force-run)
  fi
  if [[ -n "$JOBS_DIR" ]]; then
    args+=(--jobs-dir "$JOBS_DIR")
  fi
  if [[ ${#TASK_FILTERS[@]} -gt 0 ]]; then
    for task in "${TASK_FILTERS[@]}"; do
      args+=(--task "$task")
    done
  fi
  if [[ "$INJECT_MODE" == "sdk_live" || "$INJECT_MODE" == "hooks_live" ]]; then
    for tool in "${SDK_LIVE_INTERCEPT_TOOLS[@]}"; do
      args+=(--sdk-live-intercept-tool "$tool")
    done
  fi

  scripts/run_icl_matrix_canaries.sh "${args[@]}" | tee "$VARIANT_BATCH_DIR/run.log"
  python3 - "$variant" "$VARIANT_BATCH_DIR/summary.json" >> "$SUMMARY_JSONL" <<'PY'
import json
import sys
from pathlib import Path
variant = sys.argv[1]
summary_path = Path(sys.argv[2])
summary = json.loads(summary_path.read_text())
print(json.dumps({"context_variant": variant, "summary": summary}, ensure_ascii=False))
PY
done

echo
echo "== Suite summary =="
python3 - "$SUMMARY_JSONL" "$SUITE_DIR/summary.md" <<'PY'
import json
import sys
from pathlib import Path

jsonl = Path(sys.argv[1])
output = Path(sys.argv[2])
rows = []
for line in jsonl.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    outer = json.loads(line)
    variant = outer["context_variant"]
    summary = outer["summary"]
    preflight = summary.get("preflight", {})
    for row in summary.get("rows", []):
        replay = row.get("replay") or {}
        run = row.get("run") or {}
        rows.append(
            {
                "variant": variant,
                "task": row.get("task"),
                "preflight_kind": preflight.get("kind"),
                "preflight_ok": preflight.get("ok"),
                "replay": replay.get("all_injected"),
                "reasons": replay.get("reasons") or [],
                "status": run.get("status"),
                "reward": run.get("reward"),
                "trial": run.get("trial_dir") or "",
            }
        )

lines = [
    "# Runtime ICL Baseline Suite",
    "",
    f"Source: `{jsonl}`",
    "",
    "| Variant | Task | Preflight | Replay | Run status | Reward | Trial |",
    "| --- | --- | --- | --- | --- | ---: | --- |",
]
for row in rows:
    reasons = ", ".join(str(item) for item in row["reasons"] if item)
    replay = "injected" if row["replay"] else "missing"
    if reasons:
        replay += f" ({reasons})"
    preflight = f"{row['preflight_kind']} ok={row['preflight_ok']}"
    lines.append(
        f"| `{row['variant']}` | `{row['task']}` | `{preflight}` | {replay} | `{row['status']}` | {row['reward']} | `{row['trial']}` |"
    )
lines.append("")
output.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
PY

scripts/aggregate_icl_results.py --pack-dir "$PACK_DIR" > "$SUITE_DIR/aggregate.stdout.json"
scripts/report_icl_readiness.py --pack-dir "$PACK_DIR" > "$SUITE_DIR/readiness.stdout.json"
