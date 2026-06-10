from __future__ import annotations

import os
import tempfile
from pathlib import Path

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.trial.paths import EnvironmentPaths

from local_harbor_agents.claude_code_node20 import ClaudeCodeNode20


class ClaudeCodeInteractiveICL(ClaudeCodeNode20):
    async def run(
        self, instruction: str, environment: BaseEnvironment, context: AgentContext
    ) -> None:
        credentials_path = Path(
            self._get_env("CLAUDE_CODE_CREDENTIALS_PATH")
            or Path.home() / ".claude" / ".credentials.json"
        )
        if credentials_path.exists():
            remote_config_dir = EnvironmentPaths.agent_dir / "sessions"
            remote_credentials = remote_config_dir / ".credentials.json"
            home_credentials = "/root/.claude/.credentials.json"
            await self.exec_as_agent(
                environment,
                command=(
                    f"mkdir -p {remote_config_dir.as_posix()} "
                    '/root/.claude "$HOME/.claude"'
                ),
            )
            await environment.upload_file(credentials_path, remote_credentials)
            await environment.upload_file(credentials_path, home_credentials)
            if environment.default_user is not None:
                await self.exec_as_root(
                    environment,
                    command=(
                        f"chown {environment.default_user} "
                        f"{remote_credentials.as_posix()} {home_credentials}"
                    ),
                )
            await self.exec_as_agent(
                environment,
                command=(
                    'mkdir -p "$HOME/.claude" && '
                    f"cp {remote_credentials.as_posix()} "
                    '"$HOME/.claude/.credentials.json"'
                ),
            )

        env = {
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or "",
            "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL", None),
            "CLAUDE_CODE_OAUTH_TOKEN": os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", ""),
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": os.environ.get(
                "CLAUDE_CODE_MAX_OUTPUT_TOKENS", None
            ),
            "FORCE_AUTO_BACKGROUND_TASKS": "1",
            "ENABLE_BACKGROUND_TASKS": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "IS_SANDBOX": "1",
        }
        env = {k: v for k, v in env.items() if v}

        if self.model_name:
            env["ANTHROPIC_MODEL"] = self.model_name
        elif "ANTHROPIC_MODEL" in os.environ:
            env["ANTHROPIC_MODEL"] = os.environ["ANTHROPIC_MODEL"]

        if "ANTHROPIC_BASE_URL" in env and "ANTHROPIC_MODEL" in env:
            env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = env["ANTHROPIC_MODEL"]
            env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = env["ANTHROPIC_MODEL"]
            env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = env["ANTHROPIC_MODEL"]
            env["CLAUDE_CODE_SUBAGENT_MODEL"] = env["ANTHROPIC_MODEL"]

        env.update(self._resolved_env_vars)
        env["CLAUDE_CONFIG_DIR"] = (EnvironmentPaths.agent_dir / "sessions").as_posix()

        setup_command = (
            "mkdir -p $CLAUDE_CONFIG_DIR/debug $CLAUDE_CONFIG_DIR/projects/-app "
            "$CLAUDE_CONFIG_DIR/shell-snapshots $CLAUDE_CONFIG_DIR/statsig "
            "$CLAUDE_CONFIG_DIR/todos $CLAUDE_CONFIG_DIR/skills && "
            "if [ -d ~/.claude/skills ]; then "
            "cp -r ~/.claude/skills/. $CLAUDE_CONFIG_DIR/skills/ 2>/dev/null || true; "
            "fi"
        )

        for extra in (
            self._build_register_skills_command(),
            self._build_register_memory_command(),
            self._build_register_mcp_servers_command(),
        ):
            if extra:
                setup_command += f" && {extra}"

        await self.exec_as_agent(environment, command=setup_command, env=env)

        local_root = Path(__file__).resolve().parent
        driver_local = local_root / "interactive_icl_driver.py"
        driver_remote = EnvironmentPaths.agent_dir / "interactive_icl_driver.py"
        instruction_remote = EnvironmentPaths.agent_dir / "interactive_icl_instruction.txt"
        injection_remote = EnvironmentPaths.agent_dir / "interactive_icl_hint.txt"

        hint = os.environ.get("HARNESS_TRAJECDEBUG_INTERACTIVE_ICL_HINT", "").strip()
        if not hint:
            hint = (
                "TrajecDebug interactive repair hint: inspect the previous verifier "
                "failure and apply the smallest code change that makes the failing "
                "required test pass. Before finishing, run the targeted failing test."
            )

        await environment.upload_file(driver_local, driver_remote)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
            f.write(instruction)
            instruction_local = Path(f.name)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
            f.write(hint)
            injection_local = Path(f.name)
        await environment.upload_file(instruction_local, instruction_remote)
        await environment.upload_file(injection_local, injection_remote)

        await self.exec_as_agent(
            environment,
            command=(
                'export PATH="$HOME/.local/bin:$PATH"; '
                f"python3 {driver_remote.as_posix()} "
                f"{instruction_remote.as_posix()} "
                f"{injection_remote.as_posix()} "
                "/logs/agent/claude-code.txt"
            ),
            env=env,
        )
