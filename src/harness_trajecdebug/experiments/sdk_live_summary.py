"""Summarize a Harbor sdk_live trial into a machine-readable status."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def nested_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(nested_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(nested_text(v) for v in value)
    return ""


def summarize_trial(trial_dir: Path) -> dict[str, Any]:
    agent_dir = trial_dir / "agent"
    verifier_dir = trial_dir / "verifier"
    events = read_jsonl(agent_dir / "sdk-live-events.jsonl")
    result = read_json(trial_dir / "result.json") or {}
    reward_text = read_text(verifier_dir / "reward.txt").strip()
    command_return = read_text(agent_dir / "command-1" / "return-code.txt").strip()
    command_stdout = read_text(agent_dir / "command-1" / "stdout.txt")
    event_text = nested_text(events)

    sdk_install_statuses = [
        event.get("status")
        for event in events
        if event.get("type") == "sdk_install"
    ]
    tool_events = [event for event in events if event.get("type") == "pre_tool_use"]
    injections = [event for event in events if event.get("type") == "live_injection"]
    api_retries = []
    for event in events:
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        if message.get("subtype") == "api_retry":
            api_retries.append(event)
            continue
        data = message.get("data")
        if isinstance(data, dict) and data.get("subtype") == "api_retry":
            api_retries.append(event)

    reward = None
    try:
        reward = float(reward_text) if reward_text else None
    except ValueError:
        reward = None

    if command_return == "127" and (
        "python3: command not found" in command_stdout
        or "python: command not found" in command_stdout
        or "sdk_live requires Python" in command_stdout
    ):
        status = "sdk_python_missing"
    elif reward == 1.0:
        status = "passed"
    elif "quota has been exhausted" in event_text or '"code":"Throttling"' in event_text or "rate_limit" in event_text:
        status = "model_rate_limited"
    elif "timeout" in sdk_install_statuses:
        status = "sdk_install_timeout"
    elif "finished" not in sdk_install_statuses and "already_installed" not in sdk_install_statuses:
        status = "sdk_install_incomplete"
    elif not any(event.get("subtype") == "init" for event in (e.get("message", {}) for e in events if isinstance(e.get("message"), dict))):
        status = "sdk_no_claude_init"
    elif injections and reward == 0.0:
        status = "injected_but_failed_verifier"
    elif injections:
        status = "sdk_live_injected"
    elif tool_events:
        status = "tool_loop_without_injection"
    else:
        status = "sdk_started_no_tool_loop"

    return {
        "trial_dir": str(trial_dir),
        "status": status,
        "reward": reward,
        "agent_return_code": command_return or None,
        "sdk_install_statuses": sdk_install_statuses,
        "claude_init": any(
            isinstance(event.get("message"), dict)
            and event["message"].get("subtype") == "init"
            for event in events
        ),
        "api_retry_count": len(api_retries),
        "tool_event_count": len(tool_events),
        "injection_count": len(injections),
        "injection_reasons": [event.get("reason") for event in injections],
        "exception_info": result.get("exception_info"),
        "verifier_result": result.get("verifier_result"),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize a Harbor sdk_live trial.")
    parser.add_argument("trial_dir", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = summarize_trial(args.trial_dir)
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
