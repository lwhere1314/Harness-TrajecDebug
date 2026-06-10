import argparse
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

from harness_trajecdebug.experiments.live_icl_controller import (
    LiveIclController,
    ask_user_answers,
    command_is_dependency_install,
    injection_text,
    trigger_for_tool,
)
from harness_trajecdebug.experiments.live_icl_sdk_runner import run as run_sdk_live


class LiveIclSdkRunnerTest(unittest.TestCase):
    def test_ask_user_answers_injects_context(self):
        updated = ask_user_answers(
            {
                "questions": [
                    {
                        "question": "Which path should I write?",
                        "options": [{"label": "/app/answer.txt"}],
                    }
                ]
            },
            "Artifact: /app/answer.txt\n```text\n79586\n```",
        )

        self.assertIn("answers", updated)
        answer = updated["answers"]["Which path should I write?"]
        self.assertIn("Harness-TrajecDebug", answer)
        self.assertIn("/app/answer.txt", answer)

    def test_trigger_taxonomy(self):
        self.assertEqual(
            trigger_for_tool("AskUserQuestion", {"questions": []}, set()),
            "ask_user_question",
        )
        self.assertEqual(
            trigger_for_tool("WebSearch", {"query": "dataset"}, {"WebSearch"}),
            "WebSearch",
        )
        self.assertEqual(
            trigger_for_tool("Bash", {"command": "python -m pip install pyarrow"}, set()),
            "dependency_install",
        )
        self.assertIsNone(trigger_for_tool("Read", {"file_path": "/app/foo"}, set()))

    def test_dependency_command_detection(self):
        self.assertTrue(command_is_dependency_install("apt-get install -y curl"))
        self.assertTrue(command_is_dependency_install("uvx pytest /tests/test_outputs.py"))
        self.assertFalse(command_is_dependency_install("python -m py_compile test.py"))

    def test_injection_text_contains_reason_and_context(self):
        text = injection_text("teacher context", "WebSearch")
        self.assertIn("Trigger: WebSearch", text)
        self.assertIn("teacher context", text)

    def test_pre_tool_use_injects_once(self):
        controller = LiveIclController(
            context="Artifact: /app/answer.txt",
            intercept_tools={"WebSearch"},
        )

        first = controller.handle_pre_tool_use(
            {
                "tool_name": "WebSearch",
                "tool_input": {"query": "count dataset tokens"},
            }
        )
        second = controller.handle_pre_tool_use(
            {
                "tool_name": "WebSearch",
                "tool_input": {"query": "count dataset tokens"},
            }
        )

        self.assertTrue(first.injected)
        self.assertIn("hookSpecificOutput", first.response)
        self.assertIn("/app/answer.txt", first.response["hookSpecificOutput"]["additionalContext"])
        self.assertFalse(second.injected)
        self.assertEqual(second.response, {"continue_": True})

    def test_can_use_tool_answers_ask_user_question(self):
        controller = LiveIclController(context="Artifact: /app/answer.txt")
        decision = controller.handle_can_use_tool(
            "AskUserQuestion",
            {
                "questions": [
                    {
                        "question": "Which file should I write?",
                        "options": [{"label": "/app/answer.txt"}],
                    }
                ]
            },
        )

        self.assertTrue(decision.injected)
        answers = decision.response["updated_input"]["answers"]
        self.assertIn("Which file should I write?", answers)
        self.assertIn("/app/answer.txt", answers["Which file should I write?"])


class LiveIclSdkRunnerIntegrationTest(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        sys.modules.pop("claude_agent_sdk", None)

    def install_fake_sdk(self, scenario):
        module = types.ModuleType("claude_agent_sdk")

        class ClaudeAgentOptions:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class HookMatcher:
            def __init__(self, matcher=None, hooks=None):
                self.matcher = matcher
                self.hooks = hooks or []

        class PermissionResultAllow:
            def __init__(self, updated_input=None):
                self.updated_input = updated_input

        async def query(prompt, options):
            prompts = []
            async for item in prompt:
                prompts.append(item)
            yield {"subtype": "init", "prompt_count": len(prompts)}

            if scenario == "pre_tool_use":
                hook = options.hooks["PreToolUse"][0].hooks[0]
                response = await hook(
                    {
                        "tool_name": "WebSearch",
                        "tool_input": {"query": "count dataset tokens"},
                    },
                    "toolu_fake",
                    {},
                )
                yield {"subtype": "hook_response", "response": response}
            elif scenario == "ask_user_question":
                permission = await options.can_use_tool(
                    "AskUserQuestion",
                    {
                        "questions": [
                            {
                                "question": "Which artifact should I close?",
                                "options": [{"label": "/app/answer.txt"}],
                            }
                        ]
                    },
                    {},
                )
                yield {"subtype": "permission_response", "permission": permission}
            else:
                raise AssertionError(f"unknown fake SDK scenario: {scenario}")

        module.ClaudeAgentOptions = ClaudeAgentOptions
        module.HookMatcher = HookMatcher
        module.PermissionResultAllow = PermissionResultAllow
        module.query = query
        sys.modules["claude_agent_sdk"] = module

    def make_args(self, root: Path) -> argparse.Namespace:
        instruction = root / "instruction.md"
        context = root / "context.md"
        instruction.write_text("Write the required artifact.", encoding="utf-8")
        context.write_text("Artifact: /app/answer.txt\n```text\n79586\n```", encoding="utf-8")
        return argparse.Namespace(
            instruction_path=instruction,
            context_path=context,
            output_log=root / "claude-code.txt",
            event_log=root / "sdk-live-events.jsonl",
            sdk_install_log=root / "sdk-install.log",
            sdk_install_timeout_sec=1,
            cwd=root,
            cli_path=None,
            model="fake-model",
            permission_mode="bypassPermissions",
            max_turns=None,
            context_budget_chars=12000,
            intercept_tool=["WebSearch"],
            no_auto_install_sdk=True,
        )

    def read_events(self, path: Path):
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    async def test_runner_logs_pre_tool_live_injection_with_fake_sdk(self):
        self.install_fake_sdk("pre_tool_use")
        with tempfile.TemporaryDirectory() as tmp:
            args = self.make_args(Path(tmp))

            code = await run_sdk_live(args)
            events = self.read_events(args.event_log)
            output = args.output_log.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertIn("additionalContext", output)
        self.assertIn("HARNESS-TRAJECDEBUG LIVE ICL INJECTION", output)
        self.assertTrue(any(event.get("type") == "pre_tool_use" for event in events))
        self.assertTrue(
            any(
                event.get("type") == "live_injection"
                and event.get("channel") == "PreToolUse.additionalContext"
                for event in events
            )
        )
        self.assertEqual(events[-1]["type"], "finished")
        self.assertTrue(events[-1]["injected"])

    async def test_runner_answers_ask_user_question_with_fake_sdk(self):
        self.install_fake_sdk("ask_user_question")
        with tempfile.TemporaryDirectory() as tmp:
            args = self.make_args(Path(tmp))

            code = await run_sdk_live(args)
            events = self.read_events(args.event_log)
            output = args.output_log.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertIn("Which artifact should I close?", output)
        self.assertIn("/app/answer.txt", output)
        self.assertTrue(any(event.get("type") == "can_use_tool" for event in events))
        self.assertTrue(
            any(
                event.get("type") == "live_injection"
                and event.get("channel") == "AskUserQuestion.updated_input"
                for event in events
            )
        )
        self.assertEqual(events[-1]["type"], "finished")
        self.assertTrue(events[-1]["injected"])


if __name__ == "__main__":
    unittest.main()
