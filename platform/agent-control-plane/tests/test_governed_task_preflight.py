import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "governed_task_preflight.py"
)
SPEC = importlib.util.spec_from_file_location("governed_task_preflight", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GovernedTaskPreflightTests(unittest.TestCase):
    def state(self, **overrides):
        values = {
            "dirty_entries": (),
            "open_governed_pull_requests": (),
            "current_branch": "main",
            "current_pull_request_state": None,
            "current_remote_branch_exists": False,
            "stale_local_delivery_branches": (),
            "workbench_exists": False,
            "workbench_commits_behind_main": 0,
            "remote_main_tracked": True,
            "main_ahead_of_remote": 0,
            "main_behind_remote": 0,
        }
        values.update(overrides)
        return MODULE.RepositoryState(**values)

    def test_clean_default_branch_passes(self):
        self.assertEqual(MODULE.blockers_for(self.state()), [])

    def test_dirty_worktree_blocks_and_lists_changes(self):
        blockers = MODULE.blockers_for(
            self.state(dirty_entries=(" M tracked.txt", "?? untracked.txt"))
        )

        self.assertEqual(len(blockers), 1)
        self.assertIn("working tree has uncommitted changes", blockers[0])
        self.assertIn(" M tracked.txt", blockers[0])
        self.assertIn("?? untracked.txt", blockers[0])

    def test_open_governed_pull_requests_block_together(self):
        pull_requests = (
            MODULE.PullRequest(31, "First", "feature/PROJ-31-first", "https://example/31"),
            MODULE.PullRequest(32, "Second", "fix/TEAM-32-second", "https://example/32"),
        )

        blockers = MODULE.blockers_for(
            self.state(open_governed_pull_requests=pull_requests)
        )

        self.assertEqual(len(blockers), 1)
        self.assertIn("Review and merge the outstanding pull request", blockers[0])
        self.assertIn("#31 First", blockers[0])
        self.assertIn("#32 Second", blockers[0])

    def test_merged_current_branch_with_remote_requires_cleanup(self):
        blockers = MODULE.blockers_for(
            self.state(
                current_branch="chore/PROJ-30-cleanup",
                current_pull_request_state="MERGED",
                current_remote_branch_exists=True,
            )
        )

        self.assertEqual(len(blockers), 1)
        self.assertIn("remote branch origin/chore/PROJ-30-cleanup still exists", blockers[0])

    def test_unpublished_remote_feature_branch_blocks(self):
        blockers = MODULE.blockers_for(
            self.state(
                current_branch="docs/PROJ-31-unpublished",
                current_remote_branch_exists=True,
            )
        )

        self.assertEqual(len(blockers), 1)
        self.assertIn("has no pull request", blockers[0])

    def test_dirty_tree_and_open_pull_request_report_both_blockers(self):
        blockers = MODULE.blockers_for(
            self.state(
                dirty_entries=(" M tracked.txt",),
                open_governed_pull_requests=(
                    MODULE.PullRequest(
                        31,
                        "First",
                        "feature/PROJ-31-first",
                        "https://example/31",
                    ),
                ),
            )
        )

        self.assertEqual(len(blockers), 2)

    def test_stale_local_deliveries_warn_without_blocking(self):
        state = self.state(
            stale_local_delivery_branches=(
                "agent/PROJ-27-old-delivery",
                "agent/PROJ-28-old-delivery",
            )
        )

        self.assertEqual(MODULE.blockers_for(state), [])
        warnings = MODULE.warnings_for(state)
        self.assertEqual(len(warnings), 1)
        self.assertIn("cleanup debt", warnings[0])
        self.assertIn("agent/PROJ-27-old-delivery", warnings[0])
        self.assertIn("will not delete", warnings[0])

    def test_workbench_behind_main_blocks(self):
        state = self.state(workbench_exists=True, workbench_commits_behind_main=15)

        blockers = MODULE.blockers_for(state)
        self.assertEqual(len(blockers), 1)
        self.assertIn("workbench/local is 15 commit(s) behind main", blockers[0])
        self.assertEqual(MODULE.warnings_for(state), [])

    def test_workbench_behind_main_blocks_at_one_commit(self):
        """No tolerance threshold: one missing commit is the same defect."""
        state = self.state(workbench_exists=True, workbench_commits_behind_main=1)

        self.assertEqual(len(MODULE.blockers_for(state)), 1)

    def test_absent_workbench_does_not_block(self):
        """A repository on the direct-delivery path never entered the workbench."""
        state = self.state(workbench_exists=False, workbench_commits_behind_main=9)

        self.assertEqual(MODULE.blockers_for(state), [])

    def test_main_behind_remote_blocks_with_fast_forward_recovery(self):
        blockers = MODULE.blockers_for(self.state(main_behind_remote=3))

        self.assertEqual(len(blockers), 1)
        self.assertIn("3 commit(s) behind origin/main", blockers[0])
        self.assertIn("merge --ff-only", blockers[0])

    def test_main_ahead_of_remote_blocks_without_offering_to_rewrite(self):
        blockers = MODULE.blockers_for(self.state(main_ahead_of_remote=2))

        self.assertEqual(len(blockers), 1)
        self.assertIn("2 commit(s) ahead of origin/main", blockers[0])
        self.assertNotIn("--ff-only", blockers[0])

    def test_diverged_main_reports_both_sides(self):
        blockers = MODULE.blockers_for(
            self.state(main_ahead_of_remote=2, main_behind_remote=5)
        )

        self.assertEqual(len(blockers), 1)
        self.assertIn("diverged", blockers[0])
        self.assertIn("2 unique local commit(s)", blockers[0])
        self.assertIn("5 unique remote commit(s)", blockers[0])

    def test_untracked_remote_main_does_not_block(self):
        """A repository with no origin/main cannot be judged against one."""
        state = self.state(
            remote_main_tracked=False, main_ahead_of_remote=4, main_behind_remote=4
        )

        self.assertEqual(MODULE.blockers_for(state), [])

    def test_baseline_and_delivery_blockers_report_together(self):
        blockers = MODULE.blockers_for(
            self.state(
                main_behind_remote=1,
                workbench_exists=True,
                workbench_commits_behind_main=1,
                dirty_entries=(" M tracked.txt",),
            )
        )

        self.assertEqual(len(blockers), 3)

    def test_stale_local_deliveries_still_warn(self):
        state = self.state(stale_local_delivery_branches=("agent/PROJ-27-old",))

        self.assertEqual(MODULE.blockers_for(state), [])
        warnings = MODULE.warnings_for(state)
        self.assertEqual(len(warnings), 1)
        self.assertIn("cleanup debt", warnings[0])
        self.assertIn("agent/PROJ-27-old", warnings[0])

    def test_clean_repository_produces_no_warning(self):
        self.assertEqual(MODULE.warnings_for(self.state()), [])

    def test_branch_recognition_requires_intent_category_and_full_issue_key(self):
        self.assertTrue(MODULE.is_governed_delivery_branch("fix/PROJ-123-login-timeout"))
        self.assertTrue(
            MODULE.is_governed_delivery_branch("chore/TEAM-42-update-dependencies")
        )
        self.assertTrue(
            MODULE.is_governed_delivery_branch("refactor/PROJ-124-telemetry-layout")
        )
        self.assertFalse(MODULE.is_governed_delivery_branch("fix/PROJ-login-timeout"))
        self.assertFalse(
            MODULE.is_governed_delivery_branch(
                "chore/TEAM(Expanded-Project-Name)-update-dependencies"
            )
        )
        self.assertFalse(MODULE.is_governed_delivery_branch("feature/user-authentication"))

    def test_legacy_agent_branch_remains_recognizable_for_cleanup(self):
        self.assertTrue(
            MODULE.is_governed_delivery_branch("agent/PROJ-38-agent-control-plane")
        )


class WorkbenchDriftDetectionTests(unittest.TestCase):
    def repo(self):
        import subprocess
        import tempfile

        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        root = Path(temporary_directory.name)

        def git(*arguments):
            return subprocess.run(
                ["git", *arguments],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )

        git("init", "--initial-branch=main", "-q")
        git("config", "user.name", "Preflight Test")
        git("config", "user.email", "preflight@example.invalid")
        (root / "tracked.txt").write_text("main\n", encoding="utf-8")
        git("add", "tracked.txt")
        git("commit", "-q", "-m", "Initial")
        return root, git

    def test_zero_when_workbench_matches_main(self):
        root, git = self.repo()
        git("branch", "workbench/local", "main")

        self.assertEqual(MODULE.workbench_commits_behind_main(root), 0)

    def test_counts_commits_main_has_that_workbench_lacks(self):
        root, git = self.repo()
        git("branch", "workbench/local", "main")
        for message in ("Second", "Third"):
            (root / "tracked.txt").write_text(message + "\n", encoding="utf-8")
            git("commit", "-q", "-am", message)

        self.assertEqual(MODULE.workbench_commits_behind_main(root), 2)

    def test_zero_when_workbench_branch_does_not_exist(self):
        root, _git = self.repo()

        self.assertEqual(MODULE.workbench_commits_behind_main(root), 0)


class BranchCreationMatcherTests(unittest.TestCase):
    def test_matches_checkout_dash_b(self):
        self.assertTrue(MODULE.targets_branch_creation("git checkout -b fix/PROJ-1-x"))

    def test_matches_switch_dash_c(self):
        self.assertTrue(MODULE.targets_branch_creation("git switch -c fix/PROJ-1-x"))

    def test_matches_inside_a_command_chain(self):
        self.assertTrue(
            MODULE.targets_branch_creation("cd repo && git checkout -b fix/PROJ-1-x")
        )

    def test_ignores_unrelated_git_commands(self):
        self.assertFalse(MODULE.targets_branch_creation("git status"))
        self.assertFalse(MODULE.targets_branch_creation("git checkout main"))
        self.assertFalse(MODULE.targets_branch_creation("git branch fix/PROJ-1-x"))

    def test_ignores_non_git_commands(self):
        self.assertFalse(MODULE.targets_branch_creation("ls -la"))


class HookResponseTests(unittest.TestCase):
    def test_none_for_a_command_that_is_not_branch_creation(self):
        with mock.patch.object(MODULE, "inspect_repository") as inspect:
            result = MODULE.hook_response({"command": "git status"}, Path("/repo"))
        inspect.assert_not_called()
        self.assertIsNone(result)

    def test_denial_names_the_canonical_preparation_operation(self):
        """A denial that only says no leaves the agent to improvise."""
        payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "git checkout -b fix/PROJ-1-x"}}
        )
        dirty_state = MODULE.RepositoryState(
            dirty_entries=(" M tracked.txt",),
            open_governed_pull_requests=(),
            current_branch="main",
            current_pull_request_state=None,
            current_remote_branch_exists=False,
            stale_local_delivery_branches=(),
            workbench_exists=False,
            workbench_commits_behind_main=0,
            remote_main_tracked=True,
            main_ahead_of_remote=0,
            main_behind_remote=0,
        )
        with mock.patch.object(MODULE, "inspect_repository", return_value=dirty_state):
            decision = MODULE.hook_response(json.loads(payload)["tool_input"], Path("."))

        reason = decision["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("prepare_delivery_branch.py", reason)
        self.assertIn("uncommitted changes", reason)

    def test_none_when_no_blockers_apply(self):
        clean_state = MODULE.RepositoryState(
            dirty_entries=(),
            open_governed_pull_requests=(),
            current_branch="main",
            current_pull_request_state=None,
            current_remote_branch_exists=False,
            stale_local_delivery_branches=(),
            workbench_exists=False,
            workbench_commits_behind_main=0,
            remote_main_tracked=True,
            main_ahead_of_remote=0,
            main_behind_remote=0,
        )
        with mock.patch.object(MODULE, "inspect_repository", return_value=clean_state):
            result = MODULE.hook_response(
                {"command": "git checkout -b fix/PROJ-1-x"}, Path("/repo")
            )
        self.assertIsNone(result)

    def test_denies_with_the_blocker_text_as_reason(self):
        dirty_state = MODULE.RepositoryState(
            dirty_entries=(" M tracked.txt",),
            open_governed_pull_requests=(),
            current_branch="main",
            current_pull_request_state=None,
            current_remote_branch_exists=False,
            stale_local_delivery_branches=(),
            workbench_exists=False,
            workbench_commits_behind_main=0,
            remote_main_tracked=True,
            main_ahead_of_remote=0,
            main_behind_remote=0,
        )
        with mock.patch.object(MODULE, "inspect_repository", return_value=dirty_state):
            result = MODULE.hook_response(
                {"command": "git switch -c fix/PROJ-1-x"}, Path("/repo")
            )
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("uncommitted changes", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_denies_when_repository_state_cannot_be_verified(self):
        with mock.patch.object(
            MODULE, "inspect_repository", side_effect=MODULE.InspectionError("gh unavailable")
        ):
            result = MODULE.hook_response(
                {"command": "git checkout -b fix/PROJ-1-x"}, Path("/repo")
            )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("gh unavailable", result["hookSpecificOutput"]["permissionDecisionReason"])


class RunAsHookTests(unittest.TestCase):
    def test_silent_on_malformed_stdin(self):
        with mock.patch("builtins.print") as printed:
            exit_code = MODULE.run_as_hook("not json", Path("/repo"))
        printed.assert_not_called()
        self.assertEqual(exit_code, 0)

    def test_silent_for_a_non_bash_tool(self):
        payload = json.dumps({"tool_name": "Read", "tool_input": {}})
        with mock.patch("builtins.print") as printed:
            exit_code = MODULE.run_as_hook(payload, Path("/repo"))
        printed.assert_not_called()
        self.assertEqual(exit_code, 0)

    def test_silent_outside_a_git_worktree(self):
        payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "git checkout -b fix/PROJ-1-x"}}
        )
        with mock.patch.object(
            MODULE, "repository_root", side_effect=MODULE.InspectionError("no worktree")
        ):
            with mock.patch("builtins.print") as printed:
                exit_code = MODULE.run_as_hook(payload, Path("/elsewhere"))
        printed.assert_not_called()
        self.assertEqual(exit_code, 0)

    def test_prints_deny_json_for_a_blocked_branch_creation(self):
        payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "git checkout -b fix/PROJ-1-x"}}
        )
        dirty_state = MODULE.RepositoryState(
            dirty_entries=(" M tracked.txt",),
            open_governed_pull_requests=(),
            current_branch="main",
            current_pull_request_state=None,
            current_remote_branch_exists=False,
            stale_local_delivery_branches=(),
            workbench_exists=False,
            workbench_commits_behind_main=0,
            remote_main_tracked=True,
            main_ahead_of_remote=0,
            main_behind_remote=0,
        )
        with mock.patch.object(MODULE, "repository_root", return_value=Path("/repo")):
            with mock.patch.object(MODULE, "inspect_repository", return_value=dirty_state):
                with mock.patch("builtins.print") as printed:
                    exit_code = MODULE.run_as_hook(payload, Path("/repo"))
        self.assertEqual(exit_code, 0)
        printed.assert_called_once()
        emitted = json.loads(printed.call_args[0][0])
        self.assertEqual(emitted["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
