from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "copilot_review_gate", ROOT / "scripts" / "copilot_review_gate.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def review(**overrides):
    result = {
        "status": "success",
        "reviewId": "r-1",
        "headSha": "abc1234",
        "submittedAt": "2026-09-04T12:00:00Z",
        "normalizedFindings": [],
        "disputedFindings": [],
    }
    result.update(overrides)
    return result


class CopilotGateTests(unittest.TestCase):
    def test_clean_exact_head_is_success(self):
        self.assertEqual(MODULE.gate(review(), head_sha="abc1234")["conclusion"], "success")

    def test_stale_head_fails(self):
        self.assertEqual(MODULE.gate(review(headSha="old1234"), head_sha="abc1234")["conclusion"], "failure")

    def test_actionable_finding_fails(self):
        result = MODULE.gate(
            review(normalizedFindings=[{"id": "f-1", "source": "line", "actionable": True}]),
            head_sha="abc1234",
        )
        self.assertEqual(result["conclusion"], "failure")

    def test_disputed_findings_are_neutral(self):
        result = MODULE.gate(
            review(status="neutral", disputedFindings=["f-1"]), head_sha="abc1234"
        )
        self.assertEqual(result["conclusion"], "neutral")

    def test_pending_review_stays_pending(self):
        result = MODULE.gate(review(status="pending"), head_sha="abc1234")
        self.assertEqual(result["conclusion"], "pending")

    def test_commented_review_with_only_suppressed_findings_passes_when_status_is_explicit(self):
        # The workflow emits exactly this shape for a "Needs a closer look"
        # review with zero generated comments: state COMMENTED, explicit
        # status, a non-actionable summary, and the suppressed items.
        result = MODULE.gate(
            review(
                state="COMMENTED",
                status="success",
                normalizedFindings=None,
                summaryFindings=[{"id": "summary:r-1", "actionable": False}],
                suppressedFindings=[{"id": "suppressed:a.py:7"}, {"id": "suppressed:b.py:9"}],
            ),
            head_sha="abc1234",
        )
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(result["review"]["actionableFindings"], 0)
        self.assertEqual(len(result["review"]["normalizedFindings"]), 3)

    def test_changes_recommended_headline_fails_even_without_generated_comments(self):
        result = MODULE.gate(
            review(
                state="COMMENTED",
                status="failure",
                normalizedFindings=None,
                summaryFindings=[{"id": "summary:r-1", "actionable": True}],
            ),
            head_sha="abc1234",
        )
        self.assertEqual(result["conclusion"], "failure")

    def test_suppressed_summary_is_retained_without_blocking(self):
        result = MODULE.gate(
            review(
                suppressedFindings=[{"id": "f-2"}],
                normalizedFindings=None,
            ),
            head_sha="abc1234",
        )
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(result["review"]["normalizedFindings"][0]["disposition"], "suppressed")

    def test_unknown_finding_source_is_rejected(self):
        with self.assertRaisesRegex(MODULE.ReadinessError, "unknown format"):
            MODULE.gate(
                review(
                    normalizedFindings=[
                        {"id": "f-3", "source": "provider-specific", "actionable": False}
                    ]
                ),
                head_sha="abc1234",
            )

    def test_non_positive_or_blank_review_ids_are_rejected(self):
        for value in (0, "   "):
            with self.subTest(value=value):
                with self.assertRaises(MODULE.ReadinessError):
                    MODULE.gate(review(reviewId=value), head_sha="abc1234")


if __name__ == "__main__":
    unittest.main()
