import importlib.util
import json
from pathlib import Path
import sys
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "prepare_delivery_branch.py"
)
SPEC = importlib.util.spec_from_file_location("prepare_delivery_branch", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BranchNameTests(unittest.TestCase):
    def test_every_authoring_category_is_accepted(self):
        for category in MODULE.AUTHORING_CATEGORIES:
            with self.subTest(category=category):
                self.assertIsNone(
                    MODULE.validate_branch_name(f"{category}/PROJ-12-telemetry-layout")
                )

    def test_a_retired_category_names_its_replacement(self):
        error = MODULE.validate_branch_name("bugfix/PROJ-12-thing")

        self.assertIsNotNone(error)
        self.assertIn("retired", error)
        self.assertIn("use `fix`", error)

    def test_hotfix_points_at_priority_rather_than_the_branch_name(self):
        """Urgency is a work-item axis; encoding it in a ref hides it."""
        error = MODULE.validate_branch_name("hotfix/PROJ-12-thing")

        self.assertIn("priority", error)

    def test_release_is_rejected_as_a_process_step(self):
        error = MODULE.validate_branch_name("release/PROJ-12-thing")

        self.assertIn("process step", error)

    def test_an_unknown_category_points_at_the_class_field(self):
        error = MODULE.validate_branch_name("banana/PROJ-12-thing")

        self.assertIn("Class field", error)

    def test_a_branch_without_a_full_issue_key_is_rejected(self):
        self.assertIsNotNone(MODULE.validate_branch_name("fix/PROJ-thing"))

    def test_a_branch_without_a_slug_is_rejected(self):
        self.assertIsNotNone(MODULE.validate_branch_name("fix/PROJ-12"))

    def test_a_bare_name_is_rejected(self):
        self.assertIsNotNone(MODULE.validate_branch_name("nonsense"))


class BaselineDecisionTests(unittest.TestCase):
    def test_matching_main_needs_no_action(self):
        decision = MODULE.baseline_decision(True, 0, 0)

        self.assertEqual(decision.action, MODULE.OK)
        self.assertFalse(decision.mutates)

    def test_behind_main_fast_forwards(self):
        decision = MODULE.baseline_decision(True, 0, 4)

        self.assertEqual(decision.action, MODULE.FAST_FORWARD)
        self.assertTrue(decision.mutates)
        self.assertIn("4 commit(s) behind", decision.detail)

    def test_ahead_main_blocks_and_is_never_rewritten(self):
        decision = MODULE.baseline_decision(True, 2, 0)

        self.assertTrue(decision.blocks)
        self.assertIn("without a reviewed pull request", decision.detail)

    def test_diverged_main_blocks_and_reports_both_sides(self):
        decision = MODULE.baseline_decision(True, 2, 5)

        self.assertTrue(decision.blocks)
        self.assertIn("2 unique local commit(s)", decision.detail)
        self.assertIn("5 unique remote commit(s)", decision.detail)
        self.assertIn("will not rewrite history", decision.detail)

    def test_an_untracked_remote_is_not_treated_as_drift(self):
        """A repository with no origin/main cannot be judged against one."""
        decision = MODULE.baseline_decision(False, 9, 9)

        self.assertEqual(decision.action, MODULE.OK)


class WorkbenchDecisionTests(unittest.TestCase):
    def test_an_absent_workbench_is_not_held_to_the_contract(self):
        decision = MODULE.workbench_decision(False, 0)

        self.assertEqual(decision.action, MODULE.OK)
        self.assertIn("direct-delivery", decision.detail)

    def test_a_behind_workbench_is_synced_rather_than_blocked(self):
        decision = MODULE.workbench_decision(True, 3)

        self.assertEqual(decision.action, MODULE.SYNC)
        self.assertTrue(decision.mutates)

    def test_one_missing_commit_still_needs_a_sync(self):
        self.assertEqual(MODULE.workbench_decision(True, 1).action, MODULE.SYNC)

    def test_a_current_workbench_needs_no_action(self):
        self.assertEqual(MODULE.workbench_decision(True, 0).action, MODULE.OK)


class WorktreeAndEvidenceTests(unittest.TestCase):
    def test_a_dirty_tree_blocks_and_lists_the_entries(self):
        decision = MODULE.worktree_decision((" M one.txt", "?? two.txt"))

        self.assertTrue(decision.blocks)
        self.assertIn(" M one.txt", decision.detail)
        self.assertIn("?? two.txt", decision.detail)

    def test_a_clean_tree_passes(self):
        self.assertEqual(MODULE.worktree_decision(()).action, MODULE.OK)

    def test_unresolved_evidence_blocks_and_names_the_choices(self):
        decision = MODULE.evidence_decision(2, "    abc1234 A thing [p1]")

        self.assertTrue(decision.blocks)
        self.assertIn("2 workbench-only outcome(s)", decision.detail)
        self.assertIn("Deliver, park, or supersede", decision.detail)
        self.assertIn("abc1234", decision.detail)

    def test_fully_reconciled_evidence_passes(self):
        self.assertEqual(MODULE.evidence_decision(0, "").action, MODULE.OK)


class ReportingTests(unittest.TestCase):
    def clean_plan(self):
        return (
            MODULE.worktree_decision(()),
            MODULE.baseline_decision(True, 0, 0),
            MODULE.workbench_decision(True, 0),
            MODULE.evidence_decision(0, ""),
        )

    def test_blocking_collects_only_blocked_stages(self):
        decisions = (
            MODULE.worktree_decision((" M one.txt",)),
            MODULE.baseline_decision(True, 0, 4),
            MODULE.evidence_decision(1, "x"),
        )

        self.assertEqual(len(MODULE.blocking(decisions)), 2)

    def test_a_clean_plan_has_nothing_blocking(self):
        self.assertEqual(MODULE.blocking(self.clean_plan()), ())

    def test_plan_output_says_nothing_was_changed_when_blocked(self):
        text = MODULE.render_text(
            "fix/PROJ-1-x",
            (MODULE.worktree_decision((" M one.txt",)),),
            executed=False,
            base=None,
        )

        self.assertIn("Nothing was changed", text)

    def test_plan_output_invites_execute_when_clear(self):
        text = MODULE.render_text(
            "fix/PROJ-1-x", self.clean_plan(), executed=False, base=None
        )

        self.assertIn("--execute", text)
        self.assertNotIn("Nothing was changed", text)

    def test_pending_mutations_are_described_before_they_happen(self):
        text = MODULE.render_text(
            "fix/PROJ-1-x",
            (MODULE.baseline_decision(True, 0, 2), MODULE.workbench_decision(True, 2)),
            executed=False,
            base=None,
        )

        self.assertIn("would fast-forward", text)
        self.assertIn("would sync", text)

    def test_executed_output_reports_the_verified_base(self):
        text = MODULE.render_text(
            "fix/PROJ-1-x", self.clean_plan(), executed=True, base="abc1234"
        )

        self.assertIn("Created fix/PROJ-1-x", text)
        self.assertIn("abc1234", text)

    def test_executed_output_reports_mutations_in_the_past_tense(self):
        text = MODULE.render_text(
            "fix/PROJ-1-x",
            (MODULE.baseline_decision(True, 0, 2), MODULE.workbench_decision(True, 2)),
            executed=True,
            base="abc1234",
        )

        self.assertIn("fast-forwarded", text)
        self.assertIn("synced", text)
        self.assertNotIn("would", text)

    def test_json_report_carries_every_stage_and_the_blocked_flag(self):
        payload = json.loads(
            MODULE.render_json(
                "fix/PROJ-1-x",
                (MODULE.worktree_decision((" M one.txt",)),),
                executed=False,
                base=None,
            )
        )

        self.assertTrue(payload["blocked"])
        self.assertFalse(payload["executed"])
        self.assertIsNone(payload["base"])
        self.assertEqual(payload["stages"][0]["action"], MODULE.BLOCKED)


if __name__ == "__main__":
    unittest.main()
