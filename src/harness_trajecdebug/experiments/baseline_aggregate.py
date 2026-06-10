"""Aggregate Harbor ICL baseline results across static and runtime runs."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from harness_trajecdebug.experiments.matrix_canary_summary import read_json
from harness_trajecdebug.experiments.sdk_live_summary import summarize_trial


STATIC_PREFIX = "htd-icl-"
RUNTIME_PREFIX = "htd-dynamic-icl-"
ARTIFACT_HARBOR_PREFIX = "htd-artifact-closure-"
RUNTIME_SMOKE_PREFIX = "htd-runtime-smoke-"
RUNTIME_MODES = ["continue_after", "sdk_live", "hooks_live", "prelude", "tool"]
CONTEXT_VARIANTS = [
    "debug_trajectory",
    "debug_action",
    "prompt_filtered",
    "outcome_only",
    "raw_trace",
    "no_icl",
]
OUTCOME_STATUSES = {"passed", "failed_verifier", "injected_but_failed_verifier"}
REWARDED_SOURCES = {"harbor_static", "harbor_runtime", "matrix_canary"}


def verifier_proxy_leak(stdout: str) -> bool:
    """Detect verifier tests accidentally routed through the host proxy."""
    if "ProxyError" not in stdout:
        return False
    proxy_markers = [
        "host.docker.internal:1082",
        "Unable to connect to proxy",
        "Failed to establish a new connection",
    ]
    local_markers = [
        "localhost:",
        "127.0.0.1:",
    ]
    return any(marker in stdout for marker in proxy_markers) and any(
        marker in stdout for marker in local_markers
    )


def verifier_dependency_failure(stdout: str) -> bool:
    dependency_markers = [
        "Unable to locate package curl",
        "uvx: command not found",
        "curl: command not found",
        "Connection failed",
    ]
    return any(marker in stdout for marker in dependency_markers)


def iter_job_dirs(root: Path) -> list[tuple[Path, bool]]:
    if not root.exists():
        return []
    rows: list[tuple[Path, bool]] = []
    for job_dir in sorted(root.iterdir()):
        if job_dir.is_dir() and job_dir.name != "_archived":
            rows.append((job_dir, False))
    archive_root = root / "_archived"
    if archive_root.exists():
        for job_dir in sorted(archive_root.iterdir()):
            if job_dir.is_dir():
                rows.append((job_dir, True))
    return rows


def reward_from_result(result: dict[str, Any]) -> float | None:
    verifier = result.get("verifier_result")
    if not isinstance(verifier, dict):
        return None
    rewards = verifier.get("rewards")
    if not isinstance(rewards, dict):
        return None
    value = rewards.get("reward")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def latest_trial(job_dir: Path, task: str | None = None) -> Path | None:
    if not job_dir.exists():
        return None
    candidates = []
    for path in job_dir.iterdir():
        if not path.is_dir():
            continue
        if task is None or path.name.startswith(f"{task}__"):
            candidates.append(path)
    return sorted(candidates)[-1] if candidates else None


def infer_task_variant(config: dict[str, Any]) -> tuple[str | None, str | None]:
    tasks = config.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return None, None
    task = tasks[0]
    if not isinstance(task, dict):
        return None, None
    path = task.get("path")
    if not isinstance(path, str):
        return None, None
    parts = Path(path).parts
    if "task_variants" in parts:
        index = parts.index("task_variants")
        if len(parts) > index + 2:
            return parts[index + 2], parts[index + 1]
    return Path(path).name, None


def model_from_config(config: dict[str, Any]) -> str | None:
    agents = config.get("agents")
    if isinstance(agents, list) and agents and isinstance(agents[0], dict):
        model = agents[0].get("model_name")
        if isinstance(model, str):
            return model
    agent = config.get("agent")
    if isinstance(agent, dict):
        model = agent.get("model_name")
        if isinstance(model, str):
            return model
    return None


def parse_dynamic_job_name(name: str) -> tuple[str | None, str | None, str | None, str | None]:
    if not name.startswith(RUNTIME_PREFIX):
        return None, None, None, None
    rest = name[len(RUNTIME_PREFIX):]
    for index, char in enumerate(rest):
        if char.isdigit() and index > 0 and rest[index - 1] == "-":
            stamp = rest[index:].replace("-", "")
            if len(stamp) >= 15 and stamp[8] == "T":
                rest = rest[: index - 1]
                break
    model = None
    for suffix, model_name in [
        ("-kimi-k2-6", "kimi-k2.6"),
        ("-kimi-k2-5", "kimi-k2.5"),
        ("-kimi-for-coding", "kimi-for-coding"),
    ]:
        if rest.endswith(suffix):
            model = model_name
            rest = rest[: -len(suffix)]
            break

    for mode in RUNTIME_MODES:
        prefix = f"{mode}-"
        if not rest.startswith(prefix):
            continue
        tail = rest[len(prefix):]
        for context in CONTEXT_VARIANTS:
            context_prefix = f"{context}-"
            if tail.startswith(context_prefix):
                task = tail[len(context_prefix):]
                return task or None, mode, context, model

    return rest or None, None, None, model


def result_status(trial_dir: Path | None, sdk_live: bool = False) -> dict[str, Any]:
    if trial_dir is None:
        return {
            "status": "not_run",
            "reward": None,
            "trial_dir": None,
        }

    if sdk_live:
        summary_path = trial_dir / "sdk-live-summary.json"
        summary = read_json(summary_path) if summary_path.exists() else summarize_trial(trial_dir)
        return {
            "status": summary.get("status") or "sdk_live_unknown",
            "reward": summary.get("reward"),
            "trial_dir": str(trial_dir),
            "sdk_live": summary,
        }

    result_path = trial_dir / "result.json"
    if not result_path.exists():
        return {
            "status": "missing_result",
            "reward": None,
            "trial_dir": str(trial_dir),
        }
    result = read_json(result_path) or {}
    reward = reward_from_result(result)
    exception = result.get("exception_info")
    if reward == 1.0:
        status = "passed"
    elif reward == 0.0:
        status = "failed_verifier"
    elif exception:
        status = "infrastructure_error"
    else:
        status = "ran_unknown"
    return {
        "status": status,
        "reward": reward,
        "trial_dir": str(trial_dir),
        "exception_info": exception,
        "agent_result": result.get("agent_result"),
    }


def exception_text(exception: Any) -> str:
    if exception is None:
        return ""
    try:
        return json.dumps(exception, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(exception)


def static_row(job_dir: Path, archived: bool = False) -> dict[str, Any] | None:
    config = read_json(job_dir / "config.json") or {}
    task, variant = infer_task_variant(config)
    model = model_from_config(config)
    if not task or not variant:
        return None
    trial_dir = latest_trial(job_dir, task)
    run = result_status(trial_dir)
    return {
        "source": "harbor_static",
        "task": task,
        "model": model,
        "family": "static_instruction",
        "condition": variant,
        "endpoint_profile": config.get("endpoint_profile") or "auto",
        "variant": variant,
        "inject_mode": None,
        "context_variant": variant,
        "job_dir": str(job_dir),
        "archived": archived,
        **run,
    }


def runtime_row(job_dir: Path, default_sdk_live: bool = False, archived: bool = False) -> dict[str, Any] | None:
    config = read_json(job_dir / "config.json") or {}
    task, _variant = infer_task_variant(config)
    model = model_from_config(config)
    name_task, name_mode, name_context, name_model = parse_dynamic_job_name(job_dir.name)
    agents = config.get("agents")
    kwargs: dict[str, Any] = {}
    if isinstance(agents, list) and agents and isinstance(agents[0], dict):
        raw_kwargs = agents[0].get("kwargs")
        if isinstance(raw_kwargs, dict):
            kwargs = raw_kwargs
    inject_mode = str(kwargs.get("inject_mode") or name_mode or ("sdk_live" if default_sdk_live else "runtime_unknown"))
    context_path = kwargs.get("context_path")
    context_variant = Path(str(context_path)).stem if context_path else (name_context or "unknown")
    model = model or name_model
    endpoint_profile = config.get("endpoint_profile") or kwargs.get("endpoint_profile") or "auto"

    if task is None:
        task = name_task
    if task is None:
        return None

    trial_dir = latest_trial(job_dir, task)
    if not config and trial_dir is None:
        return None
    run = result_status(trial_dir, sdk_live=inject_mode == "sdk_live")
    return {
        "source": "harbor_runtime",
        "task": task,
        "model": model,
        "family": "runtime_injection",
        "condition": f"{inject_mode}:{context_variant}",
        "endpoint_profile": endpoint_profile,
        "variant": None,
        "inject_mode": inject_mode,
        "context_variant": context_variant,
        "job_dir": str(job_dir),
        "archived": archived,
        **run,
    }


def matrix_rows(pack_dir: Path) -> list[dict[str, Any]]:
    rows_by_key: dict[tuple[str | None, Any, Any, Any, Any], dict[str, Any]] = {}
    summary_paths = [
        *(pack_dir / "matrix_canary").glob("*/summary.json"),
        *(pack_dir / "baseline_suites").glob("*/*/summary.json"),
    ]
    for summary_path in sorted(summary_paths):
        summary = read_json(summary_path) or {}
        config = summary.get("config") if isinstance(summary.get("config"), dict) else {}
        model = config.get("model")
        inject_mode = config.get("inject_mode")
        context_variant = config.get("context_variant")
        endpoint_profile = config.get("endpoint_profile") or "auto"
        for row in summary.get("rows", []):
            if not isinstance(row, dict):
                continue
            run = row.get("run") if isinstance(row.get("run"), dict) else {}
            replay = row.get("replay") if isinstance(row.get("replay"), dict) else {}
            suite_dir = (
                str(summary_path.parents[1])
                if "baseline_suites" in summary_path.parts
                else None
            )
            aggregate_row = {
                "source": "matrix_canary",
                "task": row.get("task"),
                "model": model,
                "family": "matrix_replay",
                "condition": f"{inject_mode}:{context_variant}",
                "endpoint_profile": endpoint_profile,
                "variant": None,
                "inject_mode": inject_mode,
                "context_variant": context_variant,
                "job_dir": run.get("job_dir"),
                "trial_dir": run.get("trial_dir"),
                "status": run.get("status"),
                "reward": run.get("reward"),
                "replay_all_injected": replay.get("all_injected"),
                "replay_reasons": replay.get("reasons"),
                "batch_dir": summary.get("batch_dir"),
                "suite_dir": suite_dir,
            }
            key = (aggregate_row["task"], model, inject_mode, context_variant, endpoint_profile)
            previous = rows_by_key.get(key)
            if previous is None or aggregate_row.get("suite_dir") or not previous.get("suite_dir"):
                rows_by_key[key] = aggregate_row
    return list(rows_by_key.values())


def artifact_closure_rows(pack_dir: Path) -> list[dict[str, Any]]:
    rows_by_key: dict[tuple[Any, Any], dict[str, Any]] = {}
    for summary_path in sorted((pack_dir / "artifact_closure").glob("*.json")):
        summary = read_json(summary_path) or {}
        context_variant = summary.get("context_variant") or "debug_action"
        for row in summary.get("rows", []):
            if not isinstance(row, dict):
                continue
            aggregate_row = {
                "source": "artifact_closure",
                "task": row.get("task"),
                "model": "none",
                "family": "non_model_artifact",
                "condition": str(context_variant),
                "endpoint_profile": "none",
                "variant": None,
                "inject_mode": None,
                "context_variant": context_variant,
                "job_dir": str(summary_path.parent),
                "trial_dir": str(summary_path),
                "status": row.get("status"),
                "reward": None,
                "archived": False,
                "closure_ok": row.get("ok"),
                "artifacts": row.get("artifacts"),
                "checks": row.get("checks"),
            }
            rows_by_key[(aggregate_row["task"], context_variant)] = aggregate_row
    return list(rows_by_key.values())


def artifact_harbor_row(job_dir: Path, archived: bool = False) -> dict[str, Any] | None:
    config = read_json(job_dir / "config.json") or {}
    task, _variant = infer_task_variant(config)
    agents = config.get("agents")
    context_variant = "debug_action"
    if isinstance(agents, list) and agents and isinstance(agents[0], dict):
        kwargs = agents[0].get("kwargs")
        if isinstance(kwargs, dict) and kwargs.get("context_path"):
            context_variant = Path(str(kwargs["context_path"])).stem
    if not task:
        name = job_dir.name
        if name.startswith(ARTIFACT_HARBOR_PREFIX):
            rest = name[len(ARTIFACT_HARBOR_PREFIX):]
            prefix = f"{context_variant}-"
            task = rest[len(prefix):] if rest.startswith(prefix) else rest
    if not task:
        return None
    trial_dir = latest_trial(job_dir, task)
    run = result_status(trial_dir)
    if trial_dir is not None:
        materialize = read_json(trial_dir / "agent" / "debug-action-materialize.json") or {}
        verifier_stdout = trial_dir / "verifier" / "test-stdout.txt"
        stdout = verifier_stdout.read_text(encoding="utf-8", errors="replace") if verifier_stdout.exists() else ""
        if materialize.get("return_code") == 0:
            run["materialization"] = materialize
            exception = exception_text(run.get("exception_info"))
            timeout_markers = [
                "VerifierTimeoutError",
                "Verifier execution timed out",
                "asyncio.exceptions.TimeoutError",
            ]
            verifier_started_markers = [
                "collected ",
                "test session starts",
                "../tests/test_outputs.py",
            ]
            if any(marker in exception for marker in timeout_markers):
                run["status"] = "verifier_timeout_after_materialization"
            elif run.get("status") == "missing_result" and any(
                marker in stdout for marker in verifier_started_markers
            ):
                run["status"] = "verifier_timeout_after_materialization"
            elif run.get("status") == "missing_result" and verifier_stdout.exists():
                run["status"] = "verifier_incomplete_after_materialization"
    if trial_dir is not None and run.get("status") == "failed_verifier":
        stdout_path = trial_dir / "verifier" / "test-stdout.txt"
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.exists() else ""
        if verifier_proxy_leak(stdout):
            run["status"] = "verifier_proxy_leak"
        elif verifier_dependency_failure(stdout):
            run["status"] = "verifier_dependency_failure"
    return {
        "source": "harbor_artifact_closure",
        "task": task,
        "model": "none",
        "family": "non_model_harbor_verifier",
        "condition": context_variant,
        "endpoint_profile": "none",
        "variant": None,
        "inject_mode": None,
        "context_variant": context_variant,
        "job_dir": str(job_dir),
        "archived": archived,
        **run,
    }


def runtime_smoke_row(job_dir: Path, archived: bool = False) -> dict[str, Any] | None:
    config = read_json(job_dir / "config.json") or {}
    task, _variant = infer_task_variant(config)
    agents = config.get("agents")
    context_variant = "debug_action"
    trigger = "ask_user_question"
    if isinstance(agents, list) and agents and isinstance(agents[0], dict):
        kwargs = agents[0].get("kwargs")
        if isinstance(kwargs, dict):
            if kwargs.get("context_path"):
                context_variant = Path(str(kwargs["context_path"])).stem
            if kwargs.get("trigger"):
                trigger = str(kwargs["trigger"])
    if not task:
        name = job_dir.name
        if name.startswith(RUNTIME_SMOKE_PREFIX):
            rest = name[len(RUNTIME_SMOKE_PREFIX):]
            prefix = f"{trigger}-{context_variant}-"
            task = rest[len(prefix):] if rest.startswith(prefix) else rest
    if not task:
        return None
    trial_dir = latest_trial(job_dir, task)
    run = result_status(trial_dir)
    smoke = {}
    if trial_dir is not None:
        smoke = read_json(trial_dir / "agent" / "runtime-injection-smoke.json") or {}
        materialize = read_json(trial_dir / "agent" / "debug-action-materialize.json") or {}
        verifier_stdout = trial_dir / "verifier" / "test-stdout.txt"
        stdout = verifier_stdout.read_text(encoding="utf-8", errors="replace") if verifier_stdout.exists() else ""
        if materialize.get("return_code") == 0:
            run["materialization"] = materialize
            exception = exception_text(run.get("exception_info"))
            timeout_markers = [
                "VerifierTimeoutError",
                "Verifier execution timed out",
                "asyncio.exceptions.TimeoutError",
            ]
            verifier_started_markers = [
                "collected ",
                "test session starts",
                "../tests/test_outputs.py",
            ]
            if any(marker in exception for marker in timeout_markers):
                run["status"] = "verifier_timeout_after_materialization"
            elif run.get("status") == "missing_result" and any(
                marker in stdout for marker in verifier_started_markers
            ):
                run["status"] = "verifier_timeout_after_materialization"
            elif run.get("status") == "missing_result" and verifier_stdout.exists():
                run["status"] = "verifier_incomplete_after_materialization"
        if run.get("status") == "failed_verifier":
            if verifier_proxy_leak(stdout):
                run["status"] = "verifier_proxy_leak"
            elif verifier_dependency_failure(stdout):
                run["status"] = "verifier_dependency_failure"
    return {
        "source": "harbor_runtime_smoke",
        "task": task,
        "model": "none",
        "family": "non_model_runtime_injection",
        "condition": f"{trigger}:{context_variant}",
        "endpoint_profile": "none",
        "variant": None,
        "inject_mode": trigger,
        "context_variant": context_variant,
        "job_dir": str(job_dir),
        "archived": archived,
        "runtime_smoke": smoke,
        **run,
    }


def aggregate(pack_dir: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    seen_job_dirs: set[Path] = set()
    harbor_roots = sorted(path for path in pack_dir.glob("harbor_runs*") if path.is_dir())
    for harbor_root in harbor_roots:
        default_sdk_live = harbor_root.name == "harbor_runs_sdk_live"
        for job_dir, archived in iter_job_dirs(harbor_root):
            resolved = job_dir.resolve()
            if resolved in seen_job_dirs:
                continue
            seen_job_dirs.add(resolved)
            if job_dir.name.startswith(STATIC_PREFIX):
                row = static_row(job_dir, archived=archived)
            elif job_dir.name.startswith(RUNTIME_PREFIX):
                row = runtime_row(
                    job_dir,
                    default_sdk_live=default_sdk_live,
                    archived=archived,
                )
            elif job_dir.name.startswith(ARTIFACT_HARBOR_PREFIX):
                row = artifact_harbor_row(job_dir, archived=archived)
            elif job_dir.name.startswith(RUNTIME_SMOKE_PREFIX):
                row = runtime_smoke_row(job_dir, archived=archived)
            else:
                row = None
            if row:
                rows.append(row)

    rows.extend(matrix_rows(pack_dir))
    rows.extend(artifact_closure_rows(pack_dir))

    conditions: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = "|".join(
            str(row.get(part) or "")
            for part in ("source", "family", "condition", "model", "endpoint_profile")
        )
        grouped[key].append(row)

    for key, group in grouped.items():
        rewards = [
            row.get("reward")
            for row in group
            if row.get("source") in REWARDED_SOURCES
            and row.get("status") in OUTCOME_STATUSES
            and isinstance(row.get("reward"), (int, float))
        ]
        conditions[key] = {
            "key": key,
            "n_rows": len(group),
            "n_rewarded": len(rewards),
            "mean_reward": sum(rewards) / len(rewards) if rewards else None,
            "status_counts": dict(
                sorted(
                    {
                        status: sum(1 for row in group if row.get("status") == status)
                        for status in {row.get("status") for row in group}
                    }.items()
                )
            ),
        }

    return {
        "pack_dir": str(pack_dir),
        "row_count": len(rows),
        "rows": rows,
        "conditions": list(conditions.values()),
    }


def markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Harbor ICL Baseline Results",
        "",
        f"Pack: `{summary.get('pack_dir')}`",
        f"Rows: `{summary.get('row_count')}`",
        "",
        "Mean reward only includes rows that reached the verifier outcome set: "
        "`passed`, `failed_verifier`, or `injected_but_failed_verifier`. "
        "It is restricted to real model / benchmark rows; no-model artifact "
        "closure and runtime smoke rows are listed as mechanism evidence but "
        "excluded from reward averages. Quota, missing-result, SDK, and Docker "
        "failures are listed as infrastructure states.",
        "",
        "## Runs",
        "",
        "| Source | Task | Model | Condition | Status | Reward | Archived | Trial |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in summary.get("rows", []):
        trial = row.get("trial_dir") or ""
        endpoint = row.get("endpoint_profile") or "auto"
        lines.append(
            "| {source} | `{task}` | `{model}` | `{condition}` (`{endpoint}`) | `{status}` | {reward} | {archived} | `{trial}` |".format(
                source=row.get("source"),
                task=row.get("task"),
                model=row.get("model"),
                condition=row.get("condition"),
                endpoint=endpoint,
                status=row.get("status"),
                reward=row.get("reward"),
                archived=row.get("archived", False),
                trial=trial,
            )
        )
    lines.extend(
        [
            "",
            "## Condition Summary",
            "",
            "| Condition key | Rows | Rewarded | Mean reward | Status counts |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for condition in summary.get("conditions", []):
        lines.append(
            "| `{key}` | {n_rows} | {n_rewarded} | {mean_reward} | `{status_counts}` |".format(
                **condition
            )
        )
    lines.append("")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate Harbor ICL baseline results.")
    parser.add_argument("--pack-dir", type=Path, default=Path("runs/harbor_icl_baseline"))
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = aggregate(args.pack_dir)
    output_json = args.output_json or args.pack_dir / "baseline_results.json"
    output_md = args.output_md or args.pack_dir / "baseline_results.md"
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
