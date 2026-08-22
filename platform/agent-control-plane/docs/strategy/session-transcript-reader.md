# Session transcript reader and its consumers

One shared read-only reader (`locate_sessions`/`read_turns`) over each
runtime's own session-transcript files, implemented at
`platform/agent-control-plane/scripts/session_transcript_reader.py` and
verified against real local Claude and Codex session files. The first
consumer — [snapshot capture](#consumer-snapshot-capture), which renders a
session for a human reviewer — is built. Extraction into a runtime-neutral
form for another *agent* to pick up, and cross-agent scanning, remain
deliberately deferred, per the reader's own out-of-scope list below.

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

Now decided for the human-reviewer consumer only (see
[Consumer: snapshot capture](#consumer-snapshot-capture)): extract text
plus tool-call summaries, trigger manually like [artifact
promotion](../local-doc-mirrors.md#artifact-promotion), and land the
result outside the repo until a separate promotion decision moves it in.
Still undecided for the cross-*agent* case: what runtime-neutral form a
Codex agent should receive when picking up a Claude Code session, which is
a different extraction problem than making a session readable to a person.

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
| `tool_calls` | `tuple[str, ...]` | v2, additive. One-line summaries of tool activity a text-only flatten drops — see [Tool-call visibility (v2)](#tool-call-visibility-v2) |
| `thinking_tokens` | `int` | v3, additive, defaults to `0`. Reasoning tokens billed for this line — see [Reasoning-token visibility (v3)](#reasoning-token-visibility-v3) |

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
- Any caching or persistence of read results — every call re-reads the
  live producer file, consistent with the no-forked-copies constraint
  above.

### Tool-call visibility (v2)

`TranscriptTurn` carries a `tool_calls: tuple[str, ...]` field alongside
`text` — one-line summaries for `tool_use`/`tool_result` blocks (Claude)
and `function_call`/`function_call_output` payloads (Codex), truncated
past 400 characters. This is additive: `text` keeps meaning exactly what
it meant in v1 (message-text-only, unchanged existing tests), and a line
with no tool activity gets `tool_calls=()`.

Verified against this repo's own live session transcript (see the ledger
note trail leading here): of 208 Claude user/assistant-role lines in one
real session, 162 (78%) had empty `text` — they were pure `thinking`/
`tool_use`/`tool_result` blocks. Text-only output reads as a monologue
with silent gaps exactly where the agent's actions happened; `tool_calls`
is what closes that gap for a reviewer trying to judge what an agent
*did*, not just what it said.

**Still explicitly out of scope**: raw reasoning content. Claude's
`thinking` block is present in the transcript but empty by design — the
Anthropic API redacts it by default in interactive sessions. Measured on
one real session: 63 `thinking` blocks, every one of them with the key
shape `signature`/`thinking`/`type` and an empty string for `thinking`,
against **104,145 billed reasoning tokens** in the same session. Reasoning
happened, at scale, and none of its content survives to the log. No
reader-side code change recovers this; the only lever is
`showThinkingSummaries: true` in settings, which would surface a
paraphrased summary (not raw reasoning) for sessions run after it's
enabled — untested, and it cannot apply retroactively to an
already-written transcript.

### Reasoning-token visibility (v3)

`TranscriptTurn` carries `thinking_tokens: int = 0`, the reasoning tokens
billed for that line. Additive in the same way `tool_calls` was: defaulted,
so no existing consumer or test changes. It does not recover any reasoning
*content* — it is the evidence that reasoning occurred, which is precisely
what a reviewer needs in order to read the absence correctly. A snapshot
that silently omits reasoning invites "the agent didn't think about this";
a snapshot that says six figures of reasoning happened and none of it is
recoverable says the true thing instead.

The per-runtime sources differ in a way that is easy to get wrong:

| Runtime | Source | Semantics |
| --- | --- | --- |
| Claude | `message.usage.output_tokens_details.thinking_tokens` on `assistant` lines | Already per-message |
| Codex | `event_msg` → `payload.type == "token_count"` → `info.last_token_usage.reasoning_output_tokens` | Per-turn delta |

Codex writes two counters side by side, and the reader deliberately reads
`last_token_usage` rather than the sibling `total_token_usage`, which is a
cumulative running total. Verified rather than assumed, per this note's
standing discipline: across six real local rollout files,
`sum(last_token_usage)` equalled `max(total_token_usage)` exactly every
time (232, 6161, 356, 257, 13332, 213). Feeding the cumulative field into
a per-turn slot would overcount by roughly the number of `token_count`
events — 204 of them in one sampled session. With the delta, a consumer
sums the field and both runtimes behave identically; the snapshot
renderer does exactly that and matches a raw independent count to the
token on both producers.

Note this puts a payload the renderer cares about on `event_msg` lines,
which still map to `role="other"`. That is consistent rather than
contradictory: the reader yields every parsed line and lets each consumer
decide what to filter, which is the whole reason `raw_type` is preserved.

## Consumer: snapshot capture

The first consumer built on this reader is the `capture-session-trail`
skill (`agent-assets/skills/capture-session-trail/`), which renders one
session into a Markdown snapshot for a **human teammate** to review. It is
the layered-consumer shape this note argued for: it calls
`locate_sessions`/`read_turns` and adds only rendering, watermarking, and
placement — no second path-discovery or JSONL-parsing implementation
against the same producer.

Design points worth keeping, because each was a real fork in the road:

- **Audience is a person, not an agent.** This is what separates it from
  `handoff-agent-work`, which packages authored intent and authority for
  another agent and deliberately excludes session material. Both can exist
  for the same work; the snapshot should link out to a handoff packet
  rather than restate it.
- **Manual only.** A `Stop`- or `SessionEnd`-triggered capture was
  considered and rejected: continuous capture removes the human review
  point before raw session content becomes readable by someone else. The
  manual invocation *is* the redaction gate, which is why the skill runs
  `--dry-run` before writing.
- **Watermark lives inside the snapshot**, as a trailing
  `<!-- aep-session-snapshot turns-consumed=N -->` comment, not in a
  sidecar. The snapshot is then the entire state — nothing to desynchronize,
  and deleting the file fully resets capture.
- **The cutoff indexes yielded turns, not raw byte or line offsets.** The
  reader skips unparseable lines, so a mid-write partial final line
  contributes no turn now and exactly one turn once complete — an append
  at the end, never a shift of earlier indices. A source that has *fewer*
  turns than were already consumed means truncation or rewrite, and the
  script refuses to append rather than silently dropping or duplicating.
- **Every artifact states its own fidelity, in plain language.** A
  snapshot mixes evidence of very different weight: tool calls and message
  text are exact 1:1 copies, the reasoning-token count is exact but says
  nothing about content, raw reasoning is absent, and a thinking summary —
  where one exists — is the model's own paraphrase. The legend lives in
  the rendered header rather than only in `SKILL.md`, because the artifact
  is the part that reaches a reviewer who never read the skill. It also
  degrades honestly: at a zero token count it drops the number rather than
  printing "0 tokens of thinking happened", which would assert the
  opposite of what the legend exists to say.
- **Placement mirrors the show-me cache**, not the repo. An early
  assumption that writing under `.local-mirrors/session-snapshots/` would
  make a snapshot "repo-visible to a teammate" is wrong: `.local-mirrors/`
  is gitignored and every member is a symlink to a machine-local
  `~/.local/share/aep/...` directory. Capture is local-only; visibility to
  anyone else is the separate manual
  [artifact promotion](../local-doc-mirrors.md#artifact-promotion)
  decision.

## Resolving "this session"

Capturing "this session" requires mapping that phrase to one transcript
filename, and nothing in the reader provides it. `locate_sessions`
enumerates candidates and sorts by modification time; it has no concept of
which session is live. The runtime's own session identifier (`session_...`,
in the git-trailer instructions) is a different namespace from the
transcript UUID and does not resolve a filename.

Session identity is therefore **declared explicitly** in the context
`instruction_manifest_hook.py` injects each prompt, unconditionally,
alongside the existing `Runtime:` declaration. A consumer that needs to
act on "this session" reads it from there.

Before that declaration existed the identity still resolved, but only as a
[side effect](../../../../evidence/side-effects/session-identity-via-instruction-ledger.md)
of the evidence ledger being named `<runtime>/<session-id>.jsonl` and
cited in context — a behavior nobody promised, that was conditionally
absent, and whose silent fallback was `resolve_session_path`'s
most-recently-modified heuristic. That heuristic is still the fallback
when no identity is declared, and it is wrong when resuming an older
session or running two sessions in one project. Consumers that mean a
specific session should name it rather than rely on the default.
