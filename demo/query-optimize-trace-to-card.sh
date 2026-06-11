#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACK_DIR="$REPO_ROOT/docs/blog/raw_logs/blog_raw_logs"
FAIL_TRIAL="$PACK_DIR/harbor_runs_query_baseline/htd-icl-no_icl-query-optimize-kimi-k2-6/query-optimize__cTzLSZp"
SUCCESS_TRIAL="$PACK_DIR/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq"
CARD_PATH="$PACK_DIR/teacher_cards/query-optimize/debug_action.md"
MODE="recorded"
OUT_DIR="$REPO_ROOT/runs/demo-query-optimize-trace-to-card"
PAUSE="${HTD_DEMO_PAUSE:-1}"
LIVE_ROOT="${HTD_DEMO_LIVE_ROOT:-$REPO_ROOT}"

usage() {
  cat <<'USAGE'
Usage:
  demo/query-optimize-trace-to-card.sh [--recorded|--live] [--out-dir DIR]

Recorded mode is fast and uses checked-in failing/passing evidence.
Live mode runs the second query-optimize debug_action + sdk_live attempt.

Environment:
  HTD_DEMO_PAUSE=0             Disable short pauses between sections.
  HTD_DEMO_LIVE_ROOT=DIR       Optional repo mirror for live long Harbor runs.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --recorded) MODE="recorded"; shift ;;
    --live) MODE="live"; shift ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

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
  mkdir -p "$(dirname "$helper")"
  cat > "$helper" <<'LIVE_HELPER'
#!/usr/bin/env bash
set -euo pipefail

LIVE_JOBS="${1:?missing live jobs dir}"
LIVE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$HOME/.bashrc" ]]; then
  set +u
  # shellcheck source=/dev/null
  source "$HOME/.bashrc"
  set -u
fi

cd "$LIVE_ROOT"

printf '\n$ cd %q && scripts/run_query_optimize_sdk_live_repro.sh %q\n' "$LIVE_ROOT" "$LIVE_JOBS"
scripts/run_query_optimize_sdk_live_repro.sh "$LIVE_JOBS"

LIVE_TRIAL="$(find "$LIVE_ROOT/$LIVE_JOBS" -path '*/query-optimize__*' -type d | head -n 1)"
if [[ -z "$LIVE_TRIAL" ]]; then
  echo "Could not find live trial under $LIVE_ROOT/$LIVE_JOBS" >&2
  exit 1
fi

printf '\n$ cat %q\n' "$LIVE_TRIAL/verifier/reward.txt"
cat "$LIVE_TRIAL/verifier/reward.txt"

printf '\n$ tail -n 45 %q\n' "$LIVE_TRIAL/verifier/test-stdout.txt"
tail -n 45 "$LIVE_TRIAL/verifier/test-stdout.txt"

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

if [[ ! -d "$FAIL_TRIAL" ]]; then
  echo "Missing failing trial: $FAIL_TRIAL" >&2
  exit 1
fi
if [[ ! -f "$CARD_PATH" ]]; then
  echo "Missing Debug-Action card: $CARD_PATH" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

say "0. Setup: same terminal-bench task, same model, same verifier"
run_shell "source ~/.bashrc >/dev/null 2>&1 || true; cd '$REPO_ROOT' && plugins/harness-trajdebug-agent/scripts/htd-agent doctor"

say "1. First run failed: no ICL, kimi-k2.6, query-optimize"
run_shell "cat '$FAIL_TRIAL/verifier/reward.txt'"
run_shell "tail -n 45 '$FAIL_TRIAL/verifier/test-stdout.txt'"

say "2. Harness-TrajecDebug imports the terminal-agent trace and diagnoses it"
DIAG_DIR="$OUT_DIR/diagnosis"
rm -rf "$DIAG_DIR"
run_shell "cd '$REPO_ROOT' && plugins/harness-trajdebug-agent/scripts/htd-agent harbor-import --run '$FAIL_TRIAL' --output-dir '$DIAG_DIR' --diagnose"
DIAGNOSIS="$(find "$DIAG_DIR/diagnoses" -type f -name '*-diagnosis.json' | head -n 1)"
summarize_diagnosis "$DIAGNOSIS"

say "3. Critical-step repair becomes a Debug-Action card"
run_shell "sed -n '1,90p' '$CARD_PATH'"

say "4. The card is executable: it materializes /app/sol.sql and passes closure checks"
CLOSURE_JSON="$OUT_DIR/debug_action_closure.json"
CLOSURE_MD="$OUT_DIR/debug_action_closure.md"
run_shell "cd '$REPO_ROOT' && scripts/check_debug_action_closure.py --pack-dir '$PACK_DIR' --task query-optimize --context-variant debug_action --output-json '$CLOSURE_JSON' --output-md '$CLOSURE_MD' >/dev/null"
summarize_closure "$CLOSURE_JSON"

if [[ "$MODE" == "recorded" ]]; then
  say "5. Recorded with-TD run: sdk_live injects the card and verifier passes"
  run_shell "cat '$SUCCESS_TRIAL/verifier/reward.txt'"
  run_shell "tail -n 45 '$SUCCESS_TRIAL/verifier/test-stdout.txt'"
  summarize_sdk_live "$SUCCESS_TRIAL/sdk-live-summary.json"
  say "Recorded mode complete. Re-run with --live to execute the second attempt now."
  exit 0
fi

say "5. Live second run: inject Debug-Action at PreToolUse(Bash)"
if [[ ! -x "$LIVE_ROOT/scripts/run_query_optimize_sdk_live_repro.sh" ]]; then
  echo "Missing live runner under $LIVE_ROOT" >&2
  echo "Set HTD_DEMO_LIVE_ROOT to a repo mirror with scripts/run_query_optimize_sdk_live_repro.sh." >&2
  exit 1
fi

LIVE_JOBS="runs/demo-query-optimize-live-$(date +%Y%m%dT%H%M%S)"
LIVE_HELPER="$LIVE_ROOT/runs/htd_demo_query_optimize_live_helper.sh"
write_live_helper "$LIVE_HELPER"

printf '\n$ cd %q && %q %q\n' "$LIVE_ROOT" "$LIVE_HELPER" "$LIVE_JOBS"
cd "$LIVE_ROOT"
exec "$LIVE_HELPER" "$LIVE_JOBS"
