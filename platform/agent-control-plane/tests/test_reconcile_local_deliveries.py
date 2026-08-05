import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]
    / ".agents"
    / "skills"
    / "manage-git-workflow"
    / "scripts"
    / "reconcile_local_deliveries.py"
)
SPEC = importlib.util.spec_from_file_location(
    "reconcile_local_deliveries", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RepositoryScenario:
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
        return RepositoryScenario(Path(temporary_directory.name))

    @staticmethod
    def merged_pr(number: int, branch: str, head_oid: str):
        return MODULE.PullRequest(
            number=number,
            state="MERGED",
            merged_at="2026-08-05T00:00:00Z",
            head_branch=branch,
            head_oid=head_oid,
            url=f"https://example.invalid/pull/{number}",
        )

    def test_merged_remote_absent_branch_is_safe(self):
        scenario = self.scenario()
        branch = "agent/AEPI-100-merged"
        head_oid = scenario.create_branch(branch)

        report = MODULE.build_report(
            scenario.primary,
            live_remote_branches=set(),
            pull_requests=(self.merged_pr(100, branch, head_oid),),
        )

        candidate = report.candidates[0]
        self.assertEqual(candidate.classification, "safe-to-delete")
        self.assertEqual(candidate.pull_request, 100)

    def test_no_pr_branch_requires_manual_review(self):
        scenario = self.scenario()
        branch = "AEPI-101-no-pr"
        scenario.create_branch(branch)

        report = MODULE.build_report(
            scenario.primary,
            live_remote_branches=set(),
            pull_requests=(),
        )

        self.assertEqual(report.candidates[0].classification, "manual-review")
        self.assertIn("no associated pull request", report.candidates[0].reason)

    def test_unique_commit_is_preserved(self):
        scenario = self.scenario()
        branch = "agent/AEPI-102-unique"
        head_oid = scenario.create_branch(branch, unique_commit=True)

        report = MODULE.build_report(
            scenario.primary,
            live_remote_branches=set(),
            pull_requests=(self.merged_pr(102, branch, head_oid),),
        )

        self.assertEqual(report.candidates[0].classification, "preserve")
        self.assertIn("not reachable", report.candidates[0].reason)

    def test_checked_out_branch_is_preserved(self):
        scenario = self.scenario()
        branch = "agent/AEPI-103-checked-out"
        head_oid = scenario.create_branch(branch)
        scenario.git(scenario.primary, "switch", branch)

        report = MODULE.build_report(
            scenario.primary,
            live_remote_branches=set(),
            pull_requests=(self.merged_pr(103, branch, head_oid),),
        )

        self.assertEqual(report.candidates[0].classification, "preserve")
        self.assertEqual(report.candidates[0].reason, "branch is checked out")

    def test_live_remote_branch_is_preserved(self):
        scenario = self.scenario()
        branch = "agent/AEPI-104-remote"
        head_oid = scenario.create_branch(branch)

        report = MODULE.build_report(
            scenario.primary,
            live_remote_branches={branch},
            pull_requests=(self.merged_pr(104, branch, head_oid),),
        )

        self.assertEqual(report.candidates[0].classification, "preserve")
        self.assertEqual(report.candidates[0].reason, "remote branch still exists")

    def test_open_pull_request_is_preserved(self):
        scenario = self.scenario()
        branch = "agent/AEPI-105-open"
        head_oid = scenario.create_branch(branch)
        pull_request = MODULE.PullRequest(
            number=105,
            state="OPEN",
            merged_at=None,
            head_branch=branch,
            head_oid=head_oid,
            url="https://example.invalid/pull/105",
        )

        report = MODULE.build_report(
            scenario.primary,
            live_remote_branches=set(),
            pull_requests=(pull_request,),
        )

        self.assertEqual(report.candidates[0].classification, "preserve")
        self.assertIn("not merged", report.candidates[0].reason)

    def test_execution_deletes_only_safe_candidates(self):
        scenario = self.scenario()
        safe_branch = "agent/AEPI-106-safe"
        manual_branch = "AEPI-107-manual"
        safe_oid = scenario.create_branch(safe_branch)
        scenario.create_branch(manual_branch)
        report = MODULE.build_report(
            scenario.primary,
            live_remote_branches=set(),
            pull_requests=(self.merged_pr(106, safe_branch, safe_oid),),
        )

        MODULE.execute_reconciliation(scenario.primary, report)

        branches = MODULE.local_branches(scenario.primary)
        self.assertNotIn(safe_branch, branches)
        self.assertIn(manual_branch, branches)

    def test_execution_rejects_dirty_workspace(self):
        scenario = self.scenario()
        branch = "agent/AEPI-108-safe"
        head_oid = scenario.create_branch(branch)
        report = MODULE.build_report(
            scenario.primary,
            live_remote_branches=set(),
            pull_requests=(self.merged_pr(108, branch, head_oid),),
        )
        (scenario.primary / "untracked.txt").write_text("preserve\n", encoding="utf-8")

        with self.assertRaisesRegex(MODULE.ReconciliationError, "workspace is dirty"):
            MODULE.execute_reconciliation(scenario.primary, report)

        self.assertIn(branch, MODULE.local_branches(scenario.primary))


if __name__ == "__main__":
    unittest.main()
