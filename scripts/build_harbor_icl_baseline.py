#!/usr/bin/env python3
"""Build same-task Harbor ICL baseline packs from local teacher runs."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from harness_trajecdebug.experiments.harbor_icl_baseline import (
    DEFAULT_TARGET_TASKS,
    DEFAULT_TEACHER_STATES,
    build_baseline_pack,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs/harbor_icl_baseline"),
        help="Directory for generated prompts, task copies, and run scripts.",
    )
    parser.add_argument(
        "--teacher-state",
        action="append",
        type=Path,
        default=[],
        help="Teacher Harbor state.json. Can be passed multiple times.",
    )
    parser.add_argument(
        "--target-task",
        action="append",
        default=[],
        help="Task to build variants for. Can be passed multiple times.",
    )
    parser.add_argument(
        "--variant",
        action="append",
        default=[],
        help="Prompt variant: no_icl, outcome_only, raw_trace, prompt_filtered, debug_trajectory, or debug_action.",
    )
    parser.add_argument("--model", default="kimi-k2.5", help="Default model in generated run script.")
    parser.add_argument(
        "--max-context-chars",
        type=int,
        default=12000,
        help="Maximum injected ICL payload characters per prompt variant. Use 0 for no truncation.",
    )
    parser.add_argument(
        "--patch-verifier",
        action="store_true",
        help="Patch copied task verifier scripts for local infrastructure reliability. Off by default to preserve benchmark semantics.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_baseline_pack(
        output_dir=args.output_dir,
        teacher_states=args.teacher_state or DEFAULT_TEACHER_STATES,
        target_tasks=args.target_task or DEFAULT_TARGET_TASKS,
        variants=args.variant or None,
        model=args.model,
        max_context_chars=args.max_context_chars,
        patch_verifier=args.patch_verifier,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
