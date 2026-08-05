from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


COMPONENT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = COMPONENT_ROOT / "scripts" / "protect_main_commit.py"
HOOK_PATH = COMPONENT_ROOT.parents[1] / ".githooks" / "pre-commit"
SPEC = importlib.util.spec_from_file_location("protect_main_commit", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProtectMainCommitTests(unittest.TestCase):
    def test_main_is_blocked_without_explicit_bypass(self):
        self.assertTrue(MODULE.should_block("main", None))

    def test_explicit_bypass_allows_main(self):
        self.assertFalse(MODULE.should_block("main", "1"))

    def test_non_main_branch_is_allowed(self):
        self.assertFalse(MODULE.should_block("agent/AEPI-33-example", None))

    def test_hook_blocks_main_and_allows_explicit_bypass(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            hook = root / ".githooks" / "pre-commit"
            script = (
                root
                / "platform"
                / "agent-control-plane"
                / "scripts"
                / "protect_main_commit.py"
            )
            hook.parent.mkdir(parents=True)
            script.parent.mkdir(parents=True)
            shutil.copy2(HOOK_PATH, hook)
            shutil.copy2(SCRIPT_PATH, script)
            hook.chmod(0o755)

            self.run_git(root, "init", "--initial-branch=main")
            self.run_git(root, "config", "user.name", "Guardrail Test")
            self.run_git(root, "config", "user.email", "guardrail@example.invalid")
            self.run_git(root, "config", "core.hooksPath", ".githooks")
            (root / "tracked.txt").write_text("first\n", encoding="utf-8")
            self.run_git(root, "add", "tracked.txt")

            blocked = self.run_git(root, "commit", "-m", "Blocked", check=False)

            self.assertEqual(blocked.returncode, 1)
            self.assertIn("Commit blocked", blocked.stderr)

            environment = os.environ.copy()
            environment[MODULE.BYPASS_VARIABLE] = "1"
            allowed = self.run_git(
                root,
                "commit",
                "-m",
                "Explicitly allowed",
                environment=environment,
                check=False,
            )

            self.assertEqual(allowed.returncode, 0, allowed.stderr)

    @staticmethod
    def run_git(
        root: Path,
        *arguments: str,
        environment: dict[str, str] | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=check,
            capture_output=True,
            text=True,
            env=environment,
        )


if __name__ == "__main__":
    unittest.main()
