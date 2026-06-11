#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACK_DIR="$REPO_ROOT/docs/blog/raw_logs/blog_raw_logs"
FAIL_TRIAL="$PACK_DIR/harbor_runs_query_baseline/htd-icl-no_icl-query-optimize-kimi-k2-6/query-optimize__cTzLSZp"
SUCCESS_TRIAL="$PACK_DIR/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq"
MODE="recorded"
CARD_VARIANT="debug_action"
TEACHER_KIND="pass"
OUT_DIR="$REPO_ROOT/runs/demo-query-optimize-trace-to-card"
PAUSE="${HTD_DEMO_PAUSE:-1}"
COMPACT="${HTD_DEMO_COMPACT:-0}"
LIVE_ROOT="${HTD_DEMO_LIVE_ROOT:-$REPO_ROOT}"
LIVE_ROOT_SOURCE="${HTD_DEMO_LIVE_ROOT:+env}"
NO_FORCE_BUILD="${HTD_DEMO_NO_FORCE_BUILD:-1}"
KEEP_ENVIRONMENT="${HTD_DEMO_KEEP_ENVIRONMENT:-0}"

usage() {
  cat <<'USAGE'
Usage:
  demo/query-optimize-trace-to-card.sh [--recorded|--live|--live-fail-teacher|--live-full-fail-teacher] [--compact] [--out-dir DIR]

Recorded mode is fast and uses checked-in failing/passing evidence.
Live mode runs the second query-optimize debug_action + sdk_live attempt.
Live fail-teacher mode uses a reward-0 failure-derived card for the second run.
Live full fail-teacher mode runs a fresh no-ICL first attempt before diagnosis.

Environment:
  HTD_DEMO_PAUSE=0             Disable short pauses between sections.
  HTD_DEMO_COMPACT=1           Agent-friendly output; write long logs to files.
  HTD_DEMO_NO_FORCE_BUILD=1    Reuse warm Docker images for live mode. Default: 1.
  HTD_DEMO_KEEP_ENVIRONMENT=1  Keep Harbor Docker containers after live mode.
  HTD_DEMO_LIVE_ROOT=DIR       Optional repo mirror for live long Harbor runs.
  HARBOR_RUNNER=FILE           Required by --live-full-fail-teacher unless your
                               local default runner path exists.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --recorded) MODE="recorded"; shift ;;
    --live) MODE="live"; shift ;;
    --live-fail-teacher)
      MODE="live"
      CARD_VARIANT="fail_debug_action"
      TEACHER_KIND="fail"
      shift
      ;;
    --live-full-fail-teacher)
      MODE="live_full_fail_teacher"
      CARD_VARIANT="fail_debug_action"
      TEACHER_KIND="fail"
      shift
      ;;
    --compact) COMPACT="1"; PAUSE="0"; shift ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$MODE" == "live_full_fail_teacher" && -z "${HTD_DEMO_LIVE_ROOT:-}" ]]; then
  DEFAULT_LIVE_MIRROR="$HOME/Documents/Harness-TrajecDebug"
  if [[ "$REPO_ROOT" == "$HOME/Projects/Harness-TrajecDebug" && -d "$DEFAULT_LIVE_MIRROR" ]]; then
    LIVE_ROOT="$DEFAULT_LIVE_MIRROR"
    LIVE_ROOT_SOURCE="auto-documents-mirror"
  fi
fi

say() {
  printf '\n\033[1;36m# %s\033[0m\n' "$*"
  if [[ "$PAUSE" != "0" ]]; then
    sleep "$PAUSE"
  fi
}

run_shell() {
  printf '\n$ %s\n' "$*"
  /bin/bash -lc "$*"
}

show_card() {
  local card="$1"
  if [[ "$COMPACT" == "1" ]]; then
    printf '\n$ python3 - %q  # compact card summary\n' "$card"
    python3 - "$card" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
print(f"card: {path}")
for line in lines:
    if line.startswith("# "):
        print(line)
    elif line.startswith("Teacher outcome:"):
        print(line)
    elif line.startswith("Failed gate:"):
        print(line)
    elif line.startswith("Pattern:"):
        print(line)
    elif line.startswith("## Recommended next action"):
        print("recommended_action: materialize /app/sol.sql")
    elif line.startswith("## Stop rule"):
        print("stop_rule: write artifact, cheap smoke check, then official verifier")
        break
PY
  else
    run_shell "sed -n '1,90p' '$card'"
  fi
}

show_verifier_stdout() {
  local stdout_file="$1"
  if [[ "$COMPACT" == "1" ]]; then
    printf '\n$ python3 - %q  # compact verifier summary\n' "$stdout_file"
    python3 - "$stdout_file" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
print(f"verifier_stdout: {path}")
for line in reversed(lines):
    if re.search(r"=+ .*passed.* in .* =+", line) or " failed, " in line or " passed in " in line:
        print(f"pytest_summary: {line.strip('= ')}")
        break
for line in lines:
    if "speedup_solution_vs_golden" in line:
        print(f"runtime_summary: {line.strip()[:220]}")
        break
for line in lines:
    if line.startswith("FAILED ") or line.startswith("PASSED "):
        print(f"verifier_case: {line.strip()[:220]}")
PY
  else
    run_shell "tail -n 45 '$stdout_file'"
  fi
}

summarize_diagnosis() {
  local diagnosis="$1"
  python3 - "$diagnosis" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
print(f"diagnosis: {path}")
print(f"outcome: {data.get('outcome')}")
print(f"final_failure: {data.get('final_failure')}")
critical = data.get("critical_step") or {}
print(
    "critical_step: "
    f"pattern={critical.get('pattern')} "
    f"step={critical.get('step_index')} "
    f"confidence={critical.get('confidence')}"
)
print(f"repair_hint: {data.get('repair_hint')}")
patterns = data.get("failure_patterns") or []
print("top_failure_patterns:")
for item in patterns[:2]:
    print(f"- {item.get('name')} ({item.get('confidence')})")
PY
}

summarize_closure() {
  local closure="$1"
  python3 - "$closure" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
row = data["rows"][0]
print(f"closure: {row['status']}")
print(f"card: {row['card_path']}")
for artifact in row.get("artifacts", []):
    print(f"artifact: {artifact['path']} bytes={artifact['bytes']}")
for check in row.get("checks", []):
    status = "ok" if check.get("ok") else "fail"
    print(f"check: {check['name']}={status} ({check['detail']})")
PY
}

summarize_sdk_live() {
  local summary="$1"
  python3 - "$summary" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
print(f"summary: {path}")
print(f"status: {data.get('status')}")
print(f"reward: {data.get('reward')}")
print(f"sdk_install: {','.join(data.get('sdk_install_statuses') or [])}")
print(f"claude_init: {data.get('claude_init')}")
print(f"injection_count: {data.get('injection_count')}")
print(f"injection_reasons: {data.get('injection_reasons')}")
PY
}

write_live_helper() {
  local helper="$1"
  local context_variant="$2"
  mkdir -p "$(dirname "$helper")"
  cat > "$helper" <<'LIVE_HELPER'
#!/usr/bin/env bash
set -euo pipefail

LIVE_JOBS="${1:?missing live jobs dir}"
CONTEXT_VARIANT="${2:-debug_action}"
LIVE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPACT="${HTD_DEMO_COMPACT:-0}"
NO_FORCE_BUILD="${HTD_DEMO_NO_FORCE_BUILD:-1}"
KEEP_ENVIRONMENT="${HTD_DEMO_KEEP_ENVIRONMENT:-0}"

if [[ -f "$HOME/.bashrc" ]]; then
  set +u
  # shellcheck source=/dev/null
  source "$HOME/.bashrc"
  set -u
fi

cd "$LIVE_ROOT"
mkdir -p "$LIVE_ROOT/$LIVE_JOBS"

printf '\n$ cd %q && scripts/run_harbor_dynamic_icl.sh --pack-dir docs/blog/raw_logs/blog_raw_logs --task query-optimize --model kimi-k2.6 --jobs-dir %q --context-variant %q --inject-mode sdk_live --endpoint-profile seed-coding-plan --sdk-live-intercept-tool Bash --sdk-live-install-timeout 900 --setup-timeout 1200 --agent-timeout 1800 --verifier-timeout 600\n' "$LIVE_ROOT" "$LIVE_JOBS" "$CONTEXT_VARIANT"
printf 'docker_reuse: no_force_build=%s keep_environment=%s\n' "$NO_FORCE_BUILD" "$KEEP_ENVIRONMENT"
RUN_LOG="$LIVE_ROOT/$LIVE_JOBS/htd-demo-live-run.log"
run_live() {
  local args=(
    scripts/run_harbor_dynamic_icl.sh
    --pack-dir docs/blog/raw_logs/blog_raw_logs \
    --task query-optimize \
    --model kimi-k2.6 \
    --jobs-dir "$LIVE_JOBS" \
    --context-variant "$CONTEXT_VARIANT" \
    --inject-mode sdk_live \
    --endpoint-profile seed-coding-plan \
    --sdk-live-intercept-tool Bash \
    --sdk-live-install-timeout 900 \
    --setup-timeout 1200 \
    --agent-timeout 1800 \
    --verifier-timeout 600
  )
  if [[ "$NO_FORCE_BUILD" == "1" ]]; then
    args+=(--no-force-build)
  fi
  if [[ "$KEEP_ENVIRONMENT" == "1" ]]; then
    args+=(--keep-environment)
  fi
  "${args[@]}"
}
if [[ "$COMPACT" == "1" ]]; then
  printf 'compact_log: %s\n' "$RUN_LOG"
  if ! run_live >"$RUN_LOG" 2>&1; then
    tail -n 80 "$RUN_LOG" >&2 || true
    exit 1
  fi
else
  run_live
fi

LIVE_TRIAL="$(find "$LIVE_ROOT/$LIVE_JOBS" -path '*/query-optimize__*' -type d | head -n 1)"
if [[ -z "$LIVE_TRIAL" ]]; then
  echo "Could not find live trial under $LIVE_ROOT/$LIVE_JOBS" >&2
  exit 1
fi

printf '\n$ cat %q\n' "$LIVE_TRIAL/verifier/reward.txt"
cat "$LIVE_TRIAL/verifier/reward.txt"

TAIL_LINES=45
if [[ "$COMPACT" == "1" ]]; then
  TAIL_LINES=18
fi
printf '\n$ tail -n %s %q\n' "$TAIL_LINES" "$LIVE_TRIAL/verifier/test-stdout.txt"
tail -n "$TAIL_LINES" "$LIVE_TRIAL/verifier/test-stdout.txt"

printf '\n$ PYTHONPATH=src python3 scripts/summarize_sdk_live_trial.py %q --output %q\n' "$LIVE_TRIAL" "$LIVE_TRIAL/sdk-live-summary.json"
PYTHONPATH=src python3 scripts/summarize_sdk_live_trial.py "$LIVE_TRIAL" --output "$LIVE_TRIAL/sdk-live-summary.json" >/dev/null

python3 - "$LIVE_TRIAL/sdk-live-summary.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
print(f"summary: {path}")
print(f"status: {data.get('status')}")
print(f"reward: {data.get('reward')}")
print(f"sdk_install: {','.join(data.get('sdk_install_statuses') or [])}")
print(f"claude_init: {data.get('claude_init')}")
print(f"injection_count: {data.get('injection_count')}")
print(f"injection_reasons: {data.get('injection_reasons')}")
PY

printf '\n\033[1;36m# Live demo complete.\033[0m\n'
LIVE_HELPER
  chmod +x "$helper"
}

write_full_fail_helper() {
  local helper="$1"
  mkdir -p "$(dirname "$helper")"
  cat > "$helper" <<'LIVE_FULL_HELPER'
#!/usr/bin/env bash
set -euo pipefail

BASELINE_JOBS="${1:?missing baseline jobs dir}"
SECOND_JOBS="${2:?missing second jobs dir}"
LIVE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPACT="${HTD_DEMO_COMPACT:-0}"
NO_FORCE_BUILD="${HTD_DEMO_NO_FORCE_BUILD:-1}"
KEEP_ENVIRONMENT="${HTD_DEMO_KEEP_ENVIRONMENT:-0}"

if [[ -f "$HOME/.bashrc" ]]; then
  set +u
  # shellcheck source=/dev/null
  source "$HOME/.bashrc"
  set -u
fi

cd "$LIVE_ROOT"
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-${SEED_CODING_PLAN_BASE_URL:-}}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-${SEED_CODING_PLAN_API_KEY:-}}"

if [[ -z "${ANTHROPIC_BASE_URL:-}" || -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "Missing ANTHROPIC_* or SEED_CODING_PLAN_* credentials for the no-ICL baseline." >&2
  exit 1
fi

printf '\n\033[1;36m# 1. Fresh first run: no ICL, kimi-k2.6, query-optimize\033[0m\n'
printf '\n$ MODEL=kimi-k2.6 scripts/run_harbor_icl_variants.sh --pack-dir docs/blog/raw_logs/blog_raw_logs --task query-optimize --variant no_icl --jobs-dir %q --no-force-build\n' "$BASELINE_JOBS"
mkdir -p "$LIVE_ROOT/$BASELINE_JOBS"
BASELINE_LOG="$LIVE_ROOT/$BASELINE_JOBS/htd-demo-baseline-run.log"
run_baseline() {
  MODEL=kimi-k2.6 scripts/run_harbor_icl_variants.sh \
    --pack-dir docs/blog/raw_logs/blog_raw_logs \
    --task query-optimize \
    --variant no_icl \
    --jobs-dir "$BASELINE_JOBS" \
    --no-force-build
}
if [[ "$COMPACT" == "1" ]]; then
  printf 'compact_log: %s\n' "$BASELINE_LOG"
  if ! run_baseline >"$BASELINE_LOG" 2>&1; then
    tail -n 80 "$BASELINE_LOG" >&2 || true
    exit 1
  fi
else
  run_baseline
fi

FAIL_TRIAL="$(find "$LIVE_ROOT/$BASELINE_JOBS" -path '*/query-optimize__*' -type d | head -n 1)"
if [[ -z "$FAIL_TRIAL" ]]; then
  echo "Could not find fresh no-ICL trial under $LIVE_ROOT/$BASELINE_JOBS" >&2
  exit 1
fi

printf '\n$ cat %q\n' "$FAIL_TRIAL/verifier/reward.txt"
cat "$FAIL_TRIAL/verifier/reward.txt"
TAIL_LINES=45
if [[ "$COMPACT" == "1" ]]; then
  TAIL_LINES=18
fi
printf '\n$ tail -n %s %q\n' "$TAIL_LINES" "$FAIL_TRIAL/verifier/test-stdout.txt"
tail -n "$TAIL_LINES" "$FAIL_TRIAL/verifier/test-stdout.txt"

if [[ "$(tr -d '[:space:]' < "$FAIL_TRIAL/verifier/reward.txt")" != "0" ]]; then
  echo "Fresh no-ICL run did not fail, so this is not a fail-teacher demo candidate." >&2
  exit 1
fi

printf '\n\033[1;36m# 2. Harness-TrajecDebug imports the fresh failed trace and diagnoses it\033[0m\n'
DIAG_DIR="$LIVE_ROOT/$BASELINE_JOBS/diagnosis"
rm -rf "$DIAG_DIR"
printf '\n$ plugins/harness-trajdebug-agent/scripts/htd-agent harbor-import --run %q --output-dir %q --diagnose\n' "$FAIL_TRIAL" "$DIAG_DIR"
plugins/harness-trajdebug-agent/scripts/htd-agent harbor-import \
  --run "$FAIL_TRIAL" \
  --output-dir "$DIAG_DIR" \
  --diagnose
DIAGNOSIS="$(find "$DIAG_DIR/diagnoses" -type f -name '*-diagnosis.json' | head -n 1)"
python3 - "$DIAGNOSIS" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
critical = data.get("critical_step") or {}
print(f"diagnosis: {path}")
print(f"outcome: {data.get('outcome')}")
print(f"final_failure: {data.get('final_failure')}")
print(
    "critical_step: "
    f"pattern={critical.get('pattern')} "
    f"step={critical.get('step_index')} "
    f"confidence={critical.get('confidence')}"
)
print(f"repair_hint: {data.get('repair_hint')}")
PY

printf '\n\033[1;36m# 3. Generate a failure-derived Debug-Action card, teacher reward=0\033[0m\n'
RUNTIME_PACK="$LIVE_ROOT/$BASELINE_JOBS/runtime_pack"
rm -rf "$RUNTIME_PACK"
mkdir -p "$RUNTIME_PACK/task_variants/no_icl" "$RUNTIME_PACK/teacher_cards/query-optimize"
ln -s "$LIVE_ROOT/docs/blog/raw_logs/blog_raw_logs/task_variants/no_icl/query-optimize" \
  "$RUNTIME_PACK/task_variants/no_icl/query-optimize"
GENERATED_CARD="$RUNTIME_PACK/teacher_cards/query-optimize/fail_debug_action_live.md"
printf '\n$ scripts/build_query_optimize_fail_debug_action_card.py --trial %q --diagnosis %q --task-dir docs/blog/raw_logs/blog_raw_logs/task_variants/no_icl/query-optimize --output %q\n' "$FAIL_TRIAL" "$DIAGNOSIS" "$GENERATED_CARD"
scripts/build_query_optimize_fail_debug_action_card.py \
  --trial "$FAIL_TRIAL" \
  --diagnosis "$DIAGNOSIS" \
  --task-dir docs/blog/raw_logs/blog_raw_logs/task_variants/no_icl/query-optimize \
  --output "$GENERATED_CARD"
if [[ "$COMPACT" == "1" ]]; then
  printf '\n$ python3 - %q  # compact generated-card summary\n' "$GENERATED_CARD"
  python3 - "$GENERATED_CARD" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
print(f"card: {path}")
for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
    if line.startswith("# ") or line.startswith("Teacher outcome:") or line.startswith("Failed gate:") or line.startswith("Pattern:"):
        print(line)
    elif line.startswith("## Recommended next action"):
        print("recommended_action: materialize /app/sol.sql")
    elif line.startswith("## Stop rule"):
        print("stop_rule: write artifact, cheap smoke check, then official verifier")
        break
PY
else
  printf '\n$ sed -n %q %q\n' '1,120p' "$GENERATED_CARD"
  sed -n '1,120p' "$GENERATED_CARD"
fi

printf '\n\033[1;36m# 4. Card closure check: synthesized action materializes /app/sol.sql\033[0m\n'
CLOSURE_JSON="$LIVE_ROOT/$BASELINE_JOBS/fail_debug_action_closure.json"
CLOSURE_MD="$LIVE_ROOT/$BASELINE_JOBS/fail_debug_action_closure.md"
printf '\n$ scripts/check_debug_action_closure.py --pack-dir %q --task query-optimize --context-variant fail_debug_action_live --output-json %q --output-md %q\n' "$RUNTIME_PACK" "$CLOSURE_JSON" "$CLOSURE_MD"
scripts/check_debug_action_closure.py \
  --pack-dir "$RUNTIME_PACK" \
  --task query-optimize \
  --context-variant fail_debug_action_live \
  --output-json "$CLOSURE_JSON" \
  --output-md "$CLOSURE_MD" >/dev/null
python3 - "$CLOSURE_JSON" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
row = data["rows"][0]
print(f"closure: {row['status']}")
for check in row.get("checks", []):
    status = "ok" if check.get("ok") else "fail"
    print(f"check: {check['name']}={status} ({check['detail']})")
PY

printf '\n\033[1;36m# 5. Live second run: inject fail_debug_action_live at PreToolUse(Bash)\033[0m\n'
printf '\n$ scripts/run_harbor_dynamic_icl.sh --pack-dir %q --task query-optimize --model kimi-k2.6 --jobs-dir %q --context-variant fail_debug_action_live --inject-mode sdk_live --endpoint-profile seed-coding-plan --sdk-live-intercept-tool Bash --sdk-live-install-timeout 900 --setup-timeout 1200 --agent-timeout 1800 --verifier-timeout 600\n' "$RUNTIME_PACK" "$SECOND_JOBS"
printf 'docker_reuse: no_force_build=%s keep_environment=%s\n' "$NO_FORCE_BUILD" "$KEEP_ENVIRONMENT"
mkdir -p "$LIVE_ROOT/$SECOND_JOBS"
SECOND_LOG="$LIVE_ROOT/$SECOND_JOBS/htd-demo-live-run.log"
run_second() {
  local args=(
    scripts/run_harbor_dynamic_icl.sh
    --pack-dir "$RUNTIME_PACK" \
    --task query-optimize \
    --model kimi-k2.6 \
    --jobs-dir "$SECOND_JOBS" \
    --context-variant fail_debug_action_live \
    --inject-mode sdk_live \
    --endpoint-profile seed-coding-plan \
    --sdk-live-intercept-tool Bash \
    --sdk-live-install-timeout 900 \
    --setup-timeout 1200 \
    --agent-timeout 1800 \
    --verifier-timeout 600
  )
  if [[ "$NO_FORCE_BUILD" == "1" ]]; then
    args+=(--no-force-build)
  fi
  if [[ "$KEEP_ENVIRONMENT" == "1" ]]; then
    args+=(--keep-environment)
  fi
  "${args[@]}"
}
if [[ "$COMPACT" == "1" ]]; then
  printf 'compact_log: %s\n' "$SECOND_LOG"
  if ! run_second >"$SECOND_LOG" 2>&1; then
    tail -n 80 "$SECOND_LOG" >&2 || true
    exit 1
  fi
else
  run_second
fi

LIVE_TRIAL="$(find "$LIVE_ROOT/$SECOND_JOBS" -path '*/query-optimize__*' -type d | head -n 1)"
if [[ -z "$LIVE_TRIAL" ]]; then
  echo "Could not find live second trial under $LIVE_ROOT/$SECOND_JOBS" >&2
  exit 1
fi
printf '\n$ cat %q\n' "$LIVE_TRIAL/verifier/reward.txt"
cat "$LIVE_TRIAL/verifier/reward.txt"
TAIL_LINES=45
if [[ "$COMPACT" == "1" ]]; then
  TAIL_LINES=18
fi
printf '\n$ tail -n %s %q\n' "$TAIL_LINES" "$LIVE_TRIAL/verifier/test-stdout.txt"
tail -n "$TAIL_LINES" "$LIVE_TRIAL/verifier/test-stdout.txt"
printf '\n$ PYTHONPATH=src python3 scripts/summarize_sdk_live_trial.py %q --output %q\n' "$LIVE_TRIAL" "$LIVE_TRIAL/sdk-live-summary.json"
PYTHONPATH=src python3 scripts/summarize_sdk_live_trial.py "$LIVE_TRIAL" --output "$LIVE_TRIAL/sdk-live-summary.json" >/dev/null
python3 - "$LIVE_TRIAL/sdk-live-summary.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(f"status: {data.get('status')}")
print(f"reward: {data.get('reward')}")
print(f"injection_count: {data.get('injection_count')}")
print(f"injection_reasons: {data.get('injection_reasons')}")
PY

printf '\n\033[1;36m# Full fail-teacher live demo complete.\033[0m\n'
LIVE_FULL_HELPER
  chmod +x "$helper"
}

require_live_file() {
  local root="$1"
  local rel="$2"
  if [[ ! -e "$root/$rel" ]]; then
    echo "Missing live-root file: $root/$rel" >&2
    echo "Set HTD_DEMO_LIVE_ROOT to an updated repo mirror, or sync/pull this path there." >&2
    exit 1
  fi
}

require_live_exec() {
  local root="$1"
  local rel="$2"
  require_live_file "$root" "$rel"
  if [[ ! -x "$root/$rel" ]]; then
    echo "Live-root file is not executable: $root/$rel" >&2
    exit 1
  fi
}

CARD_PATH="$PACK_DIR/teacher_cards/query-optimize/${CARD_VARIANT}.md"

if [[ "$MODE" != "live_full_fail_teacher" && ! -d "$FAIL_TRIAL" ]]; then
  echo "Missing failing trial: $FAIL_TRIAL" >&2
  exit 1
fi
if [[ ! -f "$CARD_PATH" ]]; then
  echo "Missing Debug-Action card: $CARD_PATH" >&2
  exit 1
fi
if [[ "$MODE" == "recorded" && "$CARD_VARIANT" != "debug_action" ]]; then
  echo "Recorded mode only has checked-in pass-teacher success evidence." >&2
  echo "Use --live-fail-teacher or --live-full-fail-teacher for reward-0 teacher demos." >&2
  exit 2
fi

mkdir -p "$OUT_DIR"

say "0. Setup: same terminal-bench task, same model, same verifier"
run_shell "source ~/.bashrc >/dev/null 2>&1 || true; cd '$REPO_ROOT' && plugins/harness-trajdebug-agent/scripts/htd-agent doctor"

if [[ "$MODE" == "live_full_fail_teacher" ]]; then
  if [[ "$LIVE_ROOT_SOURCE" == "auto-documents-mirror" ]]; then
    say "Using live Harbor mirror: $LIVE_ROOT"
  fi
  require_live_exec "$LIVE_ROOT" "scripts/run_harbor_icl_variants.sh"
  require_live_exec "$LIVE_ROOT" "scripts/run_harbor_dynamic_icl.sh"
  require_live_exec "$LIVE_ROOT" "scripts/build_query_optimize_fail_debug_action_card.py"
  require_live_file "$LIVE_ROOT" "docs/blog/raw_logs/blog_raw_logs/task_variants/no_icl/query-optimize/task.toml"
  FULL_HELPER="$LIVE_ROOT/runs/htd_demo_query_optimize_full_fail_teacher_helper.sh"
  BASELINE_JOBS="runs/demo-query-optimize-full-baseline-$(date +%Y%m%dT%H%M%S)"
  SECOND_JOBS="runs/demo-query-optimize-full-with-td-$(date +%Y%m%dT%H%M%S)"
  write_full_fail_helper "$FULL_HELPER"
  printf '\n$ cd %q && %q %q %q\n' "$LIVE_ROOT" "$FULL_HELPER" "$BASELINE_JOBS" "$SECOND_JOBS"
  cd "$LIVE_ROOT"
  HTD_DEMO_COMPACT="$COMPACT" HTD_DEMO_NO_FORCE_BUILD="$NO_FORCE_BUILD" HTD_DEMO_KEEP_ENVIRONMENT="$KEEP_ENVIRONMENT" exec "$FULL_HELPER" "$BASELINE_JOBS" "$SECOND_JOBS"
fi

say "1. First run failed: no ICL, kimi-k2.6, query-optimize"
run_shell "cat '$FAIL_TRIAL/verifier/reward.txt'"
show_verifier_stdout "$FAIL_TRIAL/verifier/test-stdout.txt"

say "2. Harness-TrajecDebug imports the terminal-agent trace and diagnoses it"
DIAG_DIR="$OUT_DIR/diagnosis"
rm -rf "$DIAG_DIR"
run_shell "cd '$REPO_ROOT' && plugins/harness-trajdebug-agent/scripts/htd-agent harbor-import --run '$FAIL_TRIAL' --output-dir '$DIAG_DIR' --diagnose"
DIAGNOSIS="$(find "$DIAG_DIR/diagnoses" -type f -name '*-diagnosis.json' | head -n 1)"
summarize_diagnosis "$DIAGNOSIS"

if [[ "$TEACHER_KIND" == "fail" ]]; then
  say "3. Failure-derived Debug-Action card, teacher reward=0"
else
  say "3. Critical-step repair becomes a Debug-Action card"
fi
show_card "$CARD_PATH"

if [[ "$TEACHER_KIND" == "fail" ]]; then
  say "4. The fail-teacher card is executable: synthesized action materializes /app/sol.sql"
else
  say "4. The card is executable: it materializes /app/sol.sql and passes closure checks"
fi
CLOSURE_JSON="$OUT_DIR/${CARD_VARIANT}_closure.json"
CLOSURE_MD="$OUT_DIR/${CARD_VARIANT}_closure.md"
run_shell "cd '$REPO_ROOT' && scripts/check_debug_action_closure.py --pack-dir '$PACK_DIR' --task query-optimize --context-variant '$CARD_VARIANT' --output-json '$CLOSURE_JSON' --output-md '$CLOSURE_MD' >/dev/null"
summarize_closure "$CLOSURE_JSON"

if [[ "$MODE" == "recorded" ]]; then
  say "5. Recorded with-TD run: sdk_live injects the card and verifier passes"
  run_shell "cat '$SUCCESS_TRIAL/verifier/reward.txt'"
  show_verifier_stdout "$SUCCESS_TRIAL/verifier/test-stdout.txt"
  summarize_sdk_live "$SUCCESS_TRIAL/sdk-live-summary.json"
  say "Recorded mode complete. Re-run with --live to execute the second attempt now."
  exit 0
fi

say "5. Live second run: inject ${CARD_VARIANT} at PreToolUse(Bash)"
require_live_exec "$LIVE_ROOT" "scripts/run_harbor_dynamic_icl.sh"
require_live_file "$LIVE_ROOT" "docs/blog/raw_logs/blog_raw_logs/teacher_cards/query-optimize/${CARD_VARIANT}.md"

LIVE_JOBS="runs/demo-query-optimize-live-${CARD_VARIANT}-$(date +%Y%m%dT%H%M%S)"
LIVE_HELPER="$LIVE_ROOT/runs/htd_demo_query_optimize_live_${CARD_VARIANT}_helper.sh"
write_live_helper "$LIVE_HELPER" "$CARD_VARIANT"

printf '\n$ cd %q && %q %q %q\n' "$LIVE_ROOT" "$LIVE_HELPER" "$LIVE_JOBS" "$CARD_VARIANT"
cd "$LIVE_ROOT"
HTD_DEMO_COMPACT="$COMPACT" HTD_DEMO_NO_FORCE_BUILD="$NO_FORCE_BUILD" HTD_DEMO_KEEP_ENVIRONMENT="$KEEP_ENVIRONMENT" exec "$LIVE_HELPER" "$LIVE_JOBS" "$CARD_VARIANT"
