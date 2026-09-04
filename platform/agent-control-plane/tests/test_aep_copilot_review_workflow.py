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
    def setUp(self):
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_required_gate_cannot_be_skipped_and_uses_exact_review(self):
        workflow = self.workflow

        self.assertNotIn("aep-copilot-review:\n    if:", workflow)
        self.assertIn("EVENT_REVIEW_ID: ${{ github.event.review.id || '' }}", workflow)
        self.assertIn("pulls/${PR_NUMBER}/reviews/${REVIEW_ID}", workflow)
        self.assertIn("Check out the exact-head tooling", workflow)
        self.assertIn("ref: ${{ env.HEAD_SHA }}", workflow)
        self.assertIn("No Copilot review exists for current head", workflow)
        # Every review comment must reach the normalizer; one page is 30.
        self.assertIn(
            'gh api --paginate "repos/${REPOSITORY}/pulls/${PR_NUMBER}/comments?per_page=100"',
            workflow,
        )

    def test_manual_recovery_requires_explicit_tuple_and_exact_head(self):
        """A dispatch is a recovery path for a missing event run, never a bypass.

        It must name the pull request and review, take the head from the live
        pull request rather than trusting the caller, and refuse a dispatched
        ref that is not at that head so the check lands on the commit it
        evaluated.
        """
        workflow = self.workflow

        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("pr_number:\n        description:", workflow)
        self.assertIn("review_id:\n        description:", workflow)
        self.assertEqual(workflow.count("required: true"), 2)
        self.assertIn(
            "HEAD_SHA=\"$(gh api \"repos/${REPOSITORY}/pulls/${PR_NUMBER}\" --jq '.head.sha')\"",
            workflow,
        )
        self.assertIn('if [ "${RUN_SHA}" != "${HEAD_SHA}" ]; then', workflow)
        self.assertIn(
            "group: aep-copilot-review-${{ github.event.pull_request.number || inputs.pr_number }}",
            workflow,
        )
        # Both entry paths converge on one validation step; there is no second
        # validation chain a dispatch could take.
        self.assertEqual(workflow.count("No Copilot review exists for current head"), 1)
        self.assertEqual(workflow.count("not current head"), 1)

    def test_human_review_event_evaluates_copilot_latest_exact_head_review(self):
        """A person's review submission must not flip the required check.

        Every reply on a review thread is wrapped in a review by the replier and
        fires this workflow. The gate must then look up Copilot's latest review
        of the exact current head rather than judging the event's author, and
        fail only when no such review exists.
        """
        workflow = self.workflow

        self.assertIn("not Copilot; evaluating Copilot's latest review of", workflow)
        self.assertIn('--paginate "repos/${REPOSITORY}/pulls/${PR_NUMBER}/reviews?per_page=100"', workflow)
        self.assertIn(".commit_id == $head", workflow)
        self.assertIn("sort_by(.submitted_at) | last // empty", workflow)
        self.assertNotIn("not attributable to Copilot", workflow)


if __name__ == "__main__":
    unittest.main()
