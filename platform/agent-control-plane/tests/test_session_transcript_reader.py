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

    def test_assistant_tool_use_yields_a_one_line_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session-tool-use.jsonl"
            _write_jsonl(path, [
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "id": "1", "name": "Bash", "input": {"command": "ls"}},
                        ]
                    },
                },
            ])

            turns = list(reader.read_turns(path, "claude"))

            self.assertEqual(turns[0].tool_calls, ('Bash({"command":"ls"})',))
            self.assertEqual(turns[0].text, "")

    def test_user_tool_result_yields_a_one_line_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session-tool-result.jsonl"
            _write_jsonl(path, [
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {"type": "tool_result", "tool_use_id": "1", "content": "3 files listed"},
                        ]
                    },
                },
            ])

            turns = list(reader.read_turns(path, "claude"))

            self.assertEqual(turns[0].tool_calls, ("→ 3 files listed",))

    def test_tool_use_input_is_truncated_past_the_summary_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session-tool-long.jsonl"
            long_command = "x" * 1000
            _write_jsonl(path, [
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "id": "1", "name": "Bash", "input": {"command": long_command}},
                        ]
                    },
                },
            ])

            turns = list(reader.read_turns(path, "claude"))

            self.assertLess(len(turns[0].tool_calls[0]), 1000)
            self.assertIn("…", turns[0].tool_calls[0])

    def test_text_only_line_has_no_tool_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session-text-only.jsonl"
            _write_jsonl(path, [
                {"type": "user", "message": {"content": "hello"}},
            ])

            turns = list(reader.read_turns(path, "claude"))

            self.assertEqual(turns[0].tool_calls, ())

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

    def test_response_item_function_call_yields_a_one_line_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout-x-abc12345-1234-5678-9abc-def012345678.jsonl"
            _write_jsonl(path, [
                {
                    "type": "response_item",
                    "payload": {"type": "function_call", "name": "shell", "arguments": '{"command":"ls"}'},
                },
            ])

            turns = list(reader.read_turns(path, "codex"))

            self.assertEqual(turns[0].tool_calls, ('shell({"command":"ls"})',))

    def test_response_item_function_call_output_yields_a_one_line_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout-x-abc12345-1234-5678-9abc-def012345678.jsonl"
            _write_jsonl(path, [
                {
                    "type": "response_item",
                    "payload": {"type": "function_call_output", "output": "3 files listed"},
                },
            ])

            turns = list(reader.read_turns(path, "codex"))

            self.assertEqual(turns[0].tool_calls, ("→ 3 files listed",))

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


def _claude_usage_line(thinking_tokens):
    """An assistant line carrying only a usage block, shaped as the real
    producer writes it."""
    return {
        "type": "assistant",
        "message": {
            "content": [{"type": "text", "text": "reasoned about it"}],
            "usage": {"output_tokens_details": {"thinking_tokens": thinking_tokens}},
        },
    }


def _codex_token_count_line(*, last, total):
    return {
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "last_token_usage": {"reasoning_output_tokens": last},
                "total_token_usage": {"reasoning_output_tokens": total},
            },
        },
    }


class ThinkingTokensTests(unittest.TestCase):
    def _turns(self, lines, runtime):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "s.jsonl"
            _write_jsonl(path, lines)
            return list(reader.read_turns(path, runtime))

    def test_claude_reads_thinking_tokens_from_usage(self):
        turns = self._turns([_claude_usage_line(355)], "claude")
        self.assertEqual(turns[0].thinking_tokens, 355)

    def test_claude_sums_across_turns(self):
        turns = self._turns(
            [_claude_usage_line(100), _claude_usage_line(250)], "claude"
        )
        self.assertEqual(sum(turn.thinking_tokens for turn in turns), 350)

    def test_defaults_to_zero_without_a_usage_block(self):
        turns = self._turns([{"type": "user", "message": {"content": "hi"}}], "claude")
        self.assertEqual(turns[0].thinking_tokens, 0)

    def test_codex_reads_the_per_turn_delta(self):
        turns = self._turns(
            [_codex_token_count_line(last=232, total=232)], "codex"
        )
        self.assertEqual(turns[0].thinking_tokens, 232)

    def test_codex_ignores_the_cumulative_total(self):
        """Regression: summing total_token_usage across events would
        overcount badly — verified on real rollouts that sum(last) equals
        max(total), so the cumulative field must never feed a per-turn
        field."""
        lines = [
            _codex_token_count_line(last=100, total=100),
            _codex_token_count_line(last=50, total=150),
            _codex_token_count_line(last=25, total=175),
        ]
        turns = self._turns(lines, "codex")
        self.assertEqual([turn.thinking_tokens for turn in turns], [100, 50, 25])
        self.assertEqual(sum(turn.thinking_tokens for turn in turns), 175)

    def test_codex_ignores_non_token_count_events(self):
        turns = self._turns(
            [{"type": "event_msg", "payload": {"type": "agent_message", "message": "x"}}],
            "codex",
        )
        self.assertEqual(turns[0].thinking_tokens, 0)

    def test_malformed_usage_shapes_do_not_raise(self):
        lines = [
            {"type": "assistant", "message": {"usage": "not-a-dict"}},
            {"type": "assistant", "message": {"usage": {"output_tokens_details": None}}},
            {
                "type": "assistant",
                "message": {"usage": {"output_tokens_details": {"thinking_tokens": True}}},
            },
        ]
        turns = self._turns(lines, "claude")
        self.assertEqual([turn.thinking_tokens for turn in turns], [0, 0, 0])


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
