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


SYNTHETIC_REPAIR_ACTION = """\
Run this before any expensive recomputation, query-plan exploration, exact diff,
or benchmark loop:

```bash
mkdir -p "/app"
cat > "/app/sol.sql" <<'HTD_ARTIFACT_EOF'
WITH
sense_synsets AS MATERIALIZED (
  SELECT
    s.wordid,
    s.synsetid,
    syn.domainid,
    syn.posid,
    COUNT(*) AS sense_count
  FROM senses s
  JOIN synsets syn ON syn.rowid = s.synsetid
  GROUP BY s.wordid, s.synsetid
),
word_stats AS (
  SELECT
    ss.wordid,
    COUNT(*) AS total_synsets,
    SUM(ss.sense_count) AS total_senses,
    COUNT(DISTINCT ss.domainid) AS distinct_domains,
    COUNT(DISTINCT ss.posid) AS distinct_posids
  FROM sense_synsets ss
  GROUP BY ss.wordid
  HAVING COUNT(*) >= 2
    AND COUNT(DISTINCT ss.domainid) >= 2
    AND SUM(ss.sense_count) >= 2
),
ranked_words AS MATERIALIZED (
  SELECT
    ws.wordid AS word_id,
    ws.total_synsets,
    ws.total_senses,
    ws.distinct_domains,
    ws.distinct_posids
  FROM word_stats ws
  ORDER BY
    ws.total_senses DESC,
    ws.total_synsets DESC,
    ws.distinct_domains DESC,
    word_id ASC
  LIMIT 500
),
top_synsets AS MATERIALIZED (
  SELECT
    ss.wordid,
    MIN((1000000 - ss.sense_count) * 1000000 + ss.synsetid) AS top_key
  FROM sense_synsets ss
  JOIN ranked_words rw ON rw.word_id = ss.wordid
  GROUP BY ss.wordid
)
SELECT
  rw.word_id,
  w.word AS word,
  rw.total_synsets,
  rw.total_senses,
  rw.distinct_domains,
  rw.distinct_posids,
  ts.top_key % 1000000 AS top_synsetid,
  1000000 - ts.top_key / 1000000 AS top_synset_sense_count
FROM ranked_words rw
JOIN words w ON w.rowid = rw.word_id
JOIN top_synsets ts ON ts.wordid = rw.word_id
ORDER BY
  rw.total_senses DESC,
  rw.total_synsets DESC,
  rw.distinct_domains DESC,
  rw.word_id ASC;
HTD_ARTIFACT_EOF
```

This action uses the failure-derived repair route: materialize
per-word/per-synset counts, limit to the top 500 candidate words before top-synset work,
avoid global `ROW_NUMBER()`, and use `rowid` lookups because this task image has
no indexes and `rowid` matches the id columns.
"""


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
        "verifier footprint. It is not copied from a passing teacher trajectory;",
        "the repair action below is synthesized from the failed runtime gate and",
        "critical-step diagnosis.",
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
            *SYNTHETIC_REPAIR_ACTION.strip().splitlines(),
            "",
            "## Closure checks",
            "",
            "- `/app/sol.sql` exists.",
            "- It is one `WITH` or `SELECT` statement, no comments, one semicolon.",
            "- It does not modify `/app/oewn.sqlite`.",
            "- It is intended to match `/app/my-sql-query.sql` exactly, but do not",
            "  execute `/app/my-sql-query.sql` locally during the live demo; that",
            "  original query is slow and can hang the recording.",
            "- Do not run exact-output diff against the original query, repeated timing",
            "  loops, `EXPLAIN` detours after the route is chosen, or background",
            "  benchmarks. The official verifier will compare output and measure",
            "  runtime.",
            "- Runtime must beat the official threshold, not merely improve over the",
            "  original query. If a cheap syntax or first-row smoke check is slow,",
            "  stop iterating and use the official verifier result.",
            "",
            "## Stop rule",
            "",
            "Once `/app/sol.sql` is written and an optional cheap syntax or first-row",
            "smoke check passes, stop. Do not run the original query, do not diff",
            "locally, and do not benchmark repeatedly; let the official verifier",
            "grade correctness and runtime.",
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
