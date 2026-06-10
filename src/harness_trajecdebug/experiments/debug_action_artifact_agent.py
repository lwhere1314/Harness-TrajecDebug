"""Harbor agent that materializes Debug-Action card artifacts without a model."""

from __future__ import annotations

import json
from pathlib import Path
import shlex

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from harness_trajecdebug.experiments.debug_action_closure import parse_artifacts


class DebugActionArtifactAgent(BaseAgent):
    """Deterministic agent for full-verifier Debug-Action closure checks."""

    def __init__(
        self,
        logs_dir: Path,
        context_path: str,
        model_name: str | None = None,
        **kwargs,
    ):
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self._context_path = Path(context_path)

    @staticmethod
    def name() -> str:
        return "debug-action-artifact"

    def version(self) -> str:
        return "0.1.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        if not self._context_path.exists():
            raise FileNotFoundError(f"missing Debug-Action card: {self._context_path}")

        card_text = self._context_path.read_text(encoding="utf-8", errors="replace")
        artifacts = parse_artifacts(card_text)
        if not artifacts:
            raise ValueError(f"no materializable artifact found in {self._context_path}")

        script = build_materialization_script(artifacts)
        script_path = self.logs_dir / "debug-action-materialize.sh"
        script_path.write_text(script, encoding="utf-8")

        await environment.upload_file(
            source_path=script_path,
            target_path="/tmp/debug-action-materialize.sh",
        )
        result = await environment.exec(
            command=(
                "bash /tmp/debug-action-materialize.sh "
                "> /logs/agent/debug-action-materialize.stdout 2> /logs/agent/debug-action-materialize.stderr"
            ),
            cwd="/app",
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )

        summary = {
            "context_path": str(self._context_path),
            "artifact_count": len(artifacts),
            "return_code": result.return_code,
            "artifacts": [
                {"path": path, "bytes": len(body.encode("utf-8"))}
                for path, body in artifacts
            ],
        }
        summary_path = self.logs_dir / "debug-action-materialize.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        if result.return_code != 0:
            raise RuntimeError(f"Debug-Action materialization failed with exit code {result.return_code}")


def _heredoc_tag(body: str, index: int) -> str:
    base = f"HTD_AGENT_ARTIFACT_{index}"
    tag = base
    suffix = 0
    while tag in body:
        suffix += 1
        tag = f"{base}_{suffix}"
    return tag


def build_materialization_script(artifacts: list[tuple[str, str]]) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "mkdir -p /logs/agent",
    ]
    for index, (artifact_path, body) in enumerate(artifacts):
        quoted_path = shlex.quote(artifact_path)
        quoted_parent = shlex.quote(str(Path(artifact_path).parent))
        tag = _heredoc_tag(body, index)
        lines.extend(
            [
                f"mkdir -p {quoted_parent}",
                f"cat > {quoted_path} <<'{tag}'",
                body,
                tag,
                f"printf '%s: ' {quoted_path}",
                f"wc -c < {quoted_path}",
            ]
        )
    return "\n".join(lines) + "\n"
