"""Readiness report for Harbor ICL baseline runs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


MECHANISM_OK_STATUSES = {"closure_passed", "preflight_blocked", "not_run"}
REWARD_STATUSES = {"passed", "failed_verifier", "injected_but_failed_verifier"}
MODEL_REWARD_SOURCES = {"harbor_static", "harbor_runtime", "matrix_canary"}
ENDPOINT_BLOCKERS = {"preflight_blocked", "model_rate_limited", "missing_credentials"}
VERIFIER_BLOCKERS = {
    "verifier_dependency_failure",
    "verifier_proxy_leak",
    "verifier_timeout_after_materialization",
    "verifier_incomplete_after_materialization",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def load_summary(pack_dir: Path) -> dict[str, Any]:
    path = pack_dir / "baseline_results.json"
    if not path.exists():
        raise FileNotFoundError(f"missing aggregate summary: {path}")
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"aggregate summary is not an object: {path}")
    return data


def rows_by_source(rows: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("source") == source]


def status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get("status")) for row in rows).items()))


def task_status_map(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_task: dict[str, list[str]] = {}
    for row in rows:
        task = str(row.get("task") or "")
        status = str(row.get("status") or "")
        if not task:
            continue
        by_task.setdefault(task, []).append(status)
    return {task: statuses for task, statuses in sorted(by_task.items())}


def build_readiness(summary: dict[str, Any]) -> dict[str, Any]:
    all_rows = [row for row in summary.get("rows", []) if isinstance(row, dict)]
    rows = [row for row in all_rows if not row.get("archived")]
    artifact_rows = rows_by_source(rows, "artifact_closure")
    matrix_rows = rows_by_source(rows, "matrix_canary")
    runtime_rows = rows_by_source(rows, "harbor_runtime")
    harbor_artifact_rows = rows_by_source(rows, "harbor_artifact_closure")
    runtime_smoke_rows = rows_by_source(rows, "harbor_runtime_smoke")
    model_outcome_rows = [
        row
        for row in rows
        if row.get("source") in MODEL_REWARD_SOURCES
        and row.get("status") in REWARD_STATUSES
    ]
    artifact_verifier_pass_rows = [
        row
        for row in harbor_artifact_rows + runtime_smoke_rows
        if row.get("status") == "passed" and row.get("reward") == 1.0
    ]
    runtime_smoke_pass_rows = [
        row for row in runtime_smoke_rows if row.get("status") == "passed"
    ]
    runtime_smoke_triggers = sorted(
        {
            str((row.get("runtime_smoke") or {}).get("trigger") or row.get("inject_mode"))
            for row in runtime_smoke_pass_rows
            if (row.get("runtime_smoke") or {}).get("trigger") or row.get("inject_mode")
        }
    )

    replay_rows = [
        row
        for row in matrix_rows
        if row.get("replay_all_injected") is True
        or (row.get("status") in MECHANISM_OK_STATUSES and row.get("condition"))
    ]
    artifact_ok_rows = [row for row in artifact_rows if row.get("status") == "closure_passed"]

    endpoint_blocker_rows = [
        row for row in rows if row.get("status") in ENDPOINT_BLOCKERS
    ]
    verifier_blocker_rows = [
        row for row in rows if row.get("status") in VERIFIER_BLOCKERS
    ]

    mechanism_ready = bool(artifact_ok_rows) and bool(replay_rows)
    model_run_ready = not endpoint_blocker_rows and bool(runtime_rows or matrix_rows)
    reward_benchmark_ready = bool(model_outcome_rows) and not verifier_blocker_rows and model_run_ready

    return {
        "pack_dir": summary.get("pack_dir"),
        "row_count": len(rows),
        "archived_row_count": len(all_rows) - len(rows),
        "mechanism_canary": {
            "ready": mechanism_ready,
            "artifact_closure_passed": len(artifact_ok_rows),
            "artifact_verifier_passed": len(artifact_verifier_pass_rows),
            "runtime_smoke_passed": len(runtime_smoke_pass_rows),
            "runtime_smoke_triggers": runtime_smoke_triggers,
            "matrix_replay_rows": len(replay_rows),
            "status_counts": status_counts(artifact_rows + matrix_rows),
            "runtime_smoke_status_counts": status_counts(runtime_smoke_rows),
        },
        "model_run": {
            "ready": model_run_ready,
            "endpoint_blocker_count": len(endpoint_blocker_rows),
            "runtime_status_counts": status_counts(runtime_rows + matrix_rows),
            "endpoint_blockers": [
                {
                    "task": row.get("task"),
                    "source": row.get("source"),
                    "condition": row.get("condition"),
                    "endpoint_profile": row.get("endpoint_profile"),
                    "status": row.get("status"),
                }
                for row in endpoint_blocker_rows
            ],
        },
        "reward_benchmark": {
            "ready": reward_benchmark_ready,
            "model_rewarded_rows": len(model_outcome_rows),
            "verifier_blocker_count": len(verifier_blocker_rows),
            "verifier_status_counts": status_counts(harbor_artifact_rows),
            "runtime_smoke_status_counts": status_counts(runtime_smoke_rows),
            "verifier_blockers_by_task": task_status_map(verifier_blocker_rows),
        },
        "decision": (
            "daily_mechanism_canary_only"
            if mechanism_ready and not reward_benchmark_ready
            else "daily_reward_benchmark_ready"
            if reward_benchmark_ready
            else "not_daily_ready"
        ),
    }


def markdown(report: dict[str, Any]) -> str:
    mechanism = report["mechanism_canary"]
    model_run = report["model_run"]
    reward = report["reward_benchmark"]
    lines = [
        "# ICL Daily Readiness",
        "",
        f"Pack: `{report.get('pack_dir')}`",
        f"Decision: `{report.get('decision')}`",
        "",
        "| Gate | Ready | Evidence |",
        "| --- | --- | --- |",
        (
            "| Mechanism canary | `{ready}` | artifact_closure_passed={artifact}; "
            "artifact_verifier_passed={artifact_verifier}; "
            "runtime_smoke_passed={runtime_smoke}; triggers=`{triggers}`; "
            "matrix_replay_rows={replay} |"
        ).format(
            ready=mechanism["ready"],
            artifact=mechanism["artifact_closure_passed"],
            artifact_verifier=mechanism["artifact_verifier_passed"],
            runtime_smoke=mechanism["runtime_smoke_passed"],
            triggers=mechanism["runtime_smoke_triggers"],
            replay=mechanism["matrix_replay_rows"],
        ),
        (
            "| Model run | `{ready}` | endpoint_blocker_count={count}; "
            "runtime_status_counts=`{counts}` |"
        ).format(
            ready=model_run["ready"],
            count=model_run["endpoint_blocker_count"],
            counts=model_run["runtime_status_counts"],
        ),
        (
            "| Reward benchmark | `{ready}` | model_rewarded_rows={rewarded}; "
            "verifier_blocker_count={blockers}; verifier_status_counts=`{counts}` |"
        ).format(
            ready=reward["ready"],
            rewarded=reward["model_rewarded_rows"],
            blockers=reward["verifier_blocker_count"],
            counts=reward["verifier_status_counts"],
        ),
        "",
    ]
    if model_run["endpoint_blockers"]:
        lines.extend(["## Endpoint Blockers", ""])
        lines.append("| Task | Source | Condition | Endpoint | Status |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in model_run["endpoint_blockers"]:
            lines.append(
                "| `{task}` | `{source}` | `{condition}` | `{endpoint}` | `{status}` |".format(
                    task=row.get("task"),
                    source=row.get("source"),
                    condition=row.get("condition"),
                    endpoint=row.get("endpoint_profile"),
                    status=row.get("status"),
                )
            )
        lines.append("")
    if reward["verifier_blockers_by_task"]:
        lines.extend(["## Verifier Blockers", ""])
        lines.append("| Task | Statuses |")
        lines.append("| --- | --- |")
        for task, statuses in reward["verifier_blockers_by_task"].items():
            lines.append(f"| `{task}` | `{statuses}` |")
        lines.append("")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report Harbor ICL daily readiness.")
    parser.add_argument("--pack-dir", type=Path, default=Path("runs/harbor_icl_baseline"))
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = build_readiness(load_summary(args.pack_dir))
    output_json = args.output_json or args.pack_dir / "icl_readiness.json"
    output_md = args.output_md or args.pack_dir / "icl_readiness.md"
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(markdown(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
