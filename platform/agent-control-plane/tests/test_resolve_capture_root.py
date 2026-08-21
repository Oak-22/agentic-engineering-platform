from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "agent-assets"
    / "skills"
    / "show-me"
    / "scripts"
    / "resolve_capture_root.py"
)
SPEC = importlib.util.spec_from_file_location("resolve_capture_root", SCRIPT_PATH)
assert SPEC and SPEC.loader
capture = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = capture
SPEC.loader.exec_module(capture)


class ResolveCaptureRootTests(unittest.TestCase):
    def test_default_base_uses_xdg_data_home_directory(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AEP_SHOW_ME_CAPTURE_DIR", None)
            os.environ.pop("XDG_DATA_HOME", None)
            root = capture.resolve_capture_root(project_dir=Path("/repo/myHealth"))
        self.assertEqual(
            root,
            Path.home()
            / ".local"
            / "share"
            / "aep"
            / "show-me-captures"
            / "myHealth",
        )

    def test_xdg_data_home_env_var_overrides_default_base(self):
        with tempfile.TemporaryDirectory() as directory:
            xdg_home = Path(directory) / "xdg-data"
            with patch.dict(os.environ, {"XDG_DATA_HOME": str(xdg_home)}, clear=False):
                os.environ.pop("AEP_SHOW_ME_CAPTURE_DIR", None)
                root = capture.resolve_capture_root(project_dir=Path("/repo/myHealth"))
            self.assertEqual(
                root, xdg_home / "aep" / "show-me-captures" / "myHealth"
            )

    def test_explicit_base_overrides_default(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = capture.resolve_capture_root(
                project_dir=Path("/repo/myHealth"), capture_base=base
            )
            self.assertEqual(root, base / "show-me-captures" / "myHealth")

    def test_missing_project_dir_falls_back_to_unknown_project(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = capture.resolve_capture_root(project_dir=None, capture_base=base)
            self.assertEqual(
                root, base / "show-me-captures" / "unknown-project"
            )


class CaptureFilenameTests(unittest.TestCase):
    def test_combines_date_show_me_marker_runtime_and_slug(self):
        import datetime as dt

        name = capture.capture_filename(
            slug="instruction-manifest-hook", runtime="claude", date=dt.date(2026, 8, 13)
        )
        self.assertEqual(
            name, "2026-08-13-show-me-claude-instruction-manifest-hook"
        )

    def test_different_runtimes_produce_different_filenames(self):
        import datetime as dt

        claude_name = capture.capture_filename(
            slug="topic", runtime="claude", date=dt.date(2026, 8, 13)
        )
        codex_name = capture.capture_filename(
            slug="topic", runtime="codex", date=dt.date(2026, 8, 13)
        )
        self.assertNotEqual(claude_name, codex_name)


class WriteCaptureTests(unittest.TestCase):
    def test_writes_new_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            written = capture.write_capture(
                "explanation", capture_root=root, stem="2026-08-13-topic", extension="md"
            )
            self.assertEqual(written, root / "2026-08-13-topic.md")
            self.assertEqual(written.read_text(encoding="utf-8"), "explanation")

    def test_collision_appends_numeric_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = capture.write_capture(
                "first", capture_root=root, stem="2026-08-13-topic", extension="md"
            )
            second = capture.write_capture(
                "second", capture_root=root, stem="2026-08-13-topic", extension="md"
            )
            third = capture.write_capture(
                "third", capture_root=root, stem="2026-08-13-topic", extension="md"
            )
            self.assertEqual(first.name, "2026-08-13-topic.md")
            self.assertEqual(second.name, "2026-08-13-topic-2.md")
            self.assertEqual(third.name, "2026-08-13-topic-3.md")
            self.assertEqual(first.read_text(encoding="utf-8"), "first")
            self.assertEqual(second.read_text(encoding="utf-8"), "second")
            self.assertEqual(third.read_text(encoding="utf-8"), "third")


class CopyCaptureTests(unittest.TestCase):
    def test_copies_source_reusing_stem_and_source_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "artifact.html"
            source.write_text("<title>Diagram</title>", encoding="utf-8")

            capture_root = root / "capture"
            copied = capture.copy_capture(
                source, capture_root=capture_root, stem="2026-08-13-topic"
            )
            self.assertEqual(copied, capture_root / "2026-08-13-topic.html")
            self.assertEqual(
                copied.read_text(encoding="utf-8"), "<title>Diagram</title>"
            )

    def test_collision_appends_numeric_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "artifact.html"
            source.write_text("v1", encoding="utf-8")
            capture_root = root / "capture"

            first = capture.copy_capture(
                source, capture_root=capture_root, stem="2026-08-13-topic"
            )
            source.write_text("v2", encoding="utf-8")
            second = capture.copy_capture(
                source, capture_root=capture_root, stem="2026-08-13-topic"
            )
            self.assertEqual(first.name, "2026-08-13-topic.html")
            self.assertEqual(second.name, "2026-08-13-topic-2.html")


class WriteLatestPointerTests(unittest.TestCase):
    def test_creates_relative_symlink_to_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            capture_root = Path(directory)
            destination = capture_root / "2026-08-13-topic.md"
            destination.write_text("content", encoding="utf-8")

            pointer = capture.write_latest_pointer(
                destination, capture_root=capture_root
            )

            self.assertEqual(pointer, capture_root / "latest.md")
            self.assertTrue(pointer.is_symlink())
            self.assertEqual(os.readlink(pointer), "2026-08-13-topic.md")
            self.assertEqual(pointer.read_text(encoding="utf-8"), "content")

    def test_overwrites_pointer_on_subsequent_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            capture_root = Path(directory)
            first = capture_root / "2026-08-13-topic.md"
            first.write_text("first", encoding="utf-8")
            second = capture_root / "2026-08-14-other-topic.md"
            second.write_text("second", encoding="utf-8")

            capture.write_latest_pointer(first, capture_root=capture_root)
            pointer = capture.write_latest_pointer(second, capture_root=capture_root)

            self.assertEqual(os.readlink(pointer), "2026-08-14-other-topic.md")
            self.assertEqual(pointer.read_text(encoding="utf-8"), "second")

    def test_md_and_html_pointers_are_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            capture_root = Path(directory)
            md = capture_root / "2026-08-13-topic.md"
            md.write_text("markdown", encoding="utf-8")
            html = capture_root / "2026-08-13-topic.html"
            html.write_text("<p>html</p>", encoding="utf-8")

            capture.write_latest_pointer(md, capture_root=capture_root)
            capture.write_latest_pointer(html, capture_root=capture_root)

            self.assertEqual(
                (capture_root / "latest.md").read_text(encoding="utf-8"), "markdown"
            )
            self.assertEqual(
                (capture_root / "latest.html").read_text(encoding="utf-8"),
                "<p>html</p>",
            )


class CaptureProjectViewTests(unittest.TestCase):
    def test_creates_symlink_on_first_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_root = root / "repo"
            repo_root.mkdir()
            canonical_root = root / "canonical"
            canonical_root.mkdir()

            view = capture.capture_project_view(repo_root, canonical_root)

            self.assertEqual(view, repo_root / ".local-mirrors" / "show-me-captures")
            self.assertTrue(view.is_symlink())
            self.assertEqual(view.resolve(), canonical_root.resolve())

    def test_second_call_returns_same_view(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_root = root / "repo"
            repo_root.mkdir()
            canonical_root = root / "canonical"
            canonical_root.mkdir()

            first = capture.capture_project_view(repo_root, canonical_root)
            second = capture.capture_project_view(repo_root, canonical_root)

            self.assertEqual(first, second)

    def test_falls_back_to_canonical_root_when_view_points_elsewhere(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_root = root / "repo"
            repo_root.mkdir()
            canonical_root = root / "canonical"
            canonical_root.mkdir()
            other_root = root / "other"
            other_root.mkdir()

            view_path = repo_root / ".local-mirrors" / "show-me-captures"
            view_path.parent.mkdir(parents=True)
            view_path.symlink_to(other_root, target_is_directory=True)

            result = capture.capture_project_view(repo_root, canonical_root)

            self.assertEqual(result, canonical_root)


if __name__ == "__main__":
    unittest.main()
