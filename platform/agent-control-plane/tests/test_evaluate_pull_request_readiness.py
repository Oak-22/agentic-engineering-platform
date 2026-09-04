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
        "schemaVersion": 2,
        "headSha": "abc1234",
        "currentWithBase": True,
        "requiredChecks": [
            {"name": "control-plane-guards", "status": "success"},
            {"name": "aep-copilot-review", "status": "success"},
        ],
        "copilotReview": {
            "status": "success",
            "reviewId": "review-1",
            "headSha": "abc1234",
            "submittedAt": "2026-09-04T12:00:00Z",
            "normalizedFindings": [],
            "disputedFindings": [],
        },
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
            "copilot-finding": lambda item: item["copilotReview"].update(
                normalizedFindings=[{"id": "finding-1", "source": "line", "actionable": True}]
            ),
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

    def test_disputed_copilot_finding_is_exposed_but_not_clean(self):
        snapshot = ready_snapshot()
        snapshot["copilotReview"]["status"] = "neutral"
        snapshot["copilotReview"]["disputedFindings"] = ["finding-2"]
        result = MODULE.evaluate(snapshot)
        self.assertFalse(result.ready)
        self.assertIn("finding-2", result.disputedFindings)

    def test_declared_success_with_disputed_findings_is_neutral_not_ready(self):
        snapshot = ready_snapshot()
        snapshot["copilotReview"]["disputedFindings"] = ["finding-3"]
        result = MODULE.evaluate(snapshot)
        self.assertFalse(result.ready)
        self.assertIn("Copilot review status is neutral", result.blockers)
        self.assertEqual(result.disputedFindings, ("finding-3",))

    def test_comment_only_review_is_not_clean(self):
        review = {
            "reviewId": "review-2",
            "headSha": "abc1234",
            "submittedAt": "2026-09-04T12:00:00Z",
            "state": "COMMENTED",
            "lineComments": [],
        }
        normalized = MODULE.normalize_copilot_review(review, current_head="abc1234")
        self.assertEqual(normalized["status"], "failure")
        self.assertEqual(normalized["actionableFindings"], 1)

    def test_missing_review_metadata_is_rejected(self):
        snapshot = ready_snapshot()
        del snapshot["copilotReview"]["reviewId"]
        with self.assertRaisesRegex(MODULE.ReadinessError, "reviewId"):
            MODULE.evaluate(snapshot)

    def test_unknown_review_status_is_rejected(self):
        snapshot = ready_snapshot()
        snapshot["copilotReview"]["status"] = "commented"
        with self.assertRaisesRegex(MODULE.ReadinessError, "unknown format"):
            MODULE.evaluate(snapshot)

    def test_duplicate_findings_merge_toward_the_severe_reading(self):
        review = ready_snapshot()["copilotReview"]
        review["normalizedFindings"] = [
            {"id": "finding-1", "source": "line", "actionable": False, "disposition": "suppressed"},
            {"id": "finding-1", "source": "summary", "actionable": True},
            {"id": "finding-2", "source": "line", "actionable": False},
            {"id": "finding-2", "source": "unknown", "actionable": False},
        ]
        normalized = MODULE.normalize_copilot_review(review)
        findings = {item["id"]: item for item in normalized["normalizedFindings"]}
        self.assertEqual(list(findings), ["finding-1", "finding-2"])
        self.assertTrue(findings["finding-1"]["actionable"])
        self.assertEqual(findings["finding-1"]["disposition"], "open")
        self.assertEqual(findings["finding-2"]["source"], "unknown")
        self.assertEqual(normalized["actionableFindings"], 1)
        self.assertEqual(normalized["unrecognizedFindings"], 1)

    def test_whitespace_only_finding_id_is_rejected(self):
        review = ready_snapshot()["copilotReview"]
        review["normalizedFindings"] = [
            {"id": "   ", "source": "line", "actionable": True}
        ]
        with self.assertRaisesRegex(MODULE.ReadinessError, "normalizedFindings\\[0\\]\\.id"):
            MODULE.normalize_copilot_review(review)

    def test_short_head_sha_is_rejected(self):
        review = ready_snapshot()["copilotReview"]
        review["headSha"] = "abc12"
        with self.assertRaisesRegex(MODULE.ReadinessError, "headSha must be at least 7"):
            MODULE.normalize_copilot_review(review)

    def test_whitespace_only_disputed_finding_id_is_rejected(self):
        review = ready_snapshot()["copilotReview"]
        review["disputedFindings"] = ["   "]
        with self.assertRaisesRegex(MODULE.ReadinessError, "disputedFindings\\[0\\]"):
            MODULE.normalize_copilot_review(review)

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
