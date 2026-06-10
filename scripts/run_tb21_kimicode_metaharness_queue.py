#!/usr/bin/env python3
"""Run a recoverable Kimi Code Meta-Harness queue over TB2.1 tasks."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = REPO_ROOT / (
    "docs/case-studies/kimi-code-tb21-metaharness-sweep-2026-06-10/"
    "tb21_89_audit.json"
)
DEFAULT_TASKS_DIR = Path(
    "/Users/hugo/Desktop/super-refactor/harbor/datasets/"
    "terminal-bench-2.1-proxy/tasks"
)
DEFAULT_JOBS_DIR = REPO_ROOT / "artifacts/harbor-runs"
DEFAULT_BRIEF_DIR = REPO_ROOT / "artifacts/metaharness-briefs"
DEFAULT_STATE = REPO_ROOT / "artifacts/metaharness-queue/state.json"
DEFAULT_MANIFEST = REPO_ROOT / "artifacts/metaharness-queue/manifest.jsonl"
HARBOR = "/opt/miniconda3/envs/terminal-bench/bin/harbor"
NODE = "/Users/hugo/.nvm/versions/node/v24.16.0/bin/node"
KIMI_CODE_ROOT = REPO_ROOT / "kimi-code"
DOCKER_HOST = "unix:///Users/hugo/.colima/tb21-harbor/docker.sock"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--tasks-dir", type=Path, default=DEFAULT_TASKS_DIR)
    parser.add_argument("--jobs-dir", type=Path, default=DEFAULT_JOBS_DIR)
    parser.add_argument("--brief-dir", type=Path, default=DEFAULT_BRIEF_DIR)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--model", default="kimi-for-coding")
    parser.add_argument("--prompt-timeout-sec", type=int, default=1200)
    parser.add_argument("--post-upload-timeout-sec", type=int, default=180)
    parser.add_argument(
        "--stop-after-path",
        help="Optional workspace-relative path; stop Kimi Code once it exists.",
    )
    parser.add_argument("--task", action="append", help="Restrict to task; repeatable.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--no-force-build",
        action="store_true",
        help="Do not pass Harbor --force-build; useful when a valid task image already exists.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--include-invalid-baseline",
        action="store_true",
        help="Also run Meta-Harness for tasks whose baseline result is invalid/missing.",
    )
    args = parser.parse_args()

    audit = json.loads(args.audit_json.read_text())
    rows = audit["tasks"]
    selected = select_tasks(rows, args)
    if args.limit:
        selected = selected[: args.limit]
    if not selected:
        print("No tasks selected")
        return 0

    state = read_json(args.state) or {"created_at": iso_now(), "tasks": {}}
    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.brief_dir.mkdir(parents=True, exist_ok=True)
    args.jobs_dir.mkdir(parents=True, exist_ok=True)

    print(json.dumps({"selected": [row["task"] for row in selected]}, indent=2))
    if args.dry_run:
        return 0

    for row in selected:
        task = row["task"]
        previous = state["tasks"].get(task)
        if previous and previous.get("status") == "finished" and not args.force:
            print(f"[{iso_now()}] skip finished {task}", flush=True)
            continue
        brief = write_repair_brief(row, args)
        job_name = f"tb21-{safe(task)}-kimicode-with-metaharness-{datetime.now():%Y%m%dT%H%M%S}"
        task_path = args.tasks_dir / task
        cmd = [
            HARBOR,
            "run",
            "--job-name",
            job_name,
            "--jobs-dir",
            str(args.jobs_dir),
            "-n",
            "1",
            "--n-attempts",
            "1",
            "--agent-import-path",
            "harbor_adapters.kimi_code_host_agent:KimiCodeHostAgent",
            "--model",
            args.model,
            "--ak",
            f"kimi_code_root={KIMI_CODE_ROOT}",
            "--ak",
            f"node_bin={NODE}",
            "--ak",
            f"prompt_timeout_sec={args.prompt_timeout_sec}",
            "--ak",
            f"previous_failure_path={brief}",
            "--ak",
            "include_env_snapshot=true",
            "--ak",
            "upload_mode=workspace",
            "--ak",
            "clear_app_before_upload=true",
            "--ak",
            f"post_upload_timeout_sec={args.post_upload_timeout_sec}",
            "--ak",
            "upload_on_timeout=true",
            "--path",
            str(task_path),
        ]
        if not args.no_force_build:
            cmd.insert(cmd.index("--agent-import-path"), "--force-build")
        if args.stop_after_path:
            cmd.extend(["--ak", f"stop_after_path={args.stop_after_path}"])
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["DOCKER_HOST"] = DOCKER_HOST
        env["PATH"] = str(Path(NODE).parent) + os.pathsep + env.get("PATH", "")
        started = iso_now()
        print(f"[{started}] run {task}: {job_name}", flush=True)
        result = subprocess.run(cmd, cwd=REPO_ROOT, env=env, text=True)
        finished = iso_now()
        job_dir = args.jobs_dir / job_name
        summary = summarize_job(job_dir)
        item = {
            "task": task,
            "status": "finished" if result.returncode == 0 else "process_error",
            "returncode": result.returncode,
            "started_at": started,
            "finished_at": finished,
            "job_name": job_name,
            "job_dir": str(job_dir),
            "brief": str(brief),
            "summary": summary,
        }
        state["tasks"][task] = item
        write_json(args.state, state)
        append_jsonl(args.manifest, item)
        print(
            f"[{finished}] {task} rc={result.returncode} "
            f"reward={summary.get('reward')} exception={summary.get('exception')}",
            flush=True,
        )
    return 0


def select_tasks(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    wanted = set(args.task or [])
    selected: list[dict[str, Any]] = []
    for row in rows:
        task = row["task"]
        if wanted and task not in wanted:
            continue
        if row.get("counts_for_without_n") is True:
            continue
        if row.get("counts_for_m") is True:
            continue
        baseline_status = row.get("baseline_status")
        if baseline_status == "invalid_or_missing" and not args.include_invalid_baseline:
            continue
        selected.append(row)
    return selected


def write_repair_brief(row: dict[str, Any], args: argparse.Namespace) -> Path:
    task = row["task"]
    task_dir = args.tasks_dir / task
    instruction = read_tail(task_dir / "instruction.md", 6000)
    baseline_result = Path(row["baseline_result_path"]) if row.get("baseline_result_path") else None
    verifier = read_tail(baseline_result.parent / "verifier" / "test-stdout.txt", 12000) if baseline_result else ""
    exception = row.get("baseline_exception") or ""
    brief = args.brief_dir / f"{task}.md"
    brief.write_text(
        "\n".join(
            [
                f"# Meta-Harness Repair Brief: {task}",
                "",
                "## Source Failure",
                "",
                "- Harness: Harbor / Terminal-Bench 2.1 proxy task",
                f"- Source task: `{task}`",
                "- Prior agent/model: `claude-code + kimi-k2.6`",
                f"- Prior reward: `{row.get('baseline_reward')}`",
                f"- Prior exception: `{exception or 'none'}`",
                f"- Prior result: `{row.get('baseline_result_path')}`",
                "",
                "## Original Instruction",
                "",
                fenced(instruction or "(instruction.md unavailable)"),
                "",
                "## Prior Verifier Output Tail",
                "",
                fenced(verifier or "(verifier stdout unavailable)"),
                "",
                "## Repair Direction",
                "",
                "- Create or modify the files required by the original instruction under `/app`.",
                "- Use the verifier failure above as the primary signal; avoid repeating the same missing-file, timeout, dependency, or assertion failure.",
                "- If the task depends on localhost, ChromeDriver, Selenium, gRPC, or other local services, account for proxy variables shown in the environment snapshot.",
                "- If container-side setup is required after upload, create `.kimi-post-upload.sh` in the workspace and make it exit promptly.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return brief


def summarize_job(job_dir: Path) -> dict[str, Any]:
    result_paths = sorted(path for path in job_dir.glob("*/result.json") if "__" in path.parent.name)
    if not result_paths:
        return {}
    path = result_paths[-1]
    try:
        data = json.loads(path.read_text())
    except Exception as exc:
        return {"result_path": str(path), "error": str(exc)}
    verifier = data.get("verifier_result") if isinstance(data.get("verifier_result"), dict) else {}
    rewards = verifier.get("rewards") if isinstance(verifier.get("rewards"), dict) else {}
    exception = data.get("exception_info") if isinstance(data.get("exception_info"), dict) else {}
    return {
        "trial": path.parent.name,
        "result_path": str(path),
        "reward": rewards.get("reward"),
        "exception": exception.get("exception_type"),
        "exception_message": exception.get("exception_message"),
    }


def read_tail(path: Path, max_chars: int) -> str:
    try:
        text = path.read_text(errors="replace")
    except Exception:
        return ""
    return text[-max_chars:]


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, data: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, sort_keys=True) + "\n")


def fenced(text: str) -> str:
    return "```text\n" + text.rstrip() + "\n```"


def safe(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-")


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
