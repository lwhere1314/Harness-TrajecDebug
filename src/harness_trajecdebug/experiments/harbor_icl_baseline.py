"""Build Harbor ICL baseline artifacts from existing teacher trajectories."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_TEACHER_STATES = [
    Path("/Volumes/SSD/terminal-bench-harbor/harbor/runs/tb21-kimi-k25-failures-codex-gpt55-host-20260603Tbatch/state.json"),
    Path("/Volumes/SSD/terminal-bench-harbor/harbor/runs/tb21-k26-true-fails-codex-gpt55-host-20260603-clean4/state.json"),
]

DEFAULT_TARGET_TASKS = [
    "cancel-async-tasks",
    "count-dataset-tokens",
    "query-optimize",
    "break-filter-js-from-html",
]
DEFAULT_HARBOR_RUNNER = Path("/Users/hugo/.codex/skills/terminal-bench-harbor-runner/scripts/run_terminal_bench_harbor.sh")
LOCALHOST_NO_PROXY = "localhost,127.0.0.1,::1"

TEXT_ARTIFACT_SUFFIXES = {
    ".c",
    ".cpp",
    ".fasta",
    ".h",
    ".html",
    ".json",
    ".md",
    ".proto",
    ".py",
    ".rs",
    ".sh",
    ".sql",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
NOISY_ARTIFACT_NAMES = {
    "server.log",
    "server.pid",
}
TASK_ARTIFACT_PRIORITY = {
    "headless-terminal": [
        "headless_terminal.py",
    ],
    "kv-store-grpc": [
        "server.py",
        "kv_store_pb2.py",
        "kv_store_pb2_grpc.py",
        "kv-store.proto",
    ],
    "torch-tensor-parallelism": [
        "parallel_linear.py",
    ],
    "torch-pipeline-parallelism": [
        "pipeline_parallel.py",
    ],
    "video-processing": [
        "output.toml",
        "jump_analyzer.py",
    ],
    "largest-eigenval": [
        "eigen.py",
    ],
}


@dataclass
class TeacherExample:
    task: str
    reward: float | None
    source_run: str
    source_state: str
    task_dir: str
    task_run_dir: str
    event_log: str | None
    verifier_reward: str | None
    verifier_summary: dict[str, Any]
    instruction: str
    debug_card: str
    debug_action_card: str
    prompt_filtered_card: str
    raw_trace_card: str
    outcome_card: str


@dataclass
class BuildResult:
    output_dir: str
    teacher_states: list[str]
    target_tasks: list[str]
    variants: list[str]
    examples: list[dict[str, Any]]
    run_script: str
    report: str


def read_text(path: Path | None, default: str = "") -> str:
    if path is None or not path.exists() or not path.is_file():
        return default
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def compact_space(text: str, limit: int = 1200) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def fenced(name: str, text: str, limit: int = 5000) -> str:
    text = text.strip()
    if len(text) > limit:
        text = text[: limit - 3].rstrip() + "..."
    return f"```{name}\n{text}\n```"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verifier_summary(task_run_dir: Path) -> tuple[str | None, dict[str, Any]]:
    reward = read_text(task_run_dir / "verifier" / "reward.txt").strip() or None
    ctrf_path = task_run_dir / "verifier" / "ctrf.json"
    if not ctrf_path.exists():
        return reward, {}
    try:
        ctrf = load_json(ctrf_path)
    except json.JSONDecodeError:
        return reward, {}
    summary = ctrf.get("results", {}).get("summary") or {}
    return reward, summary


def event_items(event_log: Path | None) -> list[dict[str, Any]]:
    if event_log is None or not event_log.exists():
        return []

    items: list[dict[str, Any]] = []
    for line in event_log.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item")
        if not isinstance(item, dict) or event.get("type") != "item.completed":
            continue
        item_type = item.get("type")
        if item_type == "agent_message":
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                items.append({"type": "agent_message", "text": text.strip()})
        elif item_type == "command_execution" and item.get("status") == "completed":
            command = item.get("command")
            if not isinstance(command, str) or not command.strip():
                continue
            output = item.get("aggregated_output")
            items.append(
                {
                    "type": "command_execution",
                    "command": command.strip(),
                    "exit_code": item.get("exit_code"),
                    "output": output.strip() if isinstance(output, str) else "",
                }
            )
    return items


def interesting_trace_items(items: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    keywords = re.compile(
        r"pytest|verifier|py_compile|inspect|assert|diff|EXPLAIN|sqlite|/app/run\.py|/app/sol\.sql|model\.bin|P@1|fasttext",
        re.I,
    )
    selected: list[dict[str, Any]] = []
    for item in items:
        blob = json.dumps(item, ensure_ascii=False)
        if keywords.search(blob):
            selected.append(item)
    selected.extend(item for item in items[-4:] if item not in selected)

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in selected:
        key = json.dumps(item, sort_keys=True, ensure_ascii=False)[:500]
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def debug_trace_items(items: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in interesting_trace_items(items, limit=limit * 2):
        blob = json.dumps(item, ensure_ascii=False)
        if "terminal-bench-harbor-runner" in blob or "SKILL.md" in blob or "runner guidance" in blob:
            continue
        result.append(item)
        if len(result) >= limit:
            break
    return result


def container_artifact_root(task_record: dict[str, Any]) -> Path | None:
    artifacts = task_record.get("container_artifacts")
    if not isinstance(artifacts, dict):
        return None
    inspect_path = artifacts.get("inspect")
    if isinstance(inspect_path, str):
        parent = Path(inspect_path).parent
        if parent.exists():
            return parent
    copied = artifacts.get("copied")
    if isinstance(copied, list):
        for entry in copied:
            if not isinstance(entry, dict):
                continue
            dest = entry.get("destination")
            if isinstance(dest, str):
                path = Path(dest)
                if path.exists():
                    return path.parent
    return None


def artifact_snippets(task: str, task_record: dict[str, Any]) -> list[tuple[str, str]]:
    root = container_artifact_root(task_record)
    if root is None:
        return []
    candidates: list[Path] = []
    app_root = root / "app"
    for name in TASK_ARTIFACT_PRIORITY.get(task, []):
        candidates.append(app_root / name)
    candidates.extend([
        root / "app" / "run.py",
        root / "app" / "sol.sql",
        root / "app" / "out.html",
        root / "app" / "solution.py",
        root / "app" / "answer.txt",
        root / "app" / "out.txt",
        root / "app" / "output.txt",
        root / "app" / "result.txt",
        root / "app" / "model.txt",
    ])
    snippets: list[tuple[str, str]] = []
    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if path.exists() and path.is_file():
            snippets.append((str(path), read_text(path)))
    if snippets:
        return snippets

    if app_root.exists():
        selected: list[Path] = []
        for path in sorted(app_root.rglob("*"), key=generic_artifact_sort_key):
            if len(selected) >= 4:
                break
            if not is_safe_text_artifact(path):
                continue
            selected.append(path)
        for path in selected:
            snippets.append((str(path), read_text(path)))
    return snippets


def is_safe_text_artifact(path: Path, max_bytes: int = 16_000) -> bool:
    if not path.is_file():
        return False
    if "__pycache__" in path.parts or path.name.startswith("."):
        return False
    if path.name in NOISY_ARTIFACT_NAMES or path.suffix in {".pyc", ".pid", ".log"}:
        return False
    if path.suffix and path.suffix not in TEXT_ARTIFACT_SUFFIXES:
        return False
    try:
        raw = path.read_bytes()
    except OSError:
        return False
    if not raw or len(raw) > max_bytes or b"\x00" in raw:
        return False
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def generic_artifact_sort_key(path: Path) -> tuple[int, int, str]:
    name = path.name
    if name in {
        "run.py",
        "server.py",
        "headless_terminal.py",
        "parallel_linear.py",
        "pipeline_parallel.py",
        "jump_analyzer.py",
    }:
        return (0, path.stat().st_size if path.exists() else 0, str(path))
    if name in {"sol.sql", "answer.txt", "out.txt", "result.txt", "output.toml", "move.txt"}:
        return (1, path.stat().st_size if path.exists() else 0, str(path))
    if path.suffix in {".py", ".sql", ".proto", ".sh", ".c", ".rs", ".toml", ".json", ".txt"}:
        return (2, path.stat().st_size if path.exists() else 0, str(path))
    return (3, path.stat().st_size if path.exists() else 0, str(path))


def artifact_label(path: str) -> str:
    marker = "/app/"
    if marker in path:
        return marker + path.split(marker, 1)[1]
    return Path(path).name


def strategy_notes(task: str) -> list[str]:
    strategies = {
        "cancel-async-tasks": [
            "Keep the public contract small: implement only /app/run.py with async run_tasks(...).",
            "Treat cancellation cleanup as a first-class requirement: cancel active tasks and await them with return_exceptions=True.",
            "Propagate the first task error or outer cancellation after cleanup; do not silently swallow failures.",
            "Verify both syntax and behavior with focused async probes before relying on the final verifier.",
        ],
        "query-optimize": [
            "Preserve exact output first, then optimize; never modify the SQLite database.",
            "Replace correlated repeated work with pre-aggregated CTEs and rank the top rows before expensive joins.",
            "Use SQLite syntax only, end /app/sol.sql with one semicolon, and keep comments out of the final file.",
            "Check byte-for-byte output equivalence and inspect the query plan before final promotion.",
        ],
        "train-fasttext": [
            "Optimize size and accuracy jointly; do not let the final artifact close without both gates.",
            "Use cheap fastText CLI sweeps to map the compact size-accuracy frontier early.",
            "Promote only after checking /app/model.bin, size, loadability, and verifier-equivalent accuracy.",
        ],
    }
    return strategies.get(
        task,
        [
            "Extract the task contract into artifact, verifier, and metric requirements before acting.",
            "Keep a state table of candidate artifacts, commands, errors, and validation results.",
            "Promote the final artifact only after a verifier-equivalent closure check.",
        ],
    )


def make_outcome_card(task: str, reward: float | None, summary: dict[str, Any]) -> str:
    lines = [
        f"Task: {task}",
        f"Teacher outcome: reward={reward}",
    ]
    if summary:
        lines.append(
            "Verifier summary: "
            + ", ".join(f"{key}={summary.get(key)}" for key in ("tests", "passed", "failed") if key in summary)
        )
    return "\n".join(lines)


def make_raw_trace_card(task: str, items: list[dict[str, Any]]) -> str:
    lines = [f"# Raw Teacher Trace: {task}", ""]
    for index, item in enumerate(interesting_trace_items(items), start=1):
        if item["type"] == "agent_message":
            lines.extend([f"{index}. Agent message:", compact_space(item["text"], 900), ""])
        else:
            output = compact_space(item.get("output") or "", 700)
            lines.extend(
                [
                    f"{index}. Command exit={item.get('exit_code')}:",
                    fenced("bash", item["command"], 900),
                    ("Output: " + output if output else "Output: <empty>"),
                    "",
                ]
            )
    return "\n".join(lines).strip()


def make_prompt_filtered_card(
    task: str,
    reward: float | None,
    summary: dict[str, Any],
    snippets: list[tuple[str, str]],
    items: list[dict[str, Any]],
) -> str:
    """Generic prompt-filter baseline without HTD process labels.

    This approximates a frozen "ask an LLM to keep useful teacher snippets"
    baseline: retain final artifacts, verifier evidence, and the most
    task-relevant commands/messages, but do not expose reference/state/
    commitment structure or critical-step labels.
    """

    lines = [
        f"# Prompt-Filtered Teacher Snippets: {task}",
        "",
        "This card is a generic filtered teacher-log baseline. It keeps useful",
        "snippets from a previous passing run but does not expose the structured",
        "process-diagnosis schema used by the main method.",
        "",
        "## Outcome",
        make_outcome_card(task, reward, summary),
    ]

    if snippets:
        lines.extend(["", "## Captured artifact snippets"])
        for path, text in snippets[:2]:
            suffix = Path(path).name
            if suffix.endswith(".py"):
                lang = "python"
            elif suffix.endswith(".sql"):
                lang = "sql"
            elif suffix.endswith(".html"):
                lang = "html"
            else:
                lang = "text"
            lines.extend([f"Artifact: {artifact_label(path)}", fenced(lang, text, 3600), ""])

    trace_bits = debug_trace_items(items, limit=8)
    if trace_bits:
        lines.append("## Filtered log snippets")
        for item in trace_bits:
            if item["type"] == "command_execution":
                command = compact_space(item["command"], 360)
                output = compact_space(item.get("output") or "", 360)
                lines.append(f"- command exit={item.get('exit_code')}: {command}")
                if output:
                    lines.append(f"  output: {output}")
            elif item["type"] == "agent_message":
                lines.append(f"- agent: {compact_space(item['text'], 360)}")

    lines.extend(
        [
            "",
            "## Use policy",
            "- Treat these as examples from a previous successful run, not as new task requirements.",
            "- Reuse snippets only when they match the live task contract and artifact path.",
            "- Verify the final artifact in the live environment before stopping.",
        ]
    )
    return "\n".join(lines).strip()


def make_debug_card(
    task: str,
    instruction: str,
    reward: float | None,
    summary: dict[str, Any],
    snippets: list[tuple[str, str]],
    items: list[dict[str, Any]],
) -> str:
    lines = [
        f"# Debug-Trajectory Example: {task}",
        "",
        "## Reference view",
        compact_space(instruction, 1000),
        "",
        "## State view",
        make_outcome_card(task, reward, summary),
        "",
        "## Commitment view",
    ]
    lines.extend(f"- {note}" for note in strategy_notes(task))
    lines.extend(
        [
            "",
            "## Runtime reuse protocol",
            "- Treat reusable artifacts below as candidate artifacts from a teacher run that passed the verifier.",
            "- If the live task contract and artifact path match, promote the artifact first and run the cheapest closure check.",
            "- Do not spend the main budget on heavyweight recomputation only to reproduce a verified artifact; recompute only when the artifact is missing, mismatched, or fails validation.",
        ]
    )
    lines.extend(["", "## Reusable evidence"])
    for path, text in snippets[:2]:
        suffix = Path(path).name
        lang = "python" if suffix.endswith(".py") else "sql" if suffix.endswith(".sql") else "text"
        lines.extend([f"Artifact: {artifact_label(path)}", fenced(lang, text, 4200), ""])

    trace_bits = debug_trace_items(items, limit=6)
    if trace_bits:
        lines.append("## Verifier and promotion trace")
        for item in trace_bits:
            if item["type"] == "command_execution":
                lines.append(f"- command exit={item.get('exit_code')}: {compact_space(item['command'], 280)}")
            elif item["type"] == "agent_message":
                lines.append(f"- agent: {compact_space(item['text'], 280)}")
    return "\n".join(lines).strip()


def _artifact_write_command(label: str, text: str) -> str | None:
    if not label.startswith("/app/"):
        return None
    payload = text.rstrip("\n") + "\n"
    return "\n".join(
        [
            f"mkdir -p {json.dumps(str(Path(label).parent))}",
            f"cat > {json.dumps(label)} <<'HTD_ARTIFACT_EOF'",
            payload.rstrip("\n"),
            "HTD_ARTIFACT_EOF",
        ]
    )


def make_debug_action_card(
    task: str,
    instruction: str,
    reward: float | None,
    summary: dict[str, Any],
    snippets: list[tuple[str, str]],
) -> str:
    lines = [
        f"# Debug-Action Card: {task}",
        "",
        "This is a same-task repair smoke-test card generated from a teacher run",
        "that already passed the verifier. Use it only when the live task contract",
        "matches the reference below.",
        "",
        "## Reference view",
        compact_space(instruction, 1000),
        "",
        "## Teacher outcome",
        make_outcome_card(task, reward, summary),
        "",
        "## Recommended next action",
    ]

    commands: list[str] = []
    for path, text in snippets[:3]:
        label = artifact_label(path)
        command = _artifact_write_command(label, text)
        if command is not None:
            commands.append(command)

    if commands:
        commands.append(
            "\n".join(
                [
                    "python3 - <<'PY'",
                    "from pathlib import Path",
                    "paths = [",
                    *[
                        f"    Path({json.dumps(artifact_label(path))}),"
                        for path, _ in snippets[:3]
                        if artifact_label(path).startswith("/app/")
                    ],
                    "]",
                    "for path in paths:",
                    "    data = path.read_text(encoding='utf-8', errors='replace')",
                    "    print(f'{path}: {len(data)} bytes, preview={data[:80]!r}')",
                    "PY",
                ]
            )
        )
        lines.extend(
            [
                "Run this before any expensive recomputation or dependency installation:",
                fenced("bash", "\n\n".join(commands), 24000),
            ]
        )
    else:
        lines.append(
            "No direct text artifact was captured. Fall back to the Debug-Trajectory card."
        )

    lines.extend(
        [
            "",
            "## Guardrails",
            "- If the live task differs from the reference, do not reuse the artifact blindly.",
            "- If the materialized artifact fails a cheap closure check, switch to recomputation.",
            "- Do not install heavyweight dependencies solely to reproduce the verified teacher artifact.",
            "- After materializing the artifact, stop once the required file exists and matches the contract; let the official verifier grade it.",
        ]
    )
    return "\n".join(lines).strip()


def load_teacher_examples(state_paths: list[Path]) -> dict[str, TeacherExample]:
    examples: dict[str, TeacherExample] = {}
    for state_path in state_paths:
        if not state_path.exists():
            continue
        state = load_json(state_path)
        run_name = state.get("run_name") or Path(state.get("run_root") or state_path.parent).name
        tasks = state.get("tasks") or {}
        for task, record in tasks.items():
            if not isinstance(record, dict):
                continue
            reward = record.get("reward")
            if reward is not None:
                try:
                    reward = float(reward)
                except (TypeError, ValueError):
                    reward = None
            if reward != 1.0:
                continue

            task_run_dir = Path(record.get("task_run_dir") or "")
            task_dir = Path(record.get("task_dir") or "")
            if not task_run_dir.exists() or not task_dir.exists():
                continue
            event_log = task_run_dir / "agent" / "codex-events.jsonl"
            instruction = read_text(task_dir / "instruction.md")
            reward_text, summary = verifier_summary(task_run_dir)
            items = event_items(event_log if event_log.exists() else None)
            snippets = artifact_snippets(task, record)

            candidate = TeacherExample(
                task=task,
                reward=reward,
                source_run=str(run_name),
                source_state=str(state_path),
                task_dir=str(task_dir),
                task_run_dir=str(task_run_dir),
                event_log=str(event_log) if event_log.exists() else None,
                verifier_reward=reward_text,
                verifier_summary=summary,
                instruction=instruction,
                debug_card=make_debug_card(task, instruction, reward, summary, snippets, items),
                debug_action_card=make_debug_action_card(task, instruction, reward, summary, snippets),
                prompt_filtered_card=make_prompt_filtered_card(task, reward, summary, snippets, items),
                raw_trace_card=make_raw_trace_card(task, items),
                outcome_card=make_outcome_card(task, reward, summary),
            )
            current = examples.get(task)
            if current is None:
                examples[task] = candidate
    return examples


def trim_payload(text: str, max_chars: int | None) -> str:
    if max_chars is None or max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[: max_chars - 80].rstrip() + "\n\n[TRUNCATED TO FIXED ICL CONTEXT BUDGET]"


def prompt_for_variant(
    task: str,
    instruction: str,
    example: TeacherExample | None,
    variant: str,
    max_context_chars: int | None = None,
) -> str:
    header = instruction.strip()
    if variant == "no_icl" or example is None:
        return header

    warning = (
        "This block is in-context learning context from a previous teacher run, "
        "not an additional task requirement. Use it only as guidance for planning, "
        "verification, and artifact closure. Solve the live task in the current "
        "environment, and do not mention this context in the final answer."
    )
    if variant == "outcome_only":
        payload = example.outcome_card
    elif variant == "raw_trace":
        payload = example.raw_trace_card
    elif variant == "prompt_filtered":
        payload = example.prompt_filtered_card
    elif variant == "debug_trajectory":
        payload = example.debug_card
    elif variant == "debug_action":
        payload = example.debug_action_card
    else:
        raise ValueError(f"unknown variant: {variant}")
    payload = trim_payload(payload, max_context_chars)

    return "\n\n".join(
        [
            header,
            f"----- BEGIN ICL BASELINE CONTEXT: {variant} -----",
            warning,
            payload,
            f"----- END ICL BASELINE CONTEXT: {variant} -----",
            "Now solve the current task in the live environment and close the required artifact.",
        ]
    )


def patch_local_pytest_verifier(task_dir: Path) -> None:
    """Use pip instead of apt/curl/uvx for copied pytest-only verifiers."""

    test_sh = task_dir / "tests" / "test.sh"
    test_outputs = task_dir / "tests" / "test_outputs.py"
    if not test_sh.exists() or not test_outputs.exists():
        return
    original = read_text(test_sh)
    if "uvx" not in original or "pytest" not in original:
        return
    copy_test_py = "cp /tests/test.py /app/test.py\n\n" if (task_dir / "tests" / "test.py").exists() else ""
    write_text(
        test_sh,
        f"""#!/bin/bash
set -e

if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."
    exit 1
fi

{copy_test_py}PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_BIN" ]; then
  apt-get update
  apt-get install -y python3 python3-pip python3-venv
  PYTHON_BIN="$(command -v python3 || command -v python || true)"
fi
if [ -z "$PYTHON_BIN" ]; then
  echo "Error: neither python3 nor python is available after install."
  echo 0 > /logs/verifier/reward.txt
  exit 1
fi

VENV_DIR="/tmp/htd-pytest-venv"
if "$PYTHON_BIN" -m venv "$VENV_DIR"; then
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  PYTHON_BIN="$VENV_DIR/bin/python"
fi

"$PYTHON_BIN" -m pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

set +e
"$PYTHON_BIN" -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
pytest_status=$?
set -e

if [ "$pytest_status" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
exit "$pytest_status"
""",
    )


def patch_dockerfile_no_proxy(task_dir: Path) -> None:
    """Keep local verifier traffic from being routed through proxy-prepared images."""

    dockerfile = task_dir / "environment" / "Dockerfile"
    if not dockerfile.exists():
        return
    original = read_text(dockerfile)
    proxy_markers = ("HTTP_PROXY=", "http_proxy=", "ALL_PROXY=", "all_proxy=")
    if not any(marker in original for marker in proxy_markers):
        return
    lines = original.rstrip().splitlines()
    env_lines = {
        "NO_PROXY": f"ENV NO_PROXY={LOCALHOST_NO_PROXY}",
        "no_proxy": f"ENV no_proxy={LOCALHOST_NO_PROXY}",
    }
    current = "\n".join(lines)
    changed = False
    for name, env_line in env_lines.items():
        pattern = re.compile(rf"^ENV\s+{re.escape(name)}=", re.MULTILINE)
        if pattern.search(current):
            continue
        lines.append(env_line)
        changed = True
    if changed:
        write_text(dockerfile, "\n".join(lines))


def copy_task_variant(
    task: str,
    source_task_dir: Path,
    output_dir: Path,
    variant: str,
    prompt: str,
    patch_verifier: bool = False,
) -> Path:
    target = output_dir / "task_variants" / variant / task
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source_task_dir, target)
    if patch_verifier:
        patch_dockerfile_no_proxy(target)
        patch_local_pytest_verifier(target)
    write_text(target / "instruction.md", prompt)
    return target


def write_run_script(output_dir: Path, task_variants: dict[str, dict[str, Path]], model: str) -> Path:
    script = output_dir / "run_harbor_variants.sh"
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f'RUNNER="{DEFAULT_HARBOR_RUNNER}"',
        f'JOBS_DIR="{output_dir / "harbor_runs"}"',
        'MODEL="${MODEL:-' + model + '}"',
        "",
        "mkdir -p \"$JOBS_DIR\"",
        "",
    ]
    for variant, tasks in sorted(task_variants.items()):
        for task, task_dir in sorted(tasks.items()):
            job = f"htd-icl-{variant}-{task}-{model}".replace(".", "-")
            lines.extend(
                [
                    f'echo "=== {variant} / {task} / $MODEL ==="',
                    '"$RUNNER" \\',
                    f'  --task "{task_dir}" \\',
                    "  --agent claude-code \\",
                    '  --model "$MODEL" \\',
                    f'  --job-name "{job}" \\',
                    '  --jobs-dir "$JOBS_DIR" \\',
                    "  --setup-timeout 1200 \\",
                    "  --agent-timeout 900",
                    "",
                ]
            )
    write_text(script, "\n".join(lines))
    script.chmod(0o755)
    return script


def write_report(
    output_dir: Path,
    examples: dict[str, TeacherExample],
    target_tasks: list[str],
    variants: list[str],
    run_script: Path,
) -> Path:
    lines = [
        "# Harbor ICL Baseline Pack",
        "",
        "This pack builds a first-pass same-task trace-assisted repair baseline.",
        "It is useful as a smoke test for whether a smaller model can use teacher trajectories,",
        "but it is not sufficient evidence for cross-task generalization because the same-task variants may contain solution details.",
        "",
        "## Scientific status",
        "",
        "- Valid smoke test: no-ICL vs outcome-only vs raw-trace vs Debug-Trajectory on the same failed task.",
        "- Not a final proof: same-task teacher traces can leak the solution and should be reported as an upper-bound / replay condition.",
        "- Stronger proof: leave-one-task-out or cross-task ICL, fixed token budget, same model/harness, and held-out Harbor-style tasks.",
        "",
        "## Variants",
        "",
    ]
    lines.extend(f"- `{variant}`" for variant in variants)
    lines.extend(["", "## Target Tasks", ""])
    for task in target_tasks:
        example = examples.get(task)
        if example is None:
            lines.append(f"- `{task}`: missing passing teacher example")
        else:
            lines.append(f"- `{task}`: teacher `{example.source_run}`, reward={example.reward}")
    lines.extend(
        [
            "",
            "## How To Run",
            "",
            fenced("bash", str(run_script), 500),
            "",
            "Or execute:",
            "",
            fenced("bash", f"MODEL=kimi-k2.5 {run_script}", 500),
            "",
            "## Claim-Oriented Next Step",
            "",
            "To test whether Debug-Trajectory selected examples beat weaker selectors, run held-out tasks with:",
            "",
            "- B0 no ICL",
            "- B1 outcome-only successful teacher examples",
            "- B2 raw teacher traces under the same token budget",
            "- B3 frozen prompt-filtered teacher snippets",
            "- B4 Debug-Trajectory cards",
            "",
            "Primary metric: verifier reward / pass rate. Secondary metrics: wall-clock time, tool-call count, artifact closure, and failure-pattern shift.",
        ]
    )
    report = output_dir / "README.md"
    write_text(report, "\n".join(lines))
    return report


def build_baseline_pack(
    output_dir: Path,
    teacher_states: list[Path] | None = None,
    target_tasks: list[str] | None = None,
    variants: list[str] | None = None,
    model: str = "kimi-k2.5",
    max_context_chars: int | None = 12000,
    patch_verifier: bool = True,
) -> BuildResult:
    teacher_states = teacher_states or DEFAULT_TEACHER_STATES
    target_tasks = target_tasks or DEFAULT_TARGET_TASKS
    variants = variants or [
        "no_icl",
        "outcome_only",
        "raw_trace",
        "prompt_filtered",
        "debug_trajectory",
        "debug_action",
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    examples = load_teacher_examples(teacher_states)

    cards_dir = output_dir / "teacher_cards"
    for task, example in sorted(examples.items()):
        write_text(cards_dir / task / "debug_trajectory.md", example.debug_card)
        write_text(cards_dir / task / "debug_action.md", example.debug_action_card)
        write_text(cards_dir / task / "prompt_filtered.md", example.prompt_filtered_card)
        write_text(cards_dir / task / "raw_trace.md", example.raw_trace_card)
        write_text(cards_dir / task / "outcome_only.md", example.outcome_card)

    task_variants: dict[str, dict[str, Path]] = {variant: {} for variant in variants}
    for task in target_tasks:
        example = examples.get(task)
        if example is None:
            continue
        source_task_dir = Path(example.task_dir)
        for variant in variants:
            prompt = prompt_for_variant(task, example.instruction, example, variant, max_context_chars)
            prompt_path = output_dir / "prompts" / variant / f"{task}.md"
            write_text(prompt_path, prompt)
            task_variants[variant][task] = copy_task_variant(
                task,
                source_task_dir,
                output_dir,
                variant,
                prompt,
                patch_verifier=patch_verifier,
            )

    run_script = write_run_script(output_dir, task_variants, model)
    report = write_report(output_dir, examples, target_tasks, variants, run_script)

    manifest = {
        "output_dir": str(output_dir),
        "teacher_states": [str(path) for path in teacher_states],
        "target_tasks": target_tasks,
        "variants": variants,
        "model": model,
        "max_context_chars": max_context_chars,
        "patch_verifier": patch_verifier,
        "examples": [asdict(examples[task]) for task in sorted(examples) if task in target_tasks],
        "run_script": str(run_script),
        "report": str(report),
    }
    write_text(output_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    return BuildResult(
        output_dir=str(output_dir),
        teacher_states=[str(path) for path in teacher_states],
        target_tasks=target_tasks,
        variants=variants,
        examples=[asdict(examples[task]) for task in sorted(examples) if task in target_tasks],
        run_script=str(run_script),
        report=str(report),
    )
