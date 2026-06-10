#!/usr/bin/env python3
"""Replay live Harness-TrajecDebug ICL controller decisions offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from harness_trajecdebug.experiments.live_icl_controller import LiveIclController  # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay one live ICL controller decision without running a model."
    )
    parser.add_argument("--context-path", type=Path, required=True)
    parser.add_argument("--mode", choices=["pre_tool_use", "can_use_tool"], required=True)
    parser.add_argument("--tool-name", required=True)
    parser.add_argument("--tool-input-json", default="{}")
    parser.add_argument("--intercept-tool", action="append", default=[])
    parser.add_argument("--already-injected", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    context = args.context_path.read_text(encoding="utf-8", errors="replace")
    try:
        tool_input = json.loads(args.tool_input_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--tool-input-json must be valid JSON: {exc}") from exc
    if not isinstance(tool_input, dict):
        raise SystemExit("--tool-input-json must decode to a JSON object")

    controller = LiveIclController(
        context=context,
        intercept_tools=set(args.intercept_tool),
        injected=args.already_injected,
    )
    if args.mode == "pre_tool_use":
        decision = controller.handle_pre_tool_use(
            {"tool_name": args.tool_name, "tool_input": tool_input}
        )
    else:
        decision = controller.handle_can_use_tool(args.tool_name, tool_input)

    print(
        json.dumps(
            {
                "response": decision.response,
                "events": decision.events,
                "reason": decision.reason,
                "injected": decision.injected,
                "controller_injected": controller.injected,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
