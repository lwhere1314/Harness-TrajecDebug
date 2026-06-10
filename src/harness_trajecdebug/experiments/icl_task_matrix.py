"""Build task matrices for Harbor ICL repair baselines."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_STUDENT_STATE = Path(
    "/Volumes/SSD/terminal-bench-harbor/harbor/runs/"
    "tb21-kimi-k26-local-019e737a-colima16g-proxy/state.json"
)
DEFAULT_TEACHER_STATE = Path(
    "/Volumes/SSD/terminal-bench-harbor/harbor/runs/"
    "tb21-k26-true-fails-codex-gpt55-host-20260603-clean4/state.json"
)
DEFAULT_OUTPUT_JSON = Path("runs/harbor_icl_baseline/task_matrix.json")
DEFAULT_OUTPUT_MD = Path("runs/harbor_icl_baseline/task_matrix.md")

SMOKE_TASKS = {
    "cancel-async-tasks": "already passed same-task debug_trajectory smoke",
    "count-dataset-tokens": "historical prelude/continue_after smoke noted; pass trial artifacts are missing from current pack",
}

PRIORITY = [
    "count-dataset-tokens",
    "query-optimize",
    "break-filter-js-from-html",
    "headless-terminal",
    "kv-store-grpc",
    "train-fasttext",
    "chess-best-move",
    "torch-tensor-parallelism",
    "video-processing",
]


@dataclass
class TaskCandidate:
    task: str
    student_reward: float | None
    student_status: str
    student_exception: str | None
    student_job_dir: str | None
    student_trial_dir: str | None
    teacher_reward: float | None
    teacher_status: str
    teacher_task_dir: str | None
    teacher_task_run_dir: str | None
    teacher_artifacts: list[str]
    smoke_note: str | None
    priority_rank: int


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def coerce_reward(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def reward_from_trial_file(trial: dict[str, Any]) -> float | None:
    trial_dir = trial.get("trial_dir")
    if isinstance(trial_dir, str):
        result_path = Path(trial_dir) / "result.json"
        if result_path.exists():
            try:
                result = load_json(result_path)
            except (OSError, json.JSONDecodeError):
                result = {}
            if isinstance(result, dict):
                verifier = result.get("verifier_result")
                if isinstance(verifier, dict):
                    rewards = verifier.get("rewards")
                    if isinstance(rewards, dict):
                        reward = coerce_reward(rewards.get("reward"))
                        if reward is not None:
                            return reward
        reward_path = Path(trial_dir) / "verifier" / "reward.txt"
        if reward_path.exists():
            try:
                reward = coerce_reward(reward_path.read_text(encoding="utf-8").strip())
            except OSError:
                reward = None
            if reward is not None:
                return reward

    reward_file = trial.get("reward_file")
    if isinstance(reward_file, str):
        path = Path(reward_file)
        if path.exists():
            try:
                return coerce_reward(path.read_text(encoding="utf-8").strip())
            except OSError:
                return None
    return None


def load_tasks(state_path: Path) -> dict[str, dict[str, Any]]:
    if not state_path.exists():
        return {}
    data = load_json(state_path)
    tasks = data.get("tasks") if isinstance(data, dict) else None
    return tasks if isinstance(tasks, dict) else {}


def first_trial(record: dict[str, Any]) -> dict[str, Any]:
    summary = record.get("result_summary")
    if not isinstance(summary, dict):
        return {}
    trials = summary.get("trial_results")
    if isinstance(trials, list) and trials and isinstance(trials[0], dict):
        return trials[0]
    return {}


def student_reward(record: dict[str, Any]) -> float | None:
    summary = record.get("result_summary")
    if isinstance(summary, dict):
        reward = coerce_reward(summary.get("reward"))
        if reward is not None:
            return reward
        trial = first_trial(record)
        reward = coerce_reward(trial.get("reward"))
        if reward is not None:
            return reward
        reward = reward_from_trial_file(trial)
        if reward is not None:
            return reward
    return coerce_reward(record.get("reward"))


def student_status(record: dict[str, Any]) -> tuple[str, str | None]:
    if not record:
        return "missing_student_record", None
    trial = first_trial(record)
    exception = trial.get("exception_type") or trial.get("exception_message")
    reward = student_reward(record)
    if reward == 1.0:
        return "passed", str(exception) if exception else None
    if exception:
        return "failed_with_exception", str(exception)
    summary = record.get("result_summary")
    if isinstance(summary, dict) and summary:
        return "failed_reward", None
    return "true_fail_source_missing_reward", None


def copied_app_root(record: dict[str, Any]) -> Path | None:
    artifacts = record.get("container_artifacts")
    if not isinstance(artifacts, dict):
        return None
    copied = artifacts.get("copied")
    if not isinstance(copied, list):
        return None
    for entry in copied:
        if not isinstance(entry, dict) or entry.get("source") != "/app":
            continue
        destination = entry.get("destination")
        if isinstance(destination, str):
            path = Path(destination)
            if path.exists():
                return path
    return None


def teacher_artifacts(record: dict[str, Any], limit: int = 8) -> list[str]:
    app_root = copied_app_root(record)
    if app_root is None:
        return []
    candidates: list[Path] = []
    for path in app_root.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pid", ".log"}:
            continue
        try:
            if path.stat().st_size > 256_000:
                continue
        except OSError:
            continue
        rel = "/app/" + str(path.relative_to(app_root))
        if path.name.startswith("."):
            continue
        candidates.append(Path(rel))
    return [str(path) for path in sorted(candidates, key=artifact_sort_key)[:limit]]


def artifact_sort_key(path: Path) -> tuple[int, str]:
    name = path.name
    suffix = path.suffix
    if name in {"answer.txt", "sol.sql", "run.py", "output.toml", "move.txt"}:
        return (0, str(path))
    if suffix in {".py", ".sql", ".txt", ".toml", ".json", ".sh", ".c", ".rs"}:
        return (1, str(path))
    return (2, str(path))


def priority_rank(task: str) -> int:
    if task in PRIORITY:
        return PRIORITY.index(task)
    return len(PRIORITY) + 1


def build_matrix(
    student_state: Path = DEFAULT_STUDENT_STATE,
    teacher_state: Path = DEFAULT_TEACHER_STATE,
    include_passed_student: bool = False,
) -> list[TaskCandidate]:
    student_tasks = load_tasks(student_state)
    teacher_tasks = load_tasks(teacher_state)
    candidates: list[TaskCandidate] = []

    for task, teacher in sorted(teacher_tasks.items()):
        if not isinstance(teacher, dict):
            continue
        teacher_reward = coerce_reward(teacher.get("reward"))
        if teacher_reward != 1.0:
            continue

        student = student_tasks.get(task) or {}
        if not isinstance(student, dict):
            student = {}
        reward = student_reward(student)
        if reward == 1.0 and not include_passed_student:
            continue

        status, exception = student_status(student)
        trial = first_trial(student)
        candidates.append(
            TaskCandidate(
                task=task,
                student_reward=reward,
                student_status=status,
                student_exception=exception,
                student_job_dir=student.get("job_dir") if isinstance(student.get("job_dir"), str) else None,
                student_trial_dir=trial.get("trial_dir") if isinstance(trial.get("trial_dir"), str) else None,
                teacher_reward=teacher_reward,
                teacher_status=str(teacher.get("status") or "unknown"),
                teacher_task_dir=teacher.get("task_dir") if isinstance(teacher.get("task_dir"), str) else None,
                teacher_task_run_dir=teacher.get("task_run_dir") if isinstance(teacher.get("task_run_dir"), str) else None,
                teacher_artifacts=teacher_artifacts(teacher),
                smoke_note=SMOKE_TASKS.get(task),
                priority_rank=priority_rank(task),
            )
        )

    return sorted(candidates, key=lambda item: (item.priority_rank, item.task))


def markdown_table(candidates: list[TaskCandidate]) -> str:
    lines = [
        "# Harbor ICL Candidate Matrix",
        "",
        "Kimi-k2.6 failed or unresolved tasks where Codex+GPT-5.5 teacher reward is 1.0.",
        "",
        "| Task | Student reward/status | Teacher reward | Artifacts | Note |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for item in candidates:
        student = (
            f"{item.student_reward if item.student_reward is not None else 'missing'}"
            f" / {item.student_status}"
        )
        if item.student_exception:
            student += f" ({item.student_exception})"
        artifacts = ", ".join(item.teacher_artifacts[:3]) if item.teacher_artifacts else "none captured"
        note = item.smoke_note or ("priority" if item.priority_rank < len(PRIORITY) else "")
        lines.append(
            f"| `{item.task}` | {student} | {item.teacher_reward} | {artifacts} | {note} |"
        )
    lines.extend(
        [
            "",
            "## Suggested next canaries",
            "",
            "Start with tasks marked `priority` that have captured `/app` artifacts and no prior smoke pass.",
            "Use `scripts/run_daily_icl_canary.sh --task <task> --inject-mode continue_after --context-variant debug_action --run` after endpoint preflight is healthy.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Harbor ICL task candidate matrix.")
    parser.add_argument("--student-state", type=Path, default=DEFAULT_STUDENT_STATE)
    parser.add_argument("--teacher-state", type=Path, default=DEFAULT_TEACHER_STATE)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--include-passed-student", action="store_true")
    parser.add_argument("--print-top", type=int, default=12)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    candidates = build_matrix(
        student_state=args.student_state,
        teacher_state=args.teacher_state,
        include_passed_student=args.include_passed_student,
    )
    payload = {
        "student_state": str(args.student_state),
        "teacher_state": str(args.teacher_state),
        "candidate_count": len(candidates),
        "candidates": [asdict(candidate) for candidate in candidates],
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown_table(candidates), encoding="utf-8")

    print(json.dumps(payload | {"candidates": payload["candidates"][: args.print_top]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
