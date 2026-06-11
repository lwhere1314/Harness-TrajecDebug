#!/usr/bin/env python3
"""Install project-local TrajectoryDebug skills for Claude Code, Codex, and Kimi Code."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "harness-trajdebug-agent"
SKILL_ROOT = PLUGIN_ROOT / "skills"
PROJECT_TARGETS = [
    REPO_ROOT / ".claude" / "skills",
    REPO_ROOT / ".agents" / "skills",
    REPO_ROOT / ".kimi-code" / "skills",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        action="append",
        choices=["claude", "agents", "kimi"],
        help="Install only one target family. May be repeated. Defaults to all.",
    )
    parser.add_argument(
        "--copy-full",
        action="store_true",
        help="Copy the full canonical skill instead of the lightweight project shim.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected = set(args.target or ["claude", "agents", "kimi"])
    target_map = {
        "claude": REPO_ROOT / ".claude" / "skills",
        "agents": REPO_ROOT / ".agents" / "skills",
        "kimi": REPO_ROOT / ".kimi-code" / "skills",
    }

    if not SKILL_ROOT.is_dir():
        raise SystemExit(f"Missing plugin skill root: {SKILL_ROOT}")

    for name, target_root in target_map.items():
        if name not in selected:
            continue
        target_root.mkdir(parents=True, exist_ok=True)
        for skill_dir in sorted(path for path in SKILL_ROOT.iterdir() if path.is_dir()):
            target = target_root / skill_dir.name
            if target.exists():
                shutil.rmtree(target)
            if args.copy_full:
                shutil.copytree(skill_dir, target)
            else:
                target.mkdir(parents=True)
                source = skill_dir / "SKILL.md"
                frontmatter = _frontmatter_for(skill_dir.name)
                target.joinpath("SKILL.md").write_text(frontmatter + _shim_body(skill_dir.name), encoding="utf-8")
            print(f"installed {skill_dir.name} -> {target}")

    print("\nNext steps:")
    print("- Claude Code: restart in this repo; use /trajectorydebug or /harness-runtime-icl.")
    print("- Codex/Kimi Code: restart in this repo so .agents/skills is rescanned.")
    print(f"- Kimi plugin install option: /plugins install {PLUGIN_ROOT}")
    print(f"- Codex plugin source path: {PLUGIN_ROOT}")


def _frontmatter_for(name: str) -> str:
    descriptions = {
        "trajectorydebug": "Use Harness-TrajecDebug to diagnose terminal-agent trajectories, compare no-TD versus with-TD runs, build Debug-Action cards, and run Harbor or Terminal-Bench runtime ICL canaries.",
        "harness-runtime-icl": "Run Harness-TrajecDebug runtime ICL canaries and compare no-TD versus with-TD evidence on Harbor or Terminal-Bench tasks.",
    }
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {descriptions.get(name, 'Use Harness-TrajecDebug project skills.')}\n"
        "type: prompt\n"
        "---\n\n"
    )


def _shim_body(name: str) -> str:
    return (
        f"# {name}\n\n"
        "Load the canonical project skill at:\n\n"
        f"```text\nplugins/harness-trajdebug-agent/skills/{name}/SKILL.md\n```\n\n"
        "If that file is present, follow it. If not, use `harness-trajdebug diagnose`, "
        "`harness-trajdebug harbor-import --diagnose`, and the scripts under "
        "`scripts/run_*icl*` to preserve raw trace evidence, verifier output, reward "
        "files, critical-step diagnosis, injected card paths, and artifact closure evidence.\n"
    )


if __name__ == "__main__":
    main()
