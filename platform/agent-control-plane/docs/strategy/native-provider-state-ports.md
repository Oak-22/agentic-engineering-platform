# Native provider state as a port, not a dependency

Working note. Names a pattern already present, unnamed, in four places in
this repo, and scopes the gap it leaves open.

This is the canonical explanation of the pattern itself. Sibling docs that
apply it to one specific mechanism (e.g.
[session-transcript-cross-agent-pickup.md](session-transcript-cross-agent-pickup.md))
should link back here for the general "why," and state only what's
specific to their own mechanism — not re-derive the general principle.

## The pattern

Every LLM provider runtime (Claude Code, Codex, and any future OSS runtime)
owns native, unversioned local state this platform doesn't control and
must never mutate or depend on the internals of: `~/.claude/`, `~/.codex/`,
`/tmp/claude-501/`, `$TMPDIR` (`/var/folders/` on macOS), and whatever an
OSS runtime's equivalent turns out to be. These evolve on each provider's
own schedule, in formats that aren't documented as stable public contracts.

That is exactly the situation ports-and-adapters (hexagonal) architecture
names: an external system the core must integrate with, without coupling
to its internals, and without ever writing into it. Mapped directly:

- **The external systems** are the native provider paths above — plus one
  different kind: a provider's own *remote*, network-hosted documentation
  (e.g. `https://code.claude.com/docs/llms-full.txt`). The provider-docs
  mirror port's external system is an HTTP endpoint, not a local path
  another process writes to; there is no native local original to read at
  all, confirmed by an empty filesystem search for it. Same "don't couple
  to something you don't control" discipline, different kind of external
  dependency — worth keeping distinct from the local-filesystem case below.
- **The port** is one canonical interface per capability — read-only where
  the capability is "learn something from provider state," write-only into
  a location this platform owns where the capability is "persist something
  derived." A port is implemented once, not once per consumer.
- **The adapters** are the per-runtime specifics living behind that port —
  a path pattern, a payload shape, a registration format. Adapters absorb
  provider-specific change; the port's callers never see it.
- **The core** is this platform's own downstream logic — everything that
  consumes a port's normalized output and is intentionally ignorant of
  which provider produced it.

This is the same discipline `agent-context-routing.md` already names for
the opposite direction of flow — canonical repo content (instructions,
skills) projecting *out* to each runtime through one canonical source and
a per-runtime adapter, never duplicated per consumer. This note is that
pattern's mirror image: native runtime state projecting *in*, through one
port and a per-runtime adapter, never re-derived per consumer.

## Where this already exists, unnamed

| Mechanism | Port | Adapters | Normalized output |
| --- | --- | --- | --- |
| Provider-docs mirror | `ensure_manual(runtime, ...)` in `provider_docs_session_start.py` | `PROVIDERS` dict (URL + filename per runtime) | One cached manual file per runtime, same fetch/cache/TTL logic |
| Instruction evidence | `handle(runtime, payload)` in `instruction_manifest_hook.py` | Each runtime's native hook-registration format (`.claude/settings.json` vs. `.codex/hooks.json`) and event-payload shape | One evidence-record schema, written to one ledger, regardless of which runtime triggered it |
| show-me capture | The `Artifact`-tool-available branch vs. Markdown+Mermaid fallback in `SKILL.md`'s workflow | Runtime capability check (Claude has the `Artifact` tool; Codex/Copilot don't) | One write, to one canonical viewing-cache location, regardless of which runtime invoked it |
| Session transcripts | `locate_sessions(runtime)` / `read_turns(path, runtime)` in `session_transcript_reader.py` (design: [`session-transcript-cross-agent-pickup.md`](session-transcript-cross-agent-pickup.md)) | Claude's `type`-keyed JSONL shape vs. Codex's `response_item`/`event_msg` shape, both verified against real local data | One `TranscriptTurn` record shape |

Every one of these already independently converged on "one shared
script/interface, parameterized or branching per runtime, normalized
output" — without anyone naming it as a recurring principle until now.

## The other half: where derived output lives

The port pattern isn't only about reading — it constrains where this
platform's *own* derived state lives too. A port that reads native
provider state cleanly, then persists its output back into that same
provider's directory, has only re-created the coupling one level down.
This is why every mechanism above stores its output under the
provider-neutral `$XDG_DATA_HOME/aep/` namespace (or, for the show-me/EKB
case, a separately-owned personal repo) rather than nesting under
`~/.claude/` or `~/.codex/` — confirmed and corrected for
`archive_artifact_publish.py`, `resolve_capture_root.py`, and
`provider_docs_session_start.py`'s repo-local view this session. The
symmetry: never read a provider's internals directly from N places, and
never write this platform's own state into a provider's directory either.

## What's actually missing

Every instance above is a **fetch-or-observe-once** port: called at a
fixed lifecycle moment (session start, a hook event, a deliberate skill
invocation), it reads or derives once and returns. None of them are a
**change-detecting** port — something that notices a native provider path
has been modified since it was last observed, independent of whether this
platform's own tooling happened to trigger that modification.

That's the gap `preserved-default-paths-list-per-provider.md` and
`session-transcript-cross-agent-pickup.md` are both pointing at, from two
different angles: the transcript note wants to notice new turns appended
to a live session file; the preserved-paths list wants to notice *any*
provider-native path changing, not just transcripts, and turn that change
into a "repo-relevant" derived artifact, stored in one stable repo-owned
location, formatted for more than one downstream consumer to read.

Scoping that detect-and-transform mechanism — what "detect" means
operationally (poll? hook-triggered diff? something else), which specific
paths within the broad `~/.claude/`/`~/.codex/` trees actually matter, and
what "repo-relevant transform" means for each — is the next design pass,
not this note. This note exists so that pass starts from a named pattern
and four confirmed instances of it, instead of re-deriving the shape from
scratch.
