#!/usr/bin/env python3
"""Launch the query-optimize sdk_live reproduction in a detached session.

Some agent CLIs clean up background children created by their shell tool after
the tool call returns. Spawning the Harbor runner in a new session keeps the
long-running verifier alive while still giving the caller a one-command entry
point.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detached launcher for query-optimize sdk_live reproduction."
    )
    parser.add_argument(
        "jobs_dir",
        nargs="?",
        default="runs/harbor_icl_repro_seed_detached",
        help="Harbor jobs directory passed to run_query_optimize_sdk_live_repro.sh.",
    )
    parser.add_argument(
        "--context-variant",
        default="debug_action",
        help="Teacher-card context variant, for example debug_action or fail_debug_action.",
    )
    parser.add_argument("--log-file", help="Path for combined stdout/stderr.")
    parser.add_argument("--pid-file", help="Path where the detached PID is written.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    jobs_dir = Path(args.jobs_dir)
    log_file = Path(args.log_file) if args.log_file else jobs_dir.with_suffix(".nohup.log")
    pid_file = Path(args.pid_file) if args.pid_file else jobs_dir.with_suffix(".pid")

    if not log_file.is_absolute():
        log_file = repo_root / log_file
    if not pid_file.is_absolute():
        pid_file = repo_root / pid_file

    log_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    jobs_arg = shlex.quote(str(jobs_dir))
    repo_arg = shlex.quote(str(repo_root))
    context_arg = shlex.quote(args.context_variant)
    command = (
        "source ~/.bashrc >/dev/null 2>&1 || true; "
        f"cd {repo_arg}; "
        f"exec scripts/run_query_optimize_sdk_live_repro.sh {jobs_arg} {context_arg}"
    )

    log = log_file.open("ab", buffering=0)
    proc = subprocess.Popen(
        ["/bin/bash", "-lc", command],
        cwd=str(repo_root),
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
    pid_file.write_text(f"{proc.pid}\n", encoding="utf-8")

    print(f"pid={proc.pid}")
    print(f"pid_file={pid_file}")
    print(f"log_file={log_file}")
    print(f"jobs_dir={repo_root / jobs_dir if not jobs_dir.is_absolute() else jobs_dir}")
    print(f"context_variant={args.context_variant}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
