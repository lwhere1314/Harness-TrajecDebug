#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HTD_ROOT="${HTD_ROOT:-$ROOT_DIR}"
ATIF_VIEWER_ROOT="${ATIF_VIEWER_ROOT:-$HOME/projects/ATIF-trajectory-viewer}"

detect_harbor_root() {
  local candidate
  for candidate in \
    "${HARBOR_ROOT:-}" \
    "/Users/hugo/Desktop/super-refactor/harbor" \
    "/Volumes/SSD/terminal-bench-harbor/harbor" \
    "$HOME/harbor" \
    "$ROOT_DIR/harbor"; do
    if [ -n "$candidate" ] && { [ -d "$candidate/runs" ] || [ -d "$candidate/datasets" ] || [ -d "$candidate/cache" ]; }; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  printf '%s\n' "${HARBOR_ROOT:-$HOME/harbor}"
}

HARBOR_ROOT="$(detect_harbor_root)"
HARBOR_RUNS_DIR="${HARBOR_RUNS_DIR:-$HARBOR_ROOT/runs}"
HARBOR_DATASETS_DIR="${HARBOR_DATASETS_DIR:-$HARBOR_ROOT/datasets}"

FAILS=0
WARNS=0

ok() {
  printf '[OK]   %s\n' "$1"
}

warn() {
  WARNS=$((WARNS + 1))
  printf '[WARN] %s\n' "$1"
}

fail() {
  FAILS=$((FAILS + 1))
  printf '[FAIL] %s\n' "$1"
}

have() {
  command -v "$1" >/dev/null 2>&1
}

first_line() {
  "$@" 2>/dev/null | head -1
}

check_cmd() {
  if have "$1"; then
    ok "$1: $(command -v "$1")"
  else
    fail "missing command: $1"
  fi
}

check_secret_env() {
  local name="$1"
  if [ -n "${!name:-}" ]; then
    ok "$name is set (value hidden)"
  else
    fail "$name is not set"
  fi
}

detect_harbor() {
  if [ -n "${HARBOR_CLI:-}" ] && [ -x "$HARBOR_CLI" ]; then
    printf '%s\n' "$HARBOR_CLI"
    return 0
  fi
  if [ -x /opt/miniconda3/envs/terminal-bench/bin/harbor ]; then
    printf '%s\n' /opt/miniconda3/envs/terminal-bench/bin/harbor
    return 0
  fi
  if have harbor; then
    command -v harbor
    return 0
  fi
  return 1
}

detect_viewer_root() {
  local candidate
  for candidate in \
    "$ATIF_VIEWER_ROOT" \
    "$HOME/projects/ATIF-trajectory-viewer" \
    "$HOME/Documents/terminal-bench-3.0-PR/ATIF-trajectory-viewer" \
    "/Users/hugo/Documents/terminal-bench-3.0-PR/ATIF-trajectory-viewer"; do
    if [ -f "$candidate/package.json" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

print_header() {
  printf '\n## %s\n' "$1"
}

print_header "Host"
ok "os: $(uname -s) $(uname -r)"
ok "arch: $(uname -m)"
ok "htd root: $HTD_ROOT"

print_header "Required Commands"
check_cmd git
check_cmd python3
check_cmd jq
check_cmd rsync
check_cmd node
check_cmd npm

if have python3; then
  ok "python: $(first_line python3 --version)"
fi
if have node; then
  ok "node: $(first_line node --version)"
fi
if have npm; then
  ok "npm: $(first_line npm --version)"
fi

print_header "Repositories"
if [ -f "$HTD_ROOT/pyproject.toml" ] && [ -d "$HTD_ROOT/src/harness_trajecdebug" ]; then
  ok "Harness-TrajecDebug checkout found"
  if [ -d "$HTD_ROOT/.git" ]; then
    ok "branch: $(git -C "$HTD_ROOT" branch --show-current 2>/dev/null || true)"
    ok "commit: $(git -C "$HTD_ROOT" rev-parse --short HEAD 2>/dev/null || true)"
  fi
else
  fail "Harness-TrajecDebug checkout not found at HTD_ROOT=$HTD_ROOT"
fi

VIEWER_DETECTED="$(detect_viewer_root || true)"
if [ -n "$VIEWER_DETECTED" ]; then
  ok "ATIF viewer found: $VIEWER_DETECTED"
else
  fail "ATIF viewer package.json not found; set ATIF_VIEWER_ROOT"
fi

print_header "Harbor And Docker"
HARBOR_DETECTED="$(detect_harbor || true)"
if [ -n "$HARBOR_DETECTED" ]; then
  ok "harbor: $HARBOR_DETECTED"
  ok "harbor version: $(first_line "$HARBOR_DETECTED" --version)"
else
  fail "Harbor CLI not found; set HARBOR_CLI or install harbor"
fi

if have docker; then
  ok "docker: $(command -v docker)"
  if docker info >/dev/null 2>&1; then
    ok "docker daemon reachable"
  else
    fail "docker command exists but daemon is not reachable"
  fi
else
  fail "missing command: docker"
fi

ok "HARBOR_ROOT=$HARBOR_ROOT"
ok "HARBOR_RUNS_DIR=$HARBOR_RUNS_DIR"
ok "HARBOR_DATASETS_DIR=$HARBOR_DATASETS_DIR"
if [ -d "$HARBOR_RUNS_DIR" ]; then
  ok "Harbor runs dir exists"
else
  warn "Harbor runs dir does not exist yet"
fi
if [ -d "$HARBOR_DATASETS_DIR" ]; then
  ok "Harbor datasets dir exists"
else
  warn "Harbor datasets dir does not exist yet"
fi

print_header "Model Environment"
check_secret_env SEED_CODING_PLAN_BASE_URL
check_secret_env SEED_CODING_PLAN_API_KEY
if [ -n "${CODEX_MODEL:-}" ]; then
  ok "CODEX_MODEL=$CODEX_MODEL"
else
  warn "CODEX_MODEL is not set; set it before the Codex repair pass"
fi
if [ -n "${OPENAI_API_KEY:-}" ]; then
  ok "OPENAI_API_KEY is set (value hidden)"
else
  warn "OPENAI_API_KEY is not set; Codex may use another configured auth path"
fi
if [ -n "${HARBOR_CLAUDE_CODE_BINARY:-}" ]; then
  if [ -f "$HARBOR_CLAUDE_CODE_BINARY" ]; then
    ok "HARBOR_CLAUDE_CODE_BINARY exists: $HARBOR_CLAUDE_CODE_BINARY"
    if have file; then
      ok "claude binary: $(file "$HARBOR_CLAUDE_CODE_BINARY")"
    fi
  else
    fail "HARBOR_CLAUDE_CODE_BINARY is set but file does not exist"
  fi
else
  warn "HARBOR_CLAUDE_CODE_BINARY is not set; Harbor/claude-code may use its default"
fi

print_header "Harness-TrajecDebug CLI"
if have harness-trajdebug; then
  ok "harness-trajdebug: $(command -v harness-trajdebug)"
  HARNESS_CMD=(harness-trajdebug)
elif [ -f "$HTD_ROOT/src/harness_trajecdebug/cli.py" ]; then
  ok "using PYTHONPATH fallback for harness-trajdebug"
  HARNESS_CMD=(python3 -m harness_trajecdebug.cli)
else
  fail "harness-trajdebug is unavailable"
  HARNESS_CMD=()
fi

if [ "${#HARNESS_CMD[@]}" -gt 0 ]; then
  TMP_HARNESS="$(mktemp)"
  if (cd "$HTD_ROOT" && PYTHONPATH="$HTD_ROOT/src" "${HARNESS_CMD[@]}" harnesses >"$TMP_HARNESS" 2>/dev/null); then
    ok "harness inventory command runs"
    python3 - "$TMP_HARNESS" <<'PY'
import json
import sys
from pathlib import Path

items = json.loads(Path(sys.argv[1]).read_text())
for item in items:
    print(f"[INFO] harness {item.get('name')}: {item.get('status')} ({item.get('kind')})")
PY
  else
    fail "harness inventory command failed"
  fi
  rm -f "$TMP_HARNESS"
fi

print_header "Suggested Exports"
printf 'export HTD_ROOT=%q\n' "$HTD_ROOT"
if [ -n "$VIEWER_DETECTED" ]; then
  printf 'export ATIF_VIEWER_ROOT=%q\n' "$VIEWER_DETECTED"
fi
printf 'export HARBOR_ROOT=%q\n' "$HARBOR_ROOT"
printf 'export HARBOR_RUNS_DIR=%q\n' "$HARBOR_RUNS_DIR"
printf 'export HARBOR_DATASETS_DIR=%q\n' "$HARBOR_DATASETS_DIR"
if [ -n "$HARBOR_DETECTED" ]; then
  printf 'export HARBOR_CLI=%q\n' "$HARBOR_DETECTED"
fi

print_header "Summary"
if [ "$FAILS" -eq 0 ]; then
  ok "preflight passed with $WARNS warning(s)"
else
  fail "preflight found $FAILS blocker(s) and $WARNS warning(s)"
fi

exit "$FAILS"
