#!/usr/bin/env python3
"""Watch paired TB2.1 no-TD / with-TD runs and compute final numbers."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def load_state(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        print(f"{path}: invalid JSON: {exc}", flush=True)
        return None


def summarize(label: str, path: Path) -> tuple[bool, dict[str, Any]]:
    state = load_state(path)
    if state is None:
        print(f"{label}: missing state {path}", flush=True)
        return False, {"tasks": 0, "running": []}

    tasks = state.get("tasks") or {}
    counts: dict[str, int] = {}
    rewards: dict[str, int] = {}
    running: list[str] = []
    none_reward_harbor_errors: list[str] = []

    for task_name, row in tasks.items():
        status = row.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
        reward = (row.get("result_summary") or {}).get("reward")
        rewards[str(reward)] = rewards.get(str(reward), 0) + 1
        if status == "running":
            running.append(task_name)
        if status == "harbor_error" and reward is None:
            none_reward_harbor_errors.append(task_name)

    print(
        f"{label}: tasks={len(tasks)} counts={counts} rewards={rewards} "
        f"running={running} none_reward_harbor_errors={none_reward_harbor_errors} "
        f"finished_at={state.get('finished_at')}",
        flush=True,
    )
    return bool(state.get("finished_at")), {
        "tasks": len(tasks),
        "running": running,
        "none_reward_harbor_errors": none_reward_harbor_errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--without-td-state", type=Path, required=True)
    parser.add_argument("--with-td-state", type=Path, required=True)
    parser.add_argument("--expected-tasks", type=int, default=89)
    parser.add_argument("--interval-sec", type=float, default=300)
    parser.add_argument("--compute-script", type=Path, default=Path("scripts/compute_tb21_fresh_td_numbers.py"))
    parser.add_argument("--with-td-inject-mode", default="prelude")
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    while True:
        print(datetime.now().astimezone().isoformat(timespec="seconds"), flush=True)
        no_finished, no_info = summarize("without_td", args.without_td_state)
        td_finished, td_info = summarize("with_td", args.with_td_state)
        done = (
            no_finished
            and td_finished
            and no_info["tasks"] == args.expected_tasks
            and td_info["tasks"] == args.expected_tasks
            and not no_info["running"]
            and not td_info["running"]
        )
        if done:
            command = [
                sys.executable,
                str(args.compute_script),
                "--without-td-state",
                str(args.without_td_state),
                "--with-td-state",
                str(args.with_td_state),
                "--with-td-inject-mode",
                args.with_td_inject_mode,
                "--json-output",
                str(args.json_output),
                "--markdown-output",
                str(args.markdown_output),
            ]
            print("running:", " ".join(command), flush=True)
            subprocess.run(command, check=True)
            return 0
        time.sleep(args.interval_sec)


if __name__ == "__main__":
    raise SystemExit(main())
