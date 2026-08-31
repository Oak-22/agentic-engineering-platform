from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "developer_skills.py"
SPEC = importlib.util.spec_from_file_location("developer_skills", SCRIPT_PATH)
assert SPEC and SPEC.loader
skills = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = skills
SPEC.loader.exec_module(skills)


class ResolutionTests(unittest.TestCase):
    def test_the_explicit_override_wins(self):
        with patch.dict(os.environ, {skills.ENV_VAR: "/custom", "XDG_DATA_HOME": "/xdg"}):
            self.assertEqual(skills.skills_root(), Path("/custom"))

    def test_xdg_is_used_when_no_override_is_set(self):
        with patch.dict(os.environ, {"XDG_DATA_HOME": "/xdg"}, clear=False):
            os.environ.pop(skills.ENV_VAR, None)
            self.assertEqual(skills.skills_root(), Path("/xdg") / skills.NAMESPACE)

    def test_the_default_is_the_xdg_location_under_home(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(skills.ENV_VAR, None)
            os.environ.pop("XDG_DATA_HOME", None)
            self.assertEqual(
                skills.skills_root(),
                Path.home() / ".local" / "share" / skills.NAMESPACE,
            )

    def test_a_tilde_in_the_override_is_expanded(self):
        with patch.dict(os.environ, {skills.ENV_VAR: "~/elsewhere"}):
            self.assertEqual(skills.skills_root(), Path.home() / "elsewhere")

    def test_base_overrides_everything_for_testability(self):
        with patch.dict(os.environ, {skills.ENV_VAR: "/custom"}):
            self.assertEqual(skills.skills_root(base=Path("/b")), Path("/b"))

    def test_resolution_never_consults_a_repository(self):
        """These skills belong to the developer, not to whichever checkout is open.

        Checked against the code rather than the prose: the docstrings discuss
        repositories precisely because the resolver ignores them.
        """
        tree = ast.parse(SCRIPT_PATH.read_text())

        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertNotIn("subprocess", imported)

        parameters = {
            argument.arg
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            for argument in node.args.args + node.args.kwonlyargs
        }
        self.assertEqual(parameters & {"repo_root", "project_dir", "root"}, set())


class StandaloneTests(unittest.TestCase):
    """It must work where this platform is not installed at all."""

    def stdlib_names(self) -> set[str]:
        return set(sys.stdlib_module_names)

    def test_it_imports_nothing_outside_the_standard_library(self):
        tree = ast.parse(SCRIPT_PATH.read_text())
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])

        self.assertTrue(imported)
        self.assertEqual(imported - self.stdlib_names(), set())

    def test_it_makes_no_relative_import(self):
        tree = ast.parse(SCRIPT_PATH.read_text())
        relative = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level
        ]

        self.assertEqual(relative, [])

    def test_it_runs_from_a_directory_with_no_control_plane_present(self):
        """Copied out on its own, it must still resolve a path."""
        with tempfile.TemporaryDirectory() as directory:
            isolated = Path(directory) / "developer_skills.py"
            isolated.write_text(SCRIPT_PATH.read_text())

            result = subprocess.run(
                [sys.executable, str(isolated)],
                cwd=directory,
                capture_output=True,
                text=True,
                env={**os.environ, skills.ENV_VAR: "/somewhere/skills"},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "/somewhere/skills")

    def test_the_shell_equivalent_resolves_to_the_same_path(self):
        """The documented one-liner is the contract, so it has to hold."""
        with tempfile.TemporaryDirectory() as directory:
            environment = {**os.environ, "XDG_DATA_HOME": directory}
            environment.pop(skills.ENV_VAR, None)

            shell = subprocess.run(
                ["sh", "-c", f"printf %s {skills.SHELL_EQUIVALENT}"],
                capture_output=True,
                text=True,
                env=environment,
            )
            with patch.dict(os.environ, environment, clear=True):
                resolved = skills.skills_root()

            self.assertEqual(shell.stdout.strip(), str(resolved))


class WriteBoundaryTests(unittest.TestCase):
    def test_nothing_here_creates_or_removes_anything(self):
        """A resolver that also writes hands out a write path for free."""
        source = SCRIPT_PATH.read_text()

        for mutation in ("mkdir", "write_text", "unlink", "rmtree", "touch", "symlink"):
            with self.subTest(call=mutation):
                self.assertNotIn(mutation, source)


if __name__ == "__main__":
    unittest.main()
