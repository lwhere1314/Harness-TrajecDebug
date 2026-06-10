"""Claude Code command-hook bridge for live Harness-TrajecDebug ICL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from harness_trajecdebug.experiments.live_icl_controller import (
        ask_user_answers,
        injection_text,
        minimal_live_policy,
        trigger_for_tool,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from live_icl_controller import (  # type: ignore[no-redef]
        ask_user_answers,
        injection_text,
        minimal_live_policy,
        trigger_for_tool,
    )


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_hook_settings(hook_command: str, intercept_tools: list[str]) -> dict[str, Any]:
    matcher_tools = ["AskUserQuestion", *intercept_tools, "Bash"]
    seen: set[str] = set()
    matcher = "|".join(tool for tool in matcher_tools if tool and not (tool in seen or seen.add(tool)))
    return {
        "PreToolUse": [
            {
                "matcher": matcher,
                "hooks": [
                    {
                        "type": "command",
                        "command": hook_command,
                        "timeout": 30,
                    }
                ],
            }
        ],
        "SessionStart": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": f"{hook_command} --session-start",
                        "timeout": 30,
                    }
                ],
            }
        ],
    }


def session_start_response(context_hint: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": minimal_live_policy(context_hint),
        }
    }


def run_pre_tool_hook(
    hook_input: dict[str, Any],
    *,
    context: str,
    intercept_tools: set[str],
    state_path: Path,
    event_log_path: Path,
) -> dict[str, Any] | None:
    tool_name = hook_input.get("tool_name")
    tool_input = hook_input.get("tool_input", {})
    if not isinstance(tool_name, str):
        tool_name = ""
    if not isinstance(tool_input, dict):
        tool_input = {}

    state = read_json(state_path, default={})
    injected = bool(state.get("injected"))
    reason = trigger_for_tool(tool_name, tool_input, intercept_tools)
    events = [
        {
            "type": "pre_tool_use",
            "tool_name": tool_name,
            "tool_input": tool_input,
            "reason": reason,
            "already_injected": injected,
        }
    ]

    if not reason or injected:
        append_jsonl(event_log_path, events)
        return None

    state["injected"] = True
    state["reason"] = reason
    write_json(state_path, state)

    text = injection_text(context, reason)
    hook_output: dict[str, Any] = {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "additionalContext": text,
    }
    channel = "PreToolUse.additionalContext"
    if tool_name == "AskUserQuestion":
        hook_output["updatedInput"] = ask_user_answers(tool_input, context)
        channel = "PreToolUse.updatedInput+additionalContext"

    events.append(
        {
            "type": "live_injection",
            "channel": channel,
            "reason": reason,
            "chars": len(text),
        }
    )
    append_jsonl(event_log_path, events)

    return {
        "hookSpecificOutput": hook_output,
        "systemMessage": (
            "Harness-TrajecDebug injected prior-trace context before "
            f"{tool_name} because trigger={reason}."
        ),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claude Code hook bridge for Harness-TrajecDebug live ICL.")
    parser.add_argument("--context-path", type=Path, required=True)
    parser.add_argument("--state-path", type=Path, default=Path("/logs/agent/live-hook-state.json"))
    parser.add_argument("--event-log", type=Path, default=Path("/logs/agent/live-controller-events.jsonl"))
    parser.add_argument("--intercept-tool", action="append", default=[])
    parser.add_argument("--session-start", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    context = args.context_path.read_text(encoding="utf-8", errors="replace")
    if args.session_start:
        print(json.dumps(session_start_response(context), ensure_ascii=False))
        return 0

    try:
        hook_input = json.loads(sys.stdin.read())
    except json.JSONDecodeError as exc:
        print(json.dumps({"systemMessage": f"HTD hook ignored malformed JSON: {exc}"}, ensure_ascii=False))
        return 0
    if not isinstance(hook_input, dict):
        return 0

    response = run_pre_tool_hook(
        hook_input,
        context=context,
        intercept_tools=set(args.intercept_tool),
        state_path=args.state_path,
        event_log_path=args.event_log,
    )
    if response:
        print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
