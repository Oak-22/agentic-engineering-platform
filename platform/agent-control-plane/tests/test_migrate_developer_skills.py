from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).parents[1] / "scripts" / "migrate_developer_skills.py"
)
SPEC = importlib.util.spec_from_file_location("migrate_developer_skills", SCRIPT_PATH)
assert SPEC and SPEC.loader
migrate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = migrate
SPEC.loader.exec_module(migrate)

DIGEST = migrate._sibling("migrate_local_stores").file_digest


def tree(root: Path, files: dict[str, str]) -> Path:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return root


class ClassifyTests(unittest.TestCase):
    def test_an_absent_target_is_copied(self):
        with tempfile.TemporaryDirectory() as directory:
            source = tree(Path(directory) / "s", {"a.md": "one"})

            self.assertEqual(
                migrate.classify("a.md", source / "a.md", Path(directory) / "t" / "a.md", DIGEST),
                migrate.COPY,
            )

    def test_matching_content_is_already_migrated(self):
        with tempfile.TemporaryDirectory() as directory:
            source = tree(Path(directory) / "s", {"a.md": "one"})
            target = tree(Path(directory) / "t", {"a.md": "one"})

            self.assertEqual(
                migrate.classify("a.md", source / "a.md", target / "a.md", DIGEST),
                migrate.IDENTICAL,
            )

    def test_differing_content_is_a_conflict_never_an_overwrite(self):
        """This content has no other copy and no review step."""
        with tempfile.TemporaryDirectory() as directory:
            source = tree(Path(directory) / "s", {"a.md": "one"})
            target = tree(Path(directory) / "t", {"a.md": "two"})

            self.assertEqual(
                migrate.classify("a.md", source / "a.md", target / "a.md", DIGEST),
                migrate.CONFLICT,
            )


class PlanTests(unittest.TestCase):
    def test_a_clean_plan_copies_every_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source = tree(Path(directory) / "s", {"a.md": "one", "n/b.md": "two"})

            value = migrate.plan(source, Path(directory) / "t")

            self.assertFalse(value["blocked"])
            self.assertEqual({e["action"] for e in value["entries"]}, {migrate.COPY})
            self.assertEqual(len(value["entries"]), 2)

    def test_any_conflict_blocks_the_whole_run(self):
        with tempfile.TemporaryDirectory() as directory:
            source = tree(Path(directory) / "s", {"a.md": "one", "b.md": "two"})
            target = tree(Path(directory) / "t", {"b.md": "different"})

            value = migrate.plan(source, target)

            self.assertTrue(value["blocked"])
            self.assertEqual(value["conflicts"], ["b.md"])

    def test_an_absent_source_is_reported_rather_than_failing(self):
        with tempfile.TemporaryDirectory() as directory:
            value = migrate.plan(Path(directory) / "absent", Path(directory) / "t")

            self.assertFalse(value["sourcePresent"])
            self.assertEqual(value["entries"], [])


class ExecuteTests(unittest.TestCase):
    def test_files_are_copied_and_verify_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            source = tree(Path(directory) / "s", {"a.md": "one", "n/b.md": "two"})
            target = Path(directory) / "t"

            value = migrate.plan(source, target)
            migrate.execute(value)

            self.assertEqual(migrate.verify(value), [])
            self.assertEqual((target / "n" / "b.md").read_text(), "two")

    def test_the_source_is_left_intact(self):
        """Deleting the only copy of content this platform does not own is not its call."""
        with tempfile.TemporaryDirectory() as directory:
            source = tree(Path(directory) / "s", {"a.md": "one"})

            value = migrate.plan(source, Path(directory) / "t")
            migrate.execute(value)

            self.assertTrue((source / "a.md").exists())
            self.assertEqual((source / "a.md").read_text(), "one")

    def test_a_blocked_plan_refuses_to_run(self):
        with tempfile.TemporaryDirectory() as directory:
            source = tree(Path(directory) / "s", {"a.md": "one"})
            target = tree(Path(directory) / "t", {"a.md": "different"})

            value = migrate.plan(source, target)

            with self.assertRaises(RuntimeError):
                migrate.execute(value)

            self.assertEqual((target / "a.md").read_text(), "different")

    def test_running_twice_changes_nothing_the_second_time(self):
        with tempfile.TemporaryDirectory() as directory:
            source = tree(Path(directory) / "s", {"a.md": "one"})
            target = Path(directory) / "t"

            migrate.execute(migrate.plan(source, target))
            second = migrate.plan(source, target)

            self.assertFalse(second["blocked"])
            self.assertEqual({e["action"] for e in second["entries"]}, {migrate.IDENTICAL})

    def test_verify_reports_a_file_that_did_not_arrive(self):
        with tempfile.TemporaryDirectory() as directory:
            source = tree(Path(directory) / "s", {"a.md": "one", "b.md": "two"})
            target = Path(directory) / "t"

            value = migrate.plan(source, target)
            migrate.execute(value)
            (target / "b.md").unlink()

            self.assertEqual(migrate.verify(value), ["b.md"])

    def test_verify_reports_a_file_whose_content_diverged(self):
        with tempfile.TemporaryDirectory() as directory:
            source = tree(Path(directory) / "s", {"a.md": "one"})
            target = Path(directory) / "t"

            value = migrate.plan(source, target)
            migrate.execute(value)
            (target / "a.md").write_text("tampered")

            self.assertEqual(migrate.verify(value), ["a.md"])


if __name__ == "__main__":
    unittest.main()
