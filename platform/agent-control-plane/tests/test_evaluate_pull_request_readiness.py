from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "evaluate_pull_request_readiness.py"
)
SPEC = importlib.util.spec_from_file_location("evaluate_pull_request_readiness", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def ready_snapshot() -> dict:
    return {
        "schemaVersion": 1,
        "headSha": "abc1234",
        "currentWithBase": True,
        "requiredChecks": [{"name": "control-plane-guards", "status": "success"}],
        "copilotReview": {"headSha": "abc1234", "actionableFindings": 0},
        "reviewThreads": [],
        "evidenceAligned": True,
    }


class ReadinessTests(unittest.TestCase):
    def test_all_evidence_ready(self):
        result = MODULE.evaluate(ready_snapshot())
        self.assertTrue(result.ready)
        self.assertEqual(result.blockers, ())

    def test_each_required_gate_blocks_readiness(self):
        cases = {
            "stale": lambda item: item.update(currentWithBase=False),
            "check": lambda item: item["requiredChecks"][0].update(status="pending"),
            "copilot-head": lambda item: item["copilotReview"].update(headSha="old1234"),
            "copilot-finding": lambda item: item["copilotReview"].update(actionableFindings=1),
            "thread": lambda item: item["reviewThreads"].append(
                {"id": "thread-1", "state": "actionable"}
            ),
            "evidence": lambda item: item.update(evidenceAligned=False),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                snapshot = ready_snapshot()
                mutate(snapshot)
                self.assertFalse(MODULE.evaluate(snapshot).ready)

    def test_disputed_thread_is_preserved_for_human_without_becoming_actionable(self):
        snapshot = ready_snapshot()
        snapshot["reviewThreads"] = [{"id": "thread-2", "state": "disputed"}]
        result = MODULE.evaluate(snapshot)
        self.assertTrue(result.ready)
        self.assertEqual(result.disputedThreads, ("thread-2",))

    def test_unknown_thread_state_is_rejected(self):
        snapshot = ready_snapshot()
        snapshot["reviewThreads"] = [{"id": "thread-3", "state": "ignored"}]
        with self.assertRaisesRegex(MODULE.ReadinessError, "resolved, actionable, or disputed"):
            MODULE.evaluate(snapshot)

    def test_empty_required_checks_is_rejected(self):
        snapshot = ready_snapshot()
        snapshot["requiredChecks"] = []
        with self.assertRaisesRegex(MODULE.ReadinessError, "at least one"):
            MODULE.evaluate(snapshot)


if __name__ == "__main__":
    unittest.main()
