"""Local harness backend inventory for Harbor experiments."""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class HarnessBackend:
    name: str
    status: str
    kind: str
    executable: str | None
    local_paths: list[str]
    trace_formats: list[str]
    run_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def discover_harness_backends(ssd_root: Path | None = None) -> list[HarnessBackend]:
    ssd_root = ssd_root or Path("/Volumes/SSD")
    harbor_root = _first_existing(
        [
            _optional_path(os.environ.get("HARBOR_ROOT")),
            Path("/Users/hugo/Desktop/super-refactor/harbor"),
            ssd_root / "terminal-bench-harbor" / "harbor",
        ]
    )
    scripts_root = harbor_root / "scripts" if harbor_root else None
    cache_root = harbor_root / "cache" if harbor_root else None
    codex_executable = _optional_path(shutil.which("codex"))
    claude_executable = _first_executable(
        [
            _optional_path(os.environ.get("HARBOR_CLAUDE_CODE_BINARY")),
            _optional_path(shutil.which("claude")),
            Path("/Users/hugo/Desktop/super-refactor/harbor/cache/claude-code/claude-linux-arm64"),
            ssd_root / "terminal-bench-harbor" / "harbor" / "cache" / "claude-code" / "claude-linux-arm64",
        ]
    )
    kimi_executable = _optional_path(shutil.which("kimi-code"))

    codex_paths = _existing_paths(
        [
            codex_executable,
            Path("/Users/hugo/.nvm/versions/node/v20.0.0/bin/codex"),
            *(scripts_root.glob("run_tb21_codex*.py") if scripts_root and scripts_root.exists() else []),
            Path.home() / ".codex" / "sessions",
        ]
    )

    claude_paths = _existing_paths(
        [
            claude_executable,
            _optional_path(shutil.which("claude")),
            Path("/Users/hugo/Desktop/super-refactor/harbor/cache/claude-code/claude-linux-arm64"),
            ssd_root / "terminal-bench-harbor" / "harbor" / "cache" / "claude-code",
            *(cache_root.glob("claude-code*") if cache_root and cache_root.exists() else []),
        ]
    )

    kimi_paths = _existing_paths(
        [
            kimi_executable,
            *(scripts_root.glob("run_tb21_kimi*.py") if scripts_root and scripts_root.exists() else []),
            *(scripts_root.glob("supervise_tb21_kimi*.sh") if scripts_root and scripts_root.exists() else []),
        ]
    )

    backends = [
        HarnessBackend(
            name="codex",
            status="available" if codex_paths else "missing",
            kind="host-cli",
            executable=str(codex_executable.resolve()) if codex_executable and codex_executable.exists() else None,
            local_paths=[str(path) for path in codex_paths],
            trace_formats=["codex-jsonl", "local_codex_sessions"],
            run_notes=[
                "Use Codex host runners for tasks that keep a live Docker container and export agent/codex-exec.jsonl.",
                "Normalize Codex JSONL through harbor-import or diagnose JSONL directly.",
            ],
        ),
        HarnessBackend(
            name="claude-code",
            status="available" if claude_paths else "missing",
            kind="container-cli-or-sdk",
            executable=str(claude_executable) if claude_executable else None,
            local_paths=[str(path) for path in claude_paths],
            trace_formats=["ATIF-v1.2 trajectory.json", "agent/claude-code.txt"],
            run_notes=[
                "Harbor native claude-code trials usually export agent/trajectory.json.",
                "Kimi models can be routed through Claude Code with Anthropic-compatible TOKEN_PLAN/ANTHROPIC env vars.",
            ],
        ),
        HarnessBackend(
            name="kimi-code",
            status="available" if kimi_paths or claude_paths else "missing",
            kind="anthropic-compatible-model-route",
            executable=str(kimi_executable.resolve()) if kimi_executable and kimi_executable.exists() else None,
            local_paths=[str(path) for path in kimi_paths],
            trace_formats=["ATIF-v1.2 via claude-code", "codex-jsonl when run through Codex host harness"],
            run_notes=[
                "Current SSD setup exposes Kimi K2.5/K2.6 mainly as models routed through claude-code batch runners.",
                "If a standalone kimi-code CLI is installed later, add it to PATH and it will be discovered here.",
            ],
        ),
    ]
    return backends


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value)


def _first_existing(paths: list[Path | None]) -> Path | None:
    for path in paths:
        if path is not None and path.exists():
            return path.resolve()
    return None


def _first_executable(paths: list[Path | None]) -> Path | None:
    for path in paths:
        if path is None:
            continue
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        if resolved.exists() and resolved.is_file():
            return resolved
    return None


def _existing_paths(paths: list[Path | None]) -> list[Path]:
    result: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path is None:
            continue
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        if resolved.exists() and resolved not in seen:
            result.append(resolved)
            seen.add(resolved)
    return result
