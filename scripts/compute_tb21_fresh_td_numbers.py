#!/usr/bin/env python3
"""Compute fresh no-TD vs with-TD TB2.1 numbers from two state.json files."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_TASK_ROOT = Path("/Users/hugo/Desktop/super-refactor/harbor/datasets/terminal-bench-2.1-proxy/tasks")


@dataclass
class TaskResult:
    task: str
    status: str
    reward: float | None
    result_path: str | None
    job_dir: str | None
    has_agent_result: bool
    exception_type: str | None


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def reward_from_result(data: dict[str, Any]) -> float | None:
    value: Any = None
    verifier = data.get("verifier_result")
    if isinstance(verifier, dict):
        rewards = verifier.get("rewards")
        if isinstance(rewards, dict):
            value = rewards.get("reward")
        if value is None:
            value = verifier.get("reward")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def exception_type(data: dict[str, Any]) -> str | None:
    exc = data.get("exception_info")
    if isinstance(exc, dict):
        value = exc.get("exception_type") or exc.get("type") or exc.get("class")
        return str(value) if value else "exception"
    if exc:
        return str(exc)
    return None


def has_agent_result(data: dict[str, Any]) -> bool:
    agent = data.get("agent_result")
    return isinstance(agent, dict) and any(value is not None for value in agent.values())


def trial_result_for_task(job_dir: Path, task: str) -> Path | None:
    if not job_dir.exists():
        return None
    for child in sorted(job_dir.iterdir()):
        if child.is_dir() and child.name.startswith(f"{task}__"):
            result = child / "result.json"
            if result.exists():
                return result
    return None


def result_from_state(state: dict[str, Any], task: str) -> TaskResult:
    row = state.get("tasks", {}).get(task)
    if not isinstance(row, dict):
        return TaskResult(task, "missing", None, None, None, False, None)
    job_dir_value = row.get("job_dir")
    if not isinstance(job_dir_value, str):
        return TaskResult(task, str(row.get("status") or "missing_job_dir"), None, None, None, False, None)
    result_path = trial_result_for_task(Path(job_dir_value), task)
    if result_path is None:
        return TaskResult(task, "missing_result", None, None, job_dir_value, False, None)
    data = read_json(result_path) or {}
    r = reward_from_result(data)
    exc = exception_type(data)
    agent = has_agent_result(data)
    if r == 1.0:
        status = "pass"
    elif r == 0.0 and (agent or exc == "AgentTimeoutError"):
        status = "fail"
    elif r == 0.0:
        status = "fail_no_agent_result"
    else:
        status = "infra_or_unknown"
    return TaskResult(task, status, r, str(result_path), job_dir_value, agent, exc)


def summarize(records: dict[str, TaskResult]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for record in records.values():
        counts[record.status] = counts.get(record.status, 0) + 1
    return {
        "pass_count": sum(1 for record in records.values() if record.reward == 1.0),
        "valid_count": sum(1 for record in records.values() if record.status in {"pass", "fail", "fail_no_agent_result"}),
        "counts_by_status": counts,
        "records": {task: asdict(record) for task, record in sorted(records.items())},
    }


def markdown(report: dict[str, Any]) -> str:
    base = report["without_td"]
    td = report["with_td"]
    lines = [
        "# Fresh TB2.1 Claude Code + Kimi-k2.6 TD Rerun",
        "",
        "This report compares two fresh 89-task runs. It does not use old",
        "supplemental fills or scattered prior TD successes.",
        "",
        "## Final Number",
        "",
        f"- without TrajectoryDebug: `{base['pass_count']}/{report['denominator']}`",
        f"- with TrajectoryDebug: `{td['pass_count']}/{report['denominator']}`",
        f"- delta `m`: `{report['delta']}` tasks",
        "",
        "## Coverage",
        "",
        f"- without-TD valid tasks: `{base['valid_count']}/{report['denominator']}`",
        f"- with-TD valid tasks: `{td['valid_count']}/{report['denominator']}`",
        "",
        "## Lift / Regression Table",
        "",
        "| Task | without-TD | with-TD | Delta | without result | with result |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in report["task_rows"]:
        if row["delta"] == 0:
            continue
        lines.append(
            f"| `{row['task']}` | `{row['without_reward']}` | `{row['with_reward']}` | `{row['delta']}` | `{row['without_result']}` | `{row['with_result']}` |"
        )
    if not any(row["delta"] != 0 for row in report["task_rows"]):
        lines.append("| - | - | - | - | - | - |")
    return "\n".join(lines)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    tasks = sorted(path.name for path in args.task_root.iterdir() if path.is_dir())
    baseline_state = read_json(args.without_td_state) or {}
    td_state = read_json(args.with_td_state) or {}
    baseline = {task: result_from_state(baseline_state, task) for task in tasks}
    td = {task: result_from_state(td_state, task) for task in tasks}
    rows = []
    for task in tasks:
        before = baseline[task]
        after = td[task]
        before_pass = before.reward == 1.0
        after_pass = after.reward == 1.0
        rows.append(
            {
                "task": task,
                "without_reward": before.reward,
                "with_reward": after.reward,
                "delta": int(after_pass) - int(before_pass),
                "without_status": before.status,
                "with_status": after.status,
                "without_result": before.result_path,
                "with_result": after.result_path,
            }
        )
    report = {
        "task_root": str(args.task_root),
        "without_td_state": str(args.without_td_state),
        "with_td_state": str(args.with_td_state),
        "denominator": len(tasks),
        "without_td": summarize(baseline),
        "with_td": summarize(td),
        "delta": sum(row["delta"] for row in rows),
        "task_rows": rows,
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    parser.add_argument("--without-td-state", type=Path, required=True)
    parser.add_argument("--with-td-state", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, default=Path("runs/tb21_fresh_td_numbers.json"))
    parser.add_argument("--markdown-output", type=Path, default=Path("docs/tb21-kimi-k26-fresh-td-rerun.md"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.markdown_output.write_text(markdown(report) + "\n", encoding="utf-8")
    print(json.dumps({
        "without": f"{report['without_td']['pass_count']}/{report['denominator']}",
        "with": f"{report['with_td']['pass_count']}/{report['denominator']}",
        "delta": report["delta"],
        "without_valid": report["without_td"]["valid_count"],
        "with_valid": report["with_td"]["valid_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
