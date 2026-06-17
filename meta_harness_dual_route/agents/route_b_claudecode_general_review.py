import os
from urllib.parse import urlparse, urlunparse

from harbor.agents.installed.claude_code import ClaudeCode


class AgentHarness(ClaudeCode):
    """General Claude Code wrapper candidate with endpoint proxy passthrough."""

    _GENERAL_REVIEW = """

General harness review:
- Before declaring completion, check whether the requested behavior has edge
  states involving interruption, cleanup, background work, concurrency, partial
  files, subprocesses, timeouts, retries, or external services.
- Prefer a small self-check that exercises the public task contract when it is
  cheap to do so.
- Keep the final state minimal and reproducible; avoid leaving avoidable
  background processes, temporary artifacts, or half-applied setup behind.
"""

    def create_run_agent_commands(self, instruction):
        commands = super().create_run_agent_commands(instruction + self._GENERAL_REVIEW)
        commands[0].command = (
            "mkdir -p $CLAUDE_CONFIG_DIR/debug $CLAUDE_CONFIG_DIR/projects/-app "
            "$CLAUDE_CONFIG_DIR/shell-snapshots $CLAUDE_CONFIG_DIR/statsig "
            "$CLAUDE_CONFIG_DIR/todos"
        )
        proxy_keys = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
        container_proxy = (
            os.environ.get("META_HARNESS_CONTAINER_PROXY_URL")
            or os.environ.get("CONTAINER_PROXY_URL")
            or os.environ.get("HTTP_PROXY")
        )
        if container_proxy:
            parsed = urlparse(container_proxy)
            if parsed.hostname in {"127.0.0.1", "localhost"}:
                netloc = "host.docker.internal"
                if parsed.port:
                    netloc = f"{netloc}:{parsed.port}"
                container_proxy = urlunparse(parsed._replace(netloc=netloc))
        for command in commands:
            env = dict(command.env or {})
            for key in proxy_keys:
                if container_proxy:
                    env[key] = container_proxy
            command.env = env
        return commands
