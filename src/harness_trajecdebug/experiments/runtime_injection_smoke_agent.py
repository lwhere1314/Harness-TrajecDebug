"""No-model Harbor agent that smokes runtime ICL injection mechanics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from harness_trajecdebug.experiments.debug_action_artifact_agent import (
    build_materialization_script,
)
from harness_trajecdebug.experiments.debug_action_closure import parse_artifacts
from harness_trajecdebug.experiments.live_icl_controller import LiveIclController


class RuntimeInjectionSmokeAgent(BaseAgent):
    """Trigger the live ICL controller, then materialize the injected artifact."""

    def __init__(
        self,
        logs_dir: Path,
        context_path: str,
        trigger: str = "ask_user_question",
        intercept_tools: list[str] | None = None,
        model_name: str | None = None,
        **kwargs,
    ):
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self._context_path = Path(context_path)
        self._trigger = trigger
        self._intercept_tools = set(intercept_tools or ["WebSearch", "WebFetch"])

    @staticmethod
    def name() -> str:
        return "runtime-injection-smoke"

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
        controller = LiveIclController(
            context=card_text,
            intercept_tools=self._intercept_tools,
        )
        decision = self._trigger_controller(controller)

        self._write_controller_logs(decision.events, decision.response)
        if not controller.injected:
            raise RuntimeError(f"runtime controller did not inject for trigger={self._trigger}")

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
            "trigger": self._trigger,
            "injected": controller.injected,
            "injection_reason": decision.reason,
            "artifact_count": len(artifacts),
            "return_code": result.return_code,
            "artifacts": [
                {"path": path, "bytes": len(body.encode("utf-8"))}
                for path, body in artifacts
            ],
        }
        (self.logs_dir / "runtime-injection-smoke.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (self.logs_dir / "debug-action-materialize.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        if result.return_code != 0:
            raise RuntimeError(f"Debug-Action materialization failed with exit code {result.return_code}")

    def _trigger_controller(self, controller: LiveIclController):
        if self._trigger == "ask_user_question":
            return controller.handle_can_use_tool(
                "AskUserQuestion",
                {
                    "questions": [
                        {
                            "question": "Which artifact should I close?",
                            "options": [{"label": "/app/out.txt"}],
                        }
                    ]
                },
            )
        if self._trigger in self._intercept_tools:
            return controller.handle_pre_tool_use(
                {
                    "tool_name": self._trigger,
                    "tool_input": {"query": "runtime ICL smoke trigger"},
                }
            )
        if self._trigger == "dependency_install":
            return controller.handle_pre_tool_use(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "python -m pip install unnecessary-package"},
                }
            )
        raise ValueError(f"unsupported runtime smoke trigger: {self._trigger}")

    def _write_controller_logs(
        self,
        events: list[dict[str, Any]],
        response: dict[str, Any],
    ) -> None:
        events_path = self.logs_dir / "live-controller-events.jsonl"
        with events_path.open("w", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        (self.logs_dir / "live-controller-response.json").write_text(
            json.dumps(response, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
