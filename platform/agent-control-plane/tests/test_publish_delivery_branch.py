from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "platform" / "agent-control-plane" / "scripts" / "publish_delivery_branch.py"
SPEC = importlib.util.spec_from_file_location("publish_delivery_branch", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RepositoryScenario:
    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.remote = self.root / "remote.git"
        self.seed = self.root / "seed"
        self.work = self.root / "work"
        self.run("git", "init", "--bare", str(self.remote), cwd=self.root)
        self.run("git", "init", "-b", "main", str(self.seed), cwd=self.root)
        self.configure(self.seed)
        (self.seed / "base.txt").write_text("base\n")
        self.run("git", "add", "base.txt", cwd=self.seed)
        self.run("git", "commit", "-m", "base", cwd=self.seed)
        self.run("git", "remote", "add", "origin", str(self.remote), cwd=self.seed)
        self.run("git", "push", "-u", "origin", "main", cwd=self.seed)
        self.run("git", "clone", str(self.remote), str(self.work), cwd=self.root)
        self.run("git", "switch", "main", cwd=self.work)
        self.configure(self.work)
        # Publication validates the logical GitHub destination. Keep transport
        # local for the test while replacing only the configured URL afterward.
        self.run(
            "git",
            "remote",
            "set-url",
            "origin",
            "git@github.com:Oak-22/agentic-engineering-platform.git",
            cwd=self.work,
        )

    @staticmethod
    def run(*command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)

    @staticmethod
    def configure(path: Path) -> None:
        RepositoryScenario.run("git", "config", "user.name", "Test", cwd=path)
        RepositoryScenario.run("git", "config", "user.email", "test@example.invalid", cwd=path)

    def delivery_commit(self, branch: str = "feature/AEPI-999-safe-publish") -> None:
        self.run("git", "switch", "-c", branch, cwd=self.work)
        (self.work / "delivery.txt").write_text("delivery\n")
        self.run("git", "add", "delivery.txt", cwd=self.work)
        self.run("git", "commit", "-m", "delivery", cwd=self.work)

    def close(self) -> None:
        self.temporary.cleanup()


class ValidationTests(unittest.TestCase):
    def test_remote_url_accepts_ssh_and_https_for_the_canonical_repository(self):
        for url in (
            "git@github.com:Oak-22/agentic-engineering-platform.git",
            "https://github.com/Oak-22/agentic-engineering-platform",
        ):
            self.assertEqual(MODULE.repository_from_remote(url), MODULE.EXPECTED_REPOSITORY)

    def test_remote_url_rejects_a_different_repository(self):
        with self.assertRaisesRegex(MODULE.PublicationError, "expected"):
            MODULE.repository_from_remote("git@github.com:Oak-22/other.git")

    def test_delivery_branch_pattern_rejects_main_and_retired_categories(self):
        self.assertIsNone(MODULE.DELIVERY_BRANCH.match("main"))
        self.assertIsNone(MODULE.DELIVERY_BRANCH.match("hotfix/AEPI-9-x"))


class PlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = RepositoryScenario()
        self.addCleanup(self.scenario.close)

    def _use_local_transport(self) -> None:
        self.scenario.run(
            "git", "remote", "set-url", "origin", str(self.scenario.remote), cwd=self.scenario.work
        )

    def test_main_is_not_publishable(self):
        with self.assertRaisesRegex(MODULE.PublicationError, "Jira-keyed"):
            MODULE.build_plan(self.scenario.work, fetch=False)

    def test_dirty_delivery_branch_is_blocked(self):
        self.scenario.delivery_commit()
        (self.scenario.work / "dirty.txt").write_text("dirty\n")
        with self.assertRaisesRegex(MODULE.PublicationError, "not clean"):
            MODULE.build_plan(self.scenario.work, fetch=False)

    def test_plan_uses_current_origin_main_and_emits_structured_evidence(self):
        self.scenario.delivery_commit()
        plan = MODULE.build_plan(self.scenario.work, fetch=False)
        result = MODULE.result_for_plan(plan)
        self.assertEqual(result.outcome, "planned")
        self.assertEqual(result.branch, "feature/AEPI-999-safe-publish")
        self.assertEqual(result.baseSync, "none")
        self.assertFalse(result.executed)

    def test_branch_with_no_delivery_commit_is_blocked(self):
        self.scenario.run(
            "git", "switch", "-c", "docs/AEPI-999-empty-delivery", cwd=self.scenario.work
        )
        with self.assertRaisesRegex(MODULE.PublicationError, "nothing can be published"):
            MODULE.build_plan(self.scenario.work, fetch=False)

    def test_diverged_main_is_integrated_with_a_merge(self):
        self.scenario.delivery_commit()
        (self.scenario.seed / "main.txt").write_text("main\n")
        self.scenario.run("git", "add", "main.txt", cwd=self.scenario.seed)
        self.scenario.run("git", "commit", "-m", "advance main", cwd=self.scenario.seed)
        self.scenario.run("git", "push", cwd=self.scenario.seed)
        self._use_local_transport()
        self.scenario.run("git", "fetch", "origin", cwd=self.scenario.work)
        self.scenario.run(
            "git",
            "remote",
            "set-url",
            "origin",
            "git@github.com:Oak-22/agentic-engineering-platform.git",
            cwd=self.scenario.work,
        )
        plan = MODULE.build_plan(self.scenario.work, fetch=False)
        self.assertEqual(plan.base_sync, "merge")

    def test_execute_pushes_only_the_same_branch_and_verifies_remote_head(self):
        self.scenario.delivery_commit()
        self._use_local_transport()
        main_before = self.scenario.run(
            "git", "--git-dir", str(self.scenario.remote), "rev-parse", "refs/heads/main",
            cwd=self.scenario.root,
        ).stdout.strip()
        with mock.patch.object(
            MODULE, "repository_from_remote", return_value=MODULE.EXPECTED_REPOSITORY
        ):
            plan = MODULE.build_plan(self.scenario.work)
            result = MODULE.execute(self.scenario.work, plan)
        remote_head = self.scenario.run(
            "git",
            "--git-dir",
            str(self.scenario.remote),
            "rev-parse",
            "refs/heads/feature/AEPI-999-safe-publish",
            cwd=self.scenario.root,
        ).stdout.strip()
        self.assertEqual(result.outcome, "published")
        self.assertEqual(result.headAfter, remote_head)
        main_after = self.scenario.run(
            "git", "--git-dir", str(self.scenario.remote), "rev-parse", "refs/heads/main",
            cwd=self.scenario.root,
        ).stdout.strip()
        self.assertEqual(main_after, main_before)


if __name__ == "__main__":
    unittest.main()
