#!/usr/bin/env python3
"""Audit TB2.1 baseline and Meta-Harness-style recovery results.

The script is intentionally filesystem-first: it reads Harbor result.json files
and emits task-level CSV/JSON evidence for the requested n/89 and n+m/89
numbers.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


DEFAULT_TASKS_DIR = Path(
    "/Users/hugo/Desktop/super-refactor/harbor/datasets/"
    "terminal-bench-2.1-proxy/tasks"
)
DEFAULT_BASELINE_ROOT = Path(
    "/Users/hugo/Desktop/super-refactor/harbor/runs/"
    "tb21-kimi-k26-local-019e737a-colima16g-proxy"
)
DEFAULT_KIMICODE_ROOT = Path("/Users/hugo/Projects/Harness-TrajecDebug/artifacts/harbor-runs")
DEFAULT_CANCEL_CASE = Path(
    "/Users/hugo/Projects/Harness-TrajecDebug/docs/case-studies/"
    "kimi-code-cancel-async-tasks-metaharness-2026-06-10/raw"
)
DEFAULT_OUTPUT_DIR = Path(
    "/Users/hugo/Projects/Harness-TrajecDebug/docs/case-studies/"
    "kimi-code-tb21-metaharness-sweep-2026-06-10"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-dir", type=Path, default=DEFAULT_TASKS_DIR)
    parser.add_argument("--baseline-root", type=Path, default=DEFAULT_BASELINE_ROOT)
    parser.add_argument("--kimicode-root", type=Path, default=DEFAULT_KIMICODE_ROOT)
    parser.add_argument("--cancel-case-root", type=Path, default=DEFAULT_CANCEL_CASE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    tasks = sorted(path.name for path in args.tasks_dir.iterdir() if path.is_dir())
    baseline_records = collect_baseline_records(args.baseline_root, set(tasks))
    with_records = collect_kimicode_records(args.kimicode_root, args.cancel_case_root, set(tasks))

    rows: list[dict[str, Any]] = []
    for task in tasks:
        baseline = select_best_baseline(baseline_records.get(task, []))
        with_mh = select_best_with(with_records.get(task, []))
        baseline_reward = baseline.get("reward") if baseline else None
        with_reward = with_mh.get("reward") if with_mh else None
        baseline_pass = baseline_reward == 1.0
        with_pass = (not baseline_pass) and with_reward == 1.0
        row = {
            "task": task,
            "baseline_reward": baseline_reward,
            "baseline_exception": baseline.get("exception") if baseline else None,
            "baseline_status": baseline_status(baseline),
            "baseline_trial": baseline.get("trial") if baseline else None,
            "baseline_result_path": baseline.get("path") if baseline else None,
            "with_metaharness_reward": with_reward,
            "with_metaharness_exception": with_mh.get("exception") if with_mh else None,
            "with_metaharness_status": with_status(with_mh),
            "with_metaharness_trial": with_mh.get("trial") if with_mh else None,
            "with_metaharness_result_path": with_mh.get("path") if with_mh else None,
            "counts_for_without_n": baseline_pass,
            "counts_for_m": with_pass,
        }
        rows.append(row)

    summary = {
        "task_count": len(tasks),
        "without_metaharness_n": sum(1 for row in rows if row["counts_for_without_n"]),
        "with_metaharness_m_current": sum(1 for row in rows if row["counts_for_m"]),
        "with_metaharness_total_current": sum(
            1
            for row in rows
            if row["counts_for_without_n"] or row["counts_for_m"]
        ),
        "baseline_invalid_tasks": [
            row["task"] for row in rows if row["baseline_status"] == "invalid_or_missing"
        ],
        "baseline_failed_tasks": [
            row["task"] for row in rows if row["baseline_status"] in {"failed", "timeout_failure"}
        ],
        "with_metaharness_solved_tasks": [
            row["task"] for row in rows if row["counts_for_m"]
        ],
        "with_metaharness_unsolved_observed_tasks": [
            row["task"]
            for row in rows
            if row["baseline_status"] != "passed"
            and row["with_metaharness_status"] in {"failed", "timeout_failure"}
            and not row["counts_for_m"]
        ],
        "sources": {
            "tasks_dir": str(args.tasks_dir),
            "baseline_root": str(args.baseline_root),
            "kimicode_root": str(args.kimicode_root),
            "cancel_case_root": str(args.cancel_case_root),
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "tb21_89_audit.csv"
    json_path = args.output_dir / "tb21_89_audit.json"
    write_csv(csv_path, rows)
    json_path.write_text(
        json.dumps({"summary": summary, "tasks": rows}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    return 0


def collect_baseline_records(root: Path, tasks: set[str]) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result_path in root.glob("**/result.json"):
        record = read_result(result_path)
        if not record:
            continue
        task = infer_baseline_task(result_path, tasks)
        if task is None:
            continue
        trial = result_path.parent.name
        if "__" not in trial:
            continue
        record.update(
            {
                "task": task,
                "trial": trial,
                "job": next(
                    (part for part in reversed(result_path.parts) if part.startswith("tb21-")),
                    None,
                ),
                "path": str(result_path),
                "source": "claude-code+kimi-k2.6",
            }
        )
        records[task].append(record)
    return records


def collect_kimicode_records(
    artifacts_root: Path,
    cancel_case_root: Path,
    tasks: set[str],
) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    roots = [artifacts_root, cancel_case_root]
    for root in roots:
        if not root.exists():
            continue
        for result_path in root.glob("**/result.json"):
            task = infer_trial_task(result_path, tasks)
            if task is None:
                continue
            text_path = str(result_path)
            if "with-metaharness" not in text_path and "with_metaharness" not in text_path:
                continue
            record = read_result(result_path)
            if not record:
                continue
            record.update(
                {
                    "task": task,
                    "trial": result_path.parent.name,
                    "job": result_path.parent.parent.name,
                    "path": str(result_path),
                    "source": "kimi-code+Meta-Harness",
                }
            )
            records[task].append(record)
    return records


def read_result(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None
    verifier = data.get("verifier_result") if isinstance(data.get("verifier_result"), dict) else {}
    rewards = verifier.get("rewards") if isinstance(verifier.get("rewards"), dict) else {}
    exception = data.get("exception_info") if isinstance(data.get("exception_info"), dict) else {}
    return {
        "reward": as_float(rewards.get("reward")),
        "exception": exception.get("exception_type"),
        "exception_message": exception.get("exception_message"),
    }


def infer_baseline_task(path: Path, tasks: set[str]) -> str | None:
    for part in reversed(path.parts):
        match = re.match(r"tb21-(.*)-claude-code-k6(?:--[a-z_]+)?(?:-|$)", part)
        if match and match.group(1) in tasks:
            return match.group(1)
        match = re.match(r"tb21-(.*)-claude-code-k6", part)
        if match and match.group(1) in tasks:
            return match.group(1)
    return infer_trial_task(path, tasks)


def infer_trial_task(path: Path, tasks: set[str]) -> str | None:
    for part in reversed(path.parts):
        if "__" not in part:
            continue
        task = part.split("__", 1)[0]
        if task in tasks:
            return task
    return None


def select_best_baseline(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not records:
        return None
    return max(records, key=baseline_rank)


def baseline_rank(record: dict[str, Any]) -> tuple[int, int, int]:
    path = record["path"]
    reward = record.get("reward")
    exception = record.get("exception")
    location = 2 if "/jobs/" in path else (1 if "jobs_archived_before_rerun" in path else 0)
    has_reward = 1 if reward is not None else 0
    clean = 1 if exception is None else 0
    return (location, has_reward, clean)


def select_best_with(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not records:
        return None
    return max(records, key=with_rank)


def with_rank(record: dict[str, Any]) -> tuple[int, int, int]:
    reward = record.get("reward")
    exception = record.get("exception")
    return (
        2 if reward == 1.0 else (1 if reward == 0.0 else 0),
        1 if exception is None else 0,
        len(record.get("path", "")),
    )


def baseline_status(record: dict[str, Any] | None) -> str:
    if not record:
        return "invalid_or_missing"
    if record.get("reward") == 1.0:
        return "passed"
    if record.get("reward") == 0.0:
        return "timeout_failure" if record.get("exception") == "AgentTimeoutError" else "failed"
    return "invalid_or_missing"


def with_status(record: dict[str, Any] | None) -> str:
    if not record:
        return "not_run"
    if record.get("reward") == 1.0:
        return "passed"
    if record.get("reward") == 0.0:
        return "timeout_failure" if record.get("exception") == "AgentTimeoutError" else "failed"
    return "invalid_or_missing"


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
