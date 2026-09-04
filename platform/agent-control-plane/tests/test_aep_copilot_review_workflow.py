from __future__ import annotations

from pathlib import Path
import unittest


WORKFLOW = (
    Path(__file__).resolve().parents[3]
    / ".github"
    / "workflows"
    / "aep-copilot-review.yml"
)


class AepCopilotReviewWorkflowTests(unittest.TestCase):
    def test_required_gate_cannot_be_skipped_and_uses_exact_review(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertNotIn("aep-copilot-review:\n    if:", workflow)
        self.assertIn("REVIEW_ID: ${{ github.event.review.id }}", workflow)
        self.assertIn("pulls/${PR_NUMBER}/reviews/${REVIEW_ID}", workflow)
        self.assertIn("Check out the exact-head tooling", workflow)
        self.assertIn("ref: ${{ github.event.pull_request.head.sha }}", workflow)
        self.assertIn("not attributable to Copilot", workflow)


if __name__ == "__main__":
    unittest.main()
