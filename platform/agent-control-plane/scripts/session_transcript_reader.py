#!/usr/bin/env python3
"""Read-only, normalized access to per-runtime session transcript files.

One shared reader per producer (Claude Code, Codex), not one reader per
consumer. Every call re-reads the live producer file directly — no
caching, no persistence, no writes anywhere. See
platform/agent-control-plane/docs/strategy/session-transcript-reader.md
for the design this implements, and
platform/agent-control-plane/docs/strategy/native-provider-state-ports.md
for the pattern this is one instance of.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import json
from pathlib import Path
import re
from typing import Any, Iterator


@dataclass(frozen=True)
class TranscriptTurn:
    runtime: str
    session_id: str
    timestamp: str | None
    role: str
    text: str
    raw_type: str
    tool_calls: tuple[str, ...] = ()
    thinking_tokens: int = 0


_CLAUDE_TEXT_BLOCK_TYPES = frozenset({"text"})
_CODEX_TEXT_BLOCK_TYPES = frozenset({"input_text", "output_text"})
_CODEX_MESSAGE_ROLE_MAP = {"user": "user", "assistant": "assistant", "developer": "other"}
_CODEX_SESSION_ID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_TOOL_SUMMARY_MAX_CHARS = 400


def locate_sessions(
    runtime: str, since: date | None = None, *, root: Path | None = None
) -> list[Path]:
    """Enumerate session transcript files for one runtime.

    root overrides the default path for testability (mirrors
    resolve_capture_root's capture_base / resolve_archive_root's
    archive_base precedent) — not a user-facing override, no env var."""
    if runtime == "claude":
        base = root or (Path.home() / ".claude" / "projects")
        pattern = "*/*.jsonl"
    elif runtime == "codex":
        base = root or (Path.home() / ".codex" / "sessions")
        pattern = "*/*/*/rollout-*.jsonl"
    else:
        raise ValueError(f"unknown runtime: {runtime}")

    if not base.is_dir():
        return []
    paths = sorted(base.glob(pattern))
    if since is not None:
        cutoff_ts = datetime.combine(since, time.min).timestamp()
        paths = [path for path in paths if path.stat().st_mtime >= cutoff_ts]
    return paths


def _flatten_text_blocks(content: Any, accepted_types: frozenset[str]) -> str:
    """Best-effort flatten: a plain string is returned as-is; a list of
    content blocks is joined from only the blocks whose type is in
    accepted_types. Every other block shape (tool_use, tool_result,
    thinking, images, ...) is silently skipped — structured content is not
    unpacked in v1."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block["text"]
            for block in content
            if isinstance(block, dict)
            and block.get("type") in accepted_types
            and isinstance(block.get("text"), str)
        ]
        return "\n".join(parts)
    return ""


def _truncate(text: str) -> str:
    if len(text) <= _TOOL_SUMMARY_MAX_CHARS:
        return text
    return text[:_TOOL_SUMMARY_MAX_CHARS] + "…"


def _json_compact(value: Any) -> str:
    try:
        return json.dumps(value, separators=(",", ":"))
    except TypeError:
        return str(value)


def _claude_tool_calls(content: Any) -> tuple[str, ...]:
    """One-line summaries for tool_use/tool_result blocks a text-only flatten
    drops. Claude's own transcript-mode viewer (Ctrl+O) renders the same
    action as e.g. "Read 1 file" or "Update(path) — added/removed N lines";
    this is a plain-text analog a consumer can render without re-deriving
    the block shapes itself."""
    if not isinstance(content, list):
        return ()
    summaries = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "tool_use":
            name = block.get("name", "?")
            summaries.append(f"{name}({_truncate(_json_compact(block.get('input')))})")
        elif block_type == "tool_result":
            result_content = block.get("content")
            if isinstance(result_content, str):
                result_text = result_content
            else:
                result_text = _flatten_text_blocks(result_content, _CLAUDE_TEXT_BLOCK_TYPES)
            summaries.append(f"→ {_truncate(result_text) if result_text else '(no text result)'}")
    return tuple(summaries)


def _claude_role_and_text(line_type: str, obj: dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    if line_type in ("user", "assistant"):
        content = (obj.get("message") or {}).get("content")
        role = "user" if line_type == "user" else "assistant"
        return (
            role,
            _flatten_text_blocks(content, _CLAUDE_TEXT_BLOCK_TYPES),
            _claude_tool_calls(content),
        )
    return "other", "", ()


def _codex_tool_calls(payload: dict[str, Any]) -> tuple[str, ...]:
    """One-line summaries for the Codex payload.type values that carry tool
    activity instead of message content (see the type-mapping table in
    platform/agent-control-plane/docs/strategy/session-transcript-reader.md)."""
    payload_type = payload.get("type")
    if payload_type == "function_call":
        name = payload.get("name", "?")
        arguments = payload.get("arguments")
        return (f"{name}({_truncate(str(arguments))})",)
    if payload_type in ("function_call_output", "custom_tool_call_output"):
        output = payload.get("output")
        return (f"→ {_truncate(str(output)) if output else '(no output)'}",)
    return ()


def _codex_role_and_text(line_type: str, obj: dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    if line_type != "response_item":
        return "other", "", ()
    payload = obj.get("payload") or {}
    if payload.get("type") != "message":
        return "other", "", _codex_tool_calls(payload)
    role = _CODEX_MESSAGE_ROLE_MAP.get(payload.get("role"), "other")
    return role, _flatten_text_blocks(payload.get("content"), _CODEX_TEXT_BLOCK_TYPES), ()


def _nested_int(obj: Any, *keys: str) -> int:
    """Walk a chain of dict keys and return the value only if it is a real
    int. Bool is rejected explicitly (it is an int subclass), as is every
    missing or wrong-typed level — usage blocks are absent on most lines,
    so a miss is the normal case, not an error."""
    current: Any = obj
    for key in keys:
        if not isinstance(current, dict):
            return 0
        current = current.get(key)
    if isinstance(current, bool) or not isinstance(current, int):
        return 0
    return current


def _claude_thinking_tokens(obj: dict[str, Any]) -> int:
    """Reasoning tokens billed for one assistant message.

    Already per-message in Claude's transcript, so a consumer sums across
    turns to get a session total. This is the only surviving evidence that
    reasoning happened at all: the sibling `thinking` content block is
    emitted with an empty string and an opaque signature."""
    return _nested_int(obj, "message", "usage", "output_tokens_details", "thinking_tokens")


def _codex_thinking_tokens(obj: dict[str, Any]) -> int:
    """Reasoning tokens billed since the previous `token_count` event.

    Codex records two counters side by side; this deliberately reads
    `last_token_usage` (a per-turn delta) rather than `total_token_usage`
    (a cumulative running total), so summing the field across turns works
    the same way it does for Claude. Verified across six real local
    rollout files: sum(last) == max(total) exactly, every time. Reading
    the cumulative field here would overcount by roughly the number of
    `token_count` events — 204 of them in one sampled session."""
    payload = obj.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return 0
    return _nested_int(payload, "info", "last_token_usage", "reasoning_output_tokens")


def _session_id_from_path(path: Path, runtime: str) -> str:
    if runtime == "claude":
        return path.stem
    match = _CODEX_SESSION_ID_PATTERN.search(path.stem)
    return match.group(0) if match else path.stem


def read_turns(path: Path, runtime: str) -> Iterator[TranscriptTurn]:
    """Parse one session file into the normalized schema, line by line.

    Yields one TranscriptTurn per successfully-parsed JSON line, including
    metadata-only lines (role="other") — raw_type is kept so a consumer can
    filter by it without the reader making that decision. Lines that fail
    json.loads are skipped, not raised — a mid-session write in progress
    must not abort the read. Pure function: no writes, no network, no
    mutation of the source file."""
    if runtime not in ("claude", "codex"):
        raise ValueError(f"unknown runtime: {runtime}")
    is_claude = runtime == "claude"
    handler = _claude_role_and_text if is_claude else _codex_role_and_text
    thinking_tokens_of = _claude_thinking_tokens if is_claude else _codex_thinking_tokens
    session_id = _session_id_from_path(path, runtime)

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            line_type = str(obj.get("type") or "")
            role, text, tool_calls = handler(line_type, obj)
            yield TranscriptTurn(
                runtime=runtime,
                session_id=session_id,
                timestamp=obj.get("timestamp"),
                role=role,
                text=text,
                raw_type=line_type,
                tool_calls=tool_calls,
                thinking_tokens=thinking_tokens_of(obj),
            )
