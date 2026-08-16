#!/usr/bin/env python3
"""Read-only, normalized access to per-runtime session transcript files.

One shared reader per producer (Claude Code, Codex), not one reader per
consumer. Every call re-reads the live producer file directly — no
caching, no persistence, no writes anywhere. See
platform/agent-control-plane/docs/strategy/session-transcript-cross-agent-pickup.md
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


_CLAUDE_TEXT_BLOCK_TYPES = frozenset({"text"})
_CODEX_TEXT_BLOCK_TYPES = frozenset({"input_text", "output_text"})
_CODEX_MESSAGE_ROLE_MAP = {"user": "user", "assistant": "assistant", "developer": "other"}
_CODEX_SESSION_ID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


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


def _claude_role_and_text(line_type: str, obj: dict[str, Any]) -> tuple[str, str]:
    if line_type in ("user", "assistant"):
        content = (obj.get("message") or {}).get("content")
        role = "user" if line_type == "user" else "assistant"
        return role, _flatten_text_blocks(content, _CLAUDE_TEXT_BLOCK_TYPES)
    return "other", ""


def _codex_role_and_text(line_type: str, obj: dict[str, Any]) -> tuple[str, str]:
    if line_type != "response_item":
        return "other", ""
    payload = obj.get("payload") or {}
    if payload.get("type") != "message":
        return "other", ""
    role = _CODEX_MESSAGE_ROLE_MAP.get(payload.get("role"), "other")
    return role, _flatten_text_blocks(payload.get("content"), _CODEX_TEXT_BLOCK_TYPES)


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
    handler = _claude_role_and_text if runtime == "claude" else _codex_role_and_text
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
            role, text = handler(line_type, obj)
            yield TranscriptTurn(
                runtime=runtime,
                session_id=session_id,
                timestamp=obj.get("timestamp"),
                role=role,
                text=text,
                raw_type=line_type,
            )
