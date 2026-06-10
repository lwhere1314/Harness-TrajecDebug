#!/usr/bin/env python3
"""Compute TB2.1 Kimi-k2.6 lift from Harness-TrajecDebug runs.

The main score uses one canonical Claude Code + Kimi-k2.6 baseline over the 89
Terminal-Bench 2.1 tasks. Baseline entries that never reached the agent loop
because of local infrastructure errors may be filled from a no-TD supplemental
run. TrajectoryDebug lifts count only model-agent runs with a verifier reward of
1.0; deterministic artifact-closure checks are reported separately.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_TASK_ROOT = Path("/Users/hugo/Desktop/super-refactor/harbor/datasets/terminal-bench-2.1-proxy/tasks")
DEFAULT_PRIMARY_BASELINE = Path(
    "/Volumes/SSD/terminal-bench-harbor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy/state.json"
)
DEFAULT_SUPPLEMENTAL_BASELINE = Path(
    "/Volumes/SSD/terminal-bench-harbor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy-supplemental-artifacts/state.json"
)
DEFAULT_PACK_DIR = Path("runs/harbor_icl_baseline")
DEFAULT_JSON = Path("runs/harbor_icl_baseline/tb21_kimi_k26_td_lift.json")
DEFAULT_MD = Path("docs/tb21-kimi-k26-trajectorydebug-lift.md")

EXTRA_BASELINE_PATTERNS = (
    "harbor_runs_no_td_baseline/tb21-*-no-td-prompt-safe-kimi-k2-6/*/result.json",
)


TD_AGENT_PATTERNS = (
    "harbor_runs/htd-icl-debug_trajectory-*-kimi-k2-6/*/result.json",
    "harbor_runs_sdk_live/htd-dynamic-icl-sdk_live-debug_action-*-kimi-k2-6/*/result.json",
    "harbor_runs_sdk_live/htd-dynamic-icl-sdk_live-debug_trajectory-*-kimi-k2-6/*/result.json",
    "harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-*-kimi-k2-6/*/result.json",
    "harbor_runs_joint_failure/htd-dynamic-icl-prelude-debug_action-*-kimi-k2-6/*/result.json",
    "harbor_runs_joint_failure/htd-dynamic-icl-sdk_live-debug_action-*-kimi-k2-6/*/result.json",
    "harbor_runs_oracle_grounded/htd-dynamic-icl-prelude-oracle_grounded-*-kimi-k2-6/*/result.json",
    "harbor_runs_oracle_grounded/htd-dynamic-icl-sdk_live-oracle_grounded-*-kimi-k2-6/*/result.json",
)

CLOSURE_ONLY_PATTERNS = (
    "harbor_runs_artifact_closure/htd-artifact-closure-debug_action-*/*/result.json",
)


@dataclass
class TrialRecord:
    task: str
    reward: float | None
    status: str
    result_path: str | None
    source: str
    exception_type: str | None = None
    has_agent_result: bool = False


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def reward(data: dict[str, Any]) -> float | None:
    value = data.get("verifier_result", {})
    if not isinstance(value, dict):
        return None
    value = value.get("rewards", {}).get("reward")
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
    if not isinstance(agent, dict):
        return False
    return any(value is not None for value in agent.values())


def trial_result_for_job(job_dir: Path, task: str) -> Path | None:
    if not job_dir.exists():
        return None
    for trial_dir in sorted(job_dir.iterdir()):
        if trial_dir.is_dir() and trial_dir.name.startswith(f"{task}__"):
            result = trial_dir / "result.json"
            if result.exists():
                return result
    return None


def record_from_state(state_path: Path, task: str, source: str) -> TrialRecord | None:
    state = read_json(state_path)
    if not state:
        return None
    row = state.get("tasks", {}).get(task)
    if not isinstance(row, dict):
        return None
    job_dir_value = row.get("job_dir")
    if not job_dir_value:
        return None
    result_path = trial_result_for_job(Path(job_dir_value), task)
    if not result_path:
        return TrialRecord(task, None, "no_trial_result", None, source)
    data = read_json(result_path) or {}
    r = reward(data)
    exc = exception_type(data)
    agent = has_agent_result(data)
    if r == 1.0:
        status = "pass"
    elif r == 0.0 and agent:
        status = "fail"
    elif exc == "AgentTimeoutError":
        status = "fail"
    else:
        status = "infra_or_no_agent"
    return TrialRecord(task, r, status, str(result_path), source, exc, agent)


def task_from_trial_result(path: Path, known_tasks: set[str]) -> str | None:
    name = path.parent.name
    for task in known_tasks:
        if name.startswith(f"{task}__"):
            return task
    return None


def collect_td_agent_successes(pack_dir: Path, known_tasks: set[str]) -> dict[str, TrialRecord]:
    successes: dict[str, TrialRecord] = {}
    for pattern in TD_AGENT_PATTERNS:
        for path in sorted(pack_dir.glob(pattern)):
            task = task_from_trial_result(path, known_tasks)
            if not task:
                continue
            data = read_json(path) or {}
            if reward(data) != 1.0 or not has_agent_result(data):
                continue
            successes.setdefault(
                task,
                TrialRecord(
                    task=task,
                    reward=1.0,
                    status="pass",
                    result_path=str(path),
                    source="trajectorydebug_agent",
                    exception_type=exception_type(data),
                    has_agent_result=True,
                ),
            )
    return successes


def collect_closure_only_successes(pack_dir: Path, known_tasks: set[str]) -> dict[str, TrialRecord]:
    successes: dict[str, TrialRecord] = {}
    for pattern in CLOSURE_ONLY_PATTERNS:
        for path in sorted(pack_dir.glob(pattern)):
            task = task_from_trial_result(path, known_tasks)
            if not task:
                continue
            data = read_json(path) or {}
            if reward(data) != 1.0:
                continue
            successes.setdefault(
                task,
                TrialRecord(
                    task=task,
                    reward=1.0,
                    status="pass",
                    result_path=str(path),
                    source="closure_only",
                    exception_type=exception_type(data),
                    has_agent_result=has_agent_result(data),
                ),
            )
    return successes


def record_from_result_path(path: Path, known_tasks: set[str], source: str) -> TrialRecord | None:
    task = task_from_trial_result(path, known_tasks)
    if not task:
        return None
    data = read_json(path) or {}
    r = reward(data)
    exc = exception_type(data)
    agent = has_agent_result(data)
    if r == 1.0:
        status = "pass"
    elif r == 0.0 and agent:
        status = "fail"
    elif exc == "AgentTimeoutError":
        status = "fail"
    else:
        status = "infra_or_no_agent"
    return TrialRecord(task, r, status, str(path), source, exc, agent)


def collect_extra_baseline_records(pack_dir: Path, known_tasks: set[str]) -> dict[str, TrialRecord]:
    records: dict[str, TrialRecord] = {}
    for pattern in EXTRA_BASELINE_PATTERNS:
        for path in sorted(pack_dir.glob(pattern)):
            record = record_from_result_path(path, known_tasks, "prompt_safe_no_td")
            if not record:
                continue
            if record.status not in {"pass", "fail"}:
                continue
            records[record.task] = record
    return records


def markdown(report: dict[str, Any]) -> str:
    baseline = report["baseline"]
    td = report["trajectorydebug"]
    lines = [
        "# TB2.1 Kimi-k2.6 TrajectoryDebug Lift",
        "",
        "This report is generated from local Harbor result files. The main lift",
        "counts only Claude Code + Kimi-k2.6 model-agent runs; deterministic",
        "artifact-closure checks are listed separately and excluded from the main",
        "score.",
        "",
        "## Final Number",
        "",
        f"- without TrajectoryDebug: `{baseline['pass_count']}/{baseline['denominator']}`",
        f"- with TrajectoryDebug: `{td['with_td_pass_count']}/{baseline['denominator']}`",
        f"- effective lift `m`: `{td['lift_count']}` tasks",
        "",
        "## Baseline Coverage",
        "",
        f"- primary baseline passes: `{baseline['primary_pass_count']}/{baseline['denominator']}`",
        f"- infra/no-agent baseline fills used: `{len(baseline['infra_fills'])}`",
        f"- final baseline valid tasks: `{baseline['valid_count']}/{baseline['denominator']}`",
        "",
        "## Baseline Fill Details",
        "",
        "Baseline fills are used only where the primary 89-task run did not",
        "produce a valid model-agent result. `prompt_safe_no_td` removes only the",
        "leading-hyphen CLI parsing hazard from the task instruction; it does not",
        "inject any TrajectoryDebug context.",
        "",
        "| Task | Fill source | Status | Reward | Result |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for row in baseline["infra_fills"]:
        target = row["to"]
        lines.append(
            f"| `{row['task']}` | `{target['source']}` | `{target['status']}` | `{target['reward']}` | `{target['result_path']}` |"
        )
    if not baseline["infra_fills"]:
        lines.append("| - | - | - | - | - |")
    lines.extend(
        [
        "",
        "## TrajectoryDebug Agent Lifts",
        "",
        "| Task | Baseline reward | TD source | TD result |",
        "| --- | ---: | --- | --- |",
        ]
    )
    for row in td["lifted_tasks"]:
        lines.append(
            f"| `{row['task']}` | `{row['baseline_reward']}` | `{row['td_source']}` | `{row['td_result_path']}` |"
        )
    if not td["lifted_tasks"]:
        lines.append("| - | - | - | - |")
    lines.extend(
        [
            "",
            "## Closure-Only Successes",
            "",
            "These passed by directly materializing Debug-Action artifacts and do not",
            "enter the main Claude Code + Kimi-k2.6 lift count.",
            "",
            "| Task | Result |",
            "| --- | --- |",
        ]
    )
    for row in report["closure_only_successes"]:
        lines.append(f"| `{row['task']}` | `{row['result_path']}` |")
    if not report["closure_only_successes"]:
        lines.append("| - | - |")
    return "\n".join(lines)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    tasks = sorted(path.name for path in args.task_root.iterdir() if path.is_dir())
    known_tasks = set(tasks)

    primary_records: dict[str, TrialRecord] = {}
    final_records: dict[str, TrialRecord] = {}
    infra_fills: list[dict[str, Any]] = []
    extra_baselines = collect_extra_baseline_records(args.pack_dir, known_tasks)
    for task in tasks:
        primary = record_from_state(args.primary_baseline, task, "primary")
        primary_records[task] = primary or TrialRecord(task, None, "missing", None, "primary")
        final = primary_records[task]
        if final.status == "infra_or_no_agent" or final.status in {"missing", "no_trial_result"}:
            fill = record_from_state(args.supplemental_baseline, task, "supplemental_no_td")
            if fill and fill.status in {"pass", "fail"}:
                infra_fills.append({"task": task, "from": asdict(final), "to": asdict(fill)})
                final = fill
        if final.status == "infra_or_no_agent" or final.status in {"missing", "no_trial_result"}:
            fill = extra_baselines.get(task)
            if fill and fill.status in {"pass", "fail"}:
                infra_fills.append({"task": task, "from": asdict(final), "to": asdict(fill)})
                final = fill
        final_records[task] = final

    td_successes = collect_td_agent_successes(args.pack_dir, known_tasks)
    closure_successes = collect_closure_only_successes(args.pack_dir, known_tasks)

    lifted = []
    for task, td_record in sorted(td_successes.items()):
        baseline = final_records.get(task)
        if not baseline or baseline.reward == 1.0:
            continue
        if baseline.status not in {"fail", "pass"}:
            continue
        lifted.append(
            {
                "task": task,
                "baseline_reward": baseline.reward,
                "baseline_result_path": baseline.result_path,
                "td_source": td_record.source,
                "td_result_path": td_record.result_path,
            }
        )

    baseline_pass_count = sum(1 for item in final_records.values() if item.reward == 1.0)
    primary_pass_count = sum(1 for item in primary_records.values() if item.reward == 1.0)
    valid_count = sum(1 for item in final_records.values() if item.status in {"pass", "fail"})
    return {
        "task_root": str(args.task_root),
        "primary_baseline": str(args.primary_baseline),
        "supplemental_baseline": str(args.supplemental_baseline),
        "pack_dir": str(args.pack_dir),
        "baseline": {
            "denominator": len(tasks),
            "primary_pass_count": primary_pass_count,
            "pass_count": baseline_pass_count,
            "valid_count": valid_count,
            "infra_fills": infra_fills,
            "records": {task: asdict(record) for task, record in final_records.items()},
        },
        "trajectorydebug": {
            "agent_success_count": len(td_successes),
            "lift_count": len(lifted),
            "with_td_pass_count": baseline_pass_count + len(lifted),
            "lifted_tasks": lifted,
            "agent_successes": {task: asdict(record) for task, record in sorted(td_successes.items())},
        },
        "closure_only_successes": [
            asdict(record) for _, record in sorted(closure_successes.items())
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    parser.add_argument("--primary-baseline", type=Path, default=DEFAULT_PRIMARY_BASELINE)
    parser.add_argument("--supplemental-baseline", type=Path, default=DEFAULT_SUPPLEMENTAL_BASELINE)
    parser.add_argument("--pack-dir", type=Path, default=DEFAULT_PACK_DIR)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    report = build_report(args)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(markdown(report) + "\n", encoding="utf-8")
    print(json.dumps({
        "without_trajectorydebug": f"{report['baseline']['pass_count']}/{report['baseline']['denominator']}",
        "with_trajectorydebug": f"{report['trajectorydebug']['with_td_pass_count']}/{report['baseline']['denominator']}",
        "lift": report["trajectorydebug"]["lift_count"],
        "output_json": str(args.output_json),
        "output_md": str(args.output_md),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
