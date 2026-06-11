"""Run Claude Code through the Python Agent SDK with live ICL interception.

This script is designed to run inside a Harbor task container. It keeps the
full Debug-Trajectory card out of the initial task prompt, then injects it only
when a live tool event indicates uncertainty or likely drift.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

try:
    from harness_trajecdebug.experiments.live_icl_controller import (
        LiveIclController,
        minimal_live_policy,
        truncate,
    )
except ModuleNotFoundError:
    from live_icl_controller import (  # type: ignore
        LiveIclController,
        minimal_live_policy,
        truncate,
    )


SDK_VERSION = "0.1.43"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return jsonable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dict__"):
        return jsonable(vars(value))
    return value


def append_jsonl(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event.setdefault("timestamp", dt.datetime.now(dt.timezone.utc).isoformat())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(jsonable(event), ensure_ascii=False) + "\n")


def ensure_sdk(
    auto_install: bool,
    install_log: Path,
    event_log: Path,
    timeout_sec: int,
) -> None:
    try:
        import claude_agent_sdk  # noqa: F401

        append_jsonl(event_log, {"type": "sdk_install", "status": "already_installed"})
        return
    except Exception as exc:
        if not auto_install:
            raise
        append_jsonl(
            event_log,
            {"type": "sdk_install", "status": "missing", "error": repr(exc)},
        )

    install_log.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-cache-dir",
        f"claude-agent-sdk=={SDK_VERSION}",
    ]
    append_jsonl(event_log, {"type": "sdk_install", "status": "starting", "command": command})
    install_env = os.environ.copy()
    install_env.setdefault("PIP_BREAK_SYSTEM_PACKAGES", "1")
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_sec if timeout_sec > 0 else None,
            env=install_env,
        )
    except subprocess.TimeoutExpired as exc:
        install_log.write_text(exc.stdout or "", encoding="utf-8")
        append_jsonl(
            event_log,
            {
                "type": "sdk_install",
                "status": "timeout",
                "timeout_sec": timeout_sec,
                "log_path": str(install_log),
            },
        )
        raise

    install_log.write_text(completed.stdout or "", encoding="utf-8")
    append_jsonl(
        event_log,
        {
            "type": "sdk_install",
            "status": "finished",
            "return_code": completed.returncode,
            "log_path": str(install_log),
        },
    )
    completed.check_returncode()


def sdk_env() -> dict[str, str]:
    keys = [
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "CLAUDE_CODE_SUBAGENT_MODEL",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW",
        "CLAUDE_CONFIG_DIR",
        "MAX_THINKING_TOKENS",
        "IS_SANDBOX",
        "FORCE_AUTO_BACKGROUND_TASKS",
        "ENABLE_BACKGROUND_TASKS",
    ]
    return {key: os.environ[key] for key in keys if os.environ.get(key)}


async def run(args: argparse.Namespace) -> int:
    ensure_sdk(
        auto_install=not args.no_auto_install_sdk,
        install_log=args.sdk_install_log,
        event_log=args.event_log,
        timeout_sec=args.sdk_install_timeout_sec,
    )

    from claude_agent_sdk import (  # type: ignore
        ClaudeAgentOptions,
        HookMatcher,
        PermissionResultAllow,
        query,
    )

    instruction = read_text(args.instruction_path)
    context = truncate(read_text(args.context_path), args.context_budget_chars)
    controller = LiveIclController(
        context=context,
        intercept_tools=set(args.intercept_tool),
    )

    async def prompt_stream():
        yield {
            "type": "user",
            "message": {"role": "user", "content": minimal_live_policy(instruction)},
            "parent_tool_use_id": None,
        }

    async def pre_tool_use(input_data, tool_use_id, hook_context):
        decision = controller.handle_pre_tool_use(input_data if isinstance(input_data, dict) else {})
        for event in decision.events:
            append_jsonl(args.event_log, event)
        return decision.response

    async def can_use_tool(tool_name, input_data, permission_context):
        decision = controller.handle_can_use_tool(
            str(tool_name),
            input_data if isinstance(input_data, dict) else {},
        )
        for event in decision.events:
            append_jsonl(args.event_log, event)
        return PermissionResultAllow(updated_input=decision.response["updated_input"])

    def stderr_logger(data: str) -> None:
        if data:
            append_jsonl(args.event_log, {"type": "stderr", "data": data})

    options = ClaudeAgentOptions(
        tools={"type": "preset", "preset": "claude_code"},
        system_prompt={"type": "preset", "preset": "claude_code"},
        permission_mode=args.permission_mode,
        model=args.model or os.environ.get("ANTHROPIC_MODEL"),
        cwd=str(args.cwd),
        cli_path=str(args.cli_path) if args.cli_path else None,
        env=sdk_env(),
        max_turns=args.max_turns,
        can_use_tool=can_use_tool,
        hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[pre_tool_use])]},
        stderr=stderr_logger,
    )

    args.output_log.parent.mkdir(parents=True, exist_ok=True)
    with args.output_log.open("w", encoding="utf-8") as handle:
        async for message in query(prompt=prompt_stream(), options=options):
            payload = jsonable(message)
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            handle.flush()
            append_jsonl(args.event_log, {"type": "sdk_message", "message": payload})

    append_jsonl(args.event_log, {"type": "finished", "injected": controller.injected})
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Claude Code with live Harness-TrajecDebug ICL interception.")
    parser.add_argument("--instruction-path", type=Path, required=True)
    parser.add_argument("--context-path", type=Path, required=True)
    parser.add_argument("--output-log", type=Path, default=Path("/logs/agent/claude-code.txt"))
    parser.add_argument("--event-log", type=Path, default=Path("/logs/agent/sdk-live-events.jsonl"))
    parser.add_argument("--sdk-install-log", type=Path, default=Path("/logs/agent/sdk-install.log"))
    parser.add_argument("--sdk-install-timeout-sec", type=int, default=240)
    parser.add_argument("--cwd", type=Path, default=Path("/app"))
    parser.add_argument("--cli-path", type=Path, default=Path("/root/.local/bin/claude"))
    parser.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", ""))
    parser.add_argument("--permission-mode", default="bypassPermissions")
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--context-budget-chars", type=int, default=12000)
    parser.add_argument(
        "--intercept-tool",
        action="append",
        default=[],
        help="Additional tool name to inject context before, e.g. WebSearch or WebFetch.",
    )
    parser.add_argument("--no-auto-install-sdk", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(run(build_arg_parser().parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
