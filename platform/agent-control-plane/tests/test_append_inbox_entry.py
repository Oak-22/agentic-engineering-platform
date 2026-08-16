from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).parents[1]
    / "agent-assets"
    / "skills"
    / "show-me"
    / "scripts"
    / "append_inbox_entry.py"
)
SPEC = importlib.util.spec_from_file_location("append_inbox_entry", SCRIPT_PATH)
assert SPEC and SPEC.loader
inbox = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inbox
SPEC.loader.exec_module(inbox)


def _write_fake_notebook(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "markdown",
                        "id": "learning-index",
                        "metadata": {},
                        "source": ["# Title\n", "\n", "Preamble."],
                    },
                    {
                        "cell_type": "markdown",
                        "id": "existing-entry",
                        "metadata": {},
                        "source": ["## Existing Entry\n", "\n", "Old content."],
                    },
                ],
                "metadata": {"language_info": {"name": "python"}},
                "nbformat": 4,
                "nbformat_minor": 5,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


class ResolveEkbRootTests(unittest.TestCase):
    def test_returns_none_when_symlink_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            self.assertIsNone(inbox.resolve_ekb_root(repo_root=repo_root))

    def test_returns_none_when_symlink_broken(self):
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            link = repo_root / "engineering-knowledge-base"
            link.symlink_to(repo_root / "nonexistent-target")
            self.assertIsNone(inbox.resolve_ekb_root(repo_root=repo_root))

    def test_returns_none_when_target_missing_inbox_notebook(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_root = root / "repo"
            repo_root.mkdir()
            target = root / "ekb"
            target.mkdir()
            (repo_root / "engineering-knowledge-base").symlink_to(
                target, target_is_directory=True
            )
            self.assertIsNone(inbox.resolve_ekb_root(repo_root=repo_root))

    def test_resolves_real_target_when_notebook_present(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_root = root / "repo"
            repo_root.mkdir()
            target = root / "ekb"
            _write_fake_notebook(target / "inbox" / "engineering-learning-dump.ipynb")
            (repo_root / "engineering-knowledge-base").symlink_to(
                target, target_is_directory=True
            )
            result = inbox.resolve_ekb_root(repo_root=repo_root)
            self.assertEqual(result, target.resolve())


class BuildEntryCellTests(unittest.TestCase):
    def test_source_split_matches_splitlines_keepends_shape(self):
        cell = inbox.build_entry_cell(
            slug="my-topic", title="My Topic", body_markdown="line one\nline two"
        )
        self.assertEqual(
            cell["source"],
            ["## My Topic\n", "\n", "line one\n", "line two"],
        )

    def test_id_equals_passed_slug(self):
        cell = inbox.build_entry_cell(slug="my-topic", title="My Topic", body_markdown="x")
        self.assertEqual(cell["id"], "my-topic")

    def test_metadata_is_empty_dict(self):
        cell = inbox.build_entry_cell(slug="my-topic", title="My Topic", body_markdown="x")
        self.assertEqual(cell["metadata"], {})

    def test_cell_type_is_markdown(self):
        cell = inbox.build_entry_cell(slug="my-topic", title="My Topic", body_markdown="x")
        self.assertEqual(cell["cell_type"], "markdown")


class AppendInboxEntryTests(unittest.TestCase):
    def test_inserts_new_cell_at_index_one(self):
        with tempfile.TemporaryDirectory() as directory:
            ekb_root = Path(directory)
            notebook_path = ekb_root / "inbox" / "engineering-learning-dump.ipynb"
            _write_fake_notebook(notebook_path)

            inbox.append_inbox_entry(
                ekb_root=ekb_root,
                slug="new-topic",
                title="New Topic",
                body_markdown="fresh content",
            )

            notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
            self.assertEqual(len(notebook["cells"]), 3)
            self.assertEqual(notebook["cells"][0]["id"], "learning-index")
            self.assertEqual(notebook["cells"][1]["id"], "new-topic")
            self.assertIn("fresh content", "".join(notebook["cells"][1]["source"]))
            self.assertEqual(notebook["cells"][2]["id"], "existing-entry")

    def test_preserves_notebook_top_level_metadata_nbformat(self):
        with tempfile.TemporaryDirectory() as directory:
            ekb_root = Path(directory)
            notebook_path = ekb_root / "inbox" / "engineering-learning-dump.ipynb"
            _write_fake_notebook(notebook_path)
            before = json.loads(notebook_path.read_text(encoding="utf-8"))

            inbox.append_inbox_entry(
                ekb_root=ekb_root, slug="t", title="T", body_markdown="x"
            )

            after = json.loads(notebook_path.read_text(encoding="utf-8"))
            self.assertEqual(after["nbformat"], before["nbformat"])
            self.assertEqual(after["nbformat_minor"], before["nbformat_minor"])
            self.assertEqual(after["metadata"], before["metadata"])

    def test_two_invocations_append_two_distinct_cells_no_dedup(self):
        with tempfile.TemporaryDirectory() as directory:
            ekb_root = Path(directory)
            notebook_path = ekb_root / "inbox" / "engineering-learning-dump.ipynb"
            _write_fake_notebook(notebook_path)

            inbox.append_inbox_entry(
                ekb_root=ekb_root, slug="topic-a", title="Topic A", body_markdown="a"
            )
            inbox.append_inbox_entry(
                ekb_root=ekb_root, slug="topic-b", title="Topic B", body_markdown="b"
            )

            notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
            self.assertEqual(len(notebook["cells"]), 4)
            self.assertEqual(notebook["cells"][1]["id"], "topic-b")
            self.assertEqual(notebook["cells"][2]["id"], "topic-a")
            self.assertEqual(notebook["cells"][3]["id"], "existing-entry")

    def test_result_is_valid_json_reparseable(self):
        with tempfile.TemporaryDirectory() as directory:
            ekb_root = Path(directory)
            notebook_path = ekb_root / "inbox" / "engineering-learning-dump.ipynb"
            _write_fake_notebook(notebook_path)

            inbox.append_inbox_entry(
                ekb_root=ekb_root, slug="t", title="T", body_markdown="x"
            )

            json.loads(notebook_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
