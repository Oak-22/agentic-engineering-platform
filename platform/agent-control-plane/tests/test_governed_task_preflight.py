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

    def test_none_when_no_blockers_apply(self):
        clean_state = MODULE.RepositoryState(
            dirty_entries=(),
            open_governed_pull_requests=(),
            current_branch="main",
            current_pull_request_state=None,
            current_remote_branch_exists=False,
            stale_local_delivery_branches=(),
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
