import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from harness_trajecdebug.experiments.baseline_aggregate import aggregate
from harness_trajecdebug.experiments.debug_action_closure import parse_artifacts, run_closure
from harness_trajecdebug.experiments.harbor_icl_baseline import make_prompt_filtered_card
from harness_trajecdebug.experiments.harbor_icl_baseline import artifact_snippets
from harness_trajecdebug.experiments.harbor_icl_baseline import patch_local_pytest_verifier
from harness_trajecdebug.experiments.harbor_icl_baseline import patch_dockerfile_no_proxy
from harness_trajecdebug.experiments.icl_task_matrix import build_matrix
from harness_trajecdebug.experiments.icl_readiness import build_readiness
from harness_trajecdebug.experiments.joint_failure_matrix import build_joint_matrix
from harness_trajecdebug.experiments.live_icl_hook import (
    build_hook_settings,
    run_pre_tool_hook,
)
from harness_trajecdebug.experiments.matrix_canary_summary import summarize_batch
from harness_trajecdebug.experiments.model_endpoint_preflight import (
    messages_url,
    resolve_endpoint_config,
)
from harness_trajecdebug.experiments.prompt_safety import claude_prompt_cli_safe
from harness_trajecdebug.experiments.sdk_live_summary import summarize_trial


class ExperimentUtilitiesTest(unittest.TestCase):
    def test_claude_prompt_cli_safe_prefixes_leading_dash_prompt(self):
        prompt = "- task starts with a dash"
        safe = claude_prompt_cli_safe(prompt)

        self.assertTrue(safe.startswith("Task instructions:\n"))
        self.assertIn(prompt, safe)
        self.assertEqual(claude_prompt_cli_safe("normal task"), "normal task")

    def test_prompt_filtered_card_has_no_htd_process_labels(self):
        card = make_prompt_filtered_card(
            task="demo-task",
            reward=1.0,
            summary={"tests": 2, "passed": 2, "failed": 0},
            snippets=[("/tmp/container/app/out.txt", "answer\n")],
            items=[
                {"type": "agent_message", "text": "I will inspect /app/out.txt and run pytest."},
                {
                    "type": "command_execution",
                    "command": "python -m pytest /tests/test_outputs.py",
                    "exit_code": 0,
                    "output": "2 passed",
                },
            ],
        )

        self.assertIn("Prompt-Filtered Teacher Snippets", card)
        self.assertIn("Artifact: /app/out.txt", card)
        self.assertIn("python -m pytest", card)
        self.assertNotIn("Reference view", card)
        self.assertNotIn("State view", card)
        self.assertNotIn("Commitment view", card)
        self.assertNotIn("critical-step", card.lower())

    def test_artifact_snippets_falls_back_to_solution_text_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            container = root / "container"
            app = container / "app"
            app.mkdir(parents=True)
            (container / "inspect.sanitized.json").write_text("{}", encoding="utf-8")
            (app / "headless_terminal.py").write_text(
                "class HeadlessTerminal:\n    pass\n",
                encoding="utf-8",
            )
            (app / "server.log").write_text("noise", encoding="utf-8")
            (app / "__pycache__").mkdir()
            (app / "__pycache__" / "headless_terminal.pyc").write_bytes(b"binary")
            record = {
                "container_artifacts": {
                    "inspect": str(container / "inspect.sanitized.json")
                }
            }

            snippets = artifact_snippets("headless-terminal", record)

        self.assertEqual(len(snippets), 1)
        self.assertTrue(snippets[0][0].endswith("/app/headless_terminal.py"))
        self.assertIn("HeadlessTerminal", snippets[0][1])

    def test_patch_dockerfile_no_proxy_adds_localhost_bypass(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "task"
            dockerfile = task_dir / "environment" / "Dockerfile"
            dockerfile.parent.mkdir(parents=True)
            dockerfile.write_text(
                "FROM python:3.13-slim-bookworm\n"
                "ENV HTTP_PROXY=http://host.docker.internal:1082\n"
                "ENV http_proxy=http://host.docker.internal:1082\n"
                "WORKDIR /app\n",
                encoding="utf-8",
            )

            patch_dockerfile_no_proxy(task_dir)
            patch_dockerfile_no_proxy(task_dir)
            patched = dockerfile.read_text(encoding="utf-8")

        self.assertIn("ENV NO_PROXY=localhost,127.0.0.1,::1", patched)
        self.assertIn("ENV no_proxy=localhost,127.0.0.1,::1", patched)
        self.assertEqual(patched.count("NO_PROXY="), 1)
        self.assertEqual(patched.count("no_proxy="), 1)

    def test_patch_local_pytest_verifier_uses_available_python_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / "task"
            tests = task_dir / "tests"
            tests.mkdir(parents=True)
            (tests / "test_outputs.py").write_text("def test_ok(): pass\n", encoding="utf-8")
            (tests / "test.sh").write_text(
                "#!/bin/bash\nuvx pytest /tests/test_outputs.py\n",
                encoding="utf-8",
            )

            patch_local_pytest_verifier(task_dir)
            patched = (tests / "test.sh").read_text(encoding="utf-8")

        self.assertIn('PYTHON_BIN="$(command -v python3 || command -v python || true)"', patched)
        self.assertIn("apt-get install -y python3 python3-pip python3-venv", patched)
        self.assertIn('VENV_DIR="/tmp/htd-pytest-venv"', patched)
        self.assertIn('"$PYTHON_BIN" -m pip install', patched)
        self.assertIn('"$PYTHON_BIN" -m pytest', patched)
        self.assertNotIn("\npython -m pip install", patched)

    def test_live_hook_settings_include_pretool_and_sessionstart(self):
        settings = build_hook_settings(
            "python3 /opt/harness-trajecdebug/live_icl_hook.py",
            ["WebSearch", "WebFetch"],
        )

        self.assertIn("PreToolUse", settings)
        self.assertIn("SessionStart", settings)
        self.assertEqual(settings["PreToolUse"][0]["matcher"], "AskUserQuestion|WebSearch|WebFetch|Bash")
        self.assertEqual(settings["PreToolUse"][0]["hooks"][0]["type"], "command")

    def test_live_hook_injects_context_once_and_updates_ask_user_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state.json"
            events = root / "events.jsonl"
            response = run_pre_tool_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "AskUserQuestion",
                    "tool_input": {
                        "questions": [
                            {
                                "question": "Which artifact should I close?",
                                "options": [{"label": "/app/out.txt"}],
                            }
                        ]
                    },
                },
                context="Use /app/out.txt from the teacher trace.",
                intercept_tools={"WebSearch"},
                state_path=state,
                event_log_path=events,
            )
            second = run_pre_tool_hook(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "WebSearch",
                    "tool_input": {"query": "fallback search"},
                },
                context="Use /app/out.txt from the teacher trace.",
                intercept_tools={"WebSearch"},
                state_path=state,
                event_log_path=events,
            )
            lines = events.read_text(encoding="utf-8").splitlines()

        self.assertIsNotNone(response)
        hook_output = response["hookSpecificOutput"]
        self.assertEqual(hook_output["permissionDecision"], "allow")
        self.assertIn("additionalContext", hook_output)
        self.assertIn("updatedInput", hook_output)
        answers = hook_output["updatedInput"]["answers"]
        self.assertIn("Which artifact should I close?", answers)
        self.assertIsNone(second)
        self.assertTrue(any("PreToolUse.updatedInput+additionalContext" in line for line in lines))

    def test_replay_live_icl_hook_cli_matches_hook_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = root / "context.md"
            state = root / "state.json"
            events = root / "events.jsonl"
            context.write_text("Use /app/out.txt from the teacher trace.", encoding="utf-8")
            script = Path(__file__).resolve().parents[1] / "scripts" / "replay_live_icl_hook.py"

            first = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context-path",
                    str(context),
                    "--tool-name",
                    "AskUserQuestion",
                    "--tool-input-json",
                    '{"questions":[{"question":"Which artifact should I close?"}]}',
                    "--intercept-tool",
                    "WebSearch",
                    "--state-path",
                    str(state),
                    "--event-log",
                    str(events),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            second = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--context-path",
                    str(context),
                    "--tool-name",
                    "WebSearch",
                    "--tool-input-json",
                    '{"query":"fallback"}',
                    "--intercept-tool",
                    "WebSearch",
                    "--state-path",
                    str(state),
                    "--event-log",
                    str(events),
                ],
                check=True,
                text=True,
                capture_output=True,
            )

        first_data = json.loads(first.stdout)
        second_data = json.loads(second.stdout)
        hook_output = first_data["response"]["hookSpecificOutput"]
        self.assertTrue(first_data["injected"])
        self.assertEqual(first_data["reason"], "ask_user_question")
        self.assertIn("additionalContext", hook_output)
        self.assertIn("updatedInput", hook_output)
        self.assertFalse(second_data["injected"])
        self.assertEqual(second_data["reason"], "WebSearch")

    def test_messages_url(self):
        self.assertEqual(messages_url("https://example.com"), "https://example.com/v1/messages")
        self.assertEqual(messages_url("https://example.com/v1"), "https://example.com/v1/messages")
        self.assertEqual(messages_url("https://example.com/v1/messages"), "https://example.com/v1/messages")

    def test_endpoint_profile_resolution(self):
        auto = resolve_endpoint_config(
            profile="auto",
            env={
                "TOKEN_PLAN_BASE_URL": "https://token.example/apps/anthropic",
                "TOKEN_PLAN_API_KEY": "token-secret",
            },
        )
        self.assertEqual(auto["base_url"], "https://token.example/apps/anthropic")
        self.assertEqual(auto["resolved_profile"], "token-plan")
        self.assertEqual(auto["api_key"], "token-secret")

        ark = resolve_endpoint_config(
            profile="ark",
            env={"ARK_API_KEY": "ark-secret"},
        )
        self.assertEqual(ark["base_url"], "https://ark.cn-beijing.volces.com/api/coding")
        self.assertEqual(ark["resolved_profile"], "ark")
        self.assertEqual(ark["api_key_source"], "ARK_API_KEY")
        self.assertEqual(ark["api_key"], "ark-secret")

        dashscope = resolve_endpoint_config(
            profile="dashscope",
            env={"DASHSCOPE_BASE_URL": "https://dash.example/apps/anthropic"},
        )
        self.assertEqual(dashscope["base_url"], "https://dash.example/apps/anthropic")
        self.assertIsNone(dashscope["api_key"])

    def test_debug_action_closure_query_optimize(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            card_dir = pack / "teacher_cards" / "query-optimize"
            task_dir = pack / "task_variants" / "no_icl" / "query-optimize"
            card_dir.mkdir(parents=True)
            task_dir.mkdir(parents=True)
            card = """# Debug-Action Card
```bash
mkdir -p "/app"
cat > "/app/sol.sql" <<'HTD_ARTIFACT_EOF'
WITH x AS (SELECT 1 AS a)
SELECT a FROM x;
HTD_ARTIFACT_EOF
```
"""
            (card_dir / "debug_action.md").write_text(card, encoding="utf-8")

            parsed = parse_artifacts(card)
            result = run_closure(pack, "query-optimize")

        self.assertEqual(parsed[0][0], "/app/sol.sql")
        self.assertEqual(result["status"], "closure_passed")
        self.assertTrue(result["ok"])
        self.assertEqual(result["artifacts"][0]["path"], "/app/sol.sql")

    def test_debug_action_closure_gcode_to_text_exact_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            card_dir = pack / "teacher_cards" / "gcode-to-text"
            task_dir = pack / "task_variants" / "no_icl" / "gcode-to-text"
            card_dir.mkdir(parents=True)
            task_dir.mkdir(parents=True)
            card = """# Debug-Action Card
```bash
mkdir -p "/app"
cat > "/app/out.txt" <<'HTD_ARTIFACT_EOF'
flag{gc0d3_iz_ch4LLenGiNg}
HTD_ARTIFACT_EOF
```
"""
            (card_dir / "debug_action.md").write_text(card, encoding="utf-8")

            result = run_closure(pack, "gcode-to-text")

        self.assertEqual(result["status"], "closure_passed")
        self.assertTrue(result["ok"])
        self.assertIn("gcode_to_text_exact_flag", {check["name"] for check in result["checks"]})

    def test_debug_action_closure_unavailable_when_no_artifact_heredoc(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            card_dir = pack / "teacher_cards" / "headless-terminal"
            task_dir = pack / "task_variants" / "no_icl" / "headless-terminal"
            card_dir.mkdir(parents=True)
            task_dir.mkdir(parents=True)
            (card_dir / "debug_action.md").write_text(
                "## Recommended next action\nNo direct text artifact was captured.\n",
                encoding="utf-8",
            )

            result = run_closure(pack, "headless-terminal")

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "closure_unavailable")
        self.assertEqual(result["artifacts"], [])

    def test_task_matrix_reads_student_reward_from_trial_result_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trial = root / "jobs" / "demo-task__trial"
            trial.mkdir(parents=True)
            (trial / "result.json").write_text(
                json.dumps({"verifier_result": {"rewards": {"reward": 0.0}}}),
                encoding="utf-8",
            )
            student_state = root / "student-state.json"
            teacher_state = root / "teacher-state.json"
            student_state.write_text(
                json.dumps(
                    {
                        "tasks": {
                            "demo-task": {
                                "status": "finished",
                                "result_summary": {
                                    "reward": None,
                                    "trial_results": [
                                        {
                                            "reward": None,
                                            "trial_dir": str(trial),
                                            "exception_type": None,
                                            "exception_message": None,
                                        }
                                    ],
                                },
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            teacher_state.write_text(
                json.dumps(
                    {
                        "tasks": {
                            "demo-task": {
                                "status": "finished",
                                "reward": 1.0,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            candidates = build_matrix(student_state=student_state, teacher_state=teacher_state)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].student_reward, 0.0)
        self.assertEqual(candidates[0].student_status, "failed_reward")

    def test_joint_failure_matrix_prefers_verifier_footprints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            student_trial = root / "student" / "task-a__123"
            teacher_task = root / "teacher" / "task-a"
            student_trial.joinpath("verifier").mkdir(parents=True)
            teacher_task.joinpath("verifier").mkdir(parents=True)
            student_trial.joinpath("verifier", "ctrf.json").write_text(
                json.dumps(
                    {
                        "results": {
                            "tests": [
                                {
                                    "name": "test_outputs.py::test_secret_removed",
                                    "status": "failed",
                                },
                                {"name": "test_outputs.py::test_other", "status": "passed"},
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            teacher_task.joinpath("verifier", "ctrf.json").write_text(
                json.dumps(
                    {
                        "results": {
                            "tests": [
                                {
                                    "name": "test_outputs.py::test_no_other_files_changed",
                                    "status": "failed",
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            student_state = root / "student-state.json"
            teacher_state = root / "teacher-state.json"
            student_state.write_text(
                json.dumps(
                    {
                        "tasks": {
                            "task-a": {
                                "result_summary": {
                                    "reward": 0,
                                    "trial_results": [{"trial_dir": str(student_trial)}],
                                }
                            },
                            "task-b": {
                                "result_summary": {
                                    "reward": 1,
                                    "trial_results": [{"trial_dir": str(root / "student" / "task-b")}],
                                }
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            teacher_state.write_text(
                json.dumps(
                    {
                        "tasks": {
                            "task-a": {
                                "reward": 0,
                                "status": "finished",
                                "task_run_dir": str(teacher_task),
                            },
                            "task-b": {
                                "reward": 0,
                                "status": "finished",
                                "task_run_dir": str(root / "teacher" / "task-b"),
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            candidates = build_joint_matrix(student_state, teacher_state)

        self.assertEqual([candidate.task for candidate in candidates], ["task-a"])
        self.assertEqual(candidates[0].failure_kind, "complementary_verifier_failure")
        self.assertEqual(candidates[0].htd_suitability, "high")

    def test_sdk_live_summary_rate_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            trial = Path(tmp)
            agent = trial / "agent"
            verifier = trial / "verifier"
            agent.mkdir()
            verifier.mkdir()
            (agent / "command-1").mkdir()
            (agent / "command-1" / "return-code.txt").write_text("10", encoding="utf-8")
            (verifier / "reward.txt").write_text("0", encoding="utf-8")
            (trial / "result.json").write_text('{"verifier_result":{"rewards":{"reward":0.0}}}', encoding="utf-8")
            (agent / "sdk-live-events.jsonl").write_text(
                "\n".join(
                    [
                        '{"type":"sdk_install","status":"finished"}',
                        '{"type":"sdk_message","message":{"subtype":"init"}}',
                        '{"type":"sdk_message","message":{"subtype":"api_retry","data":{"error_status":429}}}',
                        '{"type":"sdk_message","message":{"error":"rate_limit","content":[{"text":"quota has been exhausted"}]}}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = summarize_trial(trial)
            self.assertEqual(summary["status"], "model_rate_limited")
            self.assertEqual(summary["api_retry_count"], 1)
            self.assertEqual(summary["agent_return_code"], "10")

    def test_sdk_live_summary_python_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            trial = Path(tmp)
            agent = trial / "agent"
            verifier = trial / "verifier"
            (agent / "command-1").mkdir(parents=True)
            verifier.mkdir()
            (agent / "command-1" / "return-code.txt").write_text("127", encoding="utf-8")
            (agent / "command-1" / "stdout.txt").write_text(
                "bash: line 2: python3: command not found\n",
                encoding="utf-8",
            )
            (verifier / "reward.txt").write_text("0", encoding="utf-8")
            (trial / "result.json").write_text('{"verifier_result":{"rewards":{"reward":0.0}}}', encoding="utf-8")

            summary = summarize_trial(trial)

        self.assertEqual(summary["status"], "sdk_python_missing")
        self.assertEqual(summary["agent_return_code"], "127")

    def test_icl_task_matrix_selects_teacher_pass_student_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "teacher" / "tasks" / "query-optimize" / "container_artifacts" / "container" / "app"
            app.mkdir(parents=True)
            (app / "sol.sql").write_text("SELECT 1;\n", encoding="utf-8")
            task_dir = root / "tasks" / "query-optimize"
            task_dir.mkdir(parents=True)

            teacher_state = root / "teacher-state.json"
            teacher_state.write_text(
                """{
                  "tasks": {
                    "query-optimize": {
                      "status": "finished",
                      "reward": 1.0,
                      "task_dir": "%s",
                      "task_run_dir": "%s",
                      "container_artifacts": {
                        "copied": [{"source": "/app", "destination": "%s"}]
                      }
                    },
                    "already-passed": {"status": "finished", "reward": 1.0}
                  }
                }"""
                % (task_dir, root / "teacher" / "tasks" / "query-optimize", app),
                encoding="utf-8",
            )
            student_state = root / "student-state.json"
            student_state.write_text(
                """{
                  "tasks": {
                    "query-optimize": {
                      "job_dir": "/tmp/job",
                      "result_summary": {
                        "reward": 0.0,
                        "trial_results": [{"trial_dir": "/tmp/trial"}]
                      }
                    },
                    "already-passed": {"result_summary": {"reward": 1.0}}
                  }
                }""",
                encoding="utf-8",
            )

            matrix = build_matrix(student_state=student_state, teacher_state=teacher_state)

        self.assertEqual([item.task for item in matrix], ["query-optimize"])
        self.assertEqual(matrix[0].student_reward, 0.0)
        self.assertIn("/app/sol.sql", matrix[0].teacher_artifacts)

    def test_matrix_canary_summary_preflight_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp) / "batch"
            batch.mkdir()
            (batch / "config.json").write_text(
                """{
                  "pack_dir": "runs/harbor_icl_baseline",
                  "model": "kimi-k2.6",
                  "inject_mode": "continue_after",
                  "jobs_dir": ""
                }""",
                encoding="utf-8",
            )
            (batch / "tasks.txt").write_text("query-optimize\n", encoding="utf-8")
            (batch / "preflight.json").write_text(
                '{"ok": false, "kind": "rate_limited", "status": 429}',
                encoding="utf-8",
            )
            (batch / "replay-summary.jsonl").write_text(
                '{"task":"query-optimize","replays":[{"reason":"WebSearch","injected":true},{"reason":"ask_user_question","injected":true}]}\n',
                encoding="utf-8",
            )

            summary = summarize_batch(batch)

        self.assertEqual(summary["rows"][0]["task"], "query-optimize")
        self.assertTrue(summary["rows"][0]["replay"]["all_injected"])
        self.assertEqual(summary["rows"][0]["run"]["status"], "preflight_blocked")

    def test_matrix_canary_summary_prefers_new_dynamic_job_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "batch"
            batch.mkdir()
            jobs = root / "jobs"
            task = "query-optimize"
            model = "kimi-k2.6"
            new_trial = jobs / "htd-dynamic-icl-continue_after-debug_action-query-optimize-kimi-k2-6" / f"{task}__new"
            old_trial = jobs / "htd-dynamic-icl-query-optimize-kimi-k2-6" / f"{task}__old"
            for trial, reward in [(new_trial, 1.0), (old_trial, 0.0)]:
                trial.mkdir(parents=True)
                (trial / "result.json").write_text(
                    json.dumps({"verifier_result": {"rewards": {"reward": reward}}}),
                    encoding="utf-8",
                )

            (batch / "config.json").write_text(
                json.dumps(
                    {
                        "pack_dir": str(root),
                        "model": model,
                        "inject_mode": "continue_after",
                        "context_variant": "debug_action",
                        "jobs_dir": str(jobs),
                    }
                ),
                encoding="utf-8",
            )
            (batch / "tasks.txt").write_text(f"{task}\n", encoding="utf-8")
            (batch / "preflight.json").write_text('{"ok": true, "kind": "ok"}', encoding="utf-8")
            (batch / "replay-summary.jsonl").write_text(
                '{"task":"query-optimize","replays":[{"reason":"WebSearch","injected":true}]}\n',
                encoding="utf-8",
            )

            summary = summarize_batch(batch)

        self.assertEqual(summary["rows"][0]["run"]["reward"], 1.0)
        self.assertIn("__new", summary["rows"][0]["run"]["trial_dir"])

    def test_baseline_aggregate_reads_static_and_matrix_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            static_trial = (
                pack
                / "harbor_runs"
                / "htd-icl-debug_trajectory-cancel-async-tasks-kimi-k2-6"
                / "cancel-async-tasks__ok"
            )
            static_trial.mkdir(parents=True)
            (static_trial.parent / "config.json").write_text(
                json.dumps(
                    {
                        "agents": [{"model_name": "kimi-k2.6"}],
                        "tasks": [
                            {
                                "path": "runs/harbor_icl_baseline/task_variants/debug_trajectory/cancel-async-tasks"
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (static_trial / "result.json").write_text(
                json.dumps({"verifier_result": {"rewards": {"reward": 1.0}}}),
                encoding="utf-8",
            )

            missing_trial = (
                pack
                / "harbor_runs"
                / "htd-icl-no_icl-query-optimize-kimi-k2-6"
                / "query-optimize__missing"
            )
            missing_trial.mkdir(parents=True)
            (missing_trial.parent / "config.json").write_text(
                json.dumps(
                    {
                        "agents": [{"model_name": "kimi-k2.6"}],
                        "tasks": [
                            {
                                "path": "runs/harbor_icl_baseline/task_variants/no_icl/query-optimize"
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            dynamic_job = (
                pack
                / "harbor_runs"
                / "htd-dynamic-icl-continue_after-debug_action-query-optimize-kimi-k2-6"
            )
            dynamic_trial = dynamic_job / "query-optimize__runtime"
            dynamic_trial.mkdir(parents=True)
            (dynamic_trial / "result.json").write_text(
                json.dumps({"verifier_result": {"rewards": {"reward": 0.0}}}),
                encoding="utf-8",
            )

            batch = pack / "matrix_canary" / "batch"
            batch.mkdir(parents=True)
            (batch / "summary.json").write_text(
                json.dumps(
                    {
                        "batch_dir": str(batch),
                        "config": {
                            "model": "kimi-k2.6",
                            "inject_mode": "continue_after",
                            "context_variant": "debug_action",
                        },
                        "rows": [
                            {
                                "task": "query-optimize",
                                "replay": {"all_injected": True, "reasons": ["WebSearch"]},
                                "run": {"status": "preflight_blocked", "reward": None, "trial_dir": None},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            suite_batch = pack / "baseline_suites" / "suite" / "prompt_filtered"
            suite_batch.mkdir(parents=True)
            (suite_batch / "summary.json").write_text(
                json.dumps(
                    {
                        "batch_dir": str(suite_batch),
                        "config": {
                            "model": "kimi-k2.6",
                            "inject_mode": "continue_after",
                            "context_variant": "prompt_filtered",
                        },
                        "rows": [
                            {
                                "task": "query-optimize",
                                "replay": {
                                    "all_injected": True,
                                    "reasons": ["WebSearch", "ask_user_question"],
                                },
                                "run": {
                                    "status": "preflight_blocked",
                                    "reward": None,
                                    "trial_dir": None,
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            closure = pack / "artifact_closure"
            closure.mkdir()
            (closure / "debug_action_closure.json").write_text(
                json.dumps(
                    {
                        "pack_dir": str(pack),
                        "context_variant": "debug_action",
                        "rows": [
                            {
                                "task": "query-optimize",
                                "status": "closure_passed",
                                "ok": True,
                                "artifacts": [{"path": "/app/sol.sql"}],
                                "checks": [{"name": "card_has_artifact_heredoc", "ok": True}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            harbor_artifact_trial = (
                pack
                / "harbor_runs_artifact_closure"
                / "htd-artifact-closure-debug_action-query-optimize"
                / "query-optimize__artifact"
            )
            harbor_artifact_trial.mkdir(parents=True)
            (harbor_artifact_trial.parent / "config.json").write_text(
                json.dumps(
                    {
                        "agents": [
                            {
                                "model_name": "none",
                                "kwargs": {
                                    "context_path": str(
                                        pack / "teacher_cards" / "query-optimize" / "debug_action.md"
                                    )
                                },
                            }
                        ],
                        "tasks": [
                            {
                                "path": "runs/harbor_icl_baseline/task_variants/no_icl/query-optimize"
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (harbor_artifact_trial / "agent").mkdir()
            (harbor_artifact_trial / "verifier").mkdir()
            (harbor_artifact_trial / "agent" / "debug-action-materialize.json").write_text(
                '{"return_code": 0}',
                encoding="utf-8",
            )
            (harbor_artifact_trial / "verifier" / "test-stdout.txt").write_text(
                "============================= test session starts ==============================\n"
                "collected 6 items\n"
                "../tests/test_outputs.py ",
                encoding="utf-8",
            )

            summary = aggregate(pack)

        statuses = {(row["task"], row["condition"]): row["status"] for row in summary["rows"]}
        self.assertEqual(statuses[("cancel-async-tasks", "debug_trajectory")], "passed")
        self.assertEqual(statuses[("query-optimize", "no_icl")], "missing_result")
        self.assertEqual(statuses[("query-optimize", "continue_after:debug_action")], "preflight_blocked")
        self.assertEqual(statuses[("query-optimize", "continue_after:prompt_filtered")], "preflight_blocked")
        self.assertEqual(statuses[("query-optimize", "debug_action")], "closure_passed")
        suite_rows = [
            row
            for row in summary["rows"]
            if row["condition"] == "continue_after:prompt_filtered"
        ]
        self.assertTrue(suite_rows[0]["suite_dir"].endswith("baseline_suites/suite"))
        artifact_harbor_rows = [
            row for row in summary["rows"] if row["source"] == "harbor_artifact_closure"
        ]
        self.assertEqual(artifact_harbor_rows[0]["status"], "verifier_timeout_after_materialization")
        dynamic_rows = [
            row
            for row in summary["rows"]
            if row["source"] == "harbor_runtime"
            and row["condition"] == "continue_after:debug_action"
        ]
        self.assertEqual(dynamic_rows[0]["task"], "query-optimize")

    def test_baseline_aggregate_scans_custom_harbor_runs_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            custom_runs = pack / "harbor_runs_query_baseline"
            static_trial = (
                custom_runs
                / "htd-icl-no_icl-query-optimize-kimi-k2-6"
                / "query-optimize__base"
            )
            static_trial.mkdir(parents=True)
            (static_trial.parent / "config.json").write_text(
                json.dumps(
                    {
                        "endpoint_profile": "ark",
                        "agents": [{"model_name": "kimi-k2.6"}],
                        "tasks": [
                            {
                                "path": "runs/harbor_icl_baseline/task_variants/no_icl/query-optimize"
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (static_trial / "result.json").write_text(
                json.dumps({"verifier_result": {"rewards": {"reward": 0.0}}}),
                encoding="utf-8",
            )

            runtime_trial = (
                custom_runs
                / "htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6"
                / "query-optimize__runtime"
            )
            runtime_trial.mkdir(parents=True)
            (runtime_trial.parent / "config.json").write_text(
                json.dumps(
                    {
                        "endpoint_profile": "ark",
                        "agents": [
                            {
                                "model_name": "kimi-k2.6",
                                "kwargs": {
                                    "inject_mode": "sdk_live",
                                    "context_path": str(
                                        pack / "teacher_cards" / "query-optimize" / "debug_action.md"
                                    ),
                                },
                            }
                        ],
                        "tasks": [
                            {
                                "path": "runs/harbor_icl_baseline/task_variants/no_icl/query-optimize"
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (runtime_trial / "sdk-live-summary.json").write_text(
                json.dumps({"status": "passed", "reward": 1.0}),
                encoding="utf-8",
            )

            summary = aggregate(pack)

        rows = {
            (row["source"], row["task"], row["condition"]): row
            for row in summary["rows"]
        }
        self.assertEqual(
            rows[("harbor_static", "query-optimize", "no_icl")]["status"],
            "failed_verifier",
        )
        self.assertEqual(
            rows[("harbor_runtime", "query-optimize", "sdk_live:debug_action")]["status"],
            "passed",
        )

    def test_baseline_aggregate_marks_verifier_proxy_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            trial = (
                pack
                / "harbor_runs_artifact_closure"
                / "htd-artifact-closure-debug_action-headless-terminal"
                / "headless-terminal__artifact"
            )
            trial.mkdir(parents=True)
            (trial.parent / "config.json").write_text(
                json.dumps(
                    {
                        "agents": [
                            {
                                "model_name": "none",
                                "kwargs": {
                                    "context_path": str(
                                        pack / "teacher_cards" / "headless-terminal" / "debug_action.md"
                                    )
                                },
                            }
                        ],
                        "tasks": [
                            {
                                "path": "runs/harbor_icl_baseline/task_variants/no_icl/headless-terminal"
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (trial / "agent").mkdir()
            (trial / "verifier").mkdir()
            (trial / "agent" / "debug-action-materialize.json").write_text(
                '{"return_code": 0}',
                encoding="utf-8",
            )
            (trial / "verifier" / "test-stdout.txt").write_text(
                "requests.exceptions.ProxyError: HTTPConnectionPool(host='host.docker.internal', "
                "port=1082): Max retries exceeded with url: http://localhost:8000/ "
                "(Caused by ProxyError('Unable to connect to proxy'))",
                encoding="utf-8",
            )
            (trial / "result.json").write_text(
                json.dumps({"verifier_result": {"rewards": {"reward": 0.0}}}),
                encoding="utf-8",
            )

            summary = aggregate(pack)

        rows = [row for row in summary["rows"] if row["source"] == "harbor_artifact_closure"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "verifier_proxy_leak")

    def test_icl_readiness_separates_mechanism_from_reward_gate(self):
        summary = {
            "pack_dir": "runs/harbor_icl_baseline",
            "rows": [
                {
                    "source": "artifact_closure",
                    "task": "query-optimize",
                    "condition": "debug_action",
                    "status": "closure_passed",
                },
                {
                    "source": "matrix_canary",
                    "task": "query-optimize",
                    "condition": "continue_after:debug_action",
                    "endpoint_profile": "ark",
                    "status": "preflight_blocked",
                    "replay_all_injected": True,
                },
                {
                    "source": "harbor_artifact_closure",
                    "task": "query-optimize",
                    "condition": "debug_action",
                    "status": "verifier_timeout_after_materialization",
                },
                {
                    "source": "harbor_artifact_closure",
                    "task": "headless-terminal",
                    "condition": "debug_action",
                    "status": "verifier_proxy_leak",
                    "archived": True,
                },
                {
                    "source": "harbor_artifact_closure",
                    "task": "headless-terminal",
                    "condition": "debug_action",
                    "status": "passed",
                    "reward": 1.0,
                },
                {
                    "source": "harbor_static",
                    "task": "cancel-async-tasks",
                    "condition": "debug_trajectory",
                    "status": "passed",
                    "reward": 1.0,
                },
                {
                    "source": "harbor_runtime_smoke",
                    "task": "gcode-to-text",
                    "condition": "ask_user_question:debug_action",
                    "status": "passed",
                    "reward": 1.0,
                    "runtime_smoke": {"trigger": "ask_user_question"},
                },
            ],
        }

        report = build_readiness(summary)

        self.assertTrue(report["mechanism_canary"]["ready"])
        self.assertEqual(report["archived_row_count"], 1)
        self.assertEqual(report["mechanism_canary"]["runtime_smoke_passed"], 1)
        self.assertEqual(report["mechanism_canary"]["runtime_smoke_triggers"], ["ask_user_question"])
        self.assertEqual(report["reward_benchmark"]["model_rewarded_rows"], 1)
        self.assertFalse(report["model_run"]["ready"])
        self.assertFalse(report["reward_benchmark"]["ready"])
        self.assertEqual(report["decision"], "daily_mechanism_canary_only")
        self.assertEqual(
            report["reward_benchmark"]["verifier_blockers_by_task"]["query-optimize"],
            ["verifier_timeout_after_materialization"],
        )
        self.assertNotIn(
            "headless-terminal",
            report["reward_benchmark"]["verifier_blockers_by_task"],
        )

    def test_baseline_aggregate_reads_runtime_smoke_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack"
            trial = (
                pack
                / "harbor_runs_runtime_smoke"
                / "htd-runtime-smoke-ask_user_question-debug_action-gcode-to-text"
                / "gcode-to-text__smoke"
            )
            trial.mkdir(parents=True)
            (trial.parent / "config.json").write_text(
                json.dumps(
                    {
                        "agents": [
                            {
                                "model_name": "none",
                                "kwargs": {
                                    "context_path": str(
                                        pack / "teacher_cards" / "gcode-to-text" / "debug_action.md"
                                    ),
                                    "trigger": "ask_user_question",
                                },
                            }
                        ],
                        "tasks": [
                            {
                                "path": "runs/harbor_icl_baseline/task_variants/no_icl/gcode-to-text"
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (trial / "agent").mkdir()
            (trial / "agent" / "runtime-injection-smoke.json").write_text(
                json.dumps(
                    {
                        "trigger": "ask_user_question",
                        "injected": True,
                        "artifact_count": 1,
                        "return_code": 0,
                    }
                ),
                encoding="utf-8",
            )
            (trial / "result.json").write_text(
                json.dumps({"verifier_result": {"rewards": {"reward": 1.0}}}),
                encoding="utf-8",
            )

            summary = aggregate(pack)

        rows = [row for row in summary["rows"] if row["source"] == "harbor_runtime_smoke"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["task"], "gcode-to-text")
        self.assertEqual(rows[0]["condition"], "ask_user_question:debug_action")
        self.assertEqual(rows[0]["status"], "passed")
        self.assertTrue(rows[0]["runtime_smoke"]["injected"])
        smoke_conditions = [
            condition
            for condition in summary["conditions"]
            if condition["key"].startswith("harbor_runtime_smoke|")
        ]
        self.assertEqual(len(smoke_conditions), 1)
        self.assertEqual(smoke_conditions[0]["n_rewarded"], 0)
        self.assertIsNone(smoke_conditions[0]["mean_reward"])
        self.assertEqual(smoke_conditions[0]["status_counts"], {"passed": 1})


if __name__ == "__main__":
    unittest.main()
