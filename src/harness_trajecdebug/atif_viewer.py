"""Export Harbor runs into the ATIF trajectory viewer local bundle format."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from harness_trajecdebug.diagnose import diagnose_trace
from harness_trajecdebug.harbor import (
    HarborTrial,
    default_harbor_root,
    discover_harbor_trials,
    normalize_harbor_trial,
    read_harbor_task,
)


DEFAULT_VIEWER_ROOT = Path("/Users/hugo/Documents/terminal-bench-3.0-PR/ATIF-trajectory-viewer")

MAX_TEXT_LENGTH = 80_000
MAX_FILE_TEXT_LENGTH = 200_000
MAX_TASK_FILES = 80


def viewer_info(viewer_root: Path = DEFAULT_VIEWER_ROOT) -> dict[str, Any]:
    """Return a compact health check for an ATIF trajectory viewer checkout."""

    viewer_root = viewer_root.expanduser().resolve()
    public_dir = viewer_root / "public"
    dataset_path = public_dir / "dataset.json"
    local_index_path = public_dir / "local" / "local-bundles.json"
    dataset = _read_json(dataset_path)
    local_index = _read_json(local_index_path)
    return {
        "root": str(viewer_root),
        "exists": viewer_root.exists(),
        "package_json": str(viewer_root / "package.json") if (viewer_root / "package.json").exists() else None,
        "dataset": str(dataset_path) if dataset_path.exists() else None,
        "local_index": str(local_index_path) if local_index_path.exists() else None,
        "tasks": _count_list(dataset.get("tasks")),
        "runs": _count_list(dataset.get("runs")),
        "local_bundles": _count_list(local_index.get("bundles")),
    }


def export_harbor_run_to_viewer(
    run_path: Path,
    viewer_root: Path = DEFAULT_VIEWER_ROOT,
    label: str | None = None,
    diagnose: bool = False,
) -> dict[str, Any]:
    """Write a Harbor run or trial as a local ATIF viewer bundle.

    The viewer already loads ``public/local/local-bundles.json``. This function
    keeps all generated files under that local namespace so the imported run can
    sit beside the built-in fixture dataset without changing the viewer app.
    """

    run_path = run_path.expanduser().resolve()
    viewer_root = viewer_root.expanduser().resolve()
    trials = discover_harbor_trials(run_path)
    if not trials:
        raise ValueError(f"No Harbor trials found under {run_path}")

    bundle_id = _safe_name(label or _bundle_name(run_path, trials))
    bundle_dir = viewer_root / "public" / "local" / "runs" / bundle_id
    payload_dir = bundle_dir / "payloads"
    normalized_dir = bundle_dir / "normalized"
    diagnosis_dir = bundle_dir / "diagnoses"
    payload_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    if diagnose:
        diagnosis_dir.mkdir(parents=True, exist_ok=True)

    vendor = {
        "id": "local-harness-trajecdebug",
        "name": "Harness-TrajecDebug Local",
    }
    agents: dict[str, dict[str, Any]] = {}
    tasks: dict[str, dict[str, Any]] = {}
    runs: list[dict[str, Any]] = []
    payloads: list[Path] = []
    normalized_traces: list[Path] = []
    diagnoses: list[Path] = []

    for trial in trials:
        trace = normalize_harbor_trial(Path(trial.path))
        run_id = _run_id(bundle_id, trial)
        task_id = _task_id(trial)
        agent_id = _agent_id(trial)

        task = tasks.get(task_id)
        if task is None:
            task = _viewer_task(task_id, trial, trace, vendor["id"])
            tasks[task_id] = task

        agents.setdefault(agent_id, _viewer_agent(agent_id, trial, vendor["id"]))

        payload = {
            "steps": [_clean_step(step) for step in trace.get("steps", []) if isinstance(step, dict)],
            "verifierLog": _clip_text(trace.get("verifierLog") or trace.get("verifier_log") or ""),
        }
        payload_path = payload_dir / f"{run_id}.json"
        _write_json(payload_path, payload)
        payloads.append(payload_path)

        normalized_path = normalized_dir / f"{run_id}.json"
        _write_json(normalized_path, _redact_object(trace))
        normalized_traces.append(normalized_path)

        diagnosis_path: Path | None = None
        diagnosis_obj: dict[str, Any] | None = None
        if diagnose:
            diagnosis = diagnose_trace(normalized_path, run_id=run_id)
            diagnosis_obj = asdict(diagnosis)
            diagnosis_path = diagnosis_dir / f"{run_id}-diagnosis.json"
            _write_json(diagnosis_path, diagnosis_obj)
            diagnoses.append(diagnosis_path)

        runs.append(_viewer_run(run_id, task_id, agent_id, vendor["id"], trial, trace, bundle_id, diagnosis_obj))

    bundle = {
        "vendors": [vendor],
        "agents": sorted(agents.values(), key=lambda item: item["id"]),
        "tasks": sorted(tasks.values(), key=lambda item: item["id"]),
        "runs": runs,
    }
    bundle_path = bundle_dir / "viewer-bundle.json"
    _write_json(bundle_path, bundle)
    index_path = _upsert_local_bundle_index(viewer_root, bundle_id, bundle_path, run_path, len(runs))

    return {
        "viewer_root": str(viewer_root),
        "bundle_id": bundle_id,
        "bundle_path": str(bundle_path),
        "local_index": str(index_path),
        "runs": len(runs),
        "tasks": len(tasks),
        "agents": len(agents),
        "payloads": [str(path) for path in payloads],
        "normalized_traces": [str(path) for path in normalized_traces],
        "diagnoses": [str(path) for path in diagnoses],
    }


def _viewer_task(task_id: str, trial: HarborTrial, trace: dict[str, Any], vendor_id: str) -> dict[str, Any]:
    task_dir = _resolve_task_path(trial.task_path)
    files: list[dict[str, Any]] = []
    task_meta: dict[str, Any] = {}
    if task_dir:
        harbor_task = read_harbor_task(task_dir, root=_task_root(task_dir))
        task_meta = harbor_task.to_dict()
        instruction_path = task_dir / "instruction.md"
        instruction = _read_text(instruction_path) or _first_user_prompt(trace)
        files = _collect_task_files(task_dir)
        title = harbor_task.name or trial.task_name or task_dir.name
        category = harbor_task.category or harbor_task.compatible_family
        tags = harbor_task.tags or [_task_family(trial)]
    else:
        instruction = _first_user_prompt(trace)
        title = trial.task_name or "Harbor task"
        category = _task_family(trial)
        tags = [_task_family(trial)]

    metadata = {
        "harbor_task_name": trial.task_name,
        "harbor_task_path": trial.task_path,
        "source": "harness-trajecdebug",
    }
    if task_meta:
        metadata["harbor_task"] = task_meta

    return {
        "id": task_id,
        "vendorId": vendor_id,
        "title": title,
        "source": "harbor",
        "category": category or "harbor-compatible",
        "difficulty": "local",
        "instruction": instruction,
        "tags": sorted({tag for tag in tags if tag}),
        "files": files,
        "metadata": {key: value for key, value in metadata.items() if value not in (None, "", [])},
    }


def _viewer_agent(agent_id: str, trial: HarborTrial, vendor_id: str) -> dict[str, Any]:
    agent_name = trial.agent_name or "harbor-agent"
    model_name = trial.model_name or "unknown-model"
    if "claude" in agent_name.lower():
        harness = "Claude Code"
    elif "codex" in agent_name.lower():
        harness = "Codex"
    elif "kimi" in agent_name.lower():
        harness = "Kimi Code"
    else:
        harness = agent_name

    model_family = "Moonshot Kimi" if "kimi" in model_name.lower() else model_name
    return {
        "id": agent_id,
        "vendorId": vendor_id,
        "name": f"{harness} + {model_name}",
        "harness": harness,
        "model": model_name,
        "modelFamily": model_family,
        "harnessFamily": agent_name,
        "metadata": {
            "agent_name": trial.agent_name,
            "model_name": trial.model_name,
        },
    }


def _viewer_run(
    run_id: str,
    task_id: str,
    agent_id: str,
    vendor_id: str,
    trial: HarborTrial,
    trace: dict[str, Any],
    bundle_id: str,
    diagnosis: dict[str, Any] | None,
) -> dict[str, Any]:
    step_count = len([step for step in trace.get("steps", []) if isinstance(step, dict)])
    passed = trial.passed
    status = "passed" if passed is True else "failed" if passed is False else "completed"
    run: dict[str, Any] = {
        "id": run_id,
        "taskId": task_id,
        "agentId": agent_id,
        "vendorId": vendor_id,
        "format": "atif" if trial.trace_format == "atif-json" else "harbor",
        "status": status,
        "passed": passed,
        "reward": trial.reward,
        "steps": [],
        "stepCount": step_count,
        "hasVerifierLog": bool(trace.get("verifierLog") or trace.get("verifier_log")),
        "payloadUrl": f"local/runs/{bundle_id}/payloads/{run_id}.json",
        "turns": step_count,
        "durationSec": _duration_sec(Path(trial.path)),
        "sourceRunRoot": trial.path,
        "metadata": {
            "harbor_run_name": trial.run_name,
            "harbor_trial_name": trial.trial_name,
            "trace_path": trial.trace_path,
            "result_path": trial.result_path,
            "trace_format": trial.trace_format,
        },
    }
    if diagnosis:
        run["grade"] = {
            "outcome": diagnosis.get("outcome"),
            "taskFamily": diagnosis.get("task_family"),
            "finalFailure": diagnosis.get("final_failure"),
            "criticalStepCount": len(diagnosis.get("critical_steps") or []),
        }
        run["diagnosisUrl"] = f"local/runs/{bundle_id}/diagnoses/{run_id}-diagnosis.json"
    return _drop_empty(run)


def _collect_task_files(task_dir: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    skip_dirs = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache"}
    for path in sorted(task_dir.rglob("*")):
        if not path.is_file() or any(part in skip_dirs for part in path.parts):
            continue
        try:
            relative = path.relative_to(task_dir).as_posix()
        except ValueError:
            relative = path.name
        if len(files) >= MAX_TASK_FILES:
            files.append({"path": "...", "language": "text", "content": "File list truncated."})
            break
        text = _read_text(path)
        if text is None:
            continue
        files.append(
            {
                "path": relative,
                "language": _language_for(path),
                "content": _clip_text(text, MAX_FILE_TEXT_LENGTH),
            }
        )
    return files


def _upsert_local_bundle_index(
    viewer_root: Path,
    bundle_id: str,
    bundle_path: Path,
    source_path: Path,
    run_count: int,
) -> Path:
    index_path = viewer_root / "public" / "local" / "local-bundles.json"
    index = _read_json(index_path)
    bundles = index.get("bundles")
    if not isinstance(bundles, list):
        bundles = []

    entry = {
        "id": bundle_id,
        "title": bundle_id,
        "bundleUrl": _asset_relative(viewer_root, bundle_path),
        "description": f"Imported {run_count} Harbor run(s) from {source_path}",
        "metadata": {
            "source": "harness-trajecdebug",
            "sourcePath": str(source_path),
        },
    }
    bundles = [item for item in bundles if not (isinstance(item, dict) and item.get("id") == bundle_id)]
    bundles.append(entry)
    index["bundles"] = bundles
    _write_json(index_path, index)
    return index_path


def _resolve_task_path(value: str | None) -> Path | None:
    if not value:
        return None
    raw = Path(value).expanduser()
    candidates = [raw]
    root = default_harbor_root()
    if root:
        candidates.extend([root.parent / raw, root / raw])
    candidates.extend([Path("/Users/hugo/Desktop/super-refactor") / raw, Path("/Volumes/SSD/terminal-bench-harbor") / raw])
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if (resolved / "task.toml").exists():
            return resolved
    for search_root in _task_cache_roots(root):
        for candidate in search_root.glob(f"*/{raw.name}"):
            if (candidate / "task.toml").exists():
                return candidate.resolve()
    return None


def _task_cache_roots(root: Path | None) -> list[Path]:
    values = [
        Path.home() / ".cache" / "harbor" / "tasks",
        Path("/Users/hugo/Desktop/super-refactor/harbor/datasets/swebenchpro-ansible-candidates"),
        Path("/Volumes/SSD/terminal-bench-harbor/harbor/datasets/swebenchpro-ansible-candidates"),
    ]
    if root:
        values.append(root / "datasets" / "swebenchpro-ansible-candidates")
    return [path for path in values if path.exists()]


def _task_root(task_dir: Path) -> Path | None:
    parts = task_dir.parts
    if "tasks" not in parts:
        return None
    index = parts.index("tasks")
    return Path(*parts[: index + 1])


def _bundle_name(run_path: Path, trials: list[HarborTrial]) -> str:
    if len(trials) == 1 and Path(trials[0].path).resolve() == run_path.resolve():
        return trials[0].run_name if trials[0].run_name != run_path.parent.name else run_path.name
    return run_path.name


def _run_id(bundle_id: str, trial: HarborTrial) -> str:
    base = "__".join(part for part in (bundle_id, trial.task_name, trial.trial_name) if part)
    return _safe_name(base)


def _task_id(trial: HarborTrial) -> str:
    return "local-" + _safe_name(trial.task_name or "harbor-task")


def _agent_id(trial: HarborTrial) -> str:
    return "local-" + _safe_name("-".join(part for part in (trial.agent_name, trial.model_name) if part) or "agent")


def _task_family(trial: HarborTrial) -> str:
    identity = " ".join(part for part in (trial.task_name, trial.task_path) if part).lower()
    if "swebench" in identity or "swe-bench" in identity:
        return "swe-bench-pro"
    if "terminal-bench" in identity:
        return "terminal-bench"
    return "harbor-compatible"


def _first_user_prompt(trace: dict[str, Any]) -> str:
    for step in trace.get("steps") or []:
        if isinstance(step, dict) and step.get("role") == "user":
            text = str(step.get("text") or "").strip()
            if text:
                return _clip_text(text)
    return ""


def _duration_sec(trial_dir: Path) -> float | None:
    result = _read_json(trial_dir / "result.json")
    for key in ("duration_sec", "duration_seconds", "elapsed_seconds"):
        value = result.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _clean_step(step: dict[str, Any]) -> dict[str, Any]:
    return _drop_empty(_redact_object({key: _clip_value(value) for key, value in step.items()}))


def _clip_value(value: Any) -> Any:
    if isinstance(value, str):
        return _clip_text(value)
    if isinstance(value, list):
        return [_clip_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _clip_value(item) for key, item in value.items()}
    return value


def _clip_text(value: Any, limit: int = MAX_TEXT_LENGTH) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return _redact_text(text)
    return _redact_text(text[:limit] + f"\n...[truncated {len(text) - limit} chars]")


def _redact_object(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        return [_redact_object(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_object(item) for key, item in value.items()}
    return value


def _redact_text(text: str) -> str:
    patterns = [
        r"((?:SEED_CODING_PLAN|TOKEN_PLAN|ANTHROPIC|OPENAI|MOONSHOT|KIMI)[A-Z0-9_]*(?:API_KEY|AUTH_TOKEN|TOKEN|KEY)=)[^\s\"']+",
        r"((?:api[_-]?key|auth[_-]?token|bearer)\s*[:=]\s*)[^\s\"']+",
    ]
    result = text
    for pattern in patterns:
        result = re.sub(pattern, r"\1<redacted>", result, flags=re.IGNORECASE)
    return result


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in (None, "", [], {})}


def _asset_relative(viewer_root: Path, path: Path) -> str:
    public = viewer_root / "public"
    try:
        return path.relative_to(public).as_posix()
    except ValueError:
        return path.as_posix()


def _language_for(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".md": "markdown",
        ".py": "python",
        ".sh": "bash",
        ".toml": "toml",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".jsx": "jsx",
        ".txt": "text",
        ".dockerfile": "dockerfile",
    }.get(suffix, "text")


def _safe_name(value: str | None) -> str:
    text = value or "run"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-") or "run"


def _count_list(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _read_text(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
