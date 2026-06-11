#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIMI_CODE_ROOT="${KIMI_CODE_ROOT:-$REPO_ROOT/kimi-code}"
NODE24_BIN="${NODE24_BIN:-/Users/hugo/.nvm/versions/node/v24.16.0/bin}"
KIMI_CODE_HOME="${KIMI_CODE_HOME:-$REPO_ROOT/runs/kimi_code_smoke/home}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-stream-json}"
KIMI_SMOKE_TIMEOUT_SEC="${KIMI_SMOKE_TIMEOUT_SEC:-240}"
KIMI_SMOKE_EARLY_GRACE_SEC="${KIMI_SMOKE_EARLY_GRACE_SEC:-0}"
KIMI_SMOKE_PROGRESS_SEC="${KIMI_SMOKE_PROGRESS_SEC:-2}"

RESTORE_XTRACE=0
if [[ "$-" == *x* ]]; then
  RESTORE_XTRACE=1
  set +x
fi

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
export KIMI_MODEL_DEFAULT_THINKING="${KIMI_MODEL_DEFAULT_THINKING:-false}"
export KIMI_MODEL_THINKING_MODE="${KIMI_MODEL_THINKING_MODE:-off}"
export KIMI_MODEL_ADAPTIVE_THINKING="${KIMI_MODEL_ADAPTIVE_THINKING:-false}"

if [[ "$RESTORE_XTRACE" == "1" ]]; then
  set -x
fi

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
RUN_ID="$(date +%Y%m%dT%H%M%S)"
RUN_LOG_DIR="$KIMI_CODE_HOME/run-logs"
mkdir -p "$RUN_LOG_DIR"
STDOUT_LOG="$RUN_LOG_DIR/kimi-prompt-${RUN_ID}.stdout.log"
STDERR_LOG="$RUN_LOG_DIR/kimi-prompt-${RUN_ID}.stderr.log"
STATUS_LOG="$RUN_LOG_DIR/kimi-prompt-${RUN_ID}.status"
KIMI_CMD=(
  "$KIMI_CODE_ROOT/node_modules/.bin/tsx"
  --tsconfig "$KIMI_CODE_ROOT/apps/kimi-code/tsconfig.json"
  --import "$KIMI_CODE_ROOT/build/register-raw-text-loader.mjs"
  "$KIMI_CODE_ROOT/apps/kimi-code/src/main.ts"
  -m __kimi_env_model__
  --skills-dir "$REPO_ROOT/.kimi-code/skills"
  -p "$PROMPT"
  --output-format "$OUTPUT_FORMAT"
)

set +e
python3 - "$STDOUT_LOG" "$STDERR_LOG" "$STATUS_LOG" "$KIMI_SMOKE_TIMEOUT_SEC" "$KIMI_SMOKE_EARLY_GRACE_SEC" "$KIMI_SMOKE_PROGRESS_SEC" "${KIMI_CMD[@]}" <<'PY'
import subprocess
import sys
import threading
import time
from pathlib import Path

stdout_log = Path(sys.argv[1])
stderr_log = Path(sys.argv[2])
status_log = Path(sys.argv[3])
timeout_sec = int(sys.argv[4])
early_grace_sec = int(sys.argv[5])
progress_sec = int(sys.argv[6])
cmd = sys.argv[7:]

success_needles = (
    "KIMI_SMOKE_OK",
    "Recorded mode complete",
    "critical_step",
    "injection_count",
    "closure_passed",
)
early_success = False
early_reported = False
timed_out = False
terminated_for_success = False
lock = threading.Lock()

stdout_log.parent.mkdir(parents=True, exist_ok=True)
stdout_f = stdout_log.open("w", encoding="utf-8", errors="replace")
stderr_f = stderr_log.open("w", encoding="utf-8", errors="replace")

proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
)
print(f"kimi_prompt_pid: {proc.pid}", flush=True)
print(f"kimi_stdout_log: {stdout_log}", flush=True)
print(f"kimi_stderr_log: {stderr_log}", flush=True)

def pump(stream, log_file, dest, is_stdout):
    global early_success
    try:
        for line in iter(stream.readline, ""):
            log_file.write(line)
            log_file.flush()
            dest.write(line)
            dest.flush()
            if is_stdout and any(needle in line for needle in success_needles):
                with lock:
                    early_success = True
    finally:
        stream.close()

threads = [
    threading.Thread(target=pump, args=(proc.stdout, stdout_f, sys.stdout, True), daemon=True),
    threading.Thread(target=pump, args=(proc.stderr, stderr_f, sys.stderr, False), daemon=True),
]
for thread in threads:
    thread.start()

start = time.monotonic()
next_progress = start + max(progress_sec, 1)
success_deadline = None
while True:
    rc = proc.poll()
    now = time.monotonic()
    waited = int(now - start)
    with lock:
        saw_success = early_success
    if saw_success and not early_reported:
        print(f"kimi_early_success_detected: {waited}", flush=True)
        early_reported = True
        success_deadline = now + max(early_grace_sec, 0)
    if rc is not None:
        break
    if early_reported and success_deadline is not None and now >= success_deadline:
        terminated_for_success = True
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        break
    if timeout_sec > 0 and waited >= timeout_sec:
        timed_out = True
        print(f"kimi_timeout_sec: {waited}", flush=True)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        break
    if progress_sec > 0 and now >= next_progress:
        print(f"kimi_waiting_sec: {waited}", flush=True)
        next_progress = now + progress_sec
    time.sleep(0.2)

for thread in threads:
    thread.join(timeout=2)
stdout_f.close()
stderr_f.close()

rc = proc.returncode
if early_success:
    rc = 0
elif timed_out:
    rc = 124
elif rc is None:
    rc = 1

seconds_waited = int(time.monotonic() - start)
status_log.write_text(
    f"{rc} {1 if early_success else 0} {seconds_waited} "
    f"{1 if timed_out else 0} {1 if terminated_for_success else 0}\n",
    encoding="utf-8",
)
PY
RUNNER_RC=$?
set -e

read -r KIMI_RC KIMI_EARLY_SUCCESS SECONDS_WAITED KIMI_TIMED_OUT KIMI_TERMINATED_FOR_SUCCESS < "$STATUS_LOG"
if [[ "$RUNNER_RC" != "0" && "$KIMI_RC" == "0" ]]; then
  KIMI_RC="$RUNNER_RC"
fi

python3 - "$KIMI_CODE_HOME" "$STDOUT_LOG" "$STDERR_LOG" "$KIMI_RC" "$KIMI_EARLY_SUCCESS" "$SECONDS_WAITED" <<'PY'
import json
import re
import sys
from pathlib import Path

home = Path(sys.argv[1])
stdout_log = Path(sys.argv[2])
stderr_log = Path(sys.argv[3])
rc = int(sys.argv[4])
early_success = sys.argv[5] == "1"
seconds_waited = int(sys.argv[6])

def newest_state() -> Path | None:
    states = sorted(
        home.glob("sessions/*/session_*/state.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return states[0] if states else None

def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows

def compact(text: str, limit: int = 1200) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."

state = newest_state()
print(f"kimi_rc: {rc}")
print(f"kimi_early_success: {early_success}")
print(f"kimi_waited_sec: {seconds_waited}")
print(f"kimi_stdout_log: {stdout_log}")
print(f"kimi_stderr_log: {stderr_log}")
if stdout_log.exists() and stdout_log.stat().st_size:
    print("kimi_stdout_tail:")
    print(stdout_log.read_text(encoding="utf-8", errors="replace")[-2000:])
if stderr_log.exists() and stderr_log.stat().st_size:
    print("kimi_stderr_tail:")
    print(stderr_log.read_text(encoding="utf-8", errors="replace")[-2000:])
if state is None:
    print("kimi_session: missing")
    raise SystemExit(rc if rc else 1)

session_dir = state.parent
wire = session_dir / "agents" / "main" / "wire.jsonl"
print(f"kimi_session: {session_dir}")
print(f"kimi_wire: {wire}")

rows = load_jsonl(wire)
assistant_text: list[str] = []
tool_calls: list[str] = []
tool_results: list[str] = []
completed = False
for row in rows:
    if row.get("type") == "context.append_loop_event":
        event = row.get("event") if isinstance(row.get("event"), dict) else {}
        if event.get("type") == "content.part":
            part = event.get("part") if isinstance(event.get("part"), dict) else {}
            if part.get("type") == "text" and isinstance(part.get("text"), str):
                assistant_text.append(part["text"])
            elif part.get("type") == "tool_use":
                name = part.get("name") or part.get("toolName") or "tool"
                tool_calls.append(str(name))
        elif event.get("type") == "tool.call":
            tool_calls.append(str(event.get("name") or event.get("toolName") or "tool"))
        elif event.get("type") == "tool.result":
            output = event.get("output")
            if isinstance(output, str):
                tool_results.append(output)
            else:
                tool_results.append(json.dumps(output, ensure_ascii=False)[:2000])
        elif event.get("type") == "step.end":
            completed = True

print(f"kimi_completed: {completed}")
if tool_calls:
    print(f"kimi_tool_calls: {tool_calls}")
if assistant_text:
    print("kimi_assistant_text:")
    print(compact("\n".join(assistant_text), 4000))
for index, output in enumerate(tool_results[-3:], start=1):
    interesting = []
    for line in output.splitlines():
        if any(
            needle in line
            for needle in (
                "reward",
                "critical_step",
                "closure",
                "injection_count",
                "injection_reasons",
                "pytest_summary",
                "status:",
                "KIMI_SMOKE_OK",
            )
        ):
            interesting.append(line)
    if interesting:
        print(f"kimi_tool_result_{index}_key_lines:")
        print("\n".join(interesting[-40:]))

if early_success:
    raise SystemExit(0)
raise SystemExit(0 if completed else (rc if rc else 1))
PY
