"""Self-tests for the deployment regression gate. Run: python3 -m unittest discover .github/scripts"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import require_full_regression as gate  # noqa: E402

SHA = "a" * 40
OTHER = "b" * 40
PATH = ".github/workflows/backend-full.yml"


def run(**overrides):
    values = {"head_sha": SHA, "path": PATH, "status": "completed", "conclusion": "success"}
    values.update(overrides)
    return values


class GateTests(unittest.TestCase):
    def test_completed_success_for_the_exact_sha_passes(self):
        self.assertEqual(len(gate.passing_runs([run()], SHA)), 1)

    def test_other_revisions_never_count(self):
        # An older staging revision, or a pull-request head, is a different commit.
        self.assertEqual(gate.passing_runs([run(head_sha=OTHER)], SHA), [])

    def test_running_failed_and_cancelled_runs_never_count(self):
        for overrides in (
            {"status": "in_progress", "conclusion": None},
            {"status": "queued", "conclusion": None},
            {"conclusion": "failure"},
            {"conclusion": "cancelled"},
            {"conclusion": "timed_out"},
            {"conclusion": "skipped"},
        ):
            with self.subTest(**overrides):
                self.assertEqual(gate.passing_runs([run(**overrides)], SHA), [])

    def test_other_workflows_never_count(self):
        self.assertEqual(gate.passing_runs([run(path=".github/workflows/backend-targeted.yml")], SHA), [])

    def test_one_success_among_failures_passes(self):
        runs = [run(conclusion="failure"), run(conclusion="cancelled"), run()]
        self.assertEqual(len(gate.passing_runs(runs, SHA)), 1)


if __name__ == "__main__":
    unittest.main()
