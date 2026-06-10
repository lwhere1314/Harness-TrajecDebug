"""Prompt normalization helpers for installed agent CLIs."""

from __future__ import annotations


def claude_prompt_cli_safe(instruction: str) -> str:
    """Avoid passing a leading dash as the value immediately after `-p`.

    Some Claude Code versions parse `claude -p '- task...'` as though the prompt
    itself were an option. A neutral header keeps the task text unchanged while
    making the shell argument unambiguously a prompt value.
    """

    if instruction.lstrip().startswith("-"):
        return "Task instructions:\n" + instruction
    return instruction
