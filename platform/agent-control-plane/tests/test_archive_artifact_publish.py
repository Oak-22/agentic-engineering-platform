from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT_PATH = (
    Path(__file__).parents[1] / "scripts" / "archive_artifact_publish.py"
)
SPEC = importlib.util.spec_from_file_location("archive_artifact_publish", SCRIPT_PATH)
assert SPEC and SPEC.loader
archiver = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = archiver
SPEC.loader.exec_module(archiver)


class ResolveArchiveRootTests(unittest.TestCase):
    def test_default_base_uses_xdg_data_home_directory_not_claude(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AEP_ARTIFACT_ARCHIVE_DIR", None)
            os.environ.pop("XDG_DATA_HOME", None)
            root = archiver.resolve_archive_root(project_dir=Path("/repo/myHealth"))
        self.assertEqual(root.parent, Path.home() / ".local" / "share" / "aep" / "artifact-archive")
        self.assertTrue(root.name.startswith("myhealth--"))


class ArchiveArtifactPublishTests(unittest.TestCase):
    def test_ignores_events_other_than_post_tool_use(self):
        result = archiver.handle(
            {"hook_event_name": "PreToolUse", "tool_name": "Artifact"},
            project_dir=None,
        )
        self.assertIsNone(result)

    def test_ignores_tools_other_than_artifact(self):
        result = archiver.handle(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/whatever.html"},
            },
            project_dir=None,
        )
        self.assertIsNone(result)

    def test_missing_file_path_is_a_noop(self):
        result = archiver.handle(
            {"hook_event_name": "PostToolUse", "tool_name": "Artifact", "tool_input": {}},
            project_dir=None,
        )
        self.assertIsNone(result)

    def test_missing_source_file_reports_skip_without_raising(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "gone.html"
            result = archiver.handle(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Artifact",
                    "tool_input": {"file_path": str(source)},
                },
                project_dir=None,
            )
            self.assertIn("skipped", result["hookSpecificOutput"]["additionalContext"])

    def test_mirrors_published_file_into_project_scoped_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_dir = root / "scratchpad"
            source_dir.mkdir()
            source = source_dir / "diagram.html"
            source.write_text("<title>Diagram</title>", encoding="utf-8")

            project_dir = root / "repo-checkout"
            project_dir.mkdir()
            archive_base = root / "home"

            original_resolve = archiver.resolve_archive_root
            archiver.resolve_archive_root = lambda **kwargs: original_resolve(
                project_dir=kwargs["project_dir"], archive_base=archive_base
            )
            try:
                result = archiver.handle(
                    {
                        "hook_event_name": "PostToolUse",
                        "tool_name": "Artifact",
                        "tool_input": {"file_path": str(source)},
                    },
                    project_dir=project_dir,
                )
            finally:
                archiver.resolve_archive_root = original_resolve

            expected_destination = (
                archive_base
                / archiver.DEFAULT_ARCHIVE_DIRNAME
                / archiver._local_store.repository_identity(project_dir).partition_name
                / "diagram.html"
            )
            self.assertTrue(expected_destination.is_file())
            self.assertEqual(
                expected_destination.read_text(encoding="utf-8"),
                "<title>Diagram</title>",
            )
            self.assertIn(
                str(expected_destination),
                result["hookSpecificOutput"]["additionalContext"],
            )

    def test_republish_keeps_the_version_it_replaces(self):
        """Republishing from one path is how an artifact keeps its URL, so the
        archive would otherwise retain only the most recent publish."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "diagram.html"
            archive_root = root / "archive"
            source.write_text("v1", encoding="utf-8")
            first, superseded_first = archiver.archive_file(source, archive_root)
            self.assertIsNone(superseded_first)

            source.write_text("v2", encoding="utf-8")
            second, superseded = archiver.archive_file(source, archive_root)

            # The published name always holds the current version, so paths
            # recorded before this change stay resolvable.
            self.assertEqual(first, second)
            self.assertEqual(second.read_text(encoding="utf-8"), "v2")
            self.assertIsNotNone(superseded)
            self.assertEqual(superseded.read_text(encoding="utf-8"), "v1")
            self.assertEqual(
                sorted(path.name for path in archive_root.iterdir()),
                sorted([second.name, superseded.name]),
            )

    def test_republishing_identical_content_supersedes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "diagram.html"
            archive_root = root / "archive"
            source.write_text("unchanged", encoding="utf-8")
            archiver.archive_file(source, archive_root)
            _, superseded = archiver.archive_file(source, archive_root)

            self.assertIsNone(superseded)
            self.assertEqual(len(list(archive_root.iterdir())), 1)

    def test_versions_sharing_a_timestamp_do_not_overwrite_each_other(self):
        """The stamp resolves to the second, so distinct versions can collide."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "diagram.html"
            archive_root = root / "archive"
            archive_root.mkdir()
            destination = archive_root / "diagram.html"

            for content in ("v1", "v2", "v3"):
                source.write_text(content, encoding="utf-8")
                if destination.exists():
                    # Freeze the mtime so every superseded version competes for
                    # one name, which a real burst of republishes can do.
                    os.utime(destination, (1_760_000_000, 1_760_000_000))
                archiver.archive_file(source, archive_root)

            preserved = sorted(
                path.read_text(encoding="utf-8")
                for path in archive_root.iterdir()
            )
            self.assertEqual(preserved, ["v1", "v2", "v3"])


if __name__ == "__main__":
    unittest.main()
