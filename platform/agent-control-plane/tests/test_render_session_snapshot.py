from __future__ import annotations

import datetime as dt
import importlib.util
import json
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
    / "capture-session-trail"
    / "scripts"
    / "render_session_snapshot.py"
)
SPEC = importlib.util.spec_from_file_location("render_session_snapshot", SCRIPT_PATH)
assert SPEC and SPEC.loader
snapshot = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = snapshot
SPEC.loader.exec_module(snapshot)

reader = snapshot._load_reader()


def _unwrapped(text: str) -> str:
    """Collapse whitespace so prose assertions survive re-wrapping.

    The legend is hand-wrapped to a column width; asserting on raw text
    would make every phrase check brittle against a wrap-width change,
    which is a formatting concern rather than a behavioural one."""
    return " ".join(text.split())


def _turn(**overrides):
    fields = {
        "runtime": "claude",
        "session_id": "abc",
        "timestamp": "2026-08-19T10:00:00Z",
        "role": "assistant",
        "text": "hello",
        "raw_type": "assistant",
        "tool_calls": (),
    }
    fields.update(overrides)
    return reader.TranscriptTurn(**fields)


def _write_claude_session(root: Path, session_id: str, lines: list) -> Path:
    path = root / "project-slug" / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(json.dumps(line) + "\n")
    return path


def _assistant_line(text: str | None = None, tool: str | None = None) -> dict:
    content: list[dict] = []
    if text is not None:
        content.append({"type": "text", "text": text})
    if tool is not None:
        content.append({"type": "tool_use", "name": tool, "input": {"path": "x.py"}})
    return {
        "type": "assistant",
        "timestamp": "2026-08-19T10:00:00Z",
        "message": {"content": content},
    }


class PlacementTests(unittest.TestCase):
    def test_default_base_uses_xdg_data_home_directory(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AEP_SESSION_SNAPSHOT_DIR", None)
            os.environ.pop("XDG_DATA_HOME", None)
            root = snapshot.resolve_snapshot_root(project_dir=Path("/repo/ExampleConsumer"))
        self.assertEqual(root.parent, Path.home() / ".local" / "share" / "aep" / "session-snapshots")
        self.assertTrue(root.name.startswith("exampleconsumer--"))

    def test_env_override_wins(self):
        with patch.dict(os.environ, {"AEP_SESSION_SNAPSHOT_DIR": "/tmp/custom"}):
            root = snapshot.resolve_snapshot_root(project_dir=Path("/repo/aep"))
        self.assertEqual(root.parent, Path("/tmp/custom") / "session-snapshots")
        self.assertTrue(root.name.startswith("aep--"))

    def test_missing_project_dir_is_rejected(self):
        with self.assertRaises(ValueError):
            snapshot.resolve_snapshot_root(project_dir=None, snapshot_base=Path("/base"))

    def test_filename_is_stable_per_session_not_per_capture(self):
        name = snapshot.snapshot_filename(runtime="codex", session_id="dead-beef")
        self.assertEqual(name, "codex-dead-beef.md")

    def test_project_view_symlinks_into_local_mirrors(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            canonical = Path(tmp) / "canonical"
            canonical.mkdir(parents=True)
            repo_root.mkdir()
            view = snapshot.snapshot_project_view(repo_root, canonical)
            self.assertEqual(view, repo_root / ".local-mirrors" / "session-snapshots")
            self.assertTrue(view.is_symlink())
            self.assertEqual(view.resolve(), canonical.resolve())

    def test_project_view_falls_back_when_path_points_elsewhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            canonical = Path(tmp) / "canonical"
            other = Path(tmp) / "other"
            for directory in (canonical, other):
                directory.mkdir(parents=True)
            (repo_root / ".local-mirrors").mkdir(parents=True)
            (repo_root / ".local-mirrors" / "session-snapshots").symlink_to(other)
            view = snapshot.snapshot_project_view(repo_root, canonical)
            self.assertEqual(view, canonical)


class WatermarkTests(unittest.TestCase):
    def test_roundtrip(self):
        text = snapshot.format_watermark(turns_consumed=42)
        self.assertEqual(snapshot.parse_watermark(text), 42)

    def test_absent_watermark_reads_as_none(self):
        self.assertIsNone(snapshot.parse_watermark("# snapshot\n\nno marker here"))

    def test_last_watermark_wins(self):
        text = "\n".join(
            [
                snapshot.format_watermark(turns_consumed=3),
                "later content",
                snapshot.format_watermark(turns_consumed=9),
            ]
        )
        self.assertEqual(snapshot.parse_watermark(text), 9)

    def test_strip_removes_every_marker(self):
        text = f"body\n{snapshot.format_watermark(turns_consumed=3)}\n"
        self.assertNotIn("aep-session-snapshot", snapshot.strip_watermark(text))


class RenderTests(unittest.TestCase):
    def test_text_and_tool_calls_render_for_the_same_turn(self):
        rendered = snapshot.render_turn(
            _turn(text="did a thing", tool_calls=("Read({})", "→ ok"))
        )
        self.assertIn("did a thing", rendered)
        self.assertIn("- `Read({})`", rendered)
        self.assertIn("- `→ ok`", rendered)
        self.assertLess(rendered.index("did a thing"), rendered.index("Read({})"))

    def test_tool_only_turn_still_renders(self):
        turn = _turn(text="", tool_calls=("Bash({})",))
        self.assertTrue(snapshot.is_renderable(turn))
        self.assertIn("Bash({})", snapshot.render_turn(turn))

    def test_metadata_and_empty_turns_are_dropped(self):
        self.assertFalse(snapshot.is_renderable(_turn(role="other", text="meta")))
        self.assertFalse(snapshot.is_renderable(_turn(text="   ", tool_calls=())))

    def test_missing_timestamp_is_labelled_not_omitted(self):
        self.assertIn("no timestamp", snapshot.render_turn(_turn(timestamp=None)))

    def test_body_preserves_source_order(self):
        body = snapshot.render_body(
            [_turn(text="first"), _turn(role="other", text="skip"), _turn(text="second")]
        )
        self.assertLess(body.index("first"), body.index("second"))
        self.assertNotIn("skip", body)

    def _header(self, **overrides):
        kwargs = {
            "runtime": "claude",
            "session_id": "abc",
            "source": Path("/x/abc.jsonl"),
            "captured": dt.date(2026, 8, 19),
        }
        kwargs.update(overrides)
        return snapshot.render_header(**kwargs)

    def test_header_carries_the_fidelity_legend(self):
        header = _unwrapped(self._header())
        self.assertIn("How much to trust what you're reading", header)
        self.assertIn("take them literally", header)
        self.assertIn("not here", header)
        self.assertIn("hint, not evidence", header)
        self.assertIn("2026-08-19", header)

    def test_header_reports_the_real_reasoning_token_count(self):
        header = _unwrapped(self._header(thinking_tokens=104145))
        self.assertIn("104,145 tokens of thinking happened", header)
        self.assertIn("None of it is recoverable", header)

    def test_zero_tokens_omits_the_count_rather_than_claiming_none(self):
        """Printing '0 tokens of thinking happened' would assert the agent
        did no reasoning — the opposite of what the legend is for."""
        header = _unwrapped(self._header(thinking_tokens=0))
        self.assertNotIn("0 tokens of thinking", header)
        self.assertIn("No setting brings the raw version back", header)
        self.assertIn("not here", header)

    def test_reasoning_note_thousands_separator(self):
        self.assertIn("1,234,567", _unwrapped(snapshot.render_reasoning_note(1234567)))

    def test_legend_wraps_to_the_prose_column_width(self):
        widest = max(len(line) for line in self._header(thinking_tokens=104145).splitlines())
        self.assertLessEqual(widest, 88)


class SelectTests(unittest.TestCase):
    def test_only_turns_past_the_cutoff_are_returned(self):
        turns = [_turn(text=str(index)) for index in range(5)]
        new, total = snapshot.select_new_turns(turns, consumed=3)
        self.assertEqual(total, 5)
        self.assertEqual([turn.text for turn in new], ["3", "4"])

    def test_first_capture_takes_everything(self):
        turns = [_turn(), _turn()]
        new, total = snapshot.select_new_turns(turns, consumed=0)
        self.assertEqual((len(new), total), (2, 2))

    def test_no_new_turns_is_not_an_error(self):
        turns = [_turn()]
        new, total = snapshot.select_new_turns(turns, consumed=1)
        self.assertEqual((new, total), ([], 1))

    def test_shrunken_source_refuses_rather_than_appending(self):
        with self.assertRaises(ValueError) as caught:
            snapshot.select_new_turns([_turn()], consumed=5)
        self.assertIn("truncated or rewritten", str(caught.exception))


class WriteTests(unittest.TestCase):
    def test_first_write_includes_header_and_watermark(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "nested" / "claude-abc.md"
            snapshot.write_snapshot(
                destination, header="# head\n\n", body="### body\n", turns_consumed=2
            )
            content = destination.read_text(encoding="utf-8")
        self.assertIn("# head", content)
        self.assertEqual(snapshot.parse_watermark(content), 2)

    def test_append_keeps_one_watermark_and_prior_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "claude-abc.md"
            snapshot.write_snapshot(
                destination, header="# head\n\n", body="first\n", turns_consumed=1
            )
            snapshot.write_snapshot(
                destination, header="ignored\n", body="second\n", turns_consumed=4
            )
            content = destination.read_text(encoding="utf-8")
        self.assertIn("first", content)
        self.assertIn("second", content)
        self.assertNotIn("ignored", content)
        self.assertEqual(content.count("aep-session-snapshot"), 1)
        self.assertEqual(snapshot.parse_watermark(content), 4)
        self.assertTrue(content.rstrip().endswith("-->"))

    def test_empty_append_still_advances_the_watermark(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "claude-abc.md"
            snapshot.write_snapshot(
                destination, header="# head\n\n", body="first\n", turns_consumed=1
            )
            snapshot.write_snapshot(
                destination, header="", body="", turns_consumed=3
            )
            content = destination.read_text(encoding="utf-8")
        self.assertEqual(snapshot.parse_watermark(content), 3)
        self.assertEqual(content.count("aep-session-snapshot"), 1)


class ResolveSessionTests(unittest.TestCase):
    def test_explicit_path_is_used_directly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_claude_session(Path(tmp), "abc", [_assistant_line("hi")])
            resolved = snapshot.resolve_session_path(
                reader, runtime="claude", session=str(path), root=Path(tmp)
            )
        self.assertEqual(resolved, path)

    def test_id_fragment_matches_one_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_claude_session(root, "aaa-111", [_assistant_line("a")])
            wanted = _write_claude_session(root, "bbb-222", [_assistant_line("b")])
            resolved = snapshot.resolve_session_path(
                reader, runtime="claude", session="bbb", root=root
            )
        self.assertEqual(resolved, wanted)

    def test_ambiguous_fragment_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_claude_session(root, "shared-1", [_assistant_line("a")])
            _write_claude_session(root, "shared-2", [_assistant_line("b")])
            with self.assertRaises(ValueError):
                snapshot.resolve_session_path(
                    reader, runtime="claude", session="shared", root=root
                )

    def test_unmatched_fragment_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_claude_session(root, "aaa", [_assistant_line("a")])
            with self.assertRaises(FileNotFoundError):
                snapshot.resolve_session_path(
                    reader, runtime="claude", session="zzz", root=root
                )

    def test_no_sessions_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                snapshot.resolve_session_path(
                    reader, runtime="claude", session=None, root=Path(tmp)
                )


class CaptureTests(unittest.TestCase):
    def _capture(self, tmp: Path, **overrides):
        kwargs = {
            "runtime": "claude",
            "session": None,
            "project_dir": Path("/repo/aep"),
            "repo_root": None,
            "snapshot_base": tmp / "store",
            "session_root": tmp / "sessions",
        }
        kwargs.update(overrides)
        return snapshot.capture(**kwargs)

    def test_capture_writes_text_and_tool_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _write_claude_session(
                tmp_path / "sessions",
                "abc",
                [
                    {"type": "system", "timestamp": "t"},
                    _assistant_line("said something"),
                    _assistant_line(tool="Read"),
                ],
            )
            summary = self._capture(tmp_path)
            content = summary["destination"].read_text(encoding="utf-8")
        self.assertTrue(summary["written"])
        self.assertEqual(summary["session_id"], "abc")
        self.assertEqual(summary["total_turns"], 3)
        self.assertEqual(summary["rendered_turns"], 2)
        self.assertIn("said something", content)
        self.assertIn("Read(", content)

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _write_claude_session(
                tmp_path / "sessions", "abc", [_assistant_line("secret")]
            )
            summary = self._capture(tmp_path, dry_run=True)
            # Must be checked before the temp tree is torn down, or a
            # deleted-path exists() would pass for the wrong reason.
            self.assertFalse(summary["destination"].exists())
        self.assertFalse(summary["written"])
        self.assertIn("secret", summary["preview"])

    def test_recapture_appends_only_new_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            path = _write_claude_session(
                tmp_path / "sessions", "abc", [_assistant_line("first turn")]
            )
            first = self._capture(tmp_path)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(_assistant_line("second turn")) + "\n")
            second = self._capture(tmp_path)
            content = second["destination"].read_text(encoding="utf-8")
        self.assertEqual(first["new_turns"], 1)
        self.assertEqual(second["previously_consumed"], 1)
        self.assertEqual(second["new_turns"], 1)
        self.assertEqual(content.count("first turn"), 1)
        self.assertEqual(content.count("second turn"), 1)
        self.assertEqual(content.count("# Session snapshot"), 1)

    def test_recapture_with_no_new_turns_is_a_no_op_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _write_claude_session(
                tmp_path / "sessions", "abc", [_assistant_line("only turn")]
            )
            self._capture(tmp_path)
            second = self._capture(tmp_path)
            content = second["destination"].read_text(encoding="utf-8")
        self.assertEqual(second["new_turns"], 0)
        self.assertEqual(content.count("only turn"), 1)

    def test_repo_root_creates_the_local_mirrors_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path / "repo"
            repo_root.mkdir()
            _write_claude_session(
                tmp_path / "sessions", "abc", [_assistant_line("hi")]
            )
            summary = self._capture(tmp_path, repo_root=repo_root)
            self.assertEqual(
                summary["view"], repo_root / ".local-mirrors" / "session-snapshots"
            )
            self.assertTrue(summary["view"].is_symlink())

    def test_capture_sums_thinking_tokens_across_the_whole_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            line = _assistant_line("thought hard")
            line["message"]["usage"] = {"output_tokens_details": {"thinking_tokens": 500}}
            _write_claude_session(tmp_path / "sessions", "abc", [line, line])
            summary = self._capture(tmp_path)
            content = summary["destination"].read_text(encoding="utf-8")
        self.assertEqual(summary["thinking_tokens"], 1000)
        self.assertIn("1,000 tokens of thinking happened", _unwrapped(content))

    def test_source_transcript_is_never_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            path = _write_claude_session(
                tmp_path / "sessions", "abc", [_assistant_line("hi")]
            )
            before = path.read_bytes()
            self._capture(tmp_path)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
