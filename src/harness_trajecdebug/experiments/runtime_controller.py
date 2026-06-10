"""Runtime ICL controller decision logic.

This module is intentionally Harbor-independent so it can run both inside a
task container and as a local replay tool against saved Claude Code logs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
from typing import Any


DEFAULT_LOG_PATH = pathlib.Path("/logs/agent/claude-code-first.txt")
DEFAULT_CONTEXT_PATH = pathlib.Path("/opt/harness-trajecdebug/context.md")
DEFAULT_OUTPUT_PATH = pathlib.Path("/logs/agent/controller-decision.json")


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def expected_artifacts(context: str) -> dict[str, str | None]:
    artifacts: dict[str, str | None] = {}

    action_pattern = re.compile(
        r"cat\s+>\s+[\"'](?P<path>/app/[^\"']+)[\"']\s+<<'HTD_ARTIFACT_EOF'\n"
        r"(?P<body>.*?)\nHTD_ARTIFACT_EOF",
        re.S,
    )
    for match in action_pattern.finditer(context):
        artifacts[match.group("path")] = match.group("body") + "\n"

    snippet_pattern = re.compile(
        r"Artifact:\s*(?P<path>/app/[^\n` ]+)\s*\n```[^\n]*\n(?P<body>.*?)\n```",
        re.S,
    )
    for match in snippet_pattern.finditer(context):
        artifacts.setdefault(match.group("path"), match.group("body") + "\n")

    return artifacts


def actual_tool_uses(log_text: str) -> tuple[list[str], list[str]]:
    names: list[str] = []
    commands: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "tool_use":
                name = value.get("name")
                if isinstance(name, str):
                    names.append(name)
                tool_input = value.get("input")
                if name == "Bash" and isinstance(tool_input, dict):
                    command = tool_input.get("command")
                    if isinstance(command, str):
                        commands.append(command)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for line in log_text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            visit(json.loads(line))
        except Exception:
            continue

    return names, commands


def resolve_artifact_path(artifact_path: str, artifact_root: pathlib.Path | None) -> pathlib.Path:
    if artifact_root is not None and artifact_path.startswith("/app/"):
        return artifact_root / artifact_path.removeprefix("/app/")
    return pathlib.Path(artifact_path)


def decide_injection(
    log_text: str,
    context_text: str,
    artifact_root: pathlib.Path | None = None,
    log_path: pathlib.Path = DEFAULT_LOG_PATH,
    context_path: pathlib.Path = DEFAULT_CONTEXT_PATH,
    timestamp: str | None = None,
) -> dict[str, Any]:
    expected = expected_artifacts(context_text)
    tool_names, bash_commands = actual_tool_uses(log_text)

    reasons: list[str] = []
    if "AskUserQuestion" in tool_names:
        reasons.append("ask_user_question")
    if "WebFetch" in tool_names:
        reasons.append("web_fetch")
    if "WebSearch" in tool_names:
        reasons.append("web_search")
    if any(
        "pip install" in command or "uvx" in command or "apt-get install" in command
        for command in bash_commands
    ):
        reasons.append("dependency_install")
    if "ModuleNotFoundError" in log_text:
        reasons.append("module_missing")
    if "Command running in background" in log_text:
        reasons.append("background_task")

    for artifact, expected_text in expected.items():
        path = resolve_artifact_path(artifact, artifact_root)
        if not path.exists():
            reasons.append(f"artifact_missing:{artifact}")
            continue
        if expected_text is not None:
            actual = path.read_text(encoding="utf-8", errors="replace")
            if actual != expected_text:
                reasons.append(f"artifact_mismatch:{artifact}")

    if not log_text.strip():
        reasons.append("first_turn_log_missing_or_empty")

    return {
        "timestamp": timestamp or dt.datetime.now(dt.timezone.utc).isoformat(),
        "should_inject": bool(reasons),
        "reasons": reasons,
        "tool_names": tool_names,
        "expected_artifacts": sorted(expected),
        "log_path": str(log_path),
        "context_path": str(context_path),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay or run a runtime ICL controller decision.")
    parser.add_argument("--log-path", type=pathlib.Path, default=DEFAULT_LOG_PATH)
    parser.add_argument("--context-path", type=pathlib.Path, default=DEFAULT_CONTEXT_PATH)
    parser.add_argument("--output-path", type=pathlib.Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--artifact-root",
        type=pathlib.Path,
        default=None,
        help="Optional root used to remap /app artifacts during local replay.",
    )
    parser.add_argument("--compact", action="store_true", help="Write compact JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    decision = decide_injection(
        log_text=read_text(args.log_path),
        context_text=read_text(args.context_path),
        artifact_root=args.artifact_root,
        log_path=args.log_path,
        context_path=args.context_path,
    )
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    if args.compact:
        text = json.dumps(decision, ensure_ascii=False)
    else:
        text = json.dumps(decision, ensure_ascii=False, indent=2)
    args.output_path.write_text(text + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
