# Session transcripts as a cross-agent pickup source

The reader below (`locate_sessions`/`read_turns`) is implemented at
`platform/agent-control-plane/scripts/session_transcript_reader.py`,
verified against real local Claude and Codex session files. No consumer
(promotion, extraction, cross-agent scanning) is built yet — that remains
a deliberately deferred next step, per the reader's own out-of-scope list
below.

## Confirmed source paths

| Runtime | Path pattern | Verified |
| --- | --- | --- |
| Claude Code | `~/.claude/projects/<project-slug>/<session-id>.jsonl` | Yes — this session's own transcript |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<session-id>.jsonl` | Yes — confirmed against local `~/.codex/sessions/` contents |

Both are written incrementally by their respective CLI, continuously
during a session, not only at session end. See
[Session transcripts (already durable — no mirror needed)](../local-doc-mirrors.md#session-transcripts-already-durable--no-mirror-needed)
for why no capture hook is needed to make this data durable — it already
is, at these paths, per-runtime.

## Open design question

Neither path is portable across runtimes or committable as-is:

- Formats differ per runtime and are not documented as a stable public
  schema.
- Raw transcripts carry full prompt/response text, which may include
  content not meant for repository tracking.
- "Cross-agent pickup" implies some other agent (Codex reading a Claude
  Code session, or vice versa) can use the content — that requires
  extracting something runtime-neutral, not committing the JSONL
  verbatim.

Not yet decided: what gets extracted, how promotion is triggered (manual,
like [artifact promotion](../local-doc-mirrors.md#artifact-promotion), or
automated), and where the result lives in the repo.

## Design constraint: one reader per producer, not one reader per consumer

Each runtime's session directory is a single, stable, continuously-written
producer — `~/.claude/projects/` for Claude Code, `~/.codex/sessions/` for
Codex. The consumers we're about to design (promotion-into-repo,
cross-agent scanning, eventually maybe others) must not each grow their
own path-discovery and JSONL-parsing logic against these producers
independently. That shape — N consumers each forking their own copy or
their own bespoke read path against the same source — reintroduces the
sync/staleness/drift problem this note already ruled out for a
`SessionEnd` mirror hook (see
[Session transcripts (already durable — no mirror needed)](../local-doc-mirrors.md#session-transcripts-already-durable--no-mirror-needed)):
a forked copy needs invalidation logic and goes stale the moment the
producer writes again; a thin reader against the live producer does not.

This is the general port-and-adapters discipline named in
[Native provider state as a port, not a dependency](native-provider-state-ports.md#where-this-already-exists-unnamed)
— see that note for why it's named that way, its three sibling instances,
and its own trace back to [Agent Context
Routing](../../agent-assets/instructions/agent-context-routing.md) for the
opposite flow direction (canonical repo content projecting *out* to each
runtime). This section states only what's specific to session transcripts
as the producer.

Concretely: build one shared per-runtime reader (knows the path pattern,
knows the JSONL shape) per producer, and layer purpose-built consumers —
extraction/promotion, cross-agent scanning — on top of that shared
reader. Do not let each consumer re-derive how to locate or parse session
files.

## Reader design

Implemented. Grounded in the actual per-line JSON shapes observed across
real local sample files from both producers — one full Claude Code
project transcript (~7,700 lines) and 126 real Codex rollout files
(~127K lines total) — not assumed from documentation.

### Normalized output schema

Both per-runtime readers yield the same shape, so a consumer never
branches on runtime:

| Field | Type | Notes |
| --- | --- | --- |
| `runtime` | `"claude"` \| `"codex"` | Which producer this record came from |
| `session_id` | `str` | Derived from the filename for both runtimes — Claude's filename IS the session ID; Codex's filename encodes it as a trailing UUID (`rollout-<timestamp>-<session-id>.jsonl`). Simpler and order-independent versus parsing Codex's `session_meta` line, and avoids depending on where that line falls in the file. |
| `timestamp` | `str \| None` | Read directly from the line's top level for both runtimes. For Codex this is present on 100% of lines, no exceptions (verified). For Claude, presence is deterministic per `type` — a type either always carries it or never does; there is no "some lines lack it, inherit from a neighbor" case to handle. |
| `role` | `"user"` \| `"assistant"` \| `"other"` | See per-runtime mapping below; `"other"` covers metadata/system lines a consumer will usually skip |
| `text` | `str` | Best-effort flattened message text; structured content (tool calls, attachments) is not unpacked in v1 |
| `raw_type` | `str` | The producer's own line-type tag, kept for consumers that need it (e.g. filtering to only `assistant` reasoning) |

### Per-runtime line-type mapping

Claude Code (`~/.claude/projects/<slug>/<session-id>.jsonl`) — one JSON
object per line, keyed by top-level `type`. Verified against a real
~7,700-line sample; 15 top-level `type` values observed, not the 9
originally assumed:

| Observed `type` | Maps to `role` | Text source |
| --- | --- | --- |
| `user` | `user` | `message.content` — verified string **or** content-block array, both occur |
| `assistant` | `assistant` | `message.content` — verified always a content-block array in this sample, never a bare string |
| `system`, `mode`, `permission-mode`, `ai-title`, `bridge-session`, `file-history-snapshot`, `file-history-delta`, `attachment`, `last-prompt`, `queue-operation`, `agent-color`, `frame-link`, `agent-name` | `other` | Session/UI metadata, not conversation turns — skipped by default |

Content blocks inside `user`/`assistant` arrays: only `type: "text"`
blocks are flattened into `text` (via their own `text` key). Every other
block type is skipped, including ones not originally anticipated —
`tool_use` (has `name`/`input`, no free text), `tool_result` (its own
`content` is itself string-or-list, not recursed into in v1), and
`thinking` (has a `signature` key, not a text field) — consistent with
"structured content not unpacked in v1" below.

Codex (`~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`) — one JSON object
per line with a top-level `timestamp` (present on every line, no
exceptions, more consistently than assumed) and `type`. Verified against
a real ~127K-line sample across 126 files; 7 top-level `type` values
observed, not the 4 originally assumed:

| Observed `type` | Maps to `role` | Text source |
| --- | --- | --- |
| `response_item` where `payload.type == "message"` | `payload.role`, mapped `user`→`user`, `assistant`→`assistant`, **`developer`→`other`** (a third role value beyond user/assistant) | `payload.content` — verified always a list when present, blocks of type `input_text`/`output_text` carry the text |
| `response_item` where `payload.type` is anything else (`reasoning`, `function_call`, `function_call_output`, `custom_tool_call`, `custom_tool_call_output`, `web_search_call`, `agent_message`, `tool_search_call`, `tool_search_output`) | `other` | None of these use `payload.content`/`payload.role` the way `message` does — `function_call` has `arguments`/`name`, `function_call_output` has `output`, `reasoning` has `encrypted_content`. A naive uniform `payload.get("content")` read breaks on these; the reader branches on `payload.type` first. |
| `event_msg` | `other` | Metadata (`turn_id`, model/context info) for most sub-types, but `payload.type in {"user_message", "agent_message"}` sub-types **do** carry a flat `payload.message` string that duplicates `response_item`/`message`'s content in a simpler shape. Deliberately still mapped to `other` — `response_item` is the canonical source, to avoid yielding the same conversational turn twice. |
| `session_meta`, `turn_context`, `compacted`, `world_state`, `inter_agent_communication_metadata` | `other` | Session-level metadata — skipped by default. `session_meta.payload.id` is a valid alternative session-ID source but not used (see `session_id` row above — filename-derivation avoids the ordering dependency). |

### Function signatures

```python
# platform/agent-control-plane/scripts/session_transcript_reader.py

def locate_sessions(runtime: str, since: date | None = None, *, root: Path | None = None) -> list[Path]:
    """Enumerate session transcript files for one runtime.

    runtime: "claude" | "codex". Walks the runtime's known path pattern
    (see Confirmed source paths above) rather than accepting an arbitrary
    root by default, so every consumer discovers sessions the same way.
    `root` exists only to override the default path for testability
    (mirrors resolve_capture_root's `capture_base` / resolve_archive_root's
    `archive_base` precedent elsewhere in this repo) — not a user-facing
    override, no environment variable.
    """

def read_turns(path: Path, runtime: str) -> Iterator[TranscriptTurn]:
    """Parse one session file into the normalized schema, line by line.

    Yields one TranscriptTurn per successfully-parsed JSON line — including
    metadata-only lines, tagged role="other" — so raw_type stays available
    to a consumer that wants to filter rather than the reader deciding what
    to drop. Only lines that fail json.loads are skipped, not raised — a
    mid-session write in progress must not abort the read. Pure function:
    no writes, no network, no mutation of the source file.
    """
```

`locate_sessions` owns path discovery; `read_turns` owns parsing. Neither
writes anywhere — this is a read-only layer. Promotion/extraction
consumers call both and decide what to do with the yielded turns; the
reader has no opinion on committing, filtering by content, or redaction.
Tests at `platform/agent-control-plane/tests/test_session_transcript_reader.py`.

### Explicitly out of scope for this design

- Redaction/filtering of sensitive content — a consumer's job, not the
  reader's.
- Structured content-block unpacking (tool calls, images, thinking
  blocks) — v1 flattens to best-effort text only.
- Any caching or persistence of read results — every call re-reads the
  live producer file, consistent with the no-forked-copies constraint
  above.
