#!/usr/bin/env python3
"""Run a fresh TB2.1 89-task batch with DynamicIclClaudeCode.

This wrapper reuses Hugo's local SSD Terminal-Bench batch runner for scheduling,
trace export, container artifact preservation, and cleanup. It monkey-patches
only the Harbor job config and endpoint shell so each task runs Claude Code +
Kimi through `DynamicIclClaudeCode` with a task-specific TD context card.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_RUNNER = Path("/Users/hugo/Desktop/super-refactor/harbor/scripts/run_tb21_kimi_k26_batch.py")
DEFAULT_PACK_DIR = REPO_ROOT / "runs/harbor_icl_baseline"


def load_base_runner(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("tb21_kimi_batch_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import base runner: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")


def base_defaults(base: Any) -> argparse.Namespace:
    old = sys.argv[:]
    try:
        sys.argv = [old[0]]
        return base.parse_args()
    finally:
        sys.argv = old


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-runner", type=Path, default=DEFAULT_BASE_RUNNER)
    parser.add_argument("--pack-dir", type=Path, default=DEFAULT_PACK_DIR)
    parser.add_argument("--context-variant", default="td_full")
    parser.add_argument("--inject-mode", default="prelude", choices=["tool", "prelude", "continue_after", "sdk_live", "hooks_live"])
    parser.add_argument("--endpoint-profile", default="seed-coding-plan")
    parser.add_argument("--sdk-live-intercept-tool", action="append", default=[])
    parser.add_argument("--first-turn-timeout-sec", type=int, default=75)
    parser.add_argument("--no-force-context", dest="force_context_call", action="store_false")
    parser.set_defaults(force_context_call=True)

    parser.add_argument("--workdir", type=Path, default=None)
    parser.add_argument("--tasks-dir", type=Path, default=None)
    parser.add_argument("--runs-dir", type=Path, default=None)
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--model", default="kimi-k2.6")
    parser.add_argument("--harbor-bin", default=None)
    parser.add_argument("--setup-timeout", type=float, default=None)
    parser.add_argument("--agent-timeout", type=float, default=None)
    parser.add_argument("--timeout-multiplier", type=float, default=None)
    parser.add_argument("--harbor-retries", type=int, default=None)
    parser.add_argument("--min-concurrency", type=int, default=None)
    parser.add_argument("--max-concurrency", type=int, default=None)
    parser.add_argument("--max-task-memory-mb", type=int, default=None)
    parser.add_argument("--heavy-task-memory-mb", type=int, default=None)
    parser.add_argument("--low-disk-gb", type=float, default=None)
    parser.add_argument("--low-memory-gb", type=float, default=None)
    parser.add_argument("--prune-cache-below-gb", type=float, default=None)
    parser.add_argument("--keep-build-cache-gb", type=float, default=None)
    parser.add_argument("--pressure-cooldown-sec", type=float, default=None)
    parser.add_argument("--poll-interval-sec", type=float, default=None)
    parser.add_argument("--include-verifier-metadata", action="store_true")
    parser.add_argument("--container-copy-path", action="append", default=None)
    parser.add_argument("--export-container-rootfs", action="store_true")
    parser.add_argument("--no-preserve-container-artifacts", dest="preserve_container_artifacts", action="store_false")
    parser.set_defaults(preserve_container_artifacts=True)
    parser.add_argument("--no-force-build", action="store_true")
    parser.add_argument("--no-prune-build-cache", dest="prune_build_cache", action="store_false")
    parser.set_defaults(prune_build_cache=True)
    parser.add_argument("--task", action="append")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force-rerun", action="store_true")
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    parser.set_defaults(resume=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    return parser.parse_args()


def merge_args(base_args: argparse.Namespace, cli: argparse.Namespace) -> argparse.Namespace:
    for key, value in vars(cli).items():
        if key in {"base_runner"}:
            continue
        if value is not None:
            setattr(base_args, key, value)
    if cli.container_copy_path is not None:
        base_args.container_copy_path = cli.container_copy_path
    if cli.run_name is None:
        base_args.run_name = "tb21-kimi-k26-with-td-fresh"
    base_args.pack_dir = cli.pack_dir
    base_args.context_variant = cli.context_variant
    base_args.inject_mode = cli.inject_mode
    base_args.endpoint_profile = cli.endpoint_profile
    base_args.sdk_live_intercept_tools = cli.sdk_live_intercept_tool
    base_args.first_turn_timeout_sec = cli.first_turn_timeout_sec
    base_args.force_context_call = cli.force_context_call
    base_args.run_root = base_args.runs_dir / base_args.run_name
    base_args.jobs_dir = base_args.run_root / "jobs"
    base_args.state_path = base_args.run_root / "state.json"
    base_args.manifest_path = base_args.run_root / "manifest.jsonl"
    if base_args.container_copy_path is None:
        base_args.container_copy_path = ["/logs", "/app", "/workspace", "/tests"]
    return base_args


def install_patches(base: Any) -> None:
    def make_job_config(task: Any, args: argparse.Namespace, jobs_dir: Path, config_dir: Path) -> tuple[str, Path, Path]:
        model_short = safe_id(args.model.replace("kimi-k2.", "k"))
        context_short = safe_id(args.context_variant)
        inject_short = safe_id(args.inject_mode)
        job_name = safe_id(f"tb21-td-{inject_short}-{context_short}-{task.name}-claude-code-{model_short}")
        job_dir = jobs_dir / job_name
        context_path = args.pack_dir / "teacher_cards" / task.name / f"{args.context_variant}.md"
        if not context_path.exists():
            raise FileNotFoundError(f"missing TD context card for {task.name}: {context_path}")
        agent = {
            "import_path": "harness_trajecdebug.experiments.dynamic_icl_agent:DynamicIclClaudeCode",
            "model_name": args.model,
            "override_setup_timeout_sec": float(args.setup_timeout),
            "kwargs": {
                "context_path": str(context_path.resolve()),
                "force_context_call": bool(args.force_context_call),
                "inject_mode": args.inject_mode,
                "endpoint_profile": args.endpoint_profile,
                "first_turn_timeout_sec": int(args.first_turn_timeout_sec),
                "sdk_live_intercept_tools": list(args.sdk_live_intercept_tools or []),
            },
        }
        if args.agent_timeout is not None:
            agent["override_timeout_sec"] = float(args.agent_timeout)
        config = {
            "job_name": job_name,
            "jobs_dir": str(jobs_dir),
            "endpoint_profile": args.endpoint_profile,
            "n_attempts": 1,
            "timeout_multiplier": float(args.timeout_multiplier),
            "orchestrator": {
                "type": "local",
                "n_concurrent_trials": 1,
                "quiet": False,
                "retry": {"max_retries": int(args.harbor_retries)},
            },
            "environment": {
                "type": "docker",
                "force_build": not args.no_force_build,
                "delete": False,
                "kwargs": {"keep_containers": True},
            },
            "agents": [agent],
            "tasks": [{"path": str(task.path)}],
        }
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / f"{job_name}.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        return job_name, job_dir, config_path

    def shell_for_harbor(config_path: Path, args: argparse.Namespace) -> str:
        return f"""
set -euo pipefail
if [[ -f "$HOME/.bashrc" ]]; then
  set +u
  source "$HOME/.bashrc"
  set -u
fi
source "{REPO_ROOT}/scripts/lib_endpoint_profile.sh"
apply_endpoint_profile "{args.endpoint_profile}"
export ANTHROPIC_MODEL="{args.model}"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="${{CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:-1}}"
export CLAUDE_CODE_AUTO_COMPACT_WINDOW="${{CLAUDE_CODE_AUTO_COMPACT_WINDOW:-262144}}"
export PYTHONPATH="{REPO_ROOT}/src${{PYTHONPATH:+:$PYTHONPATH}}"
if [[ -z "${{ANTHROPIC_BASE_URL:-}}" || -z "${{ANTHROPIC_API_KEY:-}}" ]]; then
  echo "Missing credentials for endpoint profile {args.endpoint_profile}" >&2
  exit 64
fi
exec "{args.harbor_bin}" run --config "{config_path}"
""".strip()

    base.make_job_config = make_job_config
    base.shell_for_harbor = shell_for_harbor


def main() -> int:
    cli = parse_args()
    base = load_base_runner(cli.base_runner)
    install_patches(base)
    args = merge_args(base_defaults(base), cli)
    if args.status:
        return base.print_status(args)
    if args.dry_run:
        return base.asyncio.run(base.run_batch(args))
    lock_handle = base.acquire_run_lock(args)
    if lock_handle is None:
        return 3
    return base.asyncio.run(base.run_batch(args))


if __name__ == "__main__":
    raise SystemExit(main())
