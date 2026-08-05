import importlib.util
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
    / "cleanup_merged_delivery.py"
)
SPEC = importlib.util.spec_from_file_location("cleanup_merged_delivery", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RepositoryScenario:
    def __init__(self, root: Path, *, squash: bool = False):
        self.root = root
        self.origin = root / "origin.git"
        self.primary = root / "primary"
        self.feature_branch = "agent/AEPI-999-cleanup-test"

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
            "headRefName": "agent/AEPI-999-cleanup-test",
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
        self.assertEqual(
            run_mock.call_args.kwargs["timeout"],
            MODULE.NETWORK_COMMAND_TIMEOUT_SECONDS,
        )

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

        self.assertEqual(plan.deletion_flag, "-d")
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

        self.assertEqual(plan.deletion_flag, "-D")
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
        secondary = scenario.root / "secondary"
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
        self.assertFalse(
            MODULE.branch_exists(scenario.primary, scenario.feature_branch)
        )

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


if __name__ == "__main__":
    unittest.main()
