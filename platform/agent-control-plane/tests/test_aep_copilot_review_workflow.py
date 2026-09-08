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

    def test_the_gate_reports_on_the_pull_request_itself(self):
        """Only a pull-request run reaches the branch rule.

        A check run produced by any other trigger does not enter the pull
        request's status rollup, so a gate driven by the review event can
        publish a verdict the rule never reads.
        """
        workflow = self.workflow

        self.assertIn("  pull_request:\n    types: [opened, synchronize, reopened]", workflow)
        self.assertNotIn("pull_request_review:", workflow)
        self.assertNotIn("aep-copilot-review:\n    if:", workflow)
        self.assertIn("EVENT_HEAD_SHA: ${{ github.event.pull_request.head.sha || '' }}", workflow)
        self.assertIn("ref: ${{ env.HEAD_SHA }}", workflow)

    def test_the_gate_waits_for_ordered_evidence(self):
        """Guards first, then Copilot's review of the same head.

        A guard failure means Copilot is never requested, so the gate says so
        at once instead of waiting out the review window for evidence that
        cannot arrive.
        """
        workflow = self.workflow

        self.assertIn("Wait for the control-plane guards on this head", workflow)
        self.assertIn("Wait for Copilot's review of this head", workflow)
        self.assertIn("the gate has nothing to evaluate", workflow)
        self.assertIn("did not complete for ${HEAD_SHA} within the wait window", workflow)
        self.assertLess(
            workflow.index("Wait for the control-plane guards on this head"),
            workflow.index("Wait for Copilot's review of this head"),
        )
        # Waiting is only safe if the runner budget covers both windows.
        self.assertIn("timeout-minutes: 30", workflow)
        self.assertIn("checks: read", workflow)

    def test_missing_evidence_fails_closed(self):
        workflow = self.workflow

        self.assertIn("No Copilot review exists for current head", workflow)
        self.assertEqual(workflow.count("No Copilot review exists for current head"), 1)
        self.assertIn("pending|failure) exit 1 ;;", workflow)

    def test_the_review_selected_is_copilot_latest_at_the_exact_head(self):
        workflow = self.workflow

        self.assertIn('--paginate "repos/${REPOSITORY}/pulls/${PR_NUMBER}/reviews?per_page=100"', workflow)
        self.assertIn(".commit_id == $head", workflow)
        self.assertIn("sort_by(.submitted_at) | last // empty", workflow)
        # Every review comment must reach the normalizer; one page is 30.
        self.assertIn(
            'gh api --paginate "repos/${REPOSITORY}/pulls/${PR_NUMBER}/comments?per_page=100"',
            workflow,
        )

    def test_manual_dispatch_is_a_diagnostic_bound_to_the_current_head(self):
        """A dispatch runs the same evaluation and can never be a bypass.

        Its check run does not enter the rollup, so it cannot satisfy the
        required check even when it passes.
        """
        workflow = self.workflow

        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("pr_number:\n        description:", workflow)
        self.assertEqual(workflow.count("required: true"), 1)
        self.assertNotIn("review_id:", workflow)
        self.assertIn(
            "HEAD_SHA=\"$(gh api \"repos/${REPOSITORY}/pulls/${PR_NUMBER}\" --jq '.head.sha')\"",
            workflow,
        )
        self.assertIn('if [ "${RUN_SHA}" != "${HEAD_SHA}" ]; then', workflow)

    def test_a_superseded_head_stops_waiting(self):
        workflow = self.workflow

        self.assertIn(
            "group: aep-copilot-review-${{ github.event.pull_request.number || inputs.pr_number }}",
            workflow,
        )
        self.assertIn("cancel-in-progress: true", workflow)

    def test_clean_rule_follows_copilot_posting_threshold(self):
        """Actionable means a generated comment or a changes headline.

        Suppressed findings are recorded but never block, and the payload sets
        status explicitly so a COMMENTED review with nothing actionable is not
        mapped to failure by the state alone.
        """
        workflow = self.workflow

        self.assertIn("'changes recommended' in lowered or 'changes required' in lowered", workflow)
        self.assertIn("'actionable': changes_requested", workflow)
        self.assertIn("f\"suppressed:{path}:{line}\", 'actionable': False", workflow)
        self.assertIn("'suppressedFindings': suppressed", workflow)
        self.assertIn(
            "'status': 'failure' if (line_comments or changes_requested) else 'success'",
            workflow,
        )
        self.assertNotIn("no issues found", workflow)

    def test_dependabot_pull_requests_pass_without_a_copilot_review(self):
        """Copilot does not review dependabot[bot] pull requests.

        Without a waiver the gate's review wait always exhausts its window and
        exits 1, and the strict main ruleset requires this check, so every
        Dependabot pull request would be unmergeable. The waiver passes on the
        control-plane guards alone; a non-Dependabot author still fails closed.
        """
        workflow = self.workflow

        # The author is resolved once, up front, for the waiver decision.
        self.assertIn("PR_AUTHOR=${PR_AUTHOR}", workflow)
        self.assertIn(
            'PR_AUTHOR="$(gh api "repos/${REPOSITORY}/pulls/${PR_NUMBER}" --jq \'.user.login\')"',
            workflow,
        )

        # A Dependabot pull request gets a short grace window, then a success
        # result, and the normalizer steps are skipped.
        self.assertIn('if [ "${PR_AUTHOR}" = "dependabot[bot]" ]; then', workflow)
        self.assertIn("ATTEMPTS=3", workflow)
        self.assertIn('echo "COPILOT_REVIEW_WAIVED=dependabot" >> "$GITHUB_ENV"', workflow)
        self.assertIn('{\\"conclusion\\":\\"success\\",\\"waived\\":\\"dependabot\\"', workflow)
        # checkout, setup-python, fetch-and-normalize, publish-normalized are
        # all skipped on the waiver path; the waiver-summary step runs instead.
        self.assertEqual(workflow.count("if: env.COPILOT_REVIEW_WAIVED == ''"), 4)
        self.assertIn("if: env.COPILOT_REVIEW_WAIVED != ''", workflow)

        # The waiver lives inside the "no review" branch, and the
        # non-Dependabot path there still fails closed. The single-occurrence
        # assertion in test_missing_evidence_fails_closed keeps that message unique.
        waiver = workflow.index("Passing on the control-plane guards alone")
        fail_closed = workflow.index(
            "No Copilot review exists for current head ${HEAD_SHA}; nothing to evaluate."
        )
        review_wait = workflow.index("Wait for Copilot's review of this head")
        self.assertLess(review_wait, waiver)
        self.assertLess(waiver, fail_closed)
        self.assertIn("exit 1", workflow[fail_closed:fail_closed + 200])

        # The enforce step no longer needs Python, so it runs on the waived
        # path where setup-python was skipped.
        self.assertIn("CONCLUSION=\"$(jq -r '.conclusion' /tmp/copilot-result.json)\"", workflow)


if __name__ == "__main__":
    unittest.main()
