#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SRC="$REPO_ROOT/skills/harness-runtime-icl"
DST="$CODEX_HOME/skills/harness-runtime-icl"

if [[ ! -f "$SRC/SKILL.md" ]]; then
  echo "Missing repository skill at $SRC/SKILL.md" >&2
  exit 1
fi

mkdir -p "$CODEX_HOME/skills"
rm -rf "$DST"
cp -R "$SRC" "$DST"

echo "Installed harness-runtime-icl skill:"
echo "  $DST"
echo
echo "Restart Codex, or start a new Codex thread, so the skill registry reloads."
