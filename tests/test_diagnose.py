from __future__ import annotations

import unittest
from pathlib import Path

from harness_trajecdebug.diagnose import diagnose_trace


ROOT = Path(__file__).resolve().parents[1]


class DiagnoseExamplesTest(unittest.TestCase):
    def test_train_fasttext_near_miss(self) -> None:
        diagnosis = diagnose_trace(
            ROOT / "examples" / "traces" / "train-fasttext-kimi-k26-minimal.json",
            run_id="train-fasttext-kimi-k26-minimal",
        )
        self.assertEqual(diagnosis.task_family, "train-fasttext")
        self.assertEqual(diagnosis.outcome, "failed")
        self.assertEqual(diagnosis.final_failure, "final verifier P@1=0.617 < threshold 0.62")
        names = [pattern.name for pattern in diagnosis.failure_patterns]
        self.assertIn("thin-margin promotion", names)
        self.assertIn("compact-frontier search gap", names)
        self.assertIsNotNone(diagnosis.critical_step)
        assert diagnosis.critical_step is not None
        self.assertEqual(diagnosis.critical_step["pattern"], "thin-margin promotion")
        self.assertEqual(diagnosis.critical_step["step_index"], 8)

    def test_cancel_async_passed(self) -> None:
        diagnosis = diagnose_trace(
            ROOT / "examples" / "traces" / "cancel-async-tasks-passed-minimal.json",
            run_id="cancel-async-tasks-passed-minimal",
        )
        self.assertEqual(diagnosis.task_family, "cancel-async-tasks")
        self.assertEqual(diagnosis.outcome, "passed")
        self.assertIsNone(diagnosis.final_failure)
        self.assertEqual([pattern.name for pattern in diagnosis.failure_patterns], ["no critical failure detected"])
        self.assertIsNone(diagnosis.critical_step)


if __name__ == "__main__":
    unittest.main()
