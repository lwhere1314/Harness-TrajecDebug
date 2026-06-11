"""Harbor agent for runtime Debug-Trajectory context injection.

This agent intentionally does not append the full teacher trajectory to the
task instruction. Instead, it installs an in-container `htd-context` command.
Claude Code can call that command during the run to retrieve the selected
Debug-Trajectory card.
"""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import json

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.base import ExecInput
from harbor.environments.base import BaseEnvironment

from harness_trajecdebug.experiments.live_icl_controller import minimal_live_policy
from harness_trajecdebug.experiments.live_icl_hook import build_hook_settings
from harness_trajecdebug.experiments.prompt_safety import claude_prompt_cli_safe


class DynamicIclClaudeCode(ClaudeCode):
    """Claude Code with a runtime context channel for ICL ablations."""

    def __init__(
        self,
        context_path: str | None = None,
        force_context_call: bool = True,
        context_budget_chars: int = 12000,
        inject_mode: str = "tool",
        first_turn_timeout_sec: int = 75,
        sdk_live_install_timeout_sec: int = 900,
        sdk_live_intercept_tools: list[str] | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        env_context = os.environ.get("HTD_ICL_CONTEXT_PATH")
        self._context_path = Path(context_path or env_context) if context_path or env_context else None
        self._force_context_call = force_context_call
        self._context_budget_chars = context_budget_chars
        if inject_mode not in {"tool", "prelude", "continue_after", "sdk_live", "hooks_live"}:
            raise ValueError("inject_mode must be 'tool', 'prelude', 'continue_after', 'sdk_live', or 'hooks_live'")
        self._inject_mode = inject_mode
        self._first_turn_timeout_sec = first_turn_timeout_sec
        self._sdk_live_install_timeout_sec = sdk_live_install_timeout_sec
        self._sdk_live_intercept_tools = sdk_live_intercept_tools or []

    async def setup(self, environment: BaseEnvironment) -> None:
        await super().setup(environment)

        payload = self._load_context_payload()
        context_file = self.logs_dir / "dynamic_context.md"
        continue_file = self.logs_dir / "continue_prompt.md"
        tool_file = self.logs_dir / "htd-context"
        controller_file = self.logs_dir / "htd-controller-decision"
        controller_module_file = self.logs_dir / "runtime_controller.py"
        live_controller_file = self.logs_dir / "live_icl_controller.py"
        live_hook_file = self.logs_dir / "live_icl_hook.py"
        live_sdk_file = self.logs_dir / "live_icl_sdk_runner.py"
        hook_settings_file = self.logs_dir / "claude-hooks-settings.json"
        context_file.write_text(payload, encoding="utf-8")
        continue_file.write_text(self._continue_prompt(payload), encoding="utf-8")
        tool_file.write_text(_HTD_CONTEXT_TOOL, encoding="utf-8")
        controller_file.write_text(_HTD_CONTROLLER_DECISION_TOOL, encoding="utf-8")
        controller_module_file.write_text(_runtime_controller_source(), encoding="utf-8")
        live_controller_file.write_text(_live_controller_source(), encoding="utf-8")
        live_hook_file.write_text(_live_hook_source(), encoding="utf-8")
        live_sdk_file.write_text(_live_sdk_runner_source(), encoding="utf-8")
        hook_command = " ".join(
            [
                "python3",
                "/opt/harness-trajecdebug/live_icl_hook.py",
                "--context-path",
                "/opt/harness-trajecdebug/context.md",
                "--state-path",
                "/logs/agent/live-hook-state.json",
                "--event-log",
                "/logs/agent/live-controller-events.jsonl",
                *[
                    item
                    for tool in (self._sdk_live_intercept_tools or ["WebSearch", "WebFetch"])
                    for item in ["--intercept-tool", shlex.quote(tool)]
                ],
            ]
        )
        hook_settings_file.write_text(
            json.dumps(
                build_hook_settings(
                    hook_command=hook_command,
                    intercept_tools=self._sdk_live_intercept_tools or ["WebSearch", "WebFetch"],
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        await environment.exec(command="mkdir -p /opt/harness-trajecdebug")
        await environment.upload_file(
            source_path=context_file,
            target_path="/opt/harness-trajecdebug/context.md",
        )
        await environment.upload_file(
            source_path=continue_file,
            target_path="/opt/harness-trajecdebug/continue_prompt.md",
        )
        await environment.upload_file(
            source_path=tool_file,
            target_path="/usr/local/bin/htd-context",
        )
        await environment.upload_file(
            source_path=controller_file,
            target_path="/usr/local/bin/htd-controller-decision",
        )
        await environment.upload_file(
            source_path=controller_module_file,
            target_path="/opt/harness-trajecdebug/runtime_controller.py",
        )
        await environment.upload_file(
            source_path=live_controller_file,
            target_path="/opt/harness-trajecdebug/live_icl_controller.py",
        )
        await environment.upload_file(
            source_path=live_hook_file,
            target_path="/opt/harness-trajecdebug/live_icl_hook.py",
        )
        await environment.upload_file(
            source_path=live_sdk_file,
            target_path="/opt/harness-trajecdebug/live_icl_sdk_runner.py",
        )
        await environment.upload_file(
            source_path=hook_settings_file,
            target_path="/opt/harness-trajecdebug/claude-hooks-settings.json",
        )
        await environment.exec(command="chmod +x /usr/local/bin/htd-context /usr/local/bin/htd-controller-decision")

    def create_run_agent_commands(self, instruction: str):
        instruction = claude_prompt_cli_safe(instruction)
        if self._inject_mode == "prelude":
            return self._with_pipefail(
                super().create_run_agent_commands(self._with_runtime_context_prelude(instruction))
            )
        if self._inject_mode == "continue_after":
            return self._continue_after_commands(instruction)
        if self._inject_mode == "sdk_live":
            return self._sdk_live_commands(instruction)
        if self._inject_mode == "hooks_live":
            return self._hooks_live_commands(instruction)
        return self._with_pipefail(
            super().create_run_agent_commands(self._with_runtime_context_policy(instruction))
        )

    @staticmethod
    def _pipefail_command(command: str) -> str:
        if "| tee /logs/agent/claude-code" not in command:
            return command
        if command.lstrip().startswith("set -o pipefail"):
            return command
        return "set -o pipefail; " + command

    def _with_pipefail(self, commands: list[ExecInput]) -> list[ExecInput]:
        return [
            ExecInput(
                command=self._pipefail_command(item.command),
                cwd=item.cwd,
                env=item.env,
                timeout_sec=item.timeout_sec,
            )
            for item in commands
        ]

    def _load_context_payload(self) -> str:
        if not self._context_path or not self._context_path.exists():
            return (
                "# Harness-TrajecDebug Runtime Context\n\n"
                "No context payload was configured for this run."
            )

        text = self._context_path.read_text(encoding="utf-8", errors="replace").strip()
        if self._context_budget_chars > 0 and len(text) > self._context_budget_chars:
            return (
                text[: self._context_budget_chars - 80].rstrip()
                + "\n\n[TRUNCATED TO FIXED RUNTIME ICL CONTEXT BUDGET]"
            )
        return text

    def _with_runtime_context_policy(self, instruction: str) -> str:
        mode = "must" if self._force_context_call else "may"
        policy = f"""\
----- BEGIN RUNTIME ICL CHANNEL -----
A Harness-TrajecDebug runtime context command is available:

    htd-context "brief question or current plan"

The full context is not included in this initial task prompt. It will only enter
your working context if you call the command during the run. You {mode} call it
once after inspecting the task contract and before committing the final
implementation strategy. If you are about to use AskUserQuestion, call
`htd-context` first and use the retrieved prior-trace lesson to answer the
uncertainty yourself when possible.

Treat the returned content as in-context learning guidance from a prior teacher
trajectory, not as an extra task requirement. Solve the live task in the current
environment and satisfy the official verifier.

If the returned context contains a reusable artifact for the same task and the
artifact path matches the live task contract, treat it as a candidate artifact:
write or adapt it first, then run the cheapest verifier-equivalent closure
check available. Avoid heavyweight recomputation or dependency installation
whose only purpose is to reproduce an already verified teacher artifact; do that
only if the artifact is missing, mismatched, or fails validation.
----- END RUNTIME ICL CHANNEL -----"""
        return instruction.rstrip() + "\n\n" + policy

    def _with_runtime_context_prelude(self, instruction: str) -> str:
        payload = self._load_context_payload()
        prelude = f"""\
----- BEGIN HARNESS-TRAJECDEBUG RUNTIME ICL PRELUDE -----
This context was injected by the Harbor agent at run time. It is not part of
the source task's instruction.md. Treat it as in-context learning guidance from
a prior teacher trajectory.

Use this context before web searches, dependency installation, or expensive
recomputation. If it contains a same-task Debug-Action card with a matching
artifact path, materialize that artifact first and run the cheapest closure
check available.

{payload}
----- END HARNESS-TRAJECDEBUG RUNTIME ICL PRELUDE -----
"""
        return instruction.rstrip() + "\n\n" + prelude

    def _continue_prompt(self, payload: str) -> str:
        return f"""\
HARNESS-TRAJECDEBUG CONTROLLER INJECTION

The previous Claude Code turn was allowed to start without the teacher context.
The runtime controller is now injecting context because the first turn either
hit a trigger, timed out, or did not close the expected artifact.

Use the injected context now. If it contains a same-task Debug-Action card with
a matching artifact path, materialize that artifact first and run the cheapest
closure check available. Avoid web fetches, heavyweight dependency installs, or
full recomputation whose only purpose is to reproduce a verified teacher
artifact.

{payload}
"""

    def _continue_after_commands(self, instruction: str) -> list[ExecInput]:
        commands = super().create_run_agent_commands(instruction)
        if len(commands) < 2:
            return commands

        setup, first = commands[0], commands[1]
        first_command = first.command
        if self._first_turn_timeout_sec > 0:
            first_command = first_command.replace(
                "claude --verbose",
                f"timeout {int(self._first_turn_timeout_sec)}s claude --verbose",
                1,
            )
        first_command = first_command.replace(
            "| tee /logs/agent/claude-code.txt",
            "| tee /logs/agent/claude-code-first.txt | tee /logs/agent/claude-code.txt",
        )
        first_command = self._pipefail_command(first_command)

        continue_command = self._pipefail_command("\n".join(
            [
                "htd-controller-decision",
                "if python3 - <<'PY'",
                "import json",
                "from pathlib import Path",
                "p = Path('/logs/agent/controller-decision.json')",
                "data = json.loads(p.read_text()) if p.exists() else {'should_inject': True}",
                "raise SystemExit(0 if data.get('should_inject') else 1)",
                "PY",
                "then",
                "  echo '[Harness-TrajecDebug] controller injecting follow-up context' | tee -a /logs/agent/claude-code.txt",
                "  claude --verbose --output-format stream-json --permission-mode bypassPermissions --continue -p \"$(cat /opt/harness-trajecdebug/continue_prompt.md)\" 2>&1 | tee /logs/agent/claude-code-continue.txt | tee -a /logs/agent/claude-code.txt",
                "else",
                "  echo '[Harness-TrajecDebug] controller skipped follow-up injection' | tee -a /logs/agent/claude-code.txt",
                "fi",
            ]
        ))

        return [
            setup,
            ExecInput(
                command=first_command,
                cwd=first.cwd,
                env=first.env,
                timeout_sec=(self._first_turn_timeout_sec + 30 if self._first_turn_timeout_sec > 0 else first.timeout_sec),
            ),
            ExecInput(
                command=continue_command,
                env=first.env,
            ),
        ]

    def _sdk_live_commands(self, instruction: str) -> list[ExecInput]:
        commands = super().create_run_agent_commands(instruction)
        if len(commands) < 2:
            return commands

        setup, first = commands[0], commands[1]
        instruction_literal = repr(instruction)
        intercept_args = " ".join(
            f"--intercept-tool {shlex.quote(tool)}"
            for tool in self._sdk_live_intercept_tools
        )
        live_command = "\n".join(
            [
                "set -euo pipefail",
                "mkdir -p /opt/harness-trajecdebug /logs/agent",
                _PYTHON_BOOTSTRAP_SHELL,
                r"""HTD_CLAUDE_CLI="${HTD_CLAUDE_CLI:-}"
if [ -z "$HTD_CLAUDE_CLI" ]; then
  if [ -x /root/.local/bin/claude ]; then
    HTD_CLAUDE_CLI=/root/.local/bin/claude
  elif command -v claude >/dev/null 2>&1; then
    HTD_CLAUDE_CLI="$(command -v claude)"
  else
    echo "[Harness-TrajecDebug] sdk_live could not find Claude Code CLI." >&2
    exit 127
  fi
fi""",
                '"$HTD_PYTHON_BIN" - <<\'PY\'',
                "from pathlib import Path",
                f"Path('/opt/harness-trajecdebug/instruction.md').write_text({instruction_literal}, encoding='utf-8')",
                "PY",
                (
                    '"$HTD_PYTHON_BIN" /opt/harness-trajecdebug/live_icl_sdk_runner.py '
                    "--instruction-path /opt/harness-trajecdebug/instruction.md "
                    "--context-path /opt/harness-trajecdebug/context.md "
                    "--output-log /logs/agent/claude-code.txt "
                    "--event-log /logs/agent/sdk-live-events.jsonl "
                    f"--sdk-install-timeout-sec {int(self._sdk_live_install_timeout_sec)} "
                    "--cwd /app "
                    '--cli-path "$HTD_CLAUDE_CLI" '
                    "${ANTHROPIC_MODEL:+--model \"$ANTHROPIC_MODEL\"} "
                    f"{intercept_args}"
                ),
            ]
        )

        return [
            setup,
            ExecInput(
                command=live_command,
                cwd=first.cwd,
                env=first.env,
                timeout_sec=first.timeout_sec,
            ),
        ]

    def _hooks_live_commands(self, instruction: str) -> list[ExecInput]:
        commands = super().create_run_agent_commands(minimal_live_policy(instruction))
        if len(commands) < 2:
            return commands

        setup, first = commands[0], commands[1]
        hook_command = first.command.replace(
            "claude --verbose --output-format stream-json",
            (
                "claude --verbose --include-hook-events "
                "--settings /opt/harness-trajecdebug/claude-hooks-settings.json "
                "--output-format stream-json"
            ),
            1,
        )
        hook_command = hook_command.replace(
            "| tee /logs/agent/claude-code.txt",
            "| tee /logs/agent/claude-code-hooks-live.txt | tee /logs/agent/claude-code.txt",
        )
        hook_command = self._pipefail_command(hook_command)
        return [
            setup,
            ExecInput(
                command=hook_command,
                cwd=first.cwd,
                env=first.env,
                timeout_sec=first.timeout_sec,
            ),
        ]


_HTD_CONTEXT_TOOL = """#!/usr/bin/env bash
set -euo pipefail

mkdir -p /logs/agent
PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -n "$PYTHON_BIN" ]; then
  "$PYTHON_BIN" - "$@" <<'PY'
import datetime as _dt
import json as _json
import pathlib as _pathlib
import sys as _sys

entry = {
    "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    "args": _sys.argv[1:],
}
log = _pathlib.Path("/logs/agent/htd-context-uses.jsonl")
with log.open("a", encoding="utf-8") as handle:
    handle.write(_json.dumps(entry, ensure_ascii=False) + "\\n")
PY
fi

cat /opt/harness-trajecdebug/context.md
"""


_PYTHON_BOOTSTRAP_SHELL = r"""HTD_PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$HTD_PYTHON_BIN" ]; then
  export DEBIAN_FRONTEND=noninteractive
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y python3 python3-pip python3-venv
  elif command -v apk >/dev/null 2>&1; then
    apk add --no-cache python3 py3-pip
  elif command -v yum >/dev/null 2>&1; then
    yum install -y python3 python3-pip
  else
    echo "[Harness-TrajecDebug] sdk_live requires Python, but no supported package manager was found." >&2
    exit 127
  fi
  HTD_PYTHON_BIN="$(command -v python3 || command -v python || true)"
fi
if [ -z "$HTD_PYTHON_BIN" ]; then
  echo "[Harness-TrajecDebug] sdk_live could not find Python after bootstrap." >&2
  exit 127
fi
if ! "$HTD_PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  if "$HTD_PYTHON_BIN" -m ensurepip --upgrade >/dev/null 2>&1; then
    :
  elif command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y python3-pip python3-venv
  elif command -v apk >/dev/null 2>&1; then
    apk add --no-cache py3-pip
  elif command -v yum >/dev/null 2>&1; then
    yum install -y python3-pip
  else
    echo "[Harness-TrajecDebug] sdk_live requires pip for claude-agent-sdk installation." >&2
    exit 127
  fi
fi
"""


_HTD_CONTROLLER_DECISION_TOOL = r"""#!/usr/bin/env python3
import sys

sys.path.insert(0, "/opt/harness-trajecdebug")

from runtime_controller import main

raise SystemExit(main())
"""


def _runtime_controller_source() -> str:
    return (Path(__file__).with_name("runtime_controller.py")).read_text(
        encoding="utf-8"
    )


def _live_sdk_runner_source() -> str:
    return (Path(__file__).with_name("live_icl_sdk_runner.py")).read_text(
        encoding="utf-8"
    )


def _live_hook_source() -> str:
    return (Path(__file__).with_name("live_icl_hook.py")).read_text(
        encoding="utf-8"
    )


def _live_controller_source() -> str:
    return (Path(__file__).with_name("live_icl_controller.py")).read_text(
        encoding="utf-8"
    )
