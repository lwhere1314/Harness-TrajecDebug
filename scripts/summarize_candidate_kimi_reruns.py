#!/usr/bin/env python3
"""Summarize accepted candidate Kimi reruns.

This script reads expected Harbor job directories for the accepted
Harness-TrajecDebug candidates and reports whether each task/method pair has
passed, failed, is incomplete, or has not started. It does not launch model
calls, Docker, or Harbor.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_TASKS = ("make-mips-interpreter", "make-doom-for-mips")
DEFAULT_VARIANTS = ("oracle_grounded", "debug_action")


@dataclass
class CandidateRun:
    task: str
    context_variant: str
    inject_mode: str
    model: str
    jobs_dir: str
    job_name: str
    job_dir: str
    status: str
    reward: float | None
    trial_name: str | None
    verifier_tests: str | None
    exception_type: str | None
    note: str


def safe_model_name(model: str) -> str:
    return model.replace("/", "-").replace(".", "-")


def job_name(task: str, variant: str, inject_mode: str, model: str) -> str:
    return f"htd-dynamic-icl-{inject_mode}-{variant}-{task}-{safe_model_name(model)}"


def jobs_dir_for_variant(pack_dir: Path, variant: str) -> Path:
    if variant == "oracle_grounded":
        return pack_dir / "harbor_runs_oracle_grounded"
    if variant == "debug_action":
        return pack_dir / "harbor_runs_joint_failure"
    return pack_dir / "harbor_runs_candidate"


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def reward_from_trial_result(result: dict[str, Any]) -> float | None:
    value = (
        result.get("verifier_result", {})
        .get("rewards", {})
        .get("reward")
    )
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def exception_type(result: dict[str, Any]) -> str | None:
    exc = result.get("exception_info")
    if isinstance(exc, dict):
        value = exc.get("type") or exc.get("class") or exc.get("exception_type")
        return str(value) if value else "exception"
    if exc:
        return str(exc)
    return None


def verifier_summary(trial_dir: Path) -> str | None:
    ctrf = read_json(trial_dir / "verifier" / "ctrf.json")
    if not ctrf:
        reward = trial_dir / "verifier" / "reward.txt"
        return f"reward.txt={reward.read_text().strip()}" if reward.exists() else None
    summary = ctrf.get("results", {}).get("summary")
    if isinstance(summary, dict):
        passed = summary.get("passed")
        failed = summary.get("failed")
        tests = summary.get("tests")
        if tests is not None:
            return f"{passed}/{tests} passed, failed={failed}"
    return None


def summarize_one(pack_dir: Path, task: str, variant: str, inject_mode: str, model: str) -> CandidateRun:
    jobs_dir = jobs_dir_for_variant(pack_dir, variant)
    name = job_name(task, variant, inject_mode, model)
    job_dir = jobs_dir / name

    if not job_dir.exists():
        return CandidateRun(
            task=task,
            context_variant=variant,
            inject_mode=inject_mode,
            model=model,
            jobs_dir=str(jobs_dir),
            job_name=name,
            job_dir=str(job_dir),
            status="not_started",
            reward=None,
            trial_name=None,
            verifier_tests=None,
            exception_type=None,
            note="Expected job directory does not exist.",
        )

    trial_dirs = sorted(
        path for path in job_dir.iterdir()
        if path.is_dir() and path.name.startswith(f"{task}__")
    )
    trial_rows: list[tuple[Path, dict[str, Any], float | None]] = []
    for trial_dir in trial_dirs:
        result = read_json(trial_dir / "result.json")
        if result is None:
            continue
        trial_rows.append((trial_dir, result, reward_from_trial_result(result)))

    if not trial_rows:
        if (job_dir / "result.json").exists():
            note = "Job result exists but no trial result was found."
        else:
            note = "Job directory exists but Harbor did not write a result.json."
        return CandidateRun(
            task=task,
            context_variant=variant,
            inject_mode=inject_mode,
            model=model,
            jobs_dir=str(jobs_dir),
            job_name=name,
            job_dir=str(job_dir),
            status="incomplete",
            reward=None,
            trial_name=trial_dirs[0].name if trial_dirs else None,
            verifier_tests=None,
            exception_type=None,
            note=note,
        )

    best = max(trial_rows, key=lambda row: -1.0 if row[2] is None else row[2])
    best_dir, best_result, best_reward = best
    best_exception = exception_type(best_result)
    if best_reward == 1.0:
        status = "passed"
        note = "Verifier reward is 1.0."
    elif best_exception:
        status = "error"
        note = f"Trial ended with exception: {best_exception}."
    elif best_reward is None:
        status = "incomplete"
        note = "Trial result exists but reward is missing."
    else:
        status = "failed"
        note = f"Best verifier reward is {best_reward}."

    return CandidateRun(
        task=task,
        context_variant=variant,
        inject_mode=inject_mode,
        model=model,
        jobs_dir=str(jobs_dir),
        job_name=name,
        job_dir=str(job_dir),
        status=status,
        reward=best_reward,
        trial_name=best_dir.name,
        verifier_tests=verifier_summary(best_dir),
        exception_type=best_exception,
        note=note,
    )


def markdown(rows: list[CandidateRun]) -> str:
    by_task: dict[str, list[CandidateRun]] = {}
    for row in rows:
        by_task.setdefault(row.task, []).append(row)

    closed = []
    for task, task_rows in sorted(by_task.items()):
        statuses = {row.context_variant: row.status for row in task_rows}
        if all(statuses.get(variant) == "passed" for variant in DEFAULT_VARIANTS):
            closed.append(task)

    lines = [
        "# Candidate Kimi Rerun Status",
        "",
        "This report summarizes the accepted pending candidates for the",
        "two-method Harness-TrajecDebug rerun queue. It is generated from local",
        "Harbor result files and does not launch model calls.",
        "",
        f"- Closed-loop candidates in this queue: `{len(closed)}`",
        f"- Closed tasks: `{', '.join(closed) if closed else 'none'}`",
        "",
        "| Task | Context | Status | Reward | Trial | Verifier | Note |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| `{task}` | `{variant}` | `{status}` | {reward} | {trial} | {tests} | {note} |".format(
                task=row.task,
                variant=row.context_variant,
                status=row.status,
                reward="-" if row.reward is None else f"`{row.reward:g}`",
                trial="-" if row.trial_name is None else f"`{row.trial_name}`",
                tests="-" if row.verifier_tests is None else row.verifier_tests,
                note=row.note,
            )
        )
    lines.extend(
        [
            "",
            "Run or rerun the queue with:",
            "",
            "```bash",
            "scripts/run_candidate_kimi_reruns.sh --dry-run",
            "scripts/run_candidate_kimi_reruns.sh",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-dir", type=Path, default=Path("runs/harbor_icl_baseline"))
    parser.add_argument("--model", default="kimi-k2.6")
    parser.add_argument("--inject-mode", default="prelude")
    parser.add_argument("--task", action="append", dest="tasks")
    parser.add_argument("--context-variant", action="append", dest="variants")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    tasks = args.tasks or list(DEFAULT_TASKS)
    variants = args.variants or list(DEFAULT_VARIANTS)
    rows = [
        summarize_one(args.pack_dir, task, variant, args.inject_mode, args.model)
        for task in tasks
        for variant in variants
    ]

    payload = {
        "pack_dir": str(args.pack_dir),
        "model": args.model,
        "inject_mode": args.inject_mode,
        "rows": [asdict(row) for row in rows],
    }

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = markdown(rows)
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(md, encoding="utf-8")
    else:
        print(md, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
