from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).parents[1] / "scripts" / "session_transcript_reader.py"
)
SPEC = importlib.util.spec_from_file_location("session_transcript_reader", SCRIPT_PATH)
assert SPEC and SPEC.loader
reader = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reader
SPEC.loader.exec_module(reader)


def _write_jsonl(path: Path, lines: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for line in lines:
            if isinstance(line, str):
                handle.write(line + "\n")
            else:
                handle.write(json.dumps(line) + "\n")


class LocateSessionsTests(unittest.TestCase):
    def test_claude_glob_matches_project_session_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = root / "-Users-x-project" / "session-abc.jsonl"
            _write_jsonl(session, [{"type": "user"}])

            found = reader.locate_sessions("claude", root=root)

            self.assertEqual(found, [session])

    def test_codex_glob_matches_dated_rollout_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = root / "2026" / "08" / "14" / "rollout-20260814-abc123.jsonl"
            _write_jsonl(session, [{"type": "session_meta"}])

            found = reader.locate_sessions("codex", root=root)

            self.assertEqual(found, [session])

    def test_since_excludes_older_files(self):
        import datetime as dt

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "proj" / "old.jsonl"
            new = root / "proj" / "new.jsonl"
            _write_jsonl(old, [{"type": "user"}])
            _write_jsonl(new, [{"type": "user"}])
            old_time = dt.datetime(2020, 1, 1).timestamp()
            os.utime(old, (old_time, old_time))

            found = reader.locate_sessions("claude", since=dt.date(2025, 1, 1), root=root)

            self.assertEqual(found, [new])

    def test_missing_root_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "does-not-exist"
            self.assertEqual(reader.locate_sessions("claude", root=root), [])

    def test_unknown_runtime_raises(self):
        with self.assertRaises(ValueError):
            reader.locate_sessions("chatgpt")


class ReadTurnsClaudeTests(unittest.TestCase):
    def test_user_with_plain_string_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session-1.jsonl"
            _write_jsonl(path, [
                {"type": "user", "message": {"content": "hello there"}, "timestamp": "2026-08-14T00:00:00Z"},
            ])

            turns = list(reader.read_turns(path, "claude"))

            self.assertEqual(len(turns), 1)
            self.assertEqual(turns[0].role, "user")
            self.assertEqual(turns[0].text, "hello there")
            self.assertEqual(turns[0].session_id, "session-1")
            self.assertEqual(turns[0].raw_type, "user")

    def test_user_with_text_block_array(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session-2.jsonl"
            _write_jsonl(path, [
                {"type": "user", "message": {"content": [{"type": "text", "text": "block content"}]}},
            ])

            turns = list(reader.read_turns(path, "claude"))

            self.assertEqual(turns[0].role, "user")
            self.assertEqual(turns[0].text, "block content")

    def test_assistant_skips_non_text_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session-3.jsonl"
            _write_jsonl(path, [
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "thinking", "signature": "abc"},
                            {"type": "tool_use", "id": "1", "name": "Bash", "input": {}},
                            {"type": "text", "text": "final answer"},
                        ]
                    },
                },
            ])

            turns = list(reader.read_turns(path, "claude"))

            self.assertEqual(turns[0].role, "assistant")
            self.assertEqual(turns[0].text, "final answer")

    def test_skip_mapped_type_yields_other_role_empty_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session-4.jsonl"
            _write_jsonl(path, [{"type": "queue-operation", "sessionId": "x"}])

            turns = list(reader.read_turns(path, "claude"))

            self.assertEqual(turns[0].role, "other")
            self.assertEqual(turns[0].text, "")
            self.assertEqual(turns[0].raw_type, "queue-operation")

    def test_malformed_json_line_is_skipped_not_raised(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session-5.jsonl"
            _write_jsonl(path, [
                json.dumps({"type": "user", "message": {"content": "first"}}),
                "{not valid json",
                json.dumps({"type": "user", "message": {"content": "second"}}),
            ])

            turns = list(reader.read_turns(path, "claude"))

            self.assertEqual(len(turns), 2)
            self.assertEqual(turns[0].text, "first")
            self.assertEqual(turns[1].text, "second")


class ReadTurnsCodexTests(unittest.TestCase):
    def test_response_item_message_user_role(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout-20260814-000000-abc12345-1234-5678-9abc-def012345678.jsonl"
            _write_jsonl(path, [
                {
                    "timestamp": "2026-08-14T00:00:00Z",
                    "type": "response_item",
                    "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "hi"}]},
                },
            ])

            turns = list(reader.read_turns(path, "codex"))

            self.assertEqual(turns[0].role, "user")
            self.assertEqual(turns[0].text, "hi")

    def test_response_item_developer_role_maps_to_other(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout-x-abc12345-1234-5678-9abc-def012345678.jsonl"
            _write_jsonl(path, [
                {
                    "type": "response_item",
                    "payload": {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "sys"}]},
                },
            ])

            turns = list(reader.read_turns(path, "codex"))

            self.assertEqual(turns[0].role, "other")

    def test_response_item_function_call_has_no_content_field(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout-x-abc12345-1234-5678-9abc-def012345678.jsonl"
            _write_jsonl(path, [
                {
                    "type": "response_item",
                    "payload": {"type": "function_call", "name": "shell", "arguments": "{}"},
                },
            ])

            turns = list(reader.read_turns(path, "codex"))

            self.assertEqual(turns[0].role, "other")
            self.assertEqual(turns[0].text, "")

    def test_event_msg_user_message_does_not_duplicate_response_item(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout-x-abc12345-1234-5678-9abc-def012345678.jsonl"
            _write_jsonl(path, [
                {"type": "event_msg", "payload": {"type": "user_message", "message": "hi"}},
            ])

            turns = list(reader.read_turns(path, "codex"))

            self.assertEqual(turns[0].role, "other")

    def test_turn_context_session_meta_compacted_map_to_other(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout-x-abc12345-1234-5678-9abc-def012345678.jsonl"
            _write_jsonl(path, [
                {"type": "turn_context"},
                {"type": "session_meta", "payload": {"id": "abc12345-1234-5678-9abc-def012345678"}},
                {"type": "compacted"},
            ])

            turns = list(reader.read_turns(path, "codex"))

            self.assertEqual([turn.role for turn in turns], ["other", "other", "other"])


class SessionIdFromPathTests(unittest.TestCase):
    def test_claude_uses_filename_stem(self):
        path = Path("/x/y/019fb6cf-dac2-7661-8a44-8f99eb248d05.jsonl")
        self.assertEqual(
            reader._session_id_from_path(path, "claude"),
            "019fb6cf-dac2-7661-8a44-8f99eb248d05",
        )

    def test_codex_extracts_trailing_uuid_even_with_hyphenated_timestamp(self):
        path = Path("/x/y/rollout-2026-08-14T00-00-00-abc12345-1234-5678-9abc-def012345678.jsonl")
        self.assertEqual(
            reader._session_id_from_path(path, "codex"),
            "abc12345-1234-5678-9abc-def012345678",
        )


if __name__ == "__main__":
    unittest.main()
