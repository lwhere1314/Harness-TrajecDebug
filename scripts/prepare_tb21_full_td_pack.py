#!/usr/bin/env python3
"""Prepare a full 89-task TD context pack for fresh TB2.1 reruns.

The existing ICL pack contains high-signal Debug-Action cards for only the
tasks we have already diagnosed. A full 89-task with-TD rerun still needs a
context file for every task so the denominator is honest. This script writes a
uniform `td_full.md` context for each task:

- if a diagnosed card exists, use it;
- otherwise write a reference-only TD checklist from the task instruction.

The fallback cards are deliberately labeled as reference-only. They make the
with-TD condition executable for all tasks without pretending that every task
already has a mined critical step.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_TASK_ROOT = Path("/Users/hugo/Desktop/super-refactor/harbor/datasets/terminal-bench-2.1-proxy/tasks")
DEFAULT_PACK_DIR = Path("runs/harbor_icl_baseline")


@dataclass
class CardRecord:
    task: str
    card_path: str
    source: str
    source_path: str | None


def read_text(path: Path, default: str = "") -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else default


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def compact(text: str, limit: int = 5000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 80].rstrip() + "\n\n[TRUNCATED TO FIXED TD REFERENCE BUDGET]"


def fallback_card(task: str, instruction: str) -> str:
    return f"""# Reference-Only TrajectoryDebug Card: {task}

This task does not yet have a mined Debug-Action or Debug-Trajectory card in the
local TD pack. Use this as a lightweight TD checklist, not as a prior solution.

## Reference view

{compact(instruction, 5000)}

## Process checklist

- Extract the required final artifact path, metric gate, verifier semantics, and
  forbidden side effects before choosing an implementation route.
- Maintain a small state table of commands, generated artifacts, validation
  results, errors, and remaining uncertainty.
- Do not promote a final answer only because a local probe passed; align the
  closure check with the official verifier when possible.
- If a command fails, distinguish local recoverable tooling errors from a
  route-level wrong commitment.
- Stop after the required artifact is closed; avoid extra rewrites that can
  introduce verifier side effects.

## Runtime policy

Treat this card as process guidance only. It contains no teacher artifact and no
known critical step. Solve the live task in the current environment and let the
official verifier grade the result.
"""


def choose_existing_card(card_dir: Path, priority: list[str]) -> tuple[str, Path] | None:
    for name in priority:
        path = card_dir / f"{name}.md"
        if path.exists():
            return name, path
    return None


def build_pack(args: argparse.Namespace) -> dict[str, object]:
    tasks = sorted(path.name for path in args.task_root.iterdir() if path.is_dir())
    records: list[CardRecord] = []
    for task in tasks:
        card_dir = args.pack_dir / "teacher_cards" / task
        chosen = choose_existing_card(card_dir, args.priority)
        out = card_dir / f"{args.output_variant}.md"
        if chosen:
            source, path = chosen
            write_text(out, read_text(path))
            records.append(CardRecord(task, str(out), source, str(path)))
            continue

        instruction = read_text(args.task_root / task / "instruction.md")
        write_text(out, fallback_card(task, instruction))
        records.append(CardRecord(task, str(out), "reference_only_fallback", None))

    summary = {
        "task_root": str(args.task_root),
        "pack_dir": str(args.pack_dir),
        "output_variant": args.output_variant,
        "task_count": len(tasks),
        "priority": args.priority,
        "counts_by_source": {},
        "records": [asdict(record) for record in records],
    }
    counts: dict[str, int] = {}
    for record in records:
        counts[record.source] = counts.get(record.source, 0) + 1
    summary["counts_by_source"] = counts
    write_text(
        args.pack_dir / f"tb21_full_td_{args.output_variant}_manifest.json",
        json.dumps(summary, indent=2, ensure_ascii=False),
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    parser.add_argument("--pack-dir", type=Path, default=DEFAULT_PACK_DIR)
    parser.add_argument("--output-variant", default="td_full")
    parser.add_argument(
        "--priority",
        action="append",
        default=[],
        help="Existing card variant priority. May repeat.",
    )
    args = parser.parse_args()
    if not args.priority:
        args.priority = ["debug_action", "debug_trajectory", "oracle_grounded", "prompt_filtered", "outcome_only"]
    return args


def main() -> int:
    summary = build_pack(parse_args())
    print(json.dumps({k: v for k, v in summary.items() if k != "records"}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
