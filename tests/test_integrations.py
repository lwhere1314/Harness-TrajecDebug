from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harness_trajecdebug.atif_viewer import export_harbor_run_to_viewer, viewer_info
from harness_trajecdebug.diagnose import diagnose_trace
from harness_trajecdebug.harbor import discover_harbor_tasks, normalize_harbor_trial, read_harbor_trial
from harness_trajecdebug.trace_adapters import normalize_codex_jsonl


class IntegrationAdaptersTest(unittest.TestCase):
    def test_discovers_harbor_compatible_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task_dir = root / "swe-bench-pro" / "tasks" / "django-001"
            (task_dir / "environment").mkdir(parents=True)
            (task_dir / "solution").mkdir()
            (task_dir / "tests").mkdir()
            (task_dir / "task.toml").write_text(
                '\n'.join(
                    [
                        'schema_version = "1.1"',
                        "",
                        "[task]",
                        'name = "swe-bench-pro/django-001"',
                        'description = "Fix a Django regression."',
                        "",
                        "[metadata]",
                        'category = "programming"',
                        'tags = ["python", "debugging"]',
                    ]
                ),
                encoding="utf-8",
            )
            (task_dir / "instruction.md").write_text("Fix the bug.\n", encoding="utf-8")
            (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
            (task_dir / "solution" / "solve.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\n", encoding="utf-8")

            tasks = discover_harbor_tasks(root)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].name, "swe-bench-pro/django-001")
        self.assertEqual(tasks[0].dataset, "swe-bench-pro")
        self.assertEqual(tasks[0].compatible_family, "swe-bench-pro")
        self.assertTrue(tasks[0].valid)

    def test_normalizes_harbor_atif_trial_and_diagnoses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trial_dir = Path(tmp) / "runs" / "tb21-train-fasttext-claude-code-kimi-k26" / "train-fasttext__abc"
            (trial_dir / "agent").mkdir(parents=True)
            (trial_dir / "verifier").mkdir()
            trajectory = {
                "schema_version": "ATIF-v1.2",
                "agent": {"name": "claude-code", "model_name": "kimi-k2.6"},
                "steps": [
                    {
                        "step_id": 1,
                        "source": "user",
                        "message": (
                            "Please train a fasttext model. The final model size needs to be less than 150MB "
                            "but get at least 0.62 accuracy. Save it as /app/model.bin"
                        ),
                    },
                    {
                        "step_id": 2,
                        "source": "agent",
                        "message": "Promoting the compact model.",
                        "observation": {"results": [{"content": "P@1\t0.621\n-rw-r--r-- 60724105 /app/model.bin"}]},
                    },
                ],
            }
            (trial_dir / "agent" / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
            (trial_dir / "verifier" / "test-stdout.txt").write_text(
                "FAILED test_accuracy\nE AssertionError: Accuracy 0.617 is not at least 0.62\n",
                encoding="utf-8",
            )
            (trial_dir / "verifier" / "reward.txt").write_text("0\n", encoding="utf-8")
            (trial_dir / "result.json").write_text(
                json.dumps(
                    {
                        "task_name": "train-fasttext",
                        "trial_name": "train-fasttext__abc",
                        "config": {
                            "agent": {"name": "claude-code", "model_name": "kimi-k2.6"},
                            "task": {"path": "harbor/datasets/terminal-bench-2.1-proxy/tasks/train-fasttext"},
                        },
                        "verifier_result": {"rewards": {"reward": 0.0}},
                    }
                ),
                encoding="utf-8",
            )

            trial = read_harbor_trial(trial_dir)
            trace = normalize_harbor_trial(trial_dir)
            normalized_path = Path(tmp) / "normalized.json"
            normalized_path.write_text(json.dumps(trace), encoding="utf-8")
            diagnosis = diagnose_trace(normalized_path, run_id="train-fasttext__abc")

        self.assertEqual(trial.reward, 0.0)
        self.assertFalse(trial.passed)
        self.assertEqual(trace["harbor"]["agent_name"], "claude-code")
        self.assertEqual(diagnosis.task_family, "train-fasttext")
        self.assertEqual(diagnosis.state_summary["reward"], 0.0)
        self.assertFalse(diagnosis.state_summary["passed"])
        self.assertEqual(diagnosis.final_failure, "final verifier P@1=0.617 < threshold 0.62")

    def test_normalizes_codex_jsonl_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "codex-exec.jsonl"
            trace_path.write_text(
                '\n'.join(
                    [
                        "2026-06-03 WARN skipped plain log",
                        '{"type":"thread.started","thread_id":"thread-1"}',
                        '{"type":"item.completed","item":{"type":"agent_message","text":"I will inspect the task."}}',
                        (
                            '{"type":"item.completed","item":{"type":"command_execution",'
                            '"command":"fasttext test /app/model.bin /tests/private_test.txt",'
                            '"aggregated_output":"P@1\\t0.617","exit_code":0,"status":"completed"}}'
                        ),
                    ]
                ),
                encoding="utf-8",
            )

            trace = normalize_codex_jsonl(trace_path)

        self.assertEqual(trace["threadId"], "thread-1")
        self.assertEqual(len(trace["steps"]), 2)
        self.assertEqual(trace["steps"][1]["toolCalls"][0]["name"], "command_execution")
        self.assertIn("P@1", trace["steps"][1]["observation"])

    def test_harbor_reward_is_final_failure_when_verifier_text_is_sparse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "reward-only.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "steps": [{"index": 0, "role": "user", "text": "Fix the task."}],
                        "verifierLog": "",
                        "harbor": {"passed": False, "reward": 0.0},
                    }
                ),
                encoding="utf-8",
            )

            diagnosis = diagnose_trace(trace_path, run_id="reward-only")

        self.assertEqual(diagnosis.outcome, "failed")
        self.assertEqual(diagnosis.final_failure, "Harbor reward=0.0")

    def test_detects_swe_bench_pro_from_harbor_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "swebenchpro.json"
            trace_path.write_text(
                json.dumps(
                    {
                        "steps": [{"index": 0, "role": "user", "text": "Fix the uploaded repository."}],
                        "verifierLog": "RESULT: FAILED\nMissing tests: ['test_example']\n",
                        "harbor": {
                            "task_name": "instance_ansible__ansible-cd473dfb-v7eee2454",
                            "task_path": "datasets/swebenchpro/instance_ansible__ansible-cd473dfb-v7eee2454",
                            "passed": False,
                            "reward": 0.0,
                        },
                    }
                ),
                encoding="utf-8",
            )

            diagnosis = diagnose_trace(trace_path, run_id="swebenchpro")

        self.assertEqual(diagnosis.task_family, "swe-bench-pro")
        self.assertEqual(diagnosis.reference["verifier"], "SWE-bench Pro pytest/gold test harness")

    def test_exports_harbor_run_to_atif_viewer_local_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            viewer_root = root / "ATIF-trajectory-viewer"
            (viewer_root / "public" / "local").mkdir(parents=True)
            (viewer_root / "public" / "dataset.json").write_text(
                json.dumps({"tasks": [], "runs": [], "agents": [], "vendors": []}),
                encoding="utf-8",
            )

            task_dir = root / "harbor" / "datasets" / "swebenchpro" / "tasks" / "fix-ansible-invalid-hosts"
            (task_dir / "environment").mkdir(parents=True)
            (task_dir / "solution").mkdir()
            (task_dir / "tests").mkdir()
            (task_dir / "task.toml").write_text(
                '\n'.join(
                    [
                        'schema_version = "1.1"',
                        "",
                        "[task]",
                        'name = "swebenchpro-fix-ansible-invalid-hosts"',
                        'description = "Fix Ansible inventory validation."',
                        "",
                        "[metadata]",
                        'category = "programming"',
                        'tags = ["swe-bench-pro", "python"]',
                    ]
                ),
                encoding="utf-8",
            )
            (task_dir / "instruction.md").write_text("Fix the invalid hosts crash.\n", encoding="utf-8")
            (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
            (task_dir / "solution" / "solve.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\n", encoding="utf-8")

            trial_dir = root / "harbor" / "runs" / "swebenchpro-kimi" / "fix-ansible-invalid-hosts__trial"
            (trial_dir / "agent").mkdir(parents=True)
            (trial_dir / "verifier").mkdir()
            (trial_dir / "agent" / "trajectory.json").write_text(
                json.dumps(
                    {
                        "schema_version": "ATIF-v1.2",
                        "steps": [
                            {"step_id": 1, "source": "user", "message": "Fix the invalid hosts crash."},
                            {"step_id": 2, "source": "agent", "message": "Patched parser validation."},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (trial_dir / "verifier" / "test-stdout.txt").write_text("PASS\n", encoding="utf-8")
            (trial_dir / "result.json").write_text(
                json.dumps(
                    {
                        "task_name": "swebenchpro-fix-ansible-invalid-hosts",
                        "trial_name": "fix-ansible-invalid-hosts__trial",
                        "config": {
                            "agent": {"name": "claude-code", "model_name": "kimi-k2.6"},
                            "task": {"path": str(task_dir)},
                        },
                        "verifier_result": {"rewards": {"reward": 1.0}},
                    }
                ),
                encoding="utf-8",
            )

            summary = export_harbor_run_to_viewer(
                trial_dir.parent,
                viewer_root=viewer_root,
                label="swebenchpro-smoke",
                diagnose=True,
            )
            index = json.loads((viewer_root / "public" / "local" / "local-bundles.json").read_text(encoding="utf-8"))
            bundle = json.loads(Path(summary["bundle_path"]).read_text(encoding="utf-8"))
            payload = json.loads(Path(summary["payloads"][0]).read_text(encoding="utf-8"))
            info = viewer_info(viewer_root)

        self.assertEqual(summary["runs"], 1)
        self.assertEqual(index["bundles"][0]["id"], "swebenchpro-smoke")
        self.assertEqual(bundle["runs"][0]["format"], "atif")
        self.assertEqual(bundle["runs"][0]["payloadUrl"], "local/runs/swebenchpro-smoke/payloads/swebenchpro-smoke__swebenchpro-fix-ansible-invalid-hosts__fix-ansible-invalid-hosts__trial.json")
        self.assertEqual(payload["steps"][0]["role"], "user")
        self.assertEqual(info["local_bundles"], 1)


if __name__ == "__main__":
    unittest.main()
