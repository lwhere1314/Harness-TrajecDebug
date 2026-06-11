#!/usr/bin/env python3
"""Build a query-optimize fail-teacher Debug-Action card from a failed trial."""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_reward(trial: Path) -> str:
    reward_path = trial / "verifier" / "reward.txt"
    if not reward_path.exists():
        return "unknown"
    raw = read_text(reward_path).strip()
    if not raw:
        return "unknown"
    try:
        return f"{float(raw):.1f}"
    except ValueError:
        return raw


def parse_verifier_summary(stdout: str) -> tuple[int | None, int | None]:
    matches = re.findall(r"(\d+)\s+failed,\s+(\d+)\s+passed", stdout)
    if matches:
        failed, passed = matches[-1]
        return int(passed), int(failed)
    matches = re.findall(r"(\d+)\s+passed,\s+(\d+)\s+failed", stdout)
    if matches:
        passed, failed = matches[-1]
        return int(passed), int(failed)
    return None, None


def parse_runtime_summary(stdout: str) -> dict[str, Any]:
    for line in stdout.splitlines():
        if "speedup_solution_vs_golden" not in line:
            continue
        start = line.find("{")
        end = line.rfind("}")
        if start == -1 or end == -1 or end <= start:
            continue
        try:
            parsed = ast.literal_eval(line[start : end + 1])
        except (SyntaxError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def metric(summary: dict[str, Any], section: str, key: str) -> str:
    value = summary.get(section, {})
    if isinstance(value, dict) and key in value:
        return str(value[key])
    return "unknown"


def build_card(trial: Path, diagnosis: Path, task_dir: Path) -> str:
    stdout = read_text(trial / "verifier" / "test-stdout.txt")
    reward = parse_reward(trial)
    passed, failed = parse_verifier_summary(stdout)
    runtime = parse_runtime_summary(stdout)
    diagnosis_data = json.loads(read_text(diagnosis))
    critical = diagnosis_data.get("critical_step") or {}
    instruction_path = task_dir / "instruction.md"
    instruction = compact(read_text(instruction_path)) if instruction_path.exists() else (
        "Write one optimized SQLite query to /app/sol.sql for the query-optimize task."
    )

    passed_text = "unknown" if passed is None else str(passed)
    failed_text = "unknown" if failed is None else str(failed)
    pattern = critical.get("pattern") or "budget debt loop"
    step_index = critical.get("step_index")
    confidence = critical.get("confidence")
    final_failure = diagnosis_data.get("final_failure") or "final artifact failed verifier validation"

    lines = [
        "# Failure-Derived Debug-Action Card: query-optimize",
        "",
        "This card was generated from a failed same-task trajectory and its",
        "verifier footprint. It is not copied from a passing teacher artifact and",
        "does not contain a ready-made `/app/sol.sql` heredoc. Use it as",
        "failure-derived repair guidance.",
        "",
        "## Reference view",
        "",
        instruction,
        "",
        "## Failed teacher outcome",
        "",
        "Task: query-optimize",
        f"Teacher outcome: reward={reward}",
        f"Verifier summary: tests=6, passed={passed_text}, failed={failed_text}",
        "Failed gate: `test_compare_golden_vs_solution_runtime`",
        f"Final failure: `{final_failure}`",
        "",
        "The failed teacher produced a semantically correct rewrite, but the",
        "official runtime benchmark still failed:",
        "",
        f"- golden median: `{metric(runtime, 'golden', 'median_s')}`",
        f"- failed solution median: `{metric(runtime, 'solution', 'median_s')}`",
        f"- speedup solution vs golden: `{runtime.get('speedup_solution_vs_golden', 'unknown')}`",
        "",
        "## Critical step",
        "",
        f"Pattern: `{pattern}`",
    ]
    if step_index is not None or confidence is not None:
        lines.append(f"Step index: `{step_index}`; confidence: `{confidence}`")
    lines.extend(
        [
            "",
            "The failed trajectory correctly removed the obvious correlated scalar",
            "subqueries, but it then promoted a global `ROW_NUMBER()` ranking route",
            "over per-word/per-synset groups. That route matched the original output",
            "but still spent too much work before the final `LIMIT 500`, so it failed",
            "the runtime gate.",
            "",
            "## Recommended next action",
            "",
            "Before writing `/app/sol.sql`, inspect `/app/my-sql-query.sql` and the",
            "schema, then use this repair route:",
            "",
            "1. Build one grouped CTE for `(wordid, synsetid)` sense counts and joined",
            "   `domainid` / `posid`.",
            "2. Compute candidate word stats from that grouped CTE.",
            "3. Order candidate words by the verifier order and limit to 500 before",
            "   doing remaining top-synset work.",
            "4. Avoid a global `ROW_NUMBER()` window over all word/synset groups. For",
            "   the top synset, use an aggregate tie-break key such as",
            "   `(1000000 - sense_count) * 1000000 + synsetid`, then decode it in the",
            "   final projection.",
            "5. Write `/app/sol.sql` only after the query has the exact required",
            "   columns: `word_id`, `word`, `total_synsets`, `total_senses`,",
            "   `distinct_domains`, `distinct_posids`, `top_synsetid`,",
            "   `top_synset_sense_count`.",
            "",
            "## Closure checks",
            "",
            "- `/app/sol.sql` exists.",
            "- It is one `WITH` or `SELECT` statement, no comments, one semicolon.",
            "- It does not modify `/app/oewn.sqlite`.",
            "- Its output matches `/app/my-sql-query.sql` exactly.",
            "- Runtime must beat the official threshold, not merely improve over the",
            "  original query. If the solution is around `0.55s` median on this",
            "  verifier, treat it as still failed.",
            "",
            "## Stop rule",
            "",
            "Once `/app/sol.sql` is written and a cheap equivalence/performance smoke",
            "check passes, stop and let the official verifier grade it.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a query-optimize fail-teacher Debug-Action card."
    )
    parser.add_argument("--trial", type=Path, required=True)
    parser.add_argument("--diagnosis", type=Path, required=True)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    card = build_card(args.trial, args.diagnosis, args.task_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(card, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
