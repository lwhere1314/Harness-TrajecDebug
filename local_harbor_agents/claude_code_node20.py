from pathlib import Path

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.trial.paths import EnvironmentPaths


class ClaudeCodeNode20(ClaudeCode):
    async def install(self, environment: BaseEnvironment) -> None:
        await self.exec_as_root(
            environment,
            command=(
                "set -e; "
                "if ! command -v curl >/dev/null 2>&1; then "
                "  if command -v apk >/dev/null 2>&1; then apk add --no-cache curl bash; "
                "  elif command -v apt-get >/dev/null 2>&1; then apt-get update && apt-get install -y curl; "
                "  elif command -v yum >/dev/null 2>&1; then yum install -y curl; "
                "  else echo 'Warning: curl missing and no known package manager found' >&2; fi; "
                "fi; "
                "if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then "
                "  if command -v apk >/dev/null 2>&1; then apk add --no-cache nodejs npm; "
                "  elif command -v apt-get >/dev/null 2>&1; then apt-get update && apt-get install -y nodejs npm; "
                "  elif command -v yum >/dev/null 2>&1; then yum install -y nodejs npm; "
                "  else echo 'Warning: node/npm missing and no known package manager found' >&2; fi; "
                "fi; "
                "node --version; npm --version"
            ),
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )

        version_spec = f"@{self._version}" if self._version else ""
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                f"npm install -g @anthropic-ai/claude-code{version_spec}; "
                "claude --version"
            ),
        )

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

        await super().run(instruction, environment, context)
