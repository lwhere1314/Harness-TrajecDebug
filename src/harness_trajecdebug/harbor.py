"""Harbor task and run adapters."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from harness_trajecdebug.trace_adapters import normalize_codex_jsonl, normalize_trace_object

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised only on Python 3.10
    tomllib = None  # type: ignore[assignment]


REQUIRED_TASK_FILES = (
    "task.toml",
    "instruction.md",
    "environment/Dockerfile",
    "solution/solve.sh",
    "tests/test.sh",
)


@dataclass
class HarborTask:
    path: str
    name: str | None
    dataset: str | None
    compatible_family: str
    description: str | None
    category: str | None
    tags: list[str]
    valid: bool
    missing: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HarborTrial:
    path: str
    run_name: str
    trial_name: str
    task_name: str | None
    task_path: str | None
    agent_name: str | None
    model_name: str | None
    reward: float | None
    passed: bool | None
    trace_path: str | None
    verifier_log_path: str | None
    result_path: str | None
    trace_format: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_harbor_root() -> Path | None:
    candidates = [
        os.environ.get("HARBOR_ROOT"),
        "/Users/hugo/Desktop/super-refactor/harbor",
        "/Volumes/SSD/terminal-bench-harbor/harbor",
    ]
    for value in candidates:
        if not value:
            continue
        path = Path(value).expanduser()
        if path.exists():
            return path.resolve()
    return None


def default_datasets_root() -> Path | None:
    root = default_harbor_root()
    if root and (root / "datasets").exists():
        return (root / "datasets").resolve()
    return None


def default_runs_root() -> Path | None:
    root = default_harbor_root()
    if root and (root / "runs").exists():
        return (root / "runs").resolve()
    return None


def discover_harbor_tasks(root: Path, limit: int | None = None) -> list[HarborTask]:
    tasks: list[HarborTask] = []
    seen: set[Path] = set()
    for task_toml in sorted(root.rglob("task.toml")):
        task_dir = task_toml.parent.resolve()
        if task_dir in seen:
            continue
        seen.add(task_dir)
        tasks.append(read_harbor_task(task_dir, root=root))
        if limit is not None and len(tasks) >= limit:
            break
    return tasks


def read_harbor_task(path: Path, root: Path | None = None) -> HarborTask:
    path = path.resolve()
    metadata = read_toml(path / "task.toml") if (path / "task.toml").exists() else {}
    task = metadata.get("task") if isinstance(metadata.get("task"), dict) else {}
    meta = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
    missing = [name for name in REQUIRED_TASK_FILES if not (path / name).exists()]
    name = _as_str(task.get("name")) or _as_str(metadata.get("name"))
    dataset = _dataset_name(path, root)
    tags = _as_str_list(meta.get("tags") or task.get("keywords"))
    return HarborTask(
        path=str(path),
        name=name,
        dataset=dataset,
        compatible_family=_compatible_family(path, name, dataset),
        description=_as_str(task.get("description")),
        category=_as_str(meta.get("category")),
        tags=tags,
        valid=not missing,
        missing=missing,
    )


def discover_harbor_trials(run_path: Path) -> list[HarborTrial]:
    run_path = run_path.resolve()
    if _looks_like_trial_dir(run_path):
        return [read_harbor_trial(run_path)]

    trials: list[HarborTrial] = []
    for child in sorted(path for path in run_path.iterdir() if path.is_dir()):
        if _looks_like_trial_dir(child):
            trials.append(read_harbor_trial(child))
            continue
        for grandchild in sorted(path for path in child.iterdir() if path.is_dir()):
            if _looks_like_trial_dir(grandchild):
                trials.append(read_harbor_trial(grandchild))
    return trials


def read_harbor_trial(path: Path) -> HarborTrial:
    path = path.resolve()
    result_path = path / "result.json"
    result = _read_json(result_path)
    config = result.get("config") if isinstance(result.get("config"), dict) else {}
    agent_config = config.get("agent") if isinstance(config.get("agent"), dict) else {}
    task_config = config.get("task") if isinstance(config.get("task"), dict) else {}
    verifier_result = result.get("verifier_result") if isinstance(result.get("verifier_result"), dict) else {}
    rewards = verifier_result.get("rewards") if isinstance(verifier_result.get("rewards"), dict) else {}
    reward = _as_float(rewards.get("reward"))
    if reward is None:
        reward = _read_reward(path)
    trace_path = _find_trace_path(path)
    verifier_path = _find_verifier_log_path(path)

    task_name = _as_str(result.get("task_name")) or _infer_task_name(path)
    agent_name = _as_str(agent_config.get("name")) or _infer_agent_name(path)
    model_name = _as_str(agent_config.get("model_name")) or _infer_model_name(path)
    return HarborTrial(
        path=str(path),
        run_name=path.parent.name,
        trial_name=_as_str(result.get("trial_name")) or path.name,
        task_name=task_name,
        task_path=_as_str(task_config.get("path")),
        agent_name=agent_name,
        model_name=model_name,
        reward=reward,
        passed=(reward >= 1.0 if reward is not None else None),
        trace_path=str(trace_path) if trace_path else None,
        verifier_log_path=str(verifier_path) if verifier_path else None,
        result_path=str(result_path) if result_path.exists() else None,
        trace_format=_trace_format(trace_path),
    )


def normalize_harbor_trial(path: Path) -> dict[str, Any]:
    path = path.resolve()
    trial = read_harbor_trial(path)
    trace_path = Path(trial.trace_path) if trial.trace_path else None

    if trace_path and trace_path.suffix.lower() == ".jsonl":
        trace = normalize_codex_jsonl(trace_path)
    elif trace_path and trace_path.exists():
        trace = normalize_trace_object(_read_json(trace_path), source_path=trace_path)
    else:
        trace = {"steps": [], "verifierLog": ""}

    _prepend_prompt_if_needed(trace, path)
    verifier_log = _read_verifier_log(path)
    if verifier_log:
        existing = trace.get("verifierLog") or ""
        trace["verifierLog"] = "\n".join(part for part in (existing, verifier_log) if part)

    trace["runId"] = trial.trial_name
    trace["harbor"] = trial.to_dict()
    return trace


def write_normalized_harbor_run(run_path: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for trial in discover_harbor_trials(run_path):
        trace = normalize_harbor_trial(Path(trial.path))
        filename = f"{_safe_name(trial.run_name)}__{_safe_name(trial.trial_name)}.json"
        target = output_dir / filename
        target.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(target)
    return written


def read_toml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if tomllib is not None:
        return tomllib.loads(text)
    return _read_minimal_toml(text)


def _looks_like_trial_dir(path: Path) -> bool:
    return (path / "agent").is_dir() and (
        (path / "result.json").exists()
        or (path / "agent" / "trajectory.json").exists()
        or (path / "agent" / "codex-exec.jsonl").exists()
    )


def _find_trace_path(path: Path) -> Path | None:
    candidates = [
        path / "agent" / "trajectory.json",
        path / "agent" / "codex-exec.jsonl",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    sessions = path / "agent" / "local_codex_sessions"
    if sessions.exists():
        jsonl_files = sorted(sessions.glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
        if jsonl_files:
            return jsonl_files[0]
    return None


def _find_verifier_log_path(path: Path) -> Path | None:
    candidates = [
        path / "verifier" / "test-stdout.txt",
        path / "verifier" / "stdout.txt",
        path / "hardened_verifier_smoke2" / "stdout.txt",
        path / "hardened_verifier_smoke" / "stdout.txt",
        path / "supplemental_verifier_no_proxy" / "stdout.txt",
        path / "trial.log",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _read_verifier_log(path: Path) -> str:
    verifier_path = _find_verifier_log_path(path)
    if verifier_path is None:
        return ""
    return verifier_path.read_text(encoding="utf-8", errors="replace")


def _read_reward(path: Path) -> float | None:
    candidates = [
        path / "verifier" / "reward.txt",
        path / "hardened_verifier_smoke2" / "reward.txt",
        path / "hardened_verifier_smoke" / "reward.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            value = _as_float(candidate.read_text(encoding="utf-8", errors="replace").strip())
            if value is not None:
                return value
    return None


def _prepend_prompt_if_needed(trace: dict[str, Any], path: Path) -> None:
    steps = trace.setdefault("steps", [])
    if any(isinstance(step, dict) and step.get("role") == "user" for step in steps):
        return
    prompt_path = path / "agent" / "prompt.txt"
    if not prompt_path.exists():
        return
    prompt = prompt_path.read_text(encoding="utf-8", errors="replace").strip()
    if prompt:
        steps.insert(0, {"index": 0, "role": "user", "text": prompt})
        for index, step in enumerate(steps):
            if isinstance(step, dict):
                step["index"] = index


def _dataset_name(path: Path, root: Path | None) -> str | None:
    if root and root.name == "tasks":
        return root.parent.name
    try:
        relative = path.relative_to(root.resolve()) if root else path
    except ValueError:
        relative = path
    parts = relative.parts
    if "tasks" in parts:
        idx = parts.index("tasks")
        if idx > 0:
            return parts[idx - 1]
    if len(parts) >= 2:
        return parts[0]
    return path.parent.name


def _compatible_family(path: Path, name: str | None, dataset: str | None) -> str:
    identity = " ".join(part for part in (str(path), name or "", dataset or "")).lower()
    if "swe-bench-pro" in identity or "swebench-pro" in identity:
        return "swe-bench-pro"
    if "terminal-bench" in identity or "terminal_bench" in identity:
        return "terminal-bench"
    return "harbor-compatible"


def _trace_format(path: Path | None) -> str | None:
    if path is None:
        return None
    if path.suffix.lower() == ".jsonl":
        return "codex-jsonl"
    if path.name == "trajectory.json":
        return "atif-json"
    return "json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return obj if isinstance(obj, dict) else {}


def _read_minimal_toml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current: dict[str, Any] = result
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[[") and line.endswith("]]"):
            section = line[2:-2].strip()
            current = result.setdefault(section, {})  # type: ignore[assignment]
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            current = result.setdefault(section, {})  # type: ignore[assignment]
            continue
        if "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        current[key] = _parse_toml_value(value)
    return result


def _parse_toml_value(value: str) -> Any:
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_toml_value(item.strip()) for item in inner.split(",")]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _infer_task_name(path: Path) -> str | None:
    match = re.search(r"tb\d+-([a-z0-9-]+)-", path.name.lower())
    if match:
        return match.group(1)
    if "__" in path.name:
        return path.name.split("__", 1)[0]
    return None


def _infer_agent_name(path: Path) -> str | None:
    identity = str(path).lower()
    if "claude-code" in identity:
        return "claude-code"
    if "codex" in identity:
        return "codex"
    if "kimi-code" in identity:
        return "kimi-code"
    return None


def _infer_model_name(path: Path) -> str | None:
    identity = str(path).lower()
    for pattern in (r"kimi-k2\.6", r"kimi-k26", r"kimi-k2\.5", r"kimi-k25", r"gpt55", r"gpt-5\.5"):
        match = re.search(pattern, identity)
        if match:
            value = match.group(0)
            return {
                "kimi-k26": "kimi-k2.6",
                "kimi-k25": "kimi-k2.5",
                "gpt55": "gpt-5.5",
            }.get(value, value)
    return None


def _safe_name(value: str | None) -> str:
    text = value or "run"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-") or "run"


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
