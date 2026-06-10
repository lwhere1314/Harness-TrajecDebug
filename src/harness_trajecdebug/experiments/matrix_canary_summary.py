"""Summarize matrix canary batches for Harbor ICL experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from harness_trajecdebug.experiments.sdk_live_summary import summarize_trial


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def read_tasks(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def safe_model(model: str) -> str:
    return model.replace("/", "-").replace(".", "-")


def safe_part(value: str) -> str:
    return value.replace("/", "-").replace(".", "-")


def latest_trial(job_dir: Path, task: str) -> Path | None:
    if not job_dir.exists():
        return None
    trials = sorted(path for path in job_dir.iterdir() if path.is_dir() and path.name.startswith(f"{task}__"))
    return trials[-1] if trials else None


def dynamic_job_dirs(
    jobs_dir: Path,
    task: str,
    model: str,
    inject_mode: str,
    context_variant: str,
) -> list[Path]:
    new_name = (
        f"htd-dynamic-icl-{safe_part(inject_mode)}-"
        f"{safe_part(context_variant)}-{task}-{safe_model(model)}"
    )
    old_name = f"htd-dynamic-icl-{task}-{safe_model(model)}"
    dirs = [jobs_dir / new_name]
    if old_name != new_name:
        dirs.append(jobs_dir / old_name)
    return dirs


def reward_from_result(result: dict[str, Any]) -> float | None:
    value = (
        result.get("verifier_result", {})
        .get("rewards", {})
        .get("reward")
    )
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def summarize_regular_trial(trial_dir: Path) -> dict[str, Any]:
    result = read_json(trial_dir / "result.json") or {}
    reward = reward_from_result(result)
    if reward == 1.0:
        status = "passed"
    elif reward == 0.0:
        status = "failed_verifier"
    elif result.get("exception_info"):
        status = "harbor_exception"
    else:
        status = "ran_unknown"
    return {
        "trial_dir": str(trial_dir),
        "status": status,
        "reward": reward,
        "exception_info": result.get("exception_info"),
        "agent_result": result.get("agent_result"),
        "verifier_result": result.get("verifier_result"),
    }


def replay_status(batch_dir: Path) -> dict[str, dict[str, Any]]:
    by_task: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(batch_dir / "replay-summary.jsonl"):
        task = row.get("task")
        if not isinstance(task, str):
            continue
        replays = row.get("replays") if isinstance(row.get("replays"), list) else []
        by_task[task] = {
            "replay_count": len(replays),
            "all_injected": bool(replays) and all(bool(item.get("injected")) for item in replays if isinstance(item, dict)),
            "reasons": [
                item.get("reason")
                for item in replays
                if isinstance(item, dict)
            ],
            "files": [
                item.get("file")
                for item in replays
                if isinstance(item, dict)
            ],
        }
    return by_task


def summarize_batch(batch_dir: Path, pack_dir: Path | None = None) -> dict[str, Any]:
    config = read_json(batch_dir / "config.json") or {}
    pack = Path(config.get("pack_dir") or pack_dir or "runs/harbor_icl_baseline")
    model = str(config.get("model") or "kimi-k2.6")
    inject_mode = str(config.get("inject_mode") or "continue_after")
    context_variant = str(config.get("context_variant") or "debug_action")
    jobs_dir = Path(
        config.get("jobs_dir")
        or (pack / ("harbor_runs_sdk_live" if inject_mode == "sdk_live" else "harbor_runs"))
    )
    tasks = read_tasks(batch_dir / "tasks.txt")
    preflight = read_json(batch_dir / "preflight.json") or {"ok": None, "kind": "missing"}
    replay_by_task = replay_status(batch_dir)

    rows: list[dict[str, Any]] = []
    for task in tasks:
        job_dirs = dynamic_job_dirs(jobs_dir, task, model, inject_mode, context_variant)
        job_dir = job_dirs[0]
        trial_dir = None
        for candidate_job_dir in job_dirs:
            candidate_trial = latest_trial(candidate_job_dir, task)
            if candidate_trial is not None:
                job_dir = candidate_job_dir
                trial_dir = candidate_trial
                break
        if trial_dir is None:
            run = {
                "status": "preflight_blocked" if preflight.get("ok") is False else "not_run",
                "reward": None,
                "job_dir": str(job_dir),
                "candidate_job_dirs": [str(path) for path in job_dirs],
                "trial_dir": None,
            }
        elif inject_mode == "sdk_live":
            summary_path = trial_dir / "sdk-live-summary.json"
            run = read_json(summary_path) if summary_path.exists() else summarize_trial(trial_dir)
            run["job_dir"] = str(job_dir)
        else:
            run = summarize_regular_trial(trial_dir)
            run["job_dir"] = str(job_dir)

        rows.append(
            {
                "task": task,
                "replay": replay_by_task.get(task, {}),
                "run": run,
            }
        )

    return {
        "batch_dir": str(batch_dir),
        "config": config,
        "preflight": preflight,
        "tasks": tasks,
        "rows": rows,
    }


def markdown(summary: dict[str, Any]) -> str:
    preflight = summary.get("preflight", {})
    config = summary.get("config") if isinstance(summary.get("config"), dict) else {}
    lines = [
        "# Matrix Canary Summary",
        "",
        f"Batch: `{summary.get('batch_dir')}`",
        f"Endpoint profile: `{config.get('endpoint_profile', 'auto')}`",
        f"Preflight: `{preflight.get('kind')}` status=`{preflight.get('status')}` ok=`{preflight.get('ok')}`",
        "",
        "| Task | Replay | Run status | Reward | Trial |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for row in summary.get("rows", []):
        replay = row.get("replay") or {}
        run = row.get("run") or {}
        replay_text = "injected" if replay.get("all_injected") else "missing"
        reasons = ", ".join(str(reason) for reason in replay.get("reasons", []) if reason)
        if reasons:
            replay_text += f" ({reasons})"
        trial = run.get("trial_dir") or ""
        lines.append(
            f"| `{row.get('task')}` | {replay_text} | `{run.get('status')}` | {run.get('reward')} | `{trial}` |"
        )
    lines.append("")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize a matrix canary batch.")
    parser.add_argument("batch_dir", type=Path)
    parser.add_argument("--pack-dir", type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = summarize_batch(args.batch_dir, pack_dir=args.pack_dir)
    json_text = json.dumps(summary, ensure_ascii=False, indent=2)
    md_text = markdown(summary)
    output_json = args.output_json or args.batch_dir / "summary.json"
    output_md = args.output_md or args.batch_dir / "summary.md"
    output_json.write_text(json_text + "\n", encoding="utf-8")
    output_md.write_text(md_text, encoding="utf-8")
    print(json_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
