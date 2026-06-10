#!/usr/bin/env python3
"""Compute fresh no-TD vs with-TD TB2.1 numbers from two state.json files."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_TASK_ROOT = Path("/Users/hugo/Desktop/super-refactor/harbor/datasets/terminal-bench-2.1-proxy/tasks")
DEFAULT_TD_CARD_MANIFEST = Path("runs/harbor_icl_baseline/tb21_full_td_td_full_manifest.json")


@dataclass
class TaskResult:
    task: str
    status: str
    reward: float | None
    result_path: str | None
    job_dir: str | None
    has_agent_result: bool
    exception_type: str | None
    failure_hint: str | None
    trace_artifact_count: int
    trace_export_count: int
    container_count: int


def card_records_by_task(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = manifest.get("records")
    if not isinstance(records, list):
        return {}
    by_task: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        task = record.get("task")
        if isinstance(task, str) and task:
            by_task[task] = record
    return by_task


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


def verifier_failure_hint(result_path: Path, exception: str | None) -> str | None:
    if exception:
        return f"agent exception: {exception}"
    verifier_dir = result_path.parent / "verifier"
    texts: list[str] = []
    for name in ("test-stdout.txt", "test-stderr.txt", "reward.txt"):
        path = verifier_dir / name
        if path.exists():
            try:
                texts.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    joined = "\n".join(texts)
    if "Service Unavailable" in joined and "webdriver" in joined.lower():
        return "verifier infra: webdriver Service Unavailable"
    if "chromedriver" in joined.lower() and "Service Unavailable" in joined:
        return "verifier infra: chromedriver Service Unavailable"
    if "AssertionError" in joined:
        for line in joined.splitlines():
            if "AssertionError" in line:
                return line.strip()[:180]
        return "verifier assertion failure"
    if "FAILED" in joined:
        for line in joined.splitlines():
            if line.startswith("FAILED "):
                return line.strip()[:180]
        return "verifier test failure"
    return None


def classify_failure_text(text: str) -> str | None:
    lowered = text.lower()
    if "503" in text and "service unavailable" in lowered:
        if "apt-get" in lowered or "ports.ubuntu.com" in lowered or "deb.debian.org" in lowered:
            return "infra: package mirror/proxy 503 during apt setup"
        return "infra: Service Unavailable"
    if "AddTestsDirError" in text:
        return "harness setup: AddTestsDirError while adding tests directory"
    if "Docker compose command failed" in text:
        return "harness setup: Docker compose command failed"
    if "return code: 100" in lowered and ("apt-get" in lowered or "apt " in lowered):
        return "infra: apt setup failed with return code 100"
    if "AgentTimeoutError" in text:
        return "agent exception: AgentTimeoutError"
    if "VerifierTimeoutError" in text:
        return "verifier exception: VerifierTimeoutError"
    return None


def state_failure_hint(row: dict[str, Any], job_dir_value: str | None) -> str | None:
    summary = row.get("result_summary")
    if isinstance(summary, dict):
        trial_results = summary.get("trial_results")
        if isinstance(trial_results, list):
            for trial in trial_results:
                if not isinstance(trial, dict):
                    continue
                parts = [
                    trial.get("exception_type"),
                    trial.get("exception_message"),
                    trial.get("agent_error"),
                    trial.get("verifier_error"),
                ]
                text = "\n".join(str(part) for part in parts if part)
                hint = classify_failure_text(text)
                if hint:
                    return hint
        hint = classify_failure_text(json.dumps(summary, ensure_ascii=False))
        if hint:
            return hint
    if isinstance(job_dir_value, str):
        job_log = Path(job_dir_value) / "job.log"
        if job_log.exists():
            try:
                hint = classify_failure_text(job_log.read_text(encoding="utf-8", errors="replace")[-12000:])
            except OSError:
                hint = None
            if hint:
                return hint
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
        return TaskResult(task, "missing", None, None, None, False, None, "missing from state.json", 0, 0, 0)
    job_dir_value = row.get("job_dir")
    if not isinstance(job_dir_value, str):
        return TaskResult(
            task,
            str(row.get("status") or "missing_job_dir"),
            None,
            None,
            None,
            False,
            None,
            "missing job_dir in state.json",
            0,
            0,
            0,
        )
    row_summary = row.get("result_summary") if isinstance(row.get("result_summary"), dict) else {}
    trace_artifact_count = int(row_summary.get("trace_artifact_count") or 0)
    trace_exports = row.get("trace_exports") if isinstance(row.get("trace_exports"), list) else []
    container_artifacts = row.get("container_artifacts") if isinstance(row.get("container_artifacts"), dict) else {}
    container_count = int(container_artifacts.get("container_count") or 0)
    result_path = trial_result_for_task(Path(job_dir_value), task)
    if result_path is None:
        return TaskResult(
            task,
            "missing_result",
            None,
            None,
            job_dir_value,
            False,
            None,
            state_failure_hint(row, job_dir_value) or "missing result.json",
            trace_artifact_count,
            len(trace_exports),
            container_count,
        )
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
    hint = None
    if r != 1.0:
        hint = verifier_failure_hint(result_path, exc) or state_failure_hint(row, job_dir_value)
    return TaskResult(
        task,
        status,
        r,
        str(result_path),
        job_dir_value,
        agent,
        exc,
        hint,
        trace_artifact_count,
        len(trace_exports),
        container_count,
    )


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


def coverage_summary(records: dict[str, TaskResult]) -> dict[str, Any]:
    return {
        "tasks_with_result": sum(1 for record in records.values() if record.result_path),
        "tasks_with_trace_artifacts": sum(1 for record in records.values() if record.trace_artifact_count > 0),
        "tasks_with_trace_exports": sum(1 for record in records.values() if record.trace_export_count > 0),
        "tasks_with_container_artifacts": sum(1 for record in records.values() if record.container_count > 0),
        "total_trace_artifacts": sum(record.trace_artifact_count for record in records.values()),
        "total_trace_exports": sum(record.trace_export_count for record in records.values()),
        "total_container_artifacts": sum(record.container_count for record in records.values()),
    }


def summarize_by_card_source(
    records: dict[str, TaskResult],
    card_index: dict[str, dict[str, Any]],
) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for task, record in records.items():
        card = card_index.get(task, {})
        source = str(card.get("source") or "unknown")
        bucket = summary.setdefault(
            source,
            {"pass": 0, "fail": 0, "unknown_or_incomplete": 0, "total": 0},
        )
        bucket["total"] += 1
        if record.reward == 1.0:
            bucket["pass"] += 1
        elif record.status in {"fail", "fail_no_agent_result"}:
            bucket["fail"] += 1
        else:
            bucket["unknown_or_incomplete"] += 1
    return summary


def with_td_nonpass_interpretation(source: str) -> str:
    if source == "reference_only_fallback":
        return (
            "reference-only card; no mined critical step or corrective hint was "
            "available, so this is not evidence against the full TD algorithm"
        )
    if source == "debug_action":
        return (
            "diagnosed Debug-Action card existed, but this batch injects it as a "
            "prelude only; inspect whether the agent followed it and rerun with "
            "sdk_live/hooks_live if timing is the suspected issue"
        )
    return (
        "card source is not a corrective Debug-Action; treat the failure as "
        "needing trace diagnosis before making a TD claim"
    )


def with_td_attribution_note(row: dict[str, Any]) -> str:
    source = str(row["td_card_source"])
    hint = row.get("with_failure_hint")
    base = with_td_nonpass_interpretation(source)
    if hint:
        return f"{base}; observed footprint: {hint}"
    return base


def markdown(report: dict[str, Any]) -> str:
    base = report["without_td"]
    td = report["with_td"]
    card_manifest = report.get("td_card_manifest") or {}
    counts_by_source = card_manifest.get("counts_by_source") if isinstance(card_manifest, dict) else {}
    inject_mode = report.get("with_td_inject_mode")
    uses_sdk_live = report.get("with_td_uses_sdk_live")
    online_miner = report.get("with_td_online_critical_step_miner")
    lines = [
        "# Fresh TB2.1 Claude Code + Kimi-k2.6 TD Rerun",
        "",
        "This report compares two fresh 89-task runs. It does not use old",
        "supplemental fills or scattered prior TD successes.",
        "",
        "## Methodology Note",
        "",
        "The with-TD condition in this report is **TD-card injection**, not the",
        "strongest live corrective TD loop. During the run, `DynamicIclClaudeCode`",
        "injects precomputed task cards into Claude Code + Kimi-k2.6; it does not",
        "call a separate external LLM judge to decide the critical step, and it",
        "does not mine a failed teacher trajectory online.",
        "",
        "For V1, failed-run `debug_action` cards are human/Codex-in-the-loop",
        "diagnoses produced from trace evidence, verifier footprints, and case",
        "study analysis. The remaining tasks use reference-only fallback cards so",
        "the with-TD denominator stays at 89/89 without pretending every task has",
        "a mined critical step.",
        "",
        "This matters for attribution: a with-TD failure on a",
        "`reference_only_fallback` card only says the broad task checklist was not",
        "enough. It is **not** evidence that critical-step diagnosis plus a",
        "corrective hint failed, because that stronger path was never exercised",
        "for that task.",
        "",
        "The stronger TD path should be reported separately when used:",
        "`teacher trace -> critical-step diagnosis -> Debug-Action hint ->",
        "sdk_live/hooks_live insertion at a matching runtime boundary -> verifier`.",
        "",
        "Both conditions inherit the task-level agent/verifier timeouts from",
        "`task.toml` unless a run explicitly documents an override. This keeps the",
        "comparison about TD-card injection rather than about a different time",
        "budget.",
        "",
        "Algorithm coverage for this 89-task run:",
        "",
        "| Component | Value | Interpretation |",
        "| --- | --- | --- |",
        f"| Inject mode | `{inject_mode}` | context is available before the run; no timed mid-run correction unless this is `sdk_live` or `hooks_live` |",
        f"| sdk_live / hooks_live | `{bool(uses_sdk_live)}` | whether the run inserts hints at tool-use boundaries |",
        f"| online critical-step miner | `{bool(online_miner)}` | whether a separate LLM/judge mined new critical steps during the run |",
        "",
        "TD card provenance:",
        "",
        "| Source | Count | Meaning |",
        "| --- | ---: | --- |",
    ]
    if counts_by_source:
        meanings = {
            "debug_action": "diagnosed TD card from prior human/Codex-in-the-loop trace analysis",
            "debug_trajectory": "scripted process card from a passing teacher run",
            "oracle_grounded": "oracle-assisted offline audit card; not an online mined label",
            "reference_only_fallback": "reference-only TD checklist, no mined critical step",
            "prompt_filtered": "generic filtered snippets, no TD critical-step label",
            "outcome_only": "outcome summary only",
        }
        for source, count in sorted(counts_by_source.items()):
            lines.append(f"| `{source}` | `{count}` | {meanings.get(source, '')} |")
    else:
        lines.append("| - | - | TD card manifest not found when report was generated |")
    lines.extend([
        "",
        "With-TD outcomes by card provenance:",
        "",
        "| Source | Pass | Fail | Unknown / incomplete | Total |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    by_source = report.get("with_td_by_card_source") or {}
    if isinstance(by_source, dict) and by_source:
        for source, counts in sorted(by_source.items()):
            if not isinstance(counts, dict):
                continue
            lines.append(
                f"| `{source}` | `{counts.get('pass', 0)}` | `{counts.get('fail', 0)}` | "
                f"`{counts.get('unknown_or_incomplete', 0)}` | `{counts.get('total', 0)}` |"
            )
    else:
        lines.append("| - | - | - | - | - |")
    lines.extend([
        "",
        "## Final Number",
        "",
        f"- without TrajectoryDebug: `{base['pass_count']}/{report['denominator']}`",
        f"- with TD-card injection: `{td['pass_count']}/{report['denominator']}`",
        f"- delta `m`: `{report['delta']}` tasks",
        "",
        "## Coverage",
        "",
        f"- without-TD valid tasks: `{base['valid_count']}/{report['denominator']}`",
        f"- with-TD valid tasks: `{td['valid_count']}/{report['denominator']}`",
        "",
        "Raw log / artifact coverage from `state.json`:",
        "",
        "| Condition | Results | Trace artifacts | Trace exports | Container artifact sets |",
        "| --- | ---: | ---: | ---: | ---: |",
        (
            f"| without-TD | `{report['without_td_coverage']['tasks_with_result']}/{report['denominator']}` | "
            f"`{report['without_td_coverage']['tasks_with_trace_artifacts']}/{report['denominator']}` | "
            f"`{report['without_td_coverage']['tasks_with_trace_exports']}/{report['denominator']}` | "
            f"`{report['without_td_coverage']['tasks_with_container_artifacts']}/{report['denominator']}` |"
        ),
        (
            f"| with-TD | `{report['with_td_coverage']['tasks_with_result']}/{report['denominator']}` | "
            f"`{report['with_td_coverage']['tasks_with_trace_artifacts']}/{report['denominator']}` | "
            f"`{report['with_td_coverage']['tasks_with_trace_exports']}/{report['denominator']}` | "
            f"`{report['with_td_coverage']['tasks_with_container_artifacts']}/{report['denominator']}` |"
        ),
        "",
        "## Lift / Regression Table",
        "",
        "| Task | TD card source | without-TD | with-TD | Delta | without result | with result |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ])
    for row in report["task_rows"]:
        if row["delta"] == 0:
            continue
        lines.append(
            f"| `{row['task']}` | `{row['td_card_source']}` | `{row['without_reward']}` | "
            f"`{row['with_reward']}` | `{row['delta']}` | `{row['without_result']}` | `{row['with_result']}` |"
        )
    if not any(row["delta"] != 0 for row in report["task_rows"]):
        lines.append("| - | - | - | - | - | - | - |")
    lines.extend([
        "",
        "## With-TD Non-Pass Attribution",
        "",
        "| Task | TD card source | with-TD status | with-TD reward | Attribution note |",
        "| --- | --- | --- | ---: | --- |",
    ])
    nonpass_rows = [row for row in report["task_rows"] if row["with_reward"] != 1.0]
    for row in nonpass_rows:
        source = row["td_card_source"]
        lines.append(
            f"| `{row['task']}` | `{source}` | `{row['with_status']}` | `{row['with_reward']}` | "
            f"{with_td_attribution_note(row)} |"
        )
    if not nonpass_rows:
        lines.append("| - | - | - | - | - |")
    return "\n".join(lines)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    tasks = sorted(path.name for path in args.task_root.iterdir() if path.is_dir())
    baseline_state = read_json(args.without_td_state) or {}
    td_state = read_json(args.with_td_state) or {}
    card_manifest = read_json(args.td_card_manifest) or {}
    card_index = card_records_by_task(card_manifest)
    baseline = {task: result_from_state(baseline_state, task) for task in tasks}
    td = {task: result_from_state(td_state, task) for task in tasks}
    rows = []
    for task in tasks:
        before = baseline[task]
        after = td[task]
        card = card_index.get(task, {})
        card_source = str(card.get("source") or "unknown")
        before_pass = before.reward == 1.0
        after_pass = after.reward == 1.0
        rows.append(
            {
                "task": task,
                "td_card_source": card_source,
                "td_card_path": card.get("card_path"),
                "td_card_source_path": card.get("source_path"),
                "without_reward": before.reward,
                "with_reward": after.reward,
                "delta": int(after_pass) - int(before_pass),
                "without_status": before.status,
                "with_status": after.status,
                "without_failure_hint": before.failure_hint,
                "with_failure_hint": after.failure_hint,
                "without_trace_artifact_count": before.trace_artifact_count,
                "with_trace_artifact_count": after.trace_artifact_count,
                "without_trace_export_count": before.trace_export_count,
                "with_trace_export_count": after.trace_export_count,
                "without_container_count": before.container_count,
                "with_container_count": after.container_count,
                "without_result": before.result_path,
                "with_result": after.result_path,
            }
        )
    report = {
        "task_root": str(args.task_root),
        "without_td_state": str(args.without_td_state),
        "with_td_state": str(args.with_td_state),
        "td_card_manifest_path": str(args.td_card_manifest),
        "td_card_manifest": card_manifest,
        "with_td_inject_mode": args.with_td_inject_mode,
        "with_td_uses_sdk_live": bool(args.with_td_uses_sdk_live),
        "with_td_online_critical_step_miner": bool(args.with_td_online_critical_step_miner),
        "denominator": len(tasks),
        "without_td": summarize(baseline),
        "with_td": summarize(td),
        "without_td_coverage": coverage_summary(baseline),
        "with_td_coverage": coverage_summary(td),
        "with_td_by_card_source": summarize_by_card_source(td, card_index),
        "delta": sum(row["delta"] for row in rows),
        "task_rows": rows,
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    parser.add_argument("--without-td-state", type=Path, required=True)
    parser.add_argument("--with-td-state", type=Path, required=True)
    parser.add_argument("--td-card-manifest", type=Path, default=DEFAULT_TD_CARD_MANIFEST)
    parser.add_argument("--with-td-inject-mode", default="prelude")
    parser.add_argument("--with-td-uses-sdk-live", action="store_true")
    parser.add_argument("--with-td-online-critical-step-miner", action="store_true")
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
