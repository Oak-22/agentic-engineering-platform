import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "delivery_worktrees.py"
SPEC = importlib.util.spec_from_file_location("delivery_worktrees", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def ownership(
    branch="feature/PROJ-1-thing",
    jira_key="PROJ-1",
    worktree_path="/w/PROJ-1",
    base_commit="abc1234",
    agent="agent-a",
    created_at="2026-08-31T00:00:00+00:00",
    adopted=False,
):
    return MODULE.Ownership(
        branch=branch,
        jira_key=jira_key,
        worktree_path=worktree_path,
        base_commit=base_commit,
        agent=agent,
        created_at=created_at,
        adopted=adopted,
    )


class JiraKeyTests(unittest.TestCase):
    def test_the_key_is_read_from_the_branch(self):
        self.assertEqual(MODULE.jira_key_of("refactor/AEPI-115-worktrees"), "AEPI-115")

    def test_every_authoring_category_carries_a_key(self):
        for category in ("feature", "fix", "refactor", "chore", "docs"):
            with self.subTest(category=category):
                self.assertEqual(
                    MODULE.jira_key_of(f"{category}/TEAM-42-thing"), "TEAM-42"
                )

    def test_a_branch_without_a_key_is_refused(self):
        """A worktree is owned by a work item, so an unkeyed branch has no owner."""
        with self.assertRaises(MODULE.WorktreeError):
            MODULE.jira_key_of("experiment/scratch")

    def test_a_key_without_a_slug_is_refused(self):
        with self.assertRaises(MODULE.WorktreeError):
            MODULE.jira_key_of("feature/PROJ-1")


class ClaimConflictTests(unittest.TestCase):
    def test_a_free_branch_and_path_is_granted(self):
        self.assertIsNone(
            MODULE.claim_conflict("feature/PROJ-2-other", "/w/PROJ-2", (ownership(),))
        )

    def test_a_second_claim_on_one_branch_is_refused(self):
        """Two agents on one ref publish incompatible histories to it."""
        conflict = MODULE.claim_conflict(
            "feature/PROJ-1-thing", "/w/elsewhere", (ownership(),)
        )

        self.assertIsNotNone(conflict)
        self.assertIn("already owned by agent-a", conflict)

    def test_a_second_claim_on_one_directory_is_refused(self):
        """Two agents in one directory overwrite each other's files."""
        conflict = MODULE.claim_conflict(
            "feature/PROJ-2-other", "/w/PROJ-1", (ownership(),)
        )

        self.assertIsNotNone(conflict)
        self.assertIn("already the worktree for feature/PROJ-1-thing", conflict)

    def test_the_conflict_names_the_owner_and_when_they_claimed_it(self):
        conflict = MODULE.claim_conflict("feature/PROJ-1-thing", "/w/x", (ownership(),))

        self.assertIn("agent-a", conflict)
        self.assertIn("2026-08-31T00:00:00+00:00", conflict)

    def test_no_existing_claims_never_conflicts(self):
        self.assertIsNone(MODULE.claim_conflict("feature/PROJ-1-thing", "/w/PROJ-1", ()))


class ReconcileTests(unittest.TestCase):
    def test_a_recorded_worktree_that_exists_is_active(self):
        reconciled = MODULE.reconcile(
            (ownership(),), {"/w/PROJ-1": ("feature/PROJ-1-thing", "abc1234")}
        )

        self.assertEqual(len(reconciled), 1)
        self.assertEqual(reconciled[0].status, MODULE.REGISTERED_LIVE)
        self.assertFalse(reconciled[0].needs_attention)

    def test_a_record_whose_directory_is_gone_is_reported_not_dropped(self):
        """The record is the only trace that the delivery ever existed."""
        reconciled = MODULE.reconcile((ownership(),), {})

        self.assertEqual(reconciled[0].status, MODULE.REGISTERED_MISSING)
        self.assertTrue(reconciled[0].needs_attention)
        self.assertIsNotNone(reconciled[0].ownership)

    def test_a_worktree_with_no_record_is_reported_as_unowned(self):
        reconciled = MODULE.reconcile((), {"/w/stray": ("feature/PROJ-9-x", "def5678")})

        self.assertEqual(reconciled[0].status, MODULE.UNREGISTERED)
        self.assertIsNone(reconciled[0].ownership)
        self.assertEqual(reconciled[0].branch, "feature/PROJ-9-x")

    def test_both_kinds_of_drift_are_reported_together(self):
        reconciled = MODULE.reconcile(
            (ownership(), ownership(branch="feature/PROJ-2-b", worktree_path="/w/PROJ-2")),
            {"/w/PROJ-2": ("feature/PROJ-2-b", "aaa"), "/w/stray": (None, "bbb")},
        )

        by_status = {item.status for item in reconciled}
        self.assertEqual(
            by_status,
            {MODULE.REGISTERED_LIVE, MODULE.REGISTERED_MISSING, MODULE.UNREGISTERED},
        )

    def test_nothing_recorded_and_nothing_live_reconciles_empty(self):
        self.assertEqual(MODULE.reconcile((), {}), ())


class OverlapTests(unittest.TestCase):
    def test_disjoint_deliveries_report_no_overlap(self):
        found = MODULE.overlaps(
            {
                "feature/PROJ-1-a": frozenset({"one.md"}),
                "feature/PROJ-2-b": frozenset({"two.md"}),
            }
        )

        self.assertEqual(found, ())

    def test_shared_paths_are_reported_as_a_pair(self):
        found = MODULE.overlaps(
            {
                "feature/PROJ-1-a": frozenset({"one.md", "shared.md"}),
                "feature/PROJ-2-b": frozenset({"two.md", "shared.md"}),
            }
        )

        self.assertEqual(len(found), 1)
        first, second, paths = found[0]
        self.assertEqual((first, second), ("feature/PROJ-1-a", "feature/PROJ-2-b"))
        self.assertEqual(paths, ("shared.md",))

    def test_every_overlapping_pair_is_reported(self):
        found = MODULE.overlaps(
            {
                "feature/PROJ-1-a": frozenset({"shared.md"}),
                "feature/PROJ-2-b": frozenset({"shared.md"}),
                "feature/PROJ-3-c": frozenset({"shared.md"}),
            }
        )

        self.assertEqual(len(found), 3)

    def test_a_single_delivery_cannot_overlap_itself(self):
        self.assertEqual(
            MODULE.overlaps({"feature/PROJ-1-a": frozenset({"one.md"})}), ()
        )

    def test_overlap_is_reported_as_risk_rather_than_a_conflict(self):
        text = MODULE.render_overlap(
            (("feature/PROJ-1-a", "feature/PROJ-2-b", ("shared.md",)),)
        )

        self.assertIn("coordination risk, not a conflict", text)
        self.assertIn("shared.md", text)


class WorktreePlacementTests(unittest.TestCase):
    def test_a_worktree_is_placed_beside_the_repository_not_inside_it(self):
        """Nested worktrees show up as untracked content and block the next delivery."""
        root = Path("/projects/aep")

        target = MODULE.default_worktree_path(root, "PROJ-1")

        self.assertEqual(target, Path("/projects/aep.worktrees/PROJ-1"))
        self.assertNotIn(root, target.parents)

    def test_each_key_gets_its_own_directory(self):
        root = Path("/projects/aep")

        self.assertNotEqual(
            MODULE.default_worktree_path(root, "PROJ-1"),
            MODULE.default_worktree_path(root, "PROJ-2"),
        )


class OwnershipRecordTests(unittest.TestCase):
    def test_ownership_round_trips_through_the_machine_local_record(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / MODULE.OWNERSHIP_FILENAME
            MODULE.save_ownership(path, (ownership(), ownership(branch="feature/PROJ-2-b")))

            loaded = MODULE.load_ownership(path)

            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0].branch, "feature/PROJ-1-thing")
            self.assertEqual(loaded[0].agent, "agent-a")
            self.assertEqual(loaded[0].base_commit, "abc1234")

    def test_a_missing_record_is_empty_not_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(MODULE.load_ownership(Path(directory) / "absent.json"), ())

    def test_an_unreadable_record_is_reported_rather_than_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{not json")

            with self.assertRaises(MODULE.WorktreeError):
                MODULE.load_ownership(path)

    def test_records_are_written_in_a_stable_order(self):
        """An unstable order makes every write look like a change."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / MODULE.OWNERSHIP_FILENAME
            MODULE.save_ownership(
                path, (ownership(branch="feature/PROJ-9-z"), ownership())
            )

            written = json.loads(path.read_text())["worktrees"]

            self.assertEqual(
                [item["branch"] for item in written],
                ["feature/PROJ-1-thing", "feature/PROJ-9-z"],
            )


class RefreshDecisionTests(unittest.TestCase):
    def test_a_current_branch_needs_no_merge(self):
        action, detail = MODULE.refresh_decision(True, (), 0)

        self.assertEqual(action, MODULE.REFRESH_CURRENT)
        self.assertIn("every main commit", detail)

    def test_a_trailing_branch_merges(self):
        action, detail = MODULE.refresh_decision(True, (), 4)

        self.assertEqual(action, MODULE.REFRESH_MERGE)
        self.assertIn("4 commit(s) behind", detail)

    def test_a_stale_baseline_blocks_before_anything_else(self):
        """Merging a stale main pins the delivery to an older integration point."""
        action, detail = MODULE.refresh_decision(False, (), 4)

        self.assertEqual(action, MODULE.REFRESH_BLOCKED)
        self.assertIn("stale integration point", detail)

    def test_a_stale_baseline_outranks_a_clean_current_branch(self):
        """Reporting 'current' against a stale main would be a false all-clear."""
        action, _ = MODULE.refresh_decision(False, (), 0)

        self.assertEqual(action, MODULE.REFRESH_BLOCKED)

    def test_a_dirty_delivery_worktree_blocks_the_merge(self):
        action, detail = MODULE.refresh_decision(True, (" M one.py",), 3)

        self.assertEqual(action, MODULE.REFRESH_BLOCKED)
        self.assertIn(" M one.py", detail)

    def test_drift_is_reported_on_an_active_delivery(self):
        text = MODULE.render_status(
            (
                MODULE.Reconciled(
                    status=MODULE.REGISTERED_LIVE,
                    branch="feature/PROJ-1-thing",
                    worktree_path="/w/PROJ-1",
                    ownership=ownership(),
                    head_oid="abc",
                    behind_main=3,
                ),
            )
        )

        self.assertIn("3 commit(s) behind main", text)
        self.assertIn("run refresh before integration", text)

    def test_a_current_delivery_reports_no_drift_line(self):
        text = MODULE.render_status(
            MODULE.reconcile((ownership(),), {"/w/PROJ-1": ("feature/PROJ-1-thing", "abc")})
        )

        self.assertNotIn("behind:", text)


class ReleaseIsolationTests(unittest.TestCase):
    """One delivery's cleanup must not disturb another's."""

    def two_deliveries(self):
        return (
            ownership(),
            ownership(
                branch="feature/PROJ-2-other",
                jira_key="PROJ-2",
                worktree_path="/w/PROJ-2",
                base_commit="def5678",
                agent="agent-b",
            ),
        )

    def test_releasing_one_record_leaves_the_other_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / MODULE.OWNERSHIP_FILENAME
            MODULE.save_ownership(path, self.two_deliveries())

            kept = [
                item
                for item in MODULE.load_ownership(path)
                if item.branch != "feature/PROJ-1-thing"
            ]
            MODULE.save_ownership(path, kept)
            remaining = MODULE.load_ownership(path)

            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0].branch, "feature/PROJ-2-other")
            self.assertEqual(remaining[0].agent, "agent-b")
            self.assertEqual(remaining[0].base_commit, "def5678")

    def test_one_delivery_going_missing_does_not_disturb_the_other(self):
        reconciled = MODULE.reconcile(
            self.two_deliveries(), {"/w/PROJ-2": ("feature/PROJ-2-other", "def5678")}
        )

        by_branch = {item.branch: item for item in reconciled}
        self.assertEqual(by_branch["feature/PROJ-1-thing"].status, MODULE.REGISTERED_MISSING)
        self.assertEqual(by_branch["feature/PROJ-2-other"].status, MODULE.REGISTERED_LIVE)

    def test_a_claim_on_one_delivery_never_blocks_an_unrelated_one(self):
        self.assertIsNone(
            MODULE.claim_conflict("feature/PROJ-3-new", "/w/PROJ-3", self.two_deliveries())
        )


class WorktreeTargetTests(unittest.TestCase):
    def test_a_target_inside_the_primary_worktree_is_refused(self):
        root = Path("/projects/aep")
        target = root / "nested" / "PROJ-1"

        with mock.patch.object(MODULE, "primary_worktree_path", return_value=root):
            with self.assertRaises(MODULE.WorktreeError) as raised:
                MODULE.reject_nested_worktree_target(root, target)

        self.assertIn("inside the primary worktree", str(raised.exception))

    def test_a_target_beside_the_primary_worktree_is_allowed(self):
        root = Path("/projects/aep")
        target = Path("/projects/aep.worktrees/PROJ-1")

        with mock.patch.object(MODULE, "primary_worktree_path", return_value=root):
            MODULE.reject_nested_worktree_target(root, target)

    def test_a_path_that_does_not_exist_is_usable(self):
        with tempfile.TemporaryDirectory() as directory:
            MODULE.usable_worktree_target(Path(directory) / "new")

    def test_an_empty_directory_is_usable(self):
        with tempfile.TemporaryDirectory() as directory:
            MODULE.usable_worktree_target(Path(directory))

    def test_a_file_is_a_controlled_error_not_a_traceback(self):
        """iterdir() on a file raises NotADirectoryError, which escapes handling."""
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "a-file"
            target.write_text("")

            with self.assertRaises(MODULE.WorktreeError) as raised:
                MODULE.usable_worktree_target(target)

            self.assertIn("not a directory", str(raised.exception))

    def test_a_non_empty_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "occupied").write_text("")

            with self.assertRaises(MODULE.WorktreeError):
                MODULE.usable_worktree_target(Path(directory))


class ExistingWorktreeClaimTests(unittest.TestCase):
    branch = "feature/PROJ-1-x"
    baseline = "abc1234"

    def test_a_matching_clean_worktree_is_valid(self):
        target = Path("/w/PROJ-1")

        head, base = MODULE.validate_existing_worktree(
            self.branch,
            target,
            {str(target): (self.branch, self.baseline)},
            self.baseline,
            (),
        )

        self.assertEqual(head, self.baseline)
        self.assertEqual(base, self.baseline)

    def test_a_missing_worktree_must_be_created_by_git_or_vscode_first(self):
        with self.assertRaises(MODULE.WorktreeError) as raised:
            MODULE.validate_existing_worktree(
                self.branch, Path("/w/missing"), {}, self.baseline, ()
            )

        self.assertIn("Create it with Git or VS Code", str(raised.exception))

    def test_a_different_checked_out_branch_is_refused(self):
        target = Path("/w/PROJ-1")

        with self.assertRaises(MODULE.WorktreeError) as raised:
            MODULE.validate_existing_worktree(
                self.branch,
                target,
                {str(target): ("feature/PROJ-2-other", self.baseline)},
                self.baseline,
                (),
            )

        self.assertIn("not the requested", str(raised.exception))

    def test_a_detached_worktree_is_refused(self):
        target = Path("/w/PROJ-1")

        with self.assertRaises(MODULE.WorktreeError) as raised:
            MODULE.validate_existing_worktree(
                self.branch,
                target,
                {str(target): (None, self.baseline)},
                self.baseline,
                (),
            )

        self.assertIn("detached", str(raised.exception))

    def test_uncommitted_work_cannot_enter_before_the_claim(self):
        target = Path("/w/PROJ-1")

        with self.assertRaises(MODULE.WorktreeError) as raised:
            MODULE.validate_existing_worktree(
                self.branch,
                target,
                {str(target): (self.branch, self.baseline)},
                self.baseline,
                (" M one.py",),
            )

        self.assertIn("Claim it before work begins", str(raised.exception))

    def test_status_inspection_failure_is_a_controlled_claim_error(self):
        failed = mock.Mock(returncode=128, stdout="", stderr="index unreadable")

        with mock.patch.object(MODULE, "_git", return_value=failed):
            with self.assertRaises(MODULE.WorktreeError) as raised:
                MODULE.dirty_entries(Path("/w/PROJ-1"))

        self.assertIn("index unreadable", str(raised.exception))

    def test_status_process_start_failure_is_a_controlled_claim_error(self):
        with mock.patch.object(MODULE, "_git", side_effect=OSError("git missing")):
            with self.assertRaises(MODULE.WorktreeError) as raised:
                MODULE.dirty_entries(Path("/w/PROJ-1"))

        self.assertIn("git missing", str(raised.exception))

    def test_a_branch_not_at_verified_main_is_refused(self):
        target = Path("/w/PROJ-1")

        with self.assertRaises(MODULE.WorktreeError) as raised:
            MODULE.validate_existing_worktree(
                self.branch,
                target,
                {str(target): (self.branch, "older")},
                self.baseline,
                (),
            )

        self.assertIn("verified current main", str(raised.exception))
        self.assertIn("--adopt", str(raised.exception))

    def test_an_in_flight_worktree_is_adopted_at_the_point_it_left_main(self):
        """Refusing it would leave the only recovery path ungoverned."""
        target = Path("/w/PROJ-1")

        head, base = MODULE.validate_existing_worktree(
            self.branch,
            target,
            {str(target): (self.branch, "inflight")},
            self.baseline,
            (),
            adopt=True,
            merge_base="older",
        )

        self.assertEqual(head, "inflight")
        self.assertEqual(base, "older")

    def test_adoption_still_refuses_a_branch_with_no_shared_history(self):
        target = Path("/w/PROJ-1")

        with self.assertRaises(MODULE.WorktreeError) as raised:
            MODULE.validate_existing_worktree(
                self.branch,
                target,
                {str(target): (self.branch, "inflight")},
                self.baseline,
                (),
                adopt=True,
                merge_base=None,
            )

        self.assertIn("shares no history with main", str(raised.exception))

    def test_adoption_still_refuses_an_uncommitted_change(self):
        """Commits are attributable; uncommitted changes are not."""
        target = Path("/w/PROJ-1")

        with self.assertRaises(MODULE.WorktreeError) as raised:
            MODULE.validate_existing_worktree(
                self.branch,
                target,
                {str(target): (self.branch, "inflight")},
                self.baseline,
                (" M dirty.txt",),
                adopt=True,
                merge_base="older",
            )

        self.assertIn("uncommitted changes", str(raised.exception))

    def test_claim_records_an_unregistered_worktree_without_provisioning(self):
        with tempfile.TemporaryDirectory() as directory:
            target = (Path(directory) / "PROJ-1").resolve()
            record_path = Path(directory) / MODULE.OWNERSHIP_FILENAME
            live = {str(target): (self.branch, self.baseline)}

            with (
                mock.patch.object(MODULE, "live_worktrees", return_value=live),
                mock.patch.object(
                    MODULE, "primary_worktree_path", return_value=Path(directory) / "primary"
                ),
                mock.patch.object(MODULE, "verified_main", return_value=self.baseline),
                mock.patch.object(MODULE, "dirty_entries", return_value=()),
                mock.patch.object(MODULE, "ownership_path", return_value=record_path),
                mock.patch.object(MODULE, "_git") as git,
            ):
                record = MODULE.claim(
                    Path(directory),
                    self.branch,
                    "agent-a",
                    target,
                    now="2026-09-03T00:00:00+00:00",
                )

            git.assert_not_called()
            self.assertEqual(record.base_commit, self.baseline)
            self.assertEqual(MODULE.load_ownership(record_path), (record,))
            self.assertEqual(
                MODULE.reconcile((record,), live)[0].status, MODULE.REGISTERED_LIVE
            )

    def test_claim_keeps_duplicate_ownership_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            target = (Path(directory) / "PROJ-1").resolve()
            record_path = Path(directory) / MODULE.OWNERSHIP_FILENAME
            MODULE.save_ownership(
                record_path,
                (ownership(branch=self.branch, worktree_path="/w/already"),),
            )

            with (
                mock.patch.object(
                    MODULE,
                    "live_worktrees",
                    return_value={str(target): (self.branch, self.baseline)},
                ),
                mock.patch.object(
                    MODULE, "primary_worktree_path", return_value=Path(directory) / "primary"
                ),
                mock.patch.object(MODULE, "verified_main", return_value=self.baseline),
                mock.patch.object(MODULE, "dirty_entries", return_value=()),
                mock.patch.object(MODULE, "ownership_path", return_value=record_path),
            ):
                with self.assertRaises(MODULE.WorktreeError) as raised:
                    MODULE.claim(Path(directory), self.branch, "agent-b", target)

            self.assertIn("already owned", str(raised.exception))

    def test_live_worktrees_keeps_the_current_linked_worktree_visible(self):
        primary = mock.Mock(path=Path("/w/primary"), branch="main", head_oid="base")
        linked = mock.Mock(
            path=Path("/w/PROJ-1"), branch=self.branch, head_oid=self.baseline
        )
        cleanup = mock.Mock()
        cleanup.inspect_worktrees.return_value = (primary, linked)

        with mock.patch.object(MODULE, "_cleanup_module", return_value=cleanup):
            worktrees = MODULE.live_worktrees(linked.path)

        self.assertEqual(
            worktrees,
            {str(linked.path): (self.branch, self.baseline)},
        )


class BaselineIsolationTests(unittest.TestCase):
    """A claim answers to refs, never to another worktree's working tree."""

    def repository(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name) / "primary"
        origin = Path(directory.name) / "origin.git"
        self.git(Path(directory.name), "init", "--bare", "--initial-branch=main", str(origin))
        self.git(Path(directory.name), "clone", str(origin), str(root))
        self.git(root, "config", "user.name", "Worktree Test")
        self.git(root, "config", "user.email", "worktree@example.invalid")
        (root / "tracked.txt").write_text("main\n", encoding="utf-8")
        self.git(root, "add", "tracked.txt")
        self.git(root, "commit", "-m", "Initial")
        self.git(root, "push", "--set-upstream", "origin", "main")
        return root

    @staticmethod
    def git(cwd: Path, *arguments: str):
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_a_loose_file_in_the_primary_does_not_block_the_baseline(self):
        """The primary is expected to carry capture work as its steady state."""
        root = self.repository()
        (root / "future").mkdir()
        (root / "future" / "note.md").write_text("capture\n", encoding="utf-8")

        self.assertEqual(
            MODULE.verified_main(root),
            self.git(root, "rev-parse", "main").stdout.strip(),
        )

    def test_a_modified_file_in_the_primary_does_not_block_the_baseline(self):
        root = self.repository()
        (root / "tracked.txt").write_text("edited\n", encoding="utf-8")

        self.assertEqual(
            MODULE.verified_main(root),
            self.git(root, "rev-parse", "main").stdout.strip(),
        )

    def test_a_main_behind_its_remote_is_refused_rather_than_used(self):
        """A stale baseline would reject the worktree the docs tell you to create."""
        root = self.repository()
        (root / "tracked.txt").write_text("second\n", encoding="utf-8")
        self.git(root, "add", "tracked.txt")
        self.git(root, "commit", "-m", "Second")
        self.git(root, "push", "origin", "main")
        self.git(root, "reset", "--hard", "HEAD~1")

        with self.assertRaises(MODULE.WorktreeError) as raised:
            MODULE.verified_main(root)

        self.assertIn("behind", str(raised.exception))
        self.assertIn("git fetch origin main:main", str(raised.exception))


class ProvisioningBoundaryTests(unittest.TestCase):
    branch = "feature/PROJ-1-x"
    baseline = "abc1234"

    def test_remote_branch_detection_uses_the_supported_heads_filter(self):
        remote = mock.Mock(returncode=2, stderr="")
        preflight = mock.Mock()
        preflight.local_branch_exists.return_value = False

        with (
            mock.patch.object(MODULE, "_sibling", return_value=preflight),
            mock.patch.object(MODULE, "_git", return_value=remote) as git,
        ):
            exists = MODULE.branch_exists(Path("/repo"), self.branch)

        self.assertFalse(exists)
        git.assert_called_once_with(
            Path("/repo"),
            "ls-remote",
            "--exit-code",
            "--heads",
            "origin",
            f"refs/heads/{self.branch}",
            check=False,
        )

    def test_remote_inspection_failure_is_not_treated_as_branch_absence(self):
        remote = mock.Mock(returncode=128, stderr="network failed")
        preflight = mock.Mock()
        preflight.local_branch_exists.return_value = False

        with (
            mock.patch.object(MODULE, "_sibling", return_value=preflight),
            mock.patch.object(MODULE, "_git", return_value=remote),
        ):
            with self.assertRaises(MODULE.WorktreeError) as raised:
                MODULE.branch_exists(Path("/repo"), self.branch)

        self.assertIn("network failed", str(raised.exception))

    def test_remote_process_start_failure_is_a_controlled_error(self):
        preflight = mock.Mock()
        preflight.local_branch_exists.return_value = False

        with (
            mock.patch.object(MODULE, "_sibling", return_value=preflight),
            mock.patch.object(MODULE, "_git", side_effect=OSError("git missing")),
        ):
            with self.assertRaises(MODULE.WorktreeError) as raised:
                MODULE.branch_exists(Path("/repo"), self.branch)

        self.assertIn("git missing", str(raised.exception))

    def test_provision_refuses_to_take_over_an_existing_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with (
                mock.patch.object(MODULE, "primary_worktree_path", return_value=root),
                mock.patch.object(MODULE, "branch_exists", return_value=True),
            ):
                with self.assertRaises(MODULE.WorktreeError) as raised:
                    MODULE.provision(
                        root, self.branch, "agent-a", root.parent / "wt"
                    )

        self.assertIn("then claim it", str(raised.exception))

    def test_optional_provision_uses_the_exact_verified_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root.parent / "wt"
            record_path = root / MODULE.OWNERSHIP_FILENAME
            completed = mock.Mock(returncode=0, stderr="")

            with (
                mock.patch.object(MODULE, "branch_exists", return_value=False),
                mock.patch.object(MODULE, "primary_worktree_path", return_value=root),
                mock.patch.object(MODULE, "verified_main", return_value=self.baseline),
                mock.patch.object(MODULE, "ownership_path", return_value=record_path),
                mock.patch.object(MODULE, "_git", return_value=completed) as git,
            ):
                record = MODULE.provision(
                    root,
                    self.branch,
                    "agent-a",
                    target,
                    now="2026-09-03T00:00:00+00:00",
                )

            git.assert_called_once_with(
                root,
                "worktree",
                "add",
                "-b",
                self.branch,
                str(target.resolve()),
                self.baseline,
                check=False,
            )
            self.assertEqual(record.base_commit, self.baseline)

    def test_provision_refuses_a_target_nested_under_the_primary_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "nested"

            with mock.patch.object(MODULE, "primary_worktree_path", return_value=root):
                with self.assertRaises(MODULE.WorktreeError) as raised:
                    MODULE.provision(root, self.branch, "agent-a", target)

            self.assertIn("inside the primary worktree", str(raised.exception))

    def test_claim_refuses_a_target_nested_under_the_primary_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "nested"

            with mock.patch.object(MODULE, "primary_worktree_path", return_value=root):
                with self.assertRaises(MODULE.WorktreeError) as raised:
                    MODULE.claim(root, self.branch, "agent-a", target)

            self.assertIn("inside the primary worktree", str(raised.exception))


class ConcurrentClaimTests(unittest.TestCase):
    """The tool exists for parallel agents, so the race is the normal path."""

    def claim(self, path, branch, errors):
        try:
            with MODULE.exclusive(path):
                existing = MODULE.load_ownership(path)
                if MODULE.claim_conflict(branch, f"/w/{branch}", existing):
                    return
                MODULE.save_ownership(
                    path,
                    [
                        *existing,
                        ownership(branch=branch, worktree_path=f"/w/{branch}"),
                    ],
                )
        except Exception as error:  # pragma: no cover - surfaced by the assertion
            errors.append(error)

    def test_concurrent_claims_do_not_overwrite_each_other(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / MODULE.OWNERSHIP_FILENAME
            branches = [f"feature/PROJ-{index}-thing" for index in range(1, 25)]
            errors: list[Exception] = []

            threads = [
                threading.Thread(target=self.claim, args=(path, branch, errors))
                for branch in branches
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            recorded = {item.branch for item in MODULE.load_ownership(path)}
            self.assertEqual(recorded, set(branches))

    def test_concurrent_claims_on_one_branch_yield_a_single_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / MODULE.OWNERSHIP_FILENAME
            errors: list[Exception] = []

            threads = [
                threading.Thread(
                    target=self.claim, args=(path, "feature/PROJ-1-thing", errors)
                )
                for _ in range(12)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            self.assertEqual(len(MODULE.load_ownership(path)), 1)


class JsonOutputTests(unittest.TestCase):
    def test_ownership_json_uses_the_shared_key_convention(self):
        payload = MODULE.ownership_json(ownership())

        self.assertEqual(
            set(payload),
            {
                "branch",
                "jiraKey",
                "worktreePath",
                "baseCommit",
                "agent",
                "createdAt",
                "adopted",
            },
        )

    def test_no_snake_case_key_leaks_into_the_output(self):
        """Mixed conventions make the output unusable without knowing its source."""
        self.assertFalse([key for key in MODULE.ownership_json(ownership()) if "_" in key])


class StatusReportingTests(unittest.TestCase):
    def test_an_empty_registry_says_so(self):
        self.assertIn("No delivery worktrees", MODULE.render_status(()))

    def test_an_active_delivery_reports_owner_base_and_path(self):
        text = MODULE.render_status(
            MODULE.reconcile((ownership(),), {"/w/PROJ-1": ("feature/PROJ-1-thing", "abc1234")})
        )

        self.assertIn("[active]", text)
        self.assertIn("PROJ-1", text)
        self.assertIn("/w/PROJ-1", text)
        self.assertIn("agent-a", text)
        self.assertIn("abc1234", text)

    def test_a_missing_worktree_explains_what_it_means(self):
        text = MODULE.render_status(MODULE.reconcile((ownership(),), {}))

        self.assertIn("[missing]", text)
        self.assertIn("abandoned or cleaned up outside this tooling", text)

    def test_an_unregistered_worktree_says_nobody_can_be_held_to_it(self):
        text = MODULE.render_status(
            MODULE.reconcile((), {"/w/stray": ("feature/PROJ-9-x", "def")})
        )

        self.assertIn("[unregistered]", text)
        self.assertIn("no ownership record", text)

    def test_a_jira_keyed_unregistered_worktree_names_both_ways_in(self):
        text = MODULE.render_status(
            MODULE.reconcile((), {"/w/stray": ("feature/PROJ-9-x", "def")})
        )

        self.assertIn("Claim it", text)
        self.assertIn("--adopt", text)

    def test_an_agent_session_worktree_is_told_it_can_never_be_claimed(self):
        """An editor names those after the session, so no claim will ever match."""
        text = MODULE.render_status(
            MODULE.reconcile((), {"/w/agent": ("copilot/swe-agent-1", "def")})
        )

        self.assertIn("no Jira issue key", text)
        self.assertIn("never be claimed", text)
        self.assertIn("agent session", text)

    def test_a_detached_unregistered_worktree_is_told_it_needs_a_branch(self):
        text = MODULE.render_status(MODULE.reconcile((), {"/w/detached": (None, "def")}))

        self.assertIn("detached", text)
        self.assertIn("owned by a branch", text)

    def test_an_adopted_delivery_says_its_base_is_not_its_start(self):
        text = MODULE.render_status(
            MODULE.reconcile(
                (ownership(adopted=True),),
                {"/w/PROJ-1": ("feature/PROJ-1-thing", "abc1234")},
            )
        )

        self.assertIn("adopted:", text)
        self.assertIn("claimed mid-flight", text)


if __name__ == "__main__":
    unittest.main()
