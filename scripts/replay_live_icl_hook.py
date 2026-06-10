#!/usr/bin/env python3
"""Replay the Claude Code command-hook bridge without running a model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from harness_trajecdebug.experiments.live_icl_hook import (  # noqa: E402
    run_pre_tool_hook,
    session_start_response,
)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay the Harness-TrajecDebug Claude Code hook bridge."
    )
    parser.add_argument("--context-path", type=Path, required=True)
    parser.add_argument("--tool-name", default="")
    parser.add_argument("--tool-input-json", default="{}")
    parser.add_argument("--intercept-tool", action="append", default=[])
    parser.add_argument("--state-path", type=Path)
    parser.add_argument("--event-log", type=Path)
    parser.add_argument("--session-start", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    context = args.context_path.read_text(encoding="utf-8", errors="replace")

    if args.state_path is None or args.event_log is None:
        tmp = Path(tempfile.mkdtemp(prefix="htd-live-hook-replay-"))
        state_path = args.state_path or tmp / "state.json"
        event_log = args.event_log or tmp / "events.jsonl"
    else:
        state_path = args.state_path
        event_log = args.event_log

    if args.session_start:
        response = session_start_response(context)
        print(
            json.dumps(
                {
                    "response": response,
                    "events": [],
                    "reason": "session_start",
                    "injected": bool(response.get("hookSpecificOutput", {}).get("additionalContext")),
                    "hook_state": read_json(state_path, default={}),
                    "hook_state_path": str(state_path),
                    "event_log": str(event_log),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    try:
        tool_input = json.loads(args.tool_input_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--tool-input-json must be valid JSON: {exc}") from exc
    if not isinstance(tool_input, dict):
        raise SystemExit("--tool-input-json must decode to a JSON object")

    before_count = len(read_jsonl(event_log))
    response = run_pre_tool_hook(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": args.tool_name,
            "tool_input": tool_input,
        },
        context=context,
        intercept_tools=set(args.intercept_tool),
        state_path=state_path,
        event_log_path=event_log,
    )
    events = read_jsonl(event_log)[before_count:]
    reason = None
    if events:
        value = events[0].get("reason")
        reason = value if isinstance(value, str) else None
    injected = any(event.get("type") == "live_injection" for event in events)

    print(
        json.dumps(
            {
                "response": response or {},
                "events": events,
                "reason": reason,
                "injected": injected,
                "hook_state": read_json(state_path, default={}),
                "hook_state_path": str(state_path),
                "event_log": str(event_log),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
