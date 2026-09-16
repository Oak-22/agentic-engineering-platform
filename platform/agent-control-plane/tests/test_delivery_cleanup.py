import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]
    / ".agents"
    / "skills"
    / "manage-git-workflow"
    / "scripts"
    / "delivery_cleanup.py"
)
SPEC = importlib.util.spec_from_file_location("delivery_cleanup", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RepositoryScenario:
    def __init__(self, root: Path, *, squash: bool = False):
        self.root = root
        self.origin = root / "origin.git"
        self.primary = root / "primary"
        self.feature_branch = "chore/PROJ-999-cleanup-test"

        self.git(root, "init", "--bare", "--initial-branch=main", str(self.origin))
        self.git(root, "clone", str(self.origin), str(self.primary))
        self.git(self.primary, "config", "user.name", "Cleanup Test")
        self.git(
            self.primary,
            "config",
            "user.email",
            "cleanup@example.invalid",
        )
        (self.primary / "tracked.txt").write_text("main\n", encoding="utf-8")
        self.git(self.primary, "add", "tracked.txt")
        self.git(self.primary, "commit", "-m", "Initial")
        self.git(self.primary, "push", "--set-upstream", "origin", "main")

        self.git(self.primary, "switch", "-c", self.feature_branch)
        (self.primary / "feature.txt").write_text("feature\n", encoding="utf-8")
        self.git(self.primary, "add", "feature.txt")
        self.git(self.primary, "commit", "-m", "Add feature")
        self.head_oid = self.rev_parse(self.feature_branch)
        self.git(
            self.primary,
            "push",
            "--set-upstream",
            "origin",
            self.feature_branch,
        )

        self.git(self.primary, "switch", "main")
        if squash:
            self.git(self.primary, "merge", "--squash", self.feature_branch)
            self.git(self.primary, "commit", "-m", "Squash feature")
        else:
            self.git(
                self.primary,
                "merge",
                "--no-ff",
                self.feature_branch,
                "-m",
                "Merge feature",
            )
        self.merge_oid = self.rev_parse("main")
        self.git(self.primary, "push", "origin", "main")
        self.pull_request = MODULE.PullRequest(
            number=999,
            state="MERGED",
            merged_at="2026-08-04T00:00:00Z",
            merge_oid=self.merge_oid,
            base_branch="main",
            head_branch=self.feature_branch,
            head_oid=self.head_oid,
            url="https://example.invalid/pull/999",
        )

    def rev_parse(self, revision: str) -> str:
        return self.git(self.primary, "rev-parse", revision).stdout.strip()

    @staticmethod
    def git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )


class LoadPullRequestTests(unittest.TestCase):
    def payload(self, **overrides):
        payload = {
            "number": 999,
            "state": "MERGED",
            "mergedAt": "2026-08-04T00:00:00Z",
            "mergeCommit": {"oid": "1234567890abcdef"},
            "baseRefName": "main",
            "headRefName": "chore/PROJ-999-cleanup-test",
            "headRefOid": "fedcba0987654321",
            "url": "https://example.invalid/pull/999",
        }
        payload.update(overrides)
        return payload

    def completed(self, payload) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["gh", "pr", "view"],
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    def test_load_pull_request_parses_hermetic_gh_response(self):
        with mock.patch.object(
            MODULE,
            "run",
            return_value=self.completed(self.payload()),
        ) as run_mock:
            pull_request = MODULE.load_pull_request(Path("/mock/workspace"), 999)

        self.assertEqual(pull_request.number, 999)
        self.assertEqual(pull_request.merge_oid, "1234567890abcdef")
        self.assertEqual(pull_request.base_branch, "main")
        self.assertIsNone(pull_request.changed_files)
        self.assertIn("files", run_mock.call_args.args[0][-1])
        self.assertEqual(
            run_mock.call_args.kwargs["timeout"],
            MODULE.NETWORK_COMMAND_TIMEOUT_SECONDS,
        )

    def test_load_pull_request_parses_changed_files(self):
        payload = self.payload(files=[{"path": "a.txt"}, {"path": "dir/b.md"}])
        with mock.patch.object(MODULE, "run", return_value=self.completed(payload)):
            pull_request = MODULE.load_pull_request(Path("/mock/workspace"), 999)
        self.assertEqual(pull_request.changed_files, ("a.txt", "dir/b.md"))

    def test_load_pull_request_rejects_malformed_files(self):
        payload = self.payload(files=[{"path": ""}])
        with mock.patch.object(MODULE, "run", return_value=self.completed(payload)):
            with self.assertRaisesRegex(MODULE.CleanupError, "invalid files"):
                MODULE.load_pull_request(Path("/mock/workspace"), 999)

    def test_load_pull_request_rejects_invalid_json(self):
        result = subprocess.CompletedProcess(
            args=["gh", "pr", "view"],
            returncode=0,
            stdout="not-json",
            stderr="",
        )
        with mock.patch.object(MODULE, "run", return_value=result):
            with self.assertRaisesRegex(MODULE.CleanupError, "invalid pull-request"):
                MODULE.load_pull_request(Path("/mock/workspace"), 999)

    def test_load_pull_request_rejects_missing_required_field(self):
        payload = self.payload()
        del payload["headRefOid"]
        with mock.patch.object(
            MODULE,
            "run",
            return_value=self.completed(payload),
        ):
            with self.assertRaisesRegex(MODULE.CleanupError, "headRefOid"):
                MODULE.load_pull_request(Path("/mock/workspace"), 999)

    def test_load_pull_request_rejects_invalid_merge_commit(self):
        with mock.patch.object(
            MODULE,
            "run",
            return_value=self.completed(self.payload(mergeCommit="invalid")),
        ):
            with self.assertRaisesRegex(MODULE.CleanupError, "invalid mergeCommit"):
                MODULE.load_pull_request(Path("/mock/workspace"), 999)

    def test_load_pull_request_rejects_mismatched_number(self):
        with mock.patch.object(
            MODULE,
            "run",
            return_value=self.completed(self.payload(number=1000)),
        ):
            with self.assertRaisesRegex(MODULE.CleanupError, "requested #999"):
                MODULE.load_pull_request(Path("/mock/workspace"), 999)


class SubprocessBoundaryTests(unittest.TestCase):
    @mock.patch.object(MODULE.subprocess, "run")
    def test_run_is_noninteractive_and_bounded(self, subprocess_run):
        subprocess_run.return_value = subprocess.CompletedProcess(
            args=["git", "status"],
            returncode=0,
            stdout="",
            stderr="",
        )

        MODULE.run(["git", "status"], cwd=Path("/mock/workspace"))

        call = subprocess_run.call_args
        self.assertEqual(call.kwargs["timeout"], MODULE.LOCAL_COMMAND_TIMEOUT_SECONDS)
        self.assertEqual(call.kwargs["env"]["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(call.kwargs["env"]["GH_PROMPT_DISABLED"], "1")
        self.assertEqual(call.kwargs["env"]["GCM_INTERACTIVE"], "Never")

    @mock.patch.object(MODULE.subprocess, "run")
    def test_run_translates_timeout(self, subprocess_run):
        subprocess_run.side_effect = subprocess.TimeoutExpired(
            cmd=["git", "fetch"],
            timeout=15,
        )

        with self.assertRaisesRegex(MODULE.CleanupError, "timed out after 15 seconds"):
            MODULE.run(
                ["git", "fetch"],
                cwd=Path("/mock/workspace"),
                timeout=15,
            )

    @mock.patch.object(MODULE.subprocess, "run")
    def test_run_translates_missing_executable(self, subprocess_run):
        subprocess_run.side_effect = FileNotFoundError(
            2,
            "No such file or directory",
            "gh",
        )

        with self.assertRaisesRegex(
            MODULE.CleanupError,
            "required executable is unavailable: gh",
        ):
            MODULE.run(["gh", "pr", "view", "999"], cwd=Path("/mock/workspace"))

    @mock.patch.object(MODULE.subprocess, "run")
    def test_run_translates_failed_command(self, subprocess_run):
        subprocess_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "pr", "view", "999"],
            output="",
            stderr="authentication failed",
        )

        with self.assertRaisesRegex(MODULE.CleanupError, "authentication failed"):
            MODULE.run(["gh", "pr", "view", "999"], cwd=Path("/mock/workspace"))


class CleanupMergedDeliveryTests(unittest.TestCase):
    def scenario(self, *, squash: bool = False):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        return RepositoryScenario(Path(temporary_directory.name), squash=squash)

    def test_merge_cleanup_uses_safe_delete_and_removes_local_branch(self):
        scenario = self.scenario()
        plan = MODULE.build_cleanup_plan(
            scenario.primary, scenario.pull_request
        )

        self.assertTrue(plan.head_contained_in_base)
        MODULE.execute_cleanup(plan)

        self.assertFalse(
            MODULE.branch_exists(scenario.primary, scenario.feature_branch)
        )
        self.assertEqual(MODULE.current_branch(scenario.primary), "main")

    def test_squash_cleanup_uses_verified_force_delete(self):
        scenario = self.scenario(squash=True)
        plan = MODULE.build_cleanup_plan(
            scenario.primary, scenario.pull_request
        )

        self.assertFalse(plan.head_contained_in_base)
        MODULE.execute_cleanup(plan)

        self.assertFalse(
            MODULE.branch_exists(scenario.primary, scenario.feature_branch)
        )

    def test_dirty_secondary_worktree_blocks_cleanup(self):
        scenario = self.scenario()
        secondary = scenario.root / "secondary"
        scenario.git(
            scenario.primary,
            "worktree",
            "add",
            str(secondary),
            scenario.feature_branch,
        )
        (secondary / "untracked.txt").write_text("preserve\n", encoding="utf-8")

        with self.assertRaisesRegex(MODULE.CleanupError, "delivery checkout is dirty"):
            MODULE.build_cleanup_plan(scenario.primary, scenario.pull_request)

        self.assertTrue(secondary.exists())
        self.assertTrue(
            MODULE.branch_exists(scenario.primary, scenario.feature_branch)
        )

    def test_local_branch_tip_mismatch_blocks_cleanup(self):
        scenario = self.scenario()
        scenario.git(
            scenario.primary,
            "branch",
            "--force",
            scenario.feature_branch,
            "main",
        )

        with self.assertRaisesRegex(MODULE.CleanupError, "does not match published head"):
            MODULE.build_cleanup_plan(scenario.primary, scenario.pull_request)

    def test_clean_secondary_worktree_is_removed(self):
        scenario = self.scenario()
        container = scenario.primary.parent / f"{scenario.primary.name}.worktrees"
        container.mkdir()
        secondary = container / "PROJ-999"
        scenario.git(
            scenario.primary,
            "worktree",
            "add",
            str(secondary),
            scenario.feature_branch,
        )
        plan = MODULE.build_cleanup_plan(
            scenario.primary, scenario.pull_request
        )

        self.assertEqual(plan.target_worktree.path, secondary.resolve())
        MODULE.execute_cleanup(plan)

        self.assertFalse(secondary.exists())
        self.assertFalse(container.exists())
        self.assertFalse(
            MODULE.branch_exists(scenario.primary, scenario.feature_branch)
        )

    def test_nonempty_canonical_container_is_preserved(self):
        scenario = self.scenario()
        container = scenario.primary.parent / f"{scenario.primary.name}.worktrees"
        container.mkdir()
        secondary = container / "PROJ-999"
        other = container / "other"
        scenario.git(
            scenario.primary,
            "worktree",
            "add",
            str(secondary),
            scenario.feature_branch,
        )
        scenario.git(scenario.primary, "branch", "other-work", "main")
        scenario.git(
            scenario.primary,
            "worktree",
            "add",
            str(other),
            "other-work",
        )

        plan = MODULE.build_cleanup_plan(scenario.primary, scenario.pull_request)
        MODULE.execute_cleanup(plan)

        self.assertFalse(secondary.exists())
        self.assertTrue(other.exists())
        self.assertTrue(container.exists())

    def test_custom_worktree_parent_is_preserved(self):
        scenario = self.scenario()
        custom_parent = scenario.root / "custom-worktrees"
        custom_parent.mkdir()
        secondary = custom_parent / "delivery"
        scenario.git(
            scenario.primary,
            "worktree",
            "add",
            str(secondary),
            scenario.feature_branch,
        )

        plan = MODULE.build_cleanup_plan(scenario.primary, scenario.pull_request)
        MODULE.execute_cleanup(plan)

        self.assertFalse(secondary.exists())
        self.assertTrue(custom_parent.exists())

    def test_canonical_container_removal_failure_becomes_cleanup_error(self):
        scenario = self.scenario()
        container = scenario.primary.parent / f"{scenario.primary.name}.worktrees"
        container.mkdir()
        target = container / "PROJ-999"
        worktree = MODULE.Worktree(target, scenario.head_oid, scenario.feature_branch)

        with mock.patch.object(Path, "rmdir", side_effect=OSError("permission denied")):
            with self.assertRaisesRegex(
                MODULE.CleanupError, "could not remove empty canonical worktree container"
            ):
                MODULE.remove_empty_canonical_container(scenario.primary, worktree)

    def test_open_pull_request_blocks_cleanup(self):
        scenario = self.scenario()
        pull_request = MODULE.PullRequest(
            number=999,
            state="OPEN",
            merged_at=None,
            merge_oid=None,
            base_branch="main",
            head_branch=scenario.feature_branch,
            head_oid=scenario.head_oid,
            url="https://example.invalid/pull/999",
        )

        with self.assertRaisesRegex(MODULE.CleanupError, "is not merged"):
            MODULE.build_cleanup_plan(scenario.primary, pull_request)

    def test_workbench_return_branch_is_fast_forwarded_after_cleanup(self):
        scenario = self.scenario()
        # workbench/local was captured before the feature merge landed on main.
        scenario.git(scenario.primary, "branch", "workbench/local", "main~1")

        plan = MODULE.build_cleanup_plan(scenario.primary, scenario.pull_request)
        self.assertEqual(plan.return_branch, "workbench/local")
        self.assertTrue(plan.workbench_sync_needed)

        sync = MODULE.execute_cleanup(plan)

        self.assertEqual(sync, "fast-forwarded")
        self.assertEqual(MODULE.current_branch(scenario.primary), "workbench/local")
        self.assertEqual(
            scenario.rev_parse("workbench/local"), scenario.rev_parse("main")
        )

    def test_workbench_return_branch_is_merged_when_it_has_unique_commits(self):
        scenario = self.scenario()
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main~1")
        (scenario.primary / "workbench-only.txt").write_text("wip\n", encoding="utf-8")
        scenario.git(scenario.primary, "add", "workbench-only.txt")
        scenario.git(scenario.primary, "commit", "-m", "Workbench capture")
        scenario.git(scenario.primary, "switch", "main")

        plan = MODULE.build_cleanup_plan(scenario.primary, scenario.pull_request)
        self.assertTrue(plan.workbench_sync_needed)

        sync = MODULE.execute_cleanup(plan)

        self.assertEqual(sync, "merged")
        self.assertEqual(MODULE.current_branch(scenario.primary), "workbench/local")
        self.assertTrue(MODULE.is_ancestor(scenario.primary, "main", "workbench/local"))
        self.assertTrue((scenario.primary / "workbench-only.txt").exists())
        self.assertTrue((scenario.primary / "feature.txt").exists())

    def _workbench_capture(self, scenario, path: str, content: str | None) -> None:
        """Commit one workbench change: a write, or a deletion when content is None."""
        target = scenario.primary / path
        if content is None:
            scenario.git(scenario.primary, "rm", "--quiet", path)
        else:
            target.write_text(content, encoding="utf-8")
            scenario.git(scenario.primary, "add", path)
        scenario.git(scenario.primary, "commit", "-m", f"Workbench capture of {path}")

    def _push_main_change(self, scenario, path: str, content: str | None) -> None:
        """Advance origin/main past the merge with one more change, so an
        undelivered conflict is possible: the pull request never touched path."""
        scenario.git(scenario.primary, "switch", "main")
        target = scenario.primary / path
        if content is None:
            scenario.git(scenario.primary, "rm", "--quiet", path)
        else:
            target.write_text(content, encoding="utf-8")
            scenario.git(scenario.primary, "add", path)
        scenario.git(scenario.primary, "commit", "-m", f"Main change to {path}")
        scenario.git(scenario.primary, "push", "origin", "main")

    def _reviewed_pull_request(self, scenario, number: int, path: str, *,
                               draft: str, reviewed: str | None, base: str = "main"):
        """Deliver `path` through a branch that first carried `draft` (the
        transferred workbench content) and was then changed in review to
        `reviewed` (None deletes it). Returns the merged PullRequest."""
        branch = f"chore/PROJ-{number}-reviewed"
        scenario.git(scenario.primary, "switch", "-c", branch, base)
        (scenario.primary / path).write_text(draft, encoding="utf-8")
        scenario.git(scenario.primary, "add", path)
        scenario.git(scenario.primary, "commit", "-m", f"Transfer {path}")
        if reviewed is None:
            scenario.git(scenario.primary, "rm", "--quiet", path)
        else:
            (scenario.primary / path).write_text(reviewed, encoding="utf-8")
            scenario.git(scenario.primary, "add", path)
        scenario.git(scenario.primary, "commit", "-m", f"Review fix for {path}")
        head = scenario.rev_parse(branch)
        scenario.git(scenario.primary, "push", "--set-upstream", "origin", branch)
        scenario.git(scenario.primary, "switch", base)
        scenario.git(scenario.primary, "merge", "--no-ff", branch, "-m", f"Merge {branch}")
        scenario.git(scenario.primary, "push", "origin", base)
        return MODULE.PullRequest(
            number=number, state="MERGED", merged_at="2026-08-04T00:00:00Z",
            merge_oid=scenario.rev_parse(base), base_branch=base,
            head_branch=branch, head_oid=head,
            url=f"https://example.invalid/pull/{number}",
        )

    def test_workbench_conflict_on_a_delivered_path_is_resolved_from_base(self):
        # The workbench holds the draft that was transferred; review changed
        # it on the branch; main is authoritative for it.
        scenario = self.scenario()
        pr = self._reviewed_pull_request(
            scenario, 1003, "feature.txt", draft="draft\n", reviewed="reviewed\n"
        )
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main~1")
        self._workbench_capture(scenario, "feature.txt", "draft\n")
        scenario.git(scenario.primary, "switch", "main")

        plan = MODULE.build_cleanup_plan(scenario.primary, pr)
        self.assertIn("feature.txt", plan.delivered_paths)
        self.assertEqual(plan.resolvable_conflicts, ("feature.txt",))
        self.assertEqual(plan.blocking_conflicts, ())
        rendered = MODULE.render_plan(plan, executed=False)
        self.assertIn("resolved from main", rendered)
        self.assertIn("feature.txt", rendered)

        sync = MODULE.execute_cleanup(plan)

        self.assertEqual(sync, MODULE.SYNC_MERGED_RESOLVED)
        self.assertEqual(MODULE.current_branch(scenario.primary), "workbench/local")
        self.assertTrue(MODULE.is_ancestor(scenario.primary, "main", "workbench/local"))
        self.assertEqual(
            (scenario.primary / "feature.txt").read_text(encoding="utf-8"), "reviewed\n"
        )
        status = scenario.git(scenario.primary, "status", "--porcelain=v1").stdout
        self.assertEqual(status.strip(), "")

    def test_a_later_workbench_edit_to_a_delivered_path_blocks_the_sync(self):
        # The workbench transferred "draft", then kept working on the same
        # file. That later version was never on the pull request, so taking
        # main's copy would discard it: the sync must block.
        scenario = self.scenario()
        pr = self._reviewed_pull_request(
            scenario, 1004, "feature.txt", draft="draft\n", reviewed="reviewed\n"
        )
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main~1")
        self._workbench_capture(scenario, "feature.txt", "draft\n")
        self._workbench_capture(scenario, "feature.txt", "draft\nplus a later idea\n")
        tip_before = scenario.rev_parse("workbench/local")
        scenario.git(scenario.primary, "switch", "main")

        plan = MODULE.build_cleanup_plan(scenario.primary, pr)
        self.assertIn("feature.txt", plan.delivered_paths)
        self.assertEqual(plan.resolvable_conflicts, ())
        self.assertEqual(plan.blocking_conflicts, ("feature.txt",))

        blocking: list[str] = []
        sync = MODULE.execute_cleanup(plan, blocking_out=blocking)

        self.assertEqual(sync, MODULE.SYNC_CONFLICT)
        self.assertEqual(blocking, ["feature.txt"])
        self.assertEqual(scenario.rev_parse("workbench/local"), tip_before)
        self.assertFalse((scenario.primary / ".git" / "MERGE_HEAD").exists())

    def test_a_mode_change_on_a_delivered_path_blocks_even_with_the_same_content(self):
        # The workbench holds the transferred draft's bytes but made it
        # executable. Same blob, different entry: the PR never carried that
        # mode, so the sync must not discard it.
        scenario = self.scenario()
        pr = self._reviewed_pull_request(
            scenario, 1007, "feature.txt", draft="draft\n", reviewed="reviewed\n"
        )
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main~1")
        draft_file = scenario.primary / "feature.txt"
        draft_file.write_text("draft\n", encoding="utf-8")
        draft_file.chmod(0o755)
        scenario.git(scenario.primary, "add", "feature.txt")
        scenario.git(scenario.primary, "commit", "-m", "Draft, made executable")
        self.assertEqual(
            MODULE.entry_at(scenario.primary, "workbench/local", "feature.txt")[0], "100755"
        )
        tip_before = scenario.rev_parse("workbench/local")
        scenario.git(scenario.primary, "switch", "main")

        plan = MODULE.build_cleanup_plan(scenario.primary, pr)
        self.assertEqual(plan.resolvable_conflicts, ())
        self.assertEqual(plan.blocking_conflicts, ("feature.txt",))

        sync = MODULE.execute_cleanup(plan)

        self.assertEqual(sync, MODULE.SYNC_CONFLICT)
        self.assertEqual(scenario.rev_parse("workbench/local"), tip_before)
        self.assertFalse((scenario.primary / ".git" / "MERGE_HEAD").exists())

    def test_a_directory_on_the_base_where_the_workbench_has_a_file_blocks(self):
        # The PR replaces feature.txt with a directory of the same name. The
        # workbench holds the transferred draft as a file; checking out a
        # directory over an unmerged file entry is not a resolution the
        # cleanup performs.
        scenario = self.scenario()
        branch = "chore/PROJ-1008-dir"
        scenario.git(scenario.primary, "switch", "-c", branch, "main")
        (scenario.primary / "feature.txt").write_text("draft\n", encoding="utf-8")
        scenario.git(scenario.primary, "add", "feature.txt")
        scenario.git(scenario.primary, "commit", "-m", "Transfer draft")
        scenario.git(scenario.primary, "rm", "--quiet", "feature.txt")
        (scenario.primary / "feature.txt").mkdir()
        (scenario.primary / "feature.txt" / "inner.txt").write_text("x\n", encoding="utf-8")
        scenario.git(scenario.primary, "add", "feature.txt")
        scenario.git(scenario.primary, "commit", "-m", "Turn feature into a directory")
        head = scenario.rev_parse(branch)
        scenario.git(scenario.primary, "push", "--set-upstream", "origin", branch)
        scenario.git(scenario.primary, "switch", "main")
        scenario.git(scenario.primary, "merge", "--no-ff", branch, "-m", f"Merge {branch}")
        scenario.git(scenario.primary, "push", "origin", "main")
        pr = MODULE.PullRequest(
            number=1008, state="MERGED", merged_at="2026-08-04T00:00:00Z",
            merge_oid=scenario.rev_parse("main"), base_branch="main",
            head_branch=branch, head_oid=head, url="https://example.invalid/pull/1008",
        )
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main~1")
        self._workbench_capture(scenario, "feature.txt", "draft\n")
        tip_before = scenario.rev_parse("workbench/local")
        scenario.git(scenario.primary, "switch", "main")

        plan = MODULE.build_cleanup_plan(scenario.primary, pr)
        blocking: list[str] = []
        sync = MODULE.execute_cleanup(plan, blocking_out=blocking)

        self.assertEqual(sync, MODULE.SYNC_CONFLICT)
        # Git reports the file side of a directory/file conflict under a
        # "~HEAD" suffix; either spelling must block, and nothing may move.
        self.assertTrue(any(path.startswith("feature.txt") for path in blocking), blocking)
        self.assertEqual(scenario.rev_parse("workbench/local"), tip_before)
        self.assertFalse((scenario.primary / ".git" / "MERGE_HEAD").exists())
        status = scenario.git(scenario.primary, "status", "--porcelain=v1").stdout
        self.assertEqual(status.strip(), "")

    def test_pull_request_commits_include_every_merge_base(self):
        scenario = self.scenario()
        commits = MODULE.pull_request_commits(scenario.primary, scenario.merge_oid)
        fork = scenario.git(
            scenario.primary, "merge-base", f"{scenario.merge_oid}^1", f"{scenario.merge_oid}^2"
        ).stdout.strip()
        self.assertIn(scenario.head_oid, commits)
        self.assertIn(fork, commits)

    def test_a_delivered_path_with_pathspec_magic_resolves_only_itself(self):
        # "no*.txt" would, as a bare pattern, also match "note.txt". The PR
        # delivers only "no*.txt"; the workbench holds its draft and an
        # unrelated, undelivered edit to "note.txt" that must survive.
        scenario = self.scenario()
        (scenario.primary / "note.txt").write_text("original note\n", encoding="utf-8")
        scenario.git(scenario.primary, "add", "note.txt")
        scenario.git(scenario.primary, "commit", "-m", "Add note")
        scenario.git(scenario.primary, "push", "origin", "main")
        pr = self._reviewed_pull_request(
            scenario, 1009, "no*.txt", draft="draft\n", reviewed="reviewed\n"
        )
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main~1")
        self._workbench_capture(scenario, "no*.txt", "draft\n")
        self._workbench_capture(scenario, "note.txt", "workbench note edit\n")
        scenario.git(scenario.primary, "switch", "main")

        plan = MODULE.build_cleanup_plan(scenario.primary, pr)
        self.assertEqual(plan.resolvable_conflicts, ("no*.txt",))
        self.assertEqual(plan.blocking_conflicts, ())

        sync = MODULE.execute_cleanup(plan)

        self.assertEqual(sync, MODULE.SYNC_MERGED_RESOLVED)
        self.assertEqual(
            (scenario.primary / "no*.txt").read_text(encoding="utf-8"), "reviewed\n"
        )
        self.assertEqual(
            (scenario.primary / "note.txt").read_text(encoding="utf-8"),
            "workbench note edit\n",
        )
        status = scenario.git(scenario.primary, "status", "--porcelain=v1").stdout
        self.assertEqual(status.strip(), "")

    def test_staged_changes_on_the_workbench_skip_the_merge_without_committing(self):
        scenario = self.scenario()
        pr = self._reviewed_pull_request(
            scenario, 1010, "feature.txt", draft="draft\n", reviewed="reviewed\n"
        )
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main~1")
        self._workbench_capture(scenario, "feature.txt", "draft\n")
        tip_before = scenario.rev_parse("workbench/local")
        (scenario.primary / "staged-only.txt").write_text("staged\n", encoding="utf-8")
        scenario.git(scenario.primary, "add", "staged-only.txt")

        result = MODULE.sync_workbench_with_base(
            scenario.primary, workbench_branch="workbench/local", base_branch="main",
            delivered=frozenset({"feature.txt"}),
            commits=MODULE.pull_request_commits(scenario.primary, pr.merge_oid),
        )

        self.assertEqual(result, MODULE.SYNC_INDEX_DIRTY)
        self.assertEqual(scenario.rev_parse("workbench/local"), tip_before)
        self.assertFalse((scenario.primary / ".git" / "MERGE_HEAD").exists())
        status = scenario.git(scenario.primary, "status", "--porcelain=v1").stdout
        self.assertEqual(status.strip(), "A  staged-only.txt")

    def test_predict_sync_conflicts_raises_when_no_prediction_was_made(self):
        scenario = self.scenario()
        with self.assertRaisesRegex(MODULE.CleanupError, "cannot predict"):
            MODULE.predict_sync_conflicts(
                scenario.primary, workbench_branch="no-such-branch", base_branch="main"
            )

    def test_entry_at_distinguishes_absence_from_lookup_failure(self):
        scenario = self.scenario()
        self.assertIsNone(MODULE.entry_at(scenario.primary, "main", "no-such-file.txt"))
        entry = MODULE.entry_at(scenario.primary, "main", "feature.txt")
        self.assertIsNotNone(entry)
        self.assertEqual(entry[0], "100644")
        with self.assertRaisesRegex(MODULE.CleanupError, "cannot read feature.txt"):
            MODULE.entry_at(scenario.primary, "no-such-revision", "feature.txt")

    def test_workbench_conflict_on_an_undelivered_path_still_aborts_and_names_it(self):
        # feature.txt is delivered and would resolve; tracked.txt was never in
        # the pull request, so its conflict is undelivered workbench work.
        scenario = self.scenario()
        pr = self._reviewed_pull_request(
            scenario, 1005, "feature.txt", draft="draft\n", reviewed="reviewed\n"
        )
        self._push_main_change(scenario, "tracked.txt", "main moved on\n")
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main~2")
        self._workbench_capture(scenario, "feature.txt", "draft\n")
        self._workbench_capture(scenario, "tracked.txt", "undelivered capture\n")
        workbench_tip_before = scenario.rev_parse("workbench/local")
        scenario.git(scenario.primary, "switch", "main")

        plan = MODULE.build_cleanup_plan(scenario.primary, pr)
        self.assertEqual(plan.resolvable_conflicts, ("feature.txt",))
        self.assertEqual(plan.blocking_conflicts, ("tracked.txt",))
        rendered = MODULE.render_plan(plan, executed=False)
        self.assertIn("BLOCKING", rendered)
        self.assertIn("tracked.txt", rendered)

        blocking: list[str] = []
        sync = MODULE.execute_cleanup(plan, blocking_out=blocking)

        self.assertEqual(sync, MODULE.SYNC_CONFLICT)
        self.assertEqual(blocking, ["tracked.txt"])
        self.assertEqual(MODULE.current_branch(scenario.primary), "workbench/local")
        self.assertEqual(scenario.rev_parse("workbench/local"), workbench_tip_before)
        status = scenario.git(scenario.primary, "status", "--porcelain=v1").stdout
        self.assertEqual(status.strip(), "")
        self.assertFalse((scenario.primary / ".git" / "MERGE_HEAD").exists())

    def test_delivered_paths_union_github_file_list_with_merge_diff(self):
        scenario = self.scenario()
        from_github = MODULE.PullRequest(
            **{**scenario.pull_request.__dict__, "changed_files": ("from-github.txt",)}
        )
        self.assertEqual(
            MODULE.delivered_paths(scenario.primary, from_github),
            frozenset({"from-github.txt", "feature.txt"}),
        )
        self.assertEqual(
            MODULE.delivered_paths(scenario.primary, scenario.pull_request),
            frozenset({"feature.txt"}),
        )

    def test_a_merge_that_fails_without_conflicts_is_aborted_not_committed(self):
        scenario = self.scenario()
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main~1")
        self._workbench_capture(scenario, "unrelated.txt", "capture\n")
        tip_before = scenario.rev_parse("workbench/local")
        hooks = scenario.primary / ".git" / "hooks"
        hooks.mkdir(exist_ok=True)
        hook = hooks / "pre-merge-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)

        result = MODULE.sync_workbench_with_base(
            scenario.primary, workbench_branch="workbench/local", base_branch="main",
            delivered=frozenset({"feature.txt"}),
        )

        self.assertEqual(result, MODULE.SYNC_MERGE_FAILED)
        self.assertEqual(scenario.rev_parse("workbench/local"), tip_before)
        self.assertFalse((scenario.primary / ".git" / "MERGE_HEAD").exists())
        status = scenario.git(scenario.primary, "status", "--porcelain=v1").stdout
        self.assertEqual(status.strip(), "")

    def test_a_commit_failure_after_resolution_aborts_the_merge_and_reraises(self):
        scenario = self.scenario()
        pr = self._reviewed_pull_request(
            scenario, 1006, "feature.txt", draft="draft\n", reviewed="reviewed\n"
        )
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main~1")
        self._workbench_capture(scenario, "feature.txt", "draft\n")
        tip_before = scenario.rev_parse("workbench/local")
        hooks = scenario.primary / ".git" / "hooks"
        hooks.mkdir(exist_ok=True)
        hook = hooks / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)

        with self.assertRaises(MODULE.CleanupError):
            MODULE.sync_workbench_with_base(
                scenario.primary, workbench_branch="workbench/local", base_branch="main",
                delivered=frozenset({"feature.txt"}),
                commits=MODULE.pull_request_commits(scenario.primary, pr.merge_oid),
            )

        self.assertEqual(scenario.rev_parse("workbench/local"), tip_before)
        self.assertFalse((scenario.primary / ".git" / "MERGE_HEAD").exists())
        status = scenario.git(scenario.primary, "status", "--porcelain=v1").stdout
        self.assertEqual(status.strip(), "")

    def test_workbench_conflict_on_the_source_side_of_a_delivered_rename_is_resolved(self):
        # The PR renames feature.txt -> renamed.txt and rewrites its content,
        # so Git's rename detection does not pair them and the workbench's
        # edit to feature.txt surfaces as a modify/delete conflict on the
        # source path. GitHub's file list names only the destination.
        scenario = self.scenario()
        scenario.git(scenario.primary, "switch", "-c", "chore/PROJ-1002-rename", "main")
        (scenario.primary / "feature.txt").write_text("draft\n", encoding="utf-8")
        scenario.git(scenario.primary, "add", "feature.txt")
        scenario.git(scenario.primary, "commit", "-m", "Transfer feature draft")
        scenario.git(scenario.primary, "mv", "feature.txt", "renamed.txt")
        (scenario.primary / "renamed.txt").write_text(
            "entirely rewritten on the delivery branch\n" * 4, encoding="utf-8"
        )
        scenario.git(scenario.primary, "add", "renamed.txt")
        scenario.git(scenario.primary, "commit", "-m", "Rename and rewrite feature")
        rename_head = scenario.rev_parse("chore/PROJ-1002-rename")
        scenario.git(scenario.primary, "push", "--set-upstream", "origin", "chore/PROJ-1002-rename")
        scenario.git(scenario.primary, "switch", "main")
        scenario.git(scenario.primary, "merge", "--no-ff", "chore/PROJ-1002-rename", "-m", "Merge rename")
        scenario.git(scenario.primary, "push", "origin", "main")
        rename_pr = MODULE.PullRequest(
            number=1002, state="MERGED", merged_at="2026-08-04T00:00:00Z",
            merge_oid=scenario.rev_parse("main"), base_branch="main",
            head_branch="chore/PROJ-1002-rename", head_oid=rename_head,
            url="https://example.invalid/pull/1002",
            changed_files=("renamed.txt",),
        )
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main~1")
        self._workbench_capture(scenario, "feature.txt", "draft\n")
        scenario.git(scenario.primary, "switch", "main")

        plan = MODULE.build_cleanup_plan(scenario.primary, rename_pr)
        self.assertIn("feature.txt", plan.delivered_paths)
        self.assertEqual(plan.blocking_conflicts, ())

        sync = MODULE.execute_cleanup(plan)

        self.assertEqual(sync, MODULE.SYNC_MERGED_RESOLVED)
        self.assertFalse((scenario.primary / "feature.txt").exists())
        self.assertTrue((scenario.primary / "renamed.txt").exists())
        self.assertTrue(MODULE.is_ancestor(scenario.primary, "main", "workbench/local"))

    def test_delivered_paths_fail_closed_for_a_rebase_merge_without_a_file_list(self):
        # Two PR commits replayed onto main: the tip's parent is the first
        # replayed commit, so a parent diff would miss first.txt. Without
        # GitHub's file list nothing is treated as delivered.
        scenario = self.scenario()
        scenario.git(scenario.primary, "switch", "-c", "fix/PROJ-1001-rebase", "main")
        for name in ("first.txt", "second.txt"):
            (scenario.primary / name).write_text(f"{name}\n", encoding="utf-8")
            scenario.git(scenario.primary, "add", name)
            scenario.git(scenario.primary, "commit", "-m", f"Add {name}")
        scenario.git(scenario.primary, "switch", "main")
        scenario.git(scenario.primary, "merge", "--ff-only", "fix/PROJ-1001-rebase")
        rebase_pr = MODULE.PullRequest(
            number=1001, state="MERGED", merged_at="2026-08-04T00:00:00Z",
            merge_oid=scenario.rev_parse("main"), base_branch="main",
            head_branch="fix/PROJ-1001-rebase", head_oid=scenario.rev_parse("main"),
            url="https://example.invalid/pull/1001",
        )
        self.assertEqual(MODULE.delivered_paths(scenario.primary, rebase_pr), frozenset())

    def test_workbench_conflict_where_base_deleted_a_delivered_path_is_resolved_by_removal(self):
        # A second pull request deletes feature.txt on main; the workbench still
        # edits it. Cleanup of that PR removes the file rather than keeping the
        # workbench's draft.
        scenario = self.scenario()
        removal_pr = self._reviewed_pull_request(
            scenario, 1000, "feature.txt", draft="draft\n", reviewed=None
        )
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main~1")
        self._workbench_capture(scenario, "feature.txt", "draft\n")
        scenario.git(scenario.primary, "switch", "main")

        plan = MODULE.build_cleanup_plan(scenario.primary, removal_pr)
        self.assertEqual(plan.resolvable_conflicts, ("feature.txt",))

        sync = MODULE.execute_cleanup(plan)

        self.assertEqual(sync, MODULE.SYNC_MERGED_RESOLVED)
        self.assertFalse((scenario.primary / "feature.txt").exists())
        self.assertTrue(MODULE.is_ancestor(scenario.primary, "main", "workbench/local"))
        status = scenario.git(scenario.primary, "status", "--porcelain=v1").stdout
        self.assertEqual(status.strip(), "")

    def test_sync_workbench_with_base_reports_already_up_to_date(self):
        scenario = self.scenario()
        scenario.git(scenario.primary, "branch", "workbench/local", "main")

        result = MODULE.sync_workbench_with_base(
            scenario.primary, workbench_branch="workbench/local", base_branch="main"
        )

        self.assertEqual(result, "already-up-to-date")


class PrimaryWorkspaceIsolationTests(unittest.TestCase):
    """Cleaning a delivery beside the repository is not the primary's business."""

    def scenario(self, *, squash: bool = False):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        return RepositoryScenario(Path(temporary_directory.name), squash=squash)

    def workbench_scenario(self):
        """A delivery in a secondary worktree, primary parked on the workbench."""
        scenario = self.scenario()
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main~1")
        secondary = scenario.root / "secondary"
        scenario.git(
            scenario.primary,
            "worktree",
            "add",
            str(secondary),
            scenario.feature_branch,
        )
        return scenario, secondary

    def test_a_loose_file_in_the_primary_does_not_block_cleanup(self):
        scenario, _ = self.workbench_scenario()
        loose = scenario.primary / "capture-note.md"
        loose.write_text("workbench capture\n", encoding="utf-8")

        plan = MODULE.build_cleanup_plan(scenario.primary, scenario.pull_request)

        self.assertEqual(plan.primary_conflicts, ())

        MODULE.execute_cleanup(plan)

        self.assertFalse(
            MODULE.branch_exists(scenario.primary, scenario.feature_branch)
        )
        self.assertEqual(loose.read_text(encoding="utf-8"), "workbench capture\n")

    def test_an_untracked_file_the_cleanup_would_overwrite_blocks_and_is_named(self):
        scenario, _ = self.workbench_scenario()
        # feature.txt arrives with the workbench sync, onto an untracked copy.
        (scenario.primary / "feature.txt").write_text("mine\n", encoding="utf-8")

        plan = MODULE.build_cleanup_plan(scenario.primary, scenario.pull_request)

        self.assertIn("?? feature.txt", plan.primary_conflicts)
        with self.assertRaisesRegex(MODULE.CleanupError, "paths this cleanup would"):
            MODULE.execute_cleanup(plan)
        self.assertTrue(
            MODULE.branch_exists(scenario.primary, scenario.feature_branch)
        )

    def test_the_base_advances_by_ref_update_without_a_checkout(self):
        """Advancing a branch nobody has checked out needs no working tree."""
        scenario = self.scenario()
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main")
        scenario.git(scenario.primary, "reset", "--hard", "main~1")
        scenario.git(scenario.primary, "update-ref", "refs/heads/main", "HEAD")
        before = scenario.git(
            scenario.primary, "rev-parse", "HEAD"
        ).stdout.strip()

        plan = MODULE.build_cleanup_plan(scenario.primary, scenario.pull_request)
        self.assertEqual(plan.base_advance, MODULE.BASE_REF_UPDATE)
        MODULE.advance_base(plan)

        self.assertEqual(
            scenario.rev_parse("main"), scenario.rev_parse("origin/main")
        )
        self.assertEqual(
            scenario.git(scenario.primary, "rev-parse", "HEAD").stdout.strip(), before
        )
        self.assertEqual(MODULE.current_branch(scenario.primary), "workbench/local")

    def test_cleanup_leaves_the_primary_on_the_branch_it_started_on(self):
        scenario, _ = self.workbench_scenario()
        scenario.git(scenario.primary, "merge", "--ff-only", "main")

        plan = MODULE.build_cleanup_plan(scenario.primary, scenario.pull_request)

        self.assertFalse(plan.switch_required)
        MODULE.execute_cleanup(plan)

        self.assertEqual(MODULE.current_branch(scenario.primary), "workbench/local")

    def test_deletion_is_verified_against_the_base_not_the_checked_out_branch(self):
        """From the workbench, `git branch -d` calls a merged delivery unmerged."""
        scenario, _ = self.workbench_scenario()

        plan = MODULE.build_cleanup_plan(scenario.primary, scenario.pull_request)
        self.assertTrue(plan.head_contained_in_base)
        MODULE.execute_cleanup(plan)

        self.assertFalse(
            MODULE.branch_exists(scenario.primary, scenario.feature_branch)
        )

    def test_a_delivery_tip_that_moved_since_planning_is_not_force_deleted(self):
        scenario, secondary = self.workbench_scenario()
        plan = MODULE.build_cleanup_plan(scenario.primary, scenario.pull_request)
        # The branch is checked out in the worktree, so it moves from there.
        (secondary / "late.txt").write_text("unreviewed\n", encoding="utf-8")
        scenario.git(secondary, "add", "late.txt")
        scenario.git(secondary, "commit", "-m", "Late work")

        with self.assertRaisesRegex(MODULE.CleanupError, "moved since this cleanup"):
            MODULE.delete_delivery_branch(plan)

        self.assertTrue(
            MODULE.branch_exists(scenario.primary, scenario.feature_branch)
        )

    def test_a_rename_is_recorded_at_the_path_that_would_be_written(self):
        """`-z` reverses the rename field order, so the first path is the new one."""
        scenario = self.scenario()
        scenario.git(scenario.primary, "mv", "tracked.txt", "renamed.txt")

        paths = {
            MODULE.entry_path(entry)
            for entry in MODULE.status_entries(scenario.primary)
        }

        self.assertIn("renamed.txt", paths)
        self.assertNotIn("tracked.txt", paths)

    def test_a_base_that_moved_since_planning_fails_the_ref_update(self):
        """The compare-and-swap is what makes a checkout-free advance safe."""
        scenario = self.scenario()
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main")
        current = scenario.rev_parse("main")
        stale = scenario.rev_parse("main~1")
        scenario.git(scenario.primary, "update-ref", "refs/heads/main", stale)

        plan = MODULE.build_cleanup_plan(scenario.primary, scenario.pull_request)
        self.assertEqual(plan.base_oid_at_plan, stale)
        scenario.git(scenario.primary, "update-ref", "refs/heads/main", current)

        with self.assertRaisesRegex(MODULE.CleanupError, "moved since"):
            MODULE.advance_base(plan)


class StaleRepositoryScenario:
    def __init__(self, root: Path):
        self.root = root
        self.origin = root / "origin.git"
        self.primary = root / "primary"
        self.git(root, "init", "--bare", "--initial-branch=main", str(self.origin))
        self.git(root, "clone", str(self.origin), str(self.primary))
        self.git(self.primary, "config", "user.name", "Reconciliation Test")
        self.git(
            self.primary,
            "config",
            "user.email",
            "reconciliation@example.invalid",
        )
        (self.primary / "tracked.txt").write_text("main\n", encoding="utf-8")
        self.git(self.primary, "add", "tracked.txt")
        self.git(self.primary, "commit", "-m", "Initial")
        self.git(self.primary, "push", "--set-upstream", "origin", "main")

    def create_branch(self, branch: str, *, unique_commit: bool = False) -> str:
        self.git(self.primary, "branch", branch, "main")
        if unique_commit:
            self.git(self.primary, "switch", branch)
            path = self.primary / f"{branch.rsplit('/', 1)[-1]}.txt"
            path.write_text("unique\n", encoding="utf-8")
            self.git(self.primary, "add", path.name)
            self.git(self.primary, "commit", "-m", f"Commit {branch}")
            self.git(self.primary, "switch", "main")
        return self.rev_parse(branch)

    def rev_parse(self, revision: str) -> str:
        return self.git(self.primary, "rev-parse", revision).stdout.strip()

    @staticmethod
    def git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )


class ReconcileLocalDeliveriesTests(unittest.TestCase):
    def scenario(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        return StaleRepositoryScenario(Path(temporary_directory.name))

    @staticmethod
    def merged_pr(number: int, branch: str, head_oid: str):
        return MODULE.PullRequest(
            number=number,
            state="MERGED",
            merged_at="2026-08-05T00:00:00Z",
            merge_oid=head_oid,
            base_branch="main",
            head_branch=branch,
            head_oid=head_oid,
            url=f"https://example.invalid/pull/{number}",
        )

    def report(self, scenario, *, remote_branches=None, pull_requests=()):
        return MODULE.build_reconciliation_report(
            scenario.primary,
            remote_branches=set() if remote_branches is None else remote_branches,
            pull_requests=pull_requests,
        )

    def test_branch_pattern_accepts_project_scoped_intent_names(self):
        self.assertIsNotNone(
            MODULE.BRANCH_PATTERN.match("chore/TEAM-42-update-dependencies")
        )
        self.assertIsNotNone(
            MODULE.BRANCH_PATTERN.match("refactor/PROJ-43-telemetry-layout")
        )
        self.assertIsNone(MODULE.BRANCH_PATTERN.match("fix/PROJ-login-timeout"))
        self.assertIsNone(MODULE.BRANCH_PATTERN.match("feature/user-authentication"))

    def test_branch_pattern_retains_legacy_cleanup_compatibility(self):
        self.assertIsNotNone(
            MODULE.BRANCH_PATTERN.match("agent/PROJ-38-agent-control-plane")
        )
        self.assertIsNotNone(MODULE.BRANCH_PATTERN.match("PROJ-37-older-delivery"))

    def test_merged_remote_absent_branch_is_safe(self):
        scenario = self.scenario()
        branch = "feature/PROJ-100-merged"
        head_oid = scenario.create_branch(branch)

        report = self.report(
            scenario,
            pull_requests=(self.merged_pr(100, branch, head_oid),),
        )

        candidate = report.candidates[0]
        self.assertEqual(candidate.classification, "safe-to-delete")
        self.assertEqual(candidate.pull_request, 100)

    def test_no_pr_branch_requires_manual_review(self):
        scenario = self.scenario()
        scenario.create_branch("PROJ-101-no-pr")

        report = self.report(scenario)

        self.assertEqual(report.candidates[0].classification, "manual-review")
        self.assertIn("no associated pull request", report.candidates[0].reason)

    def test_unique_commit_is_preserved(self):
        scenario = self.scenario()
        branch = "fix/PROJ-102-unique"
        head_oid = scenario.create_branch(branch, unique_commit=True)

        report = self.report(
            scenario,
            pull_requests=(self.merged_pr(102, branch, head_oid),),
        )

        self.assertEqual(report.candidates[0].classification, "preserve")
        self.assertIn("not reachable", report.candidates[0].reason)

    def test_checked_out_branch_is_preserved(self):
        scenario = self.scenario()
        branch = "bugfix/PROJ-103-checked-out"
        head_oid = scenario.create_branch(branch)
        scenario.git(scenario.primary, "switch", branch)

        report = self.report(
            scenario,
            pull_requests=(self.merged_pr(103, branch, head_oid),),
        )

        self.assertEqual(report.candidates[0].classification, "preserve")
        self.assertEqual(report.candidates[0].reason, "branch is checked out")

    def test_live_remote_branch_is_preserved(self):
        scenario = self.scenario()
        branch = "hotfix/PROJ-104-remote"
        head_oid = scenario.create_branch(branch)

        report = self.report(
            scenario,
            remote_branches={branch},
            pull_requests=(self.merged_pr(104, branch, head_oid),),
        )

        self.assertEqual(report.candidates[0].classification, "preserve")
        self.assertEqual(report.candidates[0].reason, "remote branch still exists")

    def test_open_pull_request_is_preserved(self):
        scenario = self.scenario()
        branch = "refactor/PROJ-105-open"
        head_oid = scenario.create_branch(branch)
        pull_request = MODULE.PullRequest(
            number=105,
            state="OPEN",
            merged_at=None,
            merge_oid=None,
            base_branch="main",
            head_branch=branch,
            head_oid=head_oid,
            url="https://example.invalid/pull/105",
        )

        report = self.report(scenario, pull_requests=(pull_request,))

        self.assertEqual(report.candidates[0].classification, "preserve")
        self.assertIn("not merged", report.candidates[0].reason)

    def test_execution_deletes_only_safe_candidates(self):
        scenario = self.scenario()
        safe_branch = "docs/PROJ-106-safe"
        manual_branch = "PROJ-107-manual"
        safe_oid = scenario.create_branch(safe_branch)
        scenario.create_branch(manual_branch)
        report = self.report(
            scenario,
            pull_requests=(self.merged_pr(106, safe_branch, safe_oid),),
        )

        MODULE.execute_reconciliation(scenario.primary, report)

        branches = MODULE.local_delivery_branches(scenario.primary)
        self.assertNotIn(safe_branch, branches)
        self.assertIn(manual_branch, branches)

    def test_a_loose_file_does_not_block_reconciliation_and_survives_it(self):
        """Deleting a ref and pruning metadata write nothing into the checkout."""
        scenario = self.scenario()
        branch = "chore/PROJ-108-safe"
        head_oid = scenario.create_branch(branch)
        report = self.report(
            scenario,
            pull_requests=(self.merged_pr(108, branch, head_oid),),
        )
        loose = scenario.primary / "untracked.txt"
        loose.write_text("preserve\n", encoding="utf-8")

        MODULE.execute_reconciliation(scenario.primary, report)

        self.assertNotIn(branch, MODULE.local_delivery_branches(scenario.primary))
        self.assertEqual(loose.read_text(encoding="utf-8"), "preserve\n")

    def test_a_candidate_that_moved_since_classification_is_not_deleted(self):
        """Forcing the delete gives up Git's safety net, so the ref is re-read."""
        scenario = self.scenario()
        branch = "chore/PROJ-110-safe"
        head_oid = scenario.create_branch(branch)
        report = self.report(
            scenario,
            pull_requests=(self.merged_pr(110, branch, head_oid),),
        )
        scenario.git(scenario.primary, "switch", branch)
        (scenario.primary / "late.txt").write_text("unreviewed\n", encoding="utf-8")
        scenario.git(scenario.primary, "add", "late.txt")
        scenario.git(scenario.primary, "commit", "-m", "Late work")
        scenario.git(scenario.primary, "switch", "main")

        with self.assertRaisesRegex(MODULE.CleanupError, "moved since it was classified"):
            MODULE.execute_reconciliation(scenario.primary, report)

        self.assertIn(branch, MODULE.local_delivery_branches(scenario.primary))

    def test_no_branch_is_deleted_when_any_candidate_fails_reverification(self):
        """A moved ref must not leave a half-finished reconciliation behind."""
        scenario = self.scenario()
        stable = "chore/PROJ-111-stable"
        moved = "chore/PROJ-112-moved"
        stable_oid = scenario.create_branch(stable)
        moved_oid = scenario.create_branch(moved)
        report = self.report(
            scenario,
            pull_requests=(
                self.merged_pr(111, stable, stable_oid),
                self.merged_pr(112, moved, moved_oid),
            ),
        )
        scenario.git(scenario.primary, "switch", moved)
        (scenario.primary / "late.txt").write_text("unreviewed\n", encoding="utf-8")
        scenario.git(scenario.primary, "add", "late.txt")
        scenario.git(scenario.primary, "commit", "-m", "Late work")
        scenario.git(scenario.primary, "switch", "main")

        with self.assertRaises(MODULE.CleanupError):
            MODULE.execute_reconciliation(scenario.primary, report)

        branches = MODULE.local_delivery_branches(scenario.primary)
        self.assertIn(stable, branches)
        self.assertIn(moved, branches)

    def test_a_branch_merged_into_main_is_deleted_from_the_workbench(self):
        """`git branch -d` would judge it against HEAD and refuse."""
        scenario = self.scenario()
        branch = "chore/PROJ-109-safe"
        head_oid = scenario.create_branch(branch)
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main")
        report = self.report(
            scenario,
            pull_requests=(self.merged_pr(109, branch, head_oid),),
        )

        MODULE.execute_reconciliation(scenario.primary, report)

        self.assertNotIn(branch, MODULE.local_delivery_branches(scenario.primary))
        self.assertEqual(MODULE.current_branch(scenario.primary), "workbench/local")


class CliModeTests(unittest.TestCase):
    def test_mode_is_required(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                MODULE.parse_args([])

    def test_pr_dry_run_refreshes_remote_before_planning(self):
        workspace = Path("/mock/workspace")
        pull_request = mock.sentinel.pull_request
        plan = mock.sentinel.plan
        events = []

        with (
            mock.patch.object(
                MODULE,
                "resolve_primary_workspace",
                return_value=workspace,
            ),
            mock.patch.object(
                MODULE,
                "refresh_remote",
                side_effect=lambda _: events.append("refresh"),
            ),
            mock.patch.object(
                MODULE,
                "live_remote_branches",
                side_effect=lambda _: events.append("remotes") or set(),
            ),
            mock.patch.object(
                MODULE,
                "load_pull_request",
                side_effect=lambda *_: events.append("pull-request")
                or pull_request,
            ),
            mock.patch.object(
                MODULE,
                "build_cleanup_plan",
                side_effect=lambda *_args, **_kwargs: events.append("plan") or plan,
            ),
            mock.patch.object(MODULE, "render_plan", return_value="plan"),
            mock.patch.object(MODULE, "execute_cleanup") as execute_cleanup,
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                result = MODULE.main(
                    [
                        "pr",
                        "--pr",
                        "19",
                        "--primary-workspace",
                        str(workspace),
                    ]
                )

        self.assertEqual(result, 0)
        self.assertEqual(events, ["refresh", "remotes", "pull-request", "plan"])
        execute_cleanup.assert_not_called()

    def test_pr_json_records_verified_cleanup_without_remote_deletion(self):
        pull_request = MODULE.PullRequest(
            number=19,
            state="MERGED",
            merged_at="2026-09-03T00:00:00Z",
            merge_oid="abc1234",
            base_branch="main",
            head_branch="feature/PROJ-19-x",
            head_oid="def5678",
            url="https://github.com/Oak-22/repo/pull/19",
        )
        plan = MODULE.CleanupPlan(
            primary_workspace=Path("/mock/workspace"),
            pull_request=pull_request,
            target_worktree=None,
            initial_primary_branch="workbench/local",
            return_branch="workbench/local",
            head_contained_in_base=False,
            remote_branch_exists=True,
            workbench_sync_needed=False,
            base_advance=MODULE.BASE_REF_UPDATE,
            base_oid_at_plan="0123456",
            switch_required=False,
            primary_conflicts=(),
        )
        payload = json.loads(MODULE.cleanup_plan_as_json(plan, executed=True))
        self.assertEqual(payload["baseAdvance"], MODULE.BASE_REF_UPDATE)
        self.assertFalse(payload["primarySwitched"])
        self.assertEqual(payload["outcome"], "cleaned")
        self.assertEqual(payload["localCleanup"], "completed")
        self.assertFalse(payload["remoteDeletionAttempted"])
        self.assertIsNone(payload["cleanupDebt"])

    def test_pr_json_records_cleanup_debt(self):
        payload = json.loads(
            MODULE.cleanup_debt_as_json(MODULE.CleanupError("dirty checkout"), executed=True)
        )
        self.assertEqual(payload["outcome"], "cleanup-debt")
        self.assertEqual(payload["cleanupDebt"], "dirty checkout")
        self.assertFalse(payload["remoteDeletionAttempted"])

    def test_stale_no_fetch_is_read_only_by_default(self):
        workspace = Path("/mock/workspace")
        report = MODULE.ReconciliationReport(base_ref="origin/main", candidates=())

        with (
            mock.patch.object(
                MODULE,
                "resolve_primary_workspace",
                return_value=workspace,
            ),
            mock.patch.object(MODULE, "refresh_remote") as refresh_remote,
            mock.patch.object(MODULE, "live_remote_branches", return_value=set()),
            mock.patch.object(
                MODULE,
                "build_reconciliation_report",
                return_value=report,
            ),
            mock.patch.object(MODULE, "execute_reconciliation") as execute,
            mock.patch.object(
                MODULE,
                "reconciliation_as_json",
                return_value="{}",
            ),
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                result = MODULE.main(
                    [
                        "stale",
                        "--primary-workspace",
                        str(workspace),
                        "--no-fetch",
                        "--format",
                        "json",
                    ]
                )

        self.assertEqual(result, 0)
        refresh_remote.assert_not_called()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
