"""Build matrices for tasks where both compared agent runs failed."""

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
DEFAULT_OUTPUT_JSON = Path("runs/harbor_icl_baseline/joint_failure_matrix.json")
DEFAULT_OUTPUT_MD = Path("runs/harbor_icl_baseline/joint_failure_matrix.md")


@dataclass
class JointFailureCandidate:
    task: str
    student_reward: float | None
    student_status: str
    student_exception: str | None
    student_trial_dir: str | None
    student_failed_tests: list[str]
    teacher_reward: float | None
    teacher_status: str
    teacher_task_dir: str | None
    teacher_failed_tests: list[str]
    failure_kind: str
    htd_suitability: str
    note: str


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def coerce_reward(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_tasks(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = load_json(path)
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
        trial_reward = coerce_reward(first_trial(record).get("reward"))
        if trial_reward is not None:
            return trial_reward
    return coerce_reward(record.get("reward"))


def student_status(record: dict[str, Any]) -> tuple[str, str | None]:
    if not record:
        return "missing", None
    reward = student_reward(record)
    if reward == 1.0:
        return "passed", None
    trial = first_trial(record)
    exception = trial.get("exception_type") or trial.get("exception_message")
    if exception:
        return "failed_with_exception", str(exception)
    if record.get("result_summary"):
        return "failed_reward", None
    return str(record.get("status") or "unknown"), None


def teacher_reward(record: dict[str, Any]) -> float | None:
    return coerce_reward(record.get("reward"))


def teacher_status(record: dict[str, Any]) -> str:
    if not record:
        return "missing"
    if teacher_reward(record) == 1.0:
        return "passed"
    return str(record.get("status") or record.get("codex_returncode") or "unknown")


def failed_tests_from_ctrf(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        ctrf = load_json(path)
    except (OSError, json.JSONDecodeError):
        return []
    tests = []
    results = ctrf.get("results") if isinstance(ctrf, dict) else None
    raw_tests = results.get("tests") if isinstance(results, dict) else ctrf.get("tests")
    if not isinstance(raw_tests, list):
        return []
    for test in raw_tests:
        if not isinstance(test, dict):
            continue
        status = str(test.get("status") or "").lower()
        if status in {"failed", "fail", "false"}:
            name = test.get("name") or test.get("test") or "<unknown>"
            tests.append(str(name))
    return tests


def teacher_failed_tests(record: dict[str, Any]) -> list[str]:
    task_dir = record.get("task_run_dir") or record.get("task_dir")
    if not isinstance(task_dir, str):
        return []
    return failed_tests_from_ctrf(Path(task_dir) / "verifier" / "ctrf.json")


def student_failed_tests(record: dict[str, Any]) -> list[str]:
    trial = first_trial(record)
    trial_dir = trial.get("trial_dir")
    if not isinstance(trial_dir, str):
        return []
    ctrf = Path(trial_dir) / "verifier" / "ctrf.json"
    if ctrf.exists():
        return failed_tests_from_ctrf(ctrf)
    return failed_tests_from_ctrf(Path(trial_dir) / "verifier" / "test-ctrf.json")


def classify_candidate(
    student_status_value: str,
    student_exception: str | None,
    student_tests: list[str],
    teacher_tests: list[str],
) -> tuple[str, str, str]:
    exception = (student_exception or "").lower()
    if "environmentstarttimeouterror" in exception:
        return (
            "infra_start_timeout",
            "low",
            "student run did not reach a stable task/verifier state",
        )
    if "runtimeerror" in exception and not student_tests:
        return (
            "agent_or_harness_exception",
            "medium",
            "student failed before verifier footprint was captured",
        )
    if student_status_value == "missing":
        return ("missing_student_record", "low", "student state is missing")
    if student_tests and teacher_tests:
        overlap = sorted(set(student_tests) & set(teacher_tests))
        if overlap:
            return (
                "shared_verifier_failure",
                "high",
                "both failed at least one identical verifier test",
            )
        return (
            "complementary_verifier_failure",
            "high",
            "both reached verifier with different failure footprints",
        )
    if student_tests or teacher_tests:
        return (
            "partial_verifier_failure",
            "medium",
            "only one side has detailed verifier test names",
        )
    return ("reward_zero_no_test_detail", "medium", "both failed but test details are sparse")


def build_joint_matrix(
    student_state: Path = DEFAULT_STUDENT_STATE,
    teacher_state: Path = DEFAULT_TEACHER_STATE,
    include_infra: bool = False,
) -> list[JointFailureCandidate]:
    students = load_tasks(student_state)
    teachers = load_tasks(teacher_state)
    candidates: list[JointFailureCandidate] = []

    for task in sorted(set(students) & set(teachers)):
        student = students.get(task) or {}
        teacher = teachers.get(task) or {}
        if not isinstance(student, dict) or not isinstance(teacher, dict):
            continue
        s_reward = student_reward(student)
        t_reward = teacher_reward(teacher)
        if s_reward == 1.0 or t_reward == 1.0:
            continue

        s_status, s_exception = student_status(student)
        s_tests = student_failed_tests(student)
        t_tests = teacher_failed_tests(teacher)
        failure_kind, suitability, note = classify_candidate(
            s_status, s_exception, s_tests, t_tests
        )
        if not include_infra and suitability == "low":
            continue
        trial = first_trial(student)
        trial_dir = trial.get("trial_dir")
        candidates.append(
            JointFailureCandidate(
                task=task,
                student_reward=s_reward,
                student_status=s_status,
                student_exception=s_exception,
                student_trial_dir=trial_dir if isinstance(trial_dir, str) else None,
                student_failed_tests=s_tests,
                teacher_reward=t_reward,
                teacher_status=teacher_status(teacher),
                teacher_task_dir=teacher.get("task_run_dir")
                if isinstance(teacher.get("task_run_dir"), str)
                else None,
                teacher_failed_tests=t_tests,
                failure_kind=failure_kind,
                htd_suitability=suitability,
                note=note,
            )
        )

    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(
        candidates,
        key=lambda item: (
            order.get(item.htd_suitability, 9),
            item.failure_kind,
            item.task,
        ),
    )


def write_markdown(candidates: list[JointFailureCandidate], path: Path) -> None:
    lines = [
        "# Joint-Failure Candidate Matrix",
        "",
        "Tasks where both compared runs failed. These are candidates for the",
        "failure-lifting experiment: use Harness-TrajecDebug to locate the",
        "critical step, synthesize a repair hint, then inject it into a later",
        "Claude Code + Kimi run.",
        "",
        "| Task | Kind | Suitability | Student failed tests | Teacher failed tests | Note |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for candidate in candidates:
        student_tests = "<br>".join(candidate.student_failed_tests) or "-"
        teacher_tests = "<br>".join(candidate.teacher_failed_tests) or "-"
        lines.append(
            "| {task} | {kind} | {suitability} | {student_tests} | {teacher_tests} | {note} |".format(
                task=candidate.task,
                kind=candidate.failure_kind,
                suitability=candidate.htd_suitability,
                student_tests=student_tests,
                teacher_tests=teacher_tests,
                note=candidate.note,
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--student-state", type=Path, default=DEFAULT_STUDENT_STATE)
    parser.add_argument("--teacher-state", type=Path, default=DEFAULT_TEACHER_STATE)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--include-infra", action="store_true")
    args = parser.parse_args(argv)

    candidates = build_joint_matrix(
        student_state=args.student_state,
        teacher_state=args.teacher_state,
        include_infra=args.include_infra,
    )
    payload = {
        "student_state": str(args.student_state),
        "teacher_state": str(args.teacher_state),
        "candidate_count": len(candidates),
        "candidates": [asdict(candidate) for candidate in candidates],
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_markdown(candidates, args.output_md)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

