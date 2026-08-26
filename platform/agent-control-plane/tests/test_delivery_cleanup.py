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

    def test_workbench_return_branch_conflict_is_aborted_and_reported(self):
        scenario = self.scenario()
        scenario.git(scenario.primary, "switch", "-c", "workbench/local", "main~1")
        (scenario.primary / "feature.txt").write_text(
            "conflicting workbench content\n", encoding="utf-8"
        )
        scenario.git(scenario.primary, "add", "feature.txt")
        scenario.git(scenario.primary, "commit", "-m", "Conflicting workbench capture")
        workbench_tip_before = scenario.rev_parse("workbench/local")
        scenario.git(scenario.primary, "switch", "main")

        plan = MODULE.build_cleanup_plan(scenario.primary, scenario.pull_request)
        sync = MODULE.execute_cleanup(plan)

        self.assertEqual(sync, "conflict-manual-resolution-required")
        self.assertEqual(MODULE.current_branch(scenario.primary), "workbench/local")
        self.assertEqual(scenario.rev_parse("workbench/local"), workbench_tip_before)
        status = scenario.git(scenario.primary, "status", "--porcelain=v1").stdout
        self.assertEqual(status.strip(), "")
        self.assertFalse((scenario.primary / ".git" / "MERGE_HEAD").exists())

    def test_sync_workbench_with_base_reports_already_up_to_date(self):
        scenario = self.scenario()
        scenario.git(scenario.primary, "branch", "workbench/local", "main")

        result = MODULE.sync_workbench_with_base(
            scenario.primary, workbench_branch="workbench/local", base_branch="main"
        )

        self.assertEqual(result, "already-up-to-date")


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

    def test_execution_rejects_dirty_workspace(self):
        scenario = self.scenario()
        branch = "release/PROJ-108-safe"
        head_oid = scenario.create_branch(branch)
        report = self.report(
            scenario,
            pull_requests=(self.merged_pr(108, branch, head_oid),),
        )
        (scenario.primary / "untracked.txt").write_text(
            "preserve\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(MODULE.CleanupError, "workspace is dirty"):
            MODULE.execute_reconciliation(scenario.primary, report)

        self.assertIn(branch, MODULE.local_delivery_branches(scenario.primary))


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
