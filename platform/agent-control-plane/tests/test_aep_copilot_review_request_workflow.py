from __future__ import annotations

from pathlib import Path
import unittest


WORKFLOW = (
    Path(__file__).resolve().parents[3]
    / ".github"
    / "workflows"
    / "aep-copilot-review-request.yml"
)


class AepCopilotReviewRequestWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_request_never_reports_the_required_gate(self):
        """Request orchestration is separate from the required check.

        A deferred or skipped request run must not produce a skipped
        `aep-copilot-review` check, which a ruleset would treat as satisfied.
        """
        workflow = self.workflow

        self.assertIn("request-copilot:", workflow)
        self.assertNotIn("aep-copilot-review:", workflow)
        self.assertIn("reviewers[]=copilot-pull-request-reviewer[bot]", workflow)

    def test_request_targets_the_live_head_only(self):
        """A guard run describes the head it started on, not the live one.

        When the pull request has advanced since, the request defers so the
        newer head's own guard run requests its review; a review for a
        superseded head can never satisfy the exact-head gate.
        """
        workflow = self.workflow

        self.assertIn(
            "LIVE_HEAD_SHA=\"$(gh api \"repos/${REPOSITORY}/pulls/${PR_NUMBER}\" --jq '.head.sha')\"",
            workflow,
        )
        self.assertIn('elif [ "${HEAD_SHA}" != "${LIVE_HEAD_SHA}" ]; then', workflow)
        self.assertIn("review request deferred to the current head's guard run", workflow)
        # The live-head comparison happens before the guard conclusion is
        # consulted, so a stale success never reaches the request call.
        self.assertLess(
            workflow.index('elif [ "${HEAD_SHA}" != "${LIVE_HEAD_SHA}" ]'),
            workflow.index('if [ "${GUARD}" != "success" ]; then'),
        )

    def test_requests_serialize_per_pull_request(self):
        """Every trigger path keys concurrency on the pull request.

        Grouping by the workflow_run id would let two guard runs for one pull
        request request a review concurrently.
        """
        workflow = self.workflow

        self.assertIn(
            "group: aep-copilot-review-request-${{ github.event.pull_request.number"
            " || github.event.workflow_run.pull_requests[0].number"
            " || github.event.inputs.pr_number || github.run_id }}",
            workflow,
        )
        self.assertNotIn("github.event.workflow_run.id || github.run_id", workflow)
        self.assertIn("cancel-in-progress: false", workflow)


if __name__ == "__main__":
    unittest.main()
