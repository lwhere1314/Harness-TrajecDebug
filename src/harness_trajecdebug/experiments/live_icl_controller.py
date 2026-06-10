"""Pure controller logic for live Harness-TrajecDebug ICL injection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[: max_chars - 80].rstrip() + "\n\n[TRUNCATED TO FIXED LIVE ICL CONTEXT BUDGET]"


def minimal_live_policy(instruction: str) -> str:
    policy = """\
----- BEGIN HARNESS-TRAJECDEBUG LIVE CONTROLLER NOTE -----
A runtime Harness-TrajecDebug controller is watching tool-use events. The full
prior-trace context is not included in this initial prompt. If the controller
sees uncertainty, an AskUserQuestion request, a web-search detour, or a costly
dependency route, it may inject a short prior-trace lesson before the run
continues. Treat any injected lesson as in-context guidance, not as a new task
requirement.
----- END HARNESS-TRAJECDEBUG LIVE CONTROLLER NOTE -----"""
    return instruction.rstrip() + "\n\n" + policy


def injection_text(context: str, reason: str) -> str:
    return f"""\
HARNESS-TRAJECDEBUG LIVE ICL INJECTION

Trigger: {reason}

Use the prior-trace guidance below before continuing. If it contains a
same-task Debug-Action card with a matching artifact path, materialize that
artifact first and run the cheapest closure check available. Avoid web fetches,
heavy dependency installs, or full recomputation whose only purpose is to
reproduce an already verified teacher artifact.

{context}
"""


def ask_user_answers(input_data: dict[str, Any], context: str) -> dict[str, Any]:
    questions = input_data.get("questions")
    if not isinstance(questions, list):
        questions = []

    answer_text = (
        "Use the Harness-TrajecDebug injected prior-trace context below as the "
        "answer to this uncertainty. Prefer the artifact/verification route "
        "that matches the live task contract.\n\n"
        + context
    )

    answers: dict[str, Any] = {}
    for question in questions:
        if not isinstance(question, dict):
            continue
        key = question.get("question")
        if isinstance(key, str) and key:
            answers[key] = answer_text

    if not answers:
        answers["Harness-TrajecDebug guidance"] = answer_text

    updated = dict(input_data)
    updated["answers"] = answers
    return updated


def command_is_dependency_install(command: str) -> bool:
    lowered = command.lower()
    return (
        "pip install" in lowered
        or "uvx" in lowered
        or "apt-get install" in lowered
        or "apt install" in lowered
    )


def trigger_for_tool(
    tool_name: str,
    input_data: dict[str, Any],
    intercept_tools: set[str],
) -> str | None:
    if tool_name == "AskUserQuestion":
        return "ask_user_question"
    if tool_name in intercept_tools:
        return tool_name
    if tool_name == "Bash":
        command = input_data.get("command")
        if isinstance(command, str) and command_is_dependency_install(command):
            return "dependency_install"
    return None


@dataclass
class LiveControllerDecision:
    response: dict[str, Any]
    events: list[dict[str, Any]]
    reason: str | None
    injected: bool


class LiveIclController:
    """Stateful live-injection policy shared by runner and replay tests."""

    def __init__(
        self,
        context: str,
        intercept_tools: set[str] | None = None,
        injected: bool = False,
    ):
        self.context = context
        self.intercept_tools = intercept_tools or set()
        self.injected = injected

    def handle_pre_tool_use(self, input_data: dict[str, Any]) -> LiveControllerDecision:
        tool_name = input_data.get("tool_name") if isinstance(input_data, dict) else None
        tool_input = input_data.get("tool_input", {}) if isinstance(input_data, dict) else {}
        if not isinstance(tool_name, str):
            tool_name = ""
        if not isinstance(tool_input, dict):
            tool_input = {}

        reason = trigger_for_tool(tool_name, tool_input, self.intercept_tools)
        events = [
            {
                "type": "pre_tool_use",
                "tool_name": tool_name,
                "tool_input": tool_input,
                "reason": reason,
                "already_injected": self.injected,
            }
        ]
        if reason and not self.injected:
            self.injected = True
            text = injection_text(self.context, reason)
            events.append(
                {
                    "type": "live_injection",
                    "channel": "PreToolUse.additionalContext",
                    "reason": reason,
                    "chars": len(text),
                }
            )
            return LiveControllerDecision(
                response={
                    "continue_": True,
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "additionalContext": text,
                    },
                },
                events=events,
                reason=reason,
                injected=True,
            )

        return LiveControllerDecision(
            response={"continue_": True},
            events=events,
            reason=reason,
            injected=False,
        )

    def handle_can_use_tool(
        self,
        tool_name: str,
        input_data: dict[str, Any],
    ) -> LiveControllerDecision:
        events = [
            {
                "type": "can_use_tool",
                "tool_name": tool_name,
                "tool_input": input_data,
            }
        ]
        if tool_name == "AskUserQuestion":
            injected_now = False
            if not self.injected:
                self.injected = True
                injected_now = True
                events.append(
                    {
                        "type": "live_injection",
                        "channel": "AskUserQuestion.updated_input",
                        "reason": "ask_user_question",
                        "chars": len(self.context),
                    }
                )
            return LiveControllerDecision(
                response={"updated_input": ask_user_answers(input_data, self.context)},
                events=events,
                reason="ask_user_question",
                injected=injected_now,
            )

        return LiveControllerDecision(
            response={"updated_input": input_data},
            events=events,
            reason=None,
            injected=False,
        )
