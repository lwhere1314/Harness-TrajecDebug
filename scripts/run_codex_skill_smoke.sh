#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="echo"
PROMPT=""
OUT_DIR="${HTD_CODEX_SMOKE_OUT_DIR:-$REPO_ROOT/runs/codex_cli_smoke}"
MODEL="${HTD_CODEX_MODEL:-gpt-5.5}"
DEFAULT_CODEX_BIN="codex"
if [[ -x "/Applications/Codex.app/Contents/Resources/codex" ]]; then
  DEFAULT_CODEX_BIN="/Applications/Codex.app/Contents/Resources/codex"
fi
CODEX_BIN="${HTD_CODEX_BIN:-$DEFAULT_CODEX_BIN}"
TIMEOUT_SEC="${HTD_CODEX_SMOKE_TIMEOUT_SEC:-}"
PROGRESS_SEC="${HTD_CODEX_SMOKE_PROGRESS_SEC:-2}"
CLEAN_HOME="${HTD_CODEX_SMOKE_CLEAN_HOME:-0}"
IGNORE_USER_CONFIG="${HTD_CODEX_IGNORE_USER_CONFIG:-0}"

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_codex_skill_smoke.sh [--echo|--recorded|--prompt TEXT] [options]

Options:
  --echo                 Run the minimal Codex CLI gate: echo CODEX_EXEC_OK.
  --recorded             Run the compact recorded query-optimize demo through Codex CLI.
  --prompt TEXT          Run a custom prompt.
  --model NAME           Codex model. Default: HTD_CODEX_MODEL or gpt-5.5.
  --timeout SEC          Timeout for codex exec. Defaults: echo=3, recorded=180.
  --out-dir DIR          Output directory for logs.
  --clean-home           Use a temporary CODEX_HOME with copied auth and minimal config.
  --ignore-user-config   Pass --ignore-user-config to codex exec.

Environment:
  HTD_CODEX_SMOKE_CLEAN_HOME=1     Same as --clean-home.
  HTD_CODEX_IGNORE_USER_CONFIG=1   Same as --ignore-user-config.
  HTD_CODEX_SMOKE_PROGRESS_SEC=2   Heartbeat interval while codex exec is quiet.
  HTD_CODEX_BIN=/path/to/codex       Optional Codex binary, bypassing shell shims.

This script is a gate, not a proof by itself. Do not claim nested Codex CLI
compatibility until --echo prints CODEX_EXEC_OK and --recorded prints the
recorded demo completion or injection evidence.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --echo) MODE="echo"; shift ;;
    --recorded) MODE="recorded"; shift ;;
    --prompt)
      PROMPT="${2:?--prompt requires text}"
      MODE="custom"
      shift 2
      ;;
    --model) MODEL="${2:?--model requires a value}"; shift 2 ;;
    --timeout) TIMEOUT_SEC="${2:?--timeout requires seconds}"; shift 2 ;;
    --out-dir) OUT_DIR="${2:?--out-dir requires a directory}"; shift 2 ;;
    --clean-home) CLEAN_HOME=1; shift ;;
    --ignore-user-config) IGNORE_USER_CONFIG=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$MODE" in
  echo)
    PROMPT="Run exactly this shell command and report the output: echo CODEX_EXEC_OK"
    TIMEOUT_SEC="${TIMEOUT_SEC:-3}"
    ;;
  recorded)
    PROMPT="Use Bash to run: HTD_DEMO_PAUSE=0 plugins/harness-trajdebug-agent/scripts/htd-agent demo query-optimize --recorded --compact --out-dir /tmp/htd-codex-recorded"
    TIMEOUT_SEC="${TIMEOUT_SEC:-180}"
    ;;
  custom)
    TIMEOUT_SEC="${TIMEOUT_SEC:-120}"
    ;;
esac

if ! command -v "$CODEX_BIN" >/dev/null 2>&1; then
  echo "codex: missing from PATH: $CODEX_BIN" >&2
  exit 127
fi

mkdir -p "$OUT_DIR"
RUN_ID="$(date +%Y%m%dT%H%M%S)"
LOG_FILE="$OUT_DIR/codex-${MODE}-${RUN_ID}.log"
LAST_MESSAGE="$OUT_DIR/codex-${MODE}-${RUN_ID}.last.txt"
STATUS_FILE="$OUT_DIR/codex-${MODE}-${RUN_ID}.status"

TEMP_HOME=""
cleanup() {
  if [[ -n "$TEMP_HOME" && "${HTD_CODEX_SMOKE_KEEP_HOME:-0}" != "1" ]]; then
    rm -rf "$TEMP_HOME"
  fi
}
trap cleanup EXIT

if [[ "$CLEAN_HOME" == "1" ]]; then
  SOURCE_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
  if [[ ! -f "$SOURCE_CODEX_HOME/auth.json" ]]; then
    echo "Cannot use --clean-home: $SOURCE_CODEX_HOME/auth.json is missing." >&2
    exit 1
  fi
  TEMP_HOME="$(mktemp -d "${TMPDIR:-/tmp}/htd-codex-home.XXXXXX")"
  cp "$SOURCE_CODEX_HOME/auth.json" "$TEMP_HOME/auth.json"
  chmod 600 "$TEMP_HOME/auth.json"
  {
    printf 'model = "%s"\n' "$MODEL"
    printf 'model_reasoning_effort = "medium"\n'
    printf 'approval_policy = "never"\n'
    printf 'sandbox_mode = "danger-full-access"\n\n'
    printf '[projects."%s"]\n' "$REPO_ROOT"
    printf 'trust_level = "trusted"\n'
  } > "$TEMP_HOME/config.toml"
  export CODEX_HOME="$TEMP_HOME"
fi

CODEX_CMD=(
  "$CODEX_BIN" exec
  --ephemeral
  --ignore-rules
  --color never
  --dangerously-bypass-approvals-and-sandbox
  -m "$MODEL"
  -C "$REPO_ROOT"
  -o "$LAST_MESSAGE"
)
if [[ "$IGNORE_USER_CONFIG" == "1" ]]; then
  CODEX_CMD+=(--ignore-user-config)
fi

echo "codex_smoke_mode: $MODE"
echo "codex_bin: $(command -v "$CODEX_BIN")"
echo "codex_model: $MODEL"
echo "codex_timeout_sec: $TIMEOUT_SEC"
echo "codex_log: $LOG_FILE"
echo "codex_last_message: $LAST_MESSAGE"
if [[ "$CLEAN_HOME" == "1" ]]; then
  echo "codex_clean_home: enabled"
fi

RUNNER_STATUS="$OUT_DIR/codex-${MODE}-${RUN_ID}.runner"
python3 - "$LOG_FILE" "$RUNNER_STATUS" "$TIMEOUT_SEC" "$PROGRESS_SEC" "${CODEX_CMD[@]}" "$PROMPT" <<'PY'
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

log_path = Path(sys.argv[1])
status_path = Path(sys.argv[2])
timeout_sec = int(sys.argv[3])
progress_sec = int(sys.argv[4])
cmd = sys.argv[5:]

log_path.parent.mkdir(parents=True, exist_ok=True)
with log_path.open("w", encoding="utf-8", errors="replace") as log:
    proc = subprocess.Popen(
        cmd,
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        text=True,
    )
    print(f"codex_pid: {proc.pid}", flush=True)
    start = time.monotonic()
    next_progress = start + max(progress_sec, 1)
    timed_out = False
    while True:
        rc = proc.poll()
        now = time.monotonic()
        waited = int(now - start)
        if rc is not None:
            break
        if timeout_sec > 0 and waited >= timeout_sec:
            timed_out = True
            print(f"codex_timeout_sec: {waited}", flush=True)
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                rc = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                rc = proc.wait(timeout=5)
            break
        if progress_sec > 0 and now >= next_progress:
            print(f"codex_waiting_sec: {waited}", flush=True)
            next_progress = now + progress_sec
        time.sleep(0.2)

if timed_out:
    rc = 124
seconds_waited = int(time.monotonic() - start)
status_path.write_text(f"{rc} {seconds_waited} {1 if timed_out else 0}\n", encoding="utf-8")
PY
read -r CODEX_RC SECONDS_WAITED TIMED_OUT < "$RUNNER_STATUS"

FOUND_EVIDENCE=0
case "$MODE" in
  echo)
    if grep -Ehs 'CODEX_EXEC_OK' "$LOG_FILE" "$LAST_MESSAGE" 2>/dev/null | grep -Evq 'echo CODEX_EXEC_OK|Run exactly this shell command'; then
      FOUND_EVIDENCE=1
    fi
    ;;
  *)
    if grep -Eqs 'Recorded mode complete|critical_step|closure_passed|injection_count' "$LOG_FILE" "$LAST_MESSAGE" 2>/dev/null; then
      FOUND_EVIDENCE=1
    fi
    ;;
esac

{
  echo "codex_rc: $CODEX_RC"
  echo "codex_evidence: $FOUND_EVIDENCE"
  echo "codex_waited_sec: $SECONDS_WAITED"
  echo "codex_log: $LOG_FILE"
  echo "codex_last_message: $LAST_MESSAGE"
} | tee "$STATUS_FILE"

if [[ "$FOUND_EVIDENCE" != "1" || "$CODEX_RC" != "0" ]]; then
  echo "codex_status: failed"
  echo "codex_log_tail:"
  tail -n 80 "$LOG_FILE" || true
  if [[ -s "$LAST_MESSAGE" ]]; then
    echo "codex_last_message_tail:"
    tail -n 40 "$LAST_MESSAGE" || true
  fi
  exit 1
fi

echo "codex_status: passed"
