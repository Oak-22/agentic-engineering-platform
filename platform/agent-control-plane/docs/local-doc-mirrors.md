# Local documentation and artifact mirrors

This repository has four distinct mechanisms that copy content out of a
live agent session onto local disk. They look similar — all four exist
because session-scoped content (fetched docs, published Artifacts,
in-session understanding) would otherwise be lost when the session ends —
but they differ in trigger, scope, and whether the result is tracked in
this repository.

| Mechanism | Trigger | Destination | Tracked in repo? |
| --- | --- | --- | --- |
| [Provider-docs mirror](#provider-docs-mirror) | `SessionStart` hook, automatic | `$TMPDIR/aep-provider-docs/claude-code-manual.md` (OS per-user temp dir; **not** `/tmp/` on macOS) | No |
| [Artifact archive](#artifact-archive) | `PostToolUse` hook on the `Artifact` tool, automatic | `$XDG_DATA_HOME/aep/artifact-archive/<project-slug>/` | No |
| [Artifact promotion](#artifact-promotion) | Manual, deliberate | `docs/diagrams/` | Yes |
| [Show-me viewing cache](#show-me-viewing-cache) | Manual, deliberate — the `show-me` skill | `$XDG_DATA_HOME/aep/engineering-knowledge-base/<project-slug>/` | No |

## Provider-docs mirror

`platform/agent-control-plane/scripts/provider_docs_session_start.py` runs
on every session start. It takes a `--runtime` flag and fetches that
runtime's own aggregated manual — the script does not share one manual
across runtimes, only its fetch/cache/TTL logic is shared:

| Runtime | Source URL | Cached filename |
| --- | --- | --- |
| `claude` | `https://code.claude.com/docs/llms-full.txt` (Anthropic's aggregated Claude Code documentation) | `claude-code-manual.md` |
| `codex` | `https://developers.openai.com/codex/codex-manual.md` (OpenAI's aggregated Codex documentation) | `codex-manual.md` |

Each manual is written under the same per-user OS temp directory
(`aep-provider-docs/`, resolved via Python's standard temp-dir convention —
on macOS this is `$TMPDIR`, a randomized per-user path, **not** literal
`/tmp/`, which is a different, shared system location), refreshed once its
cached copy is older than `AEP_PROVIDER_DOCS_TTL_SECONDS` (default 24
hours; see `DEFAULT_TTL_SECONDS` and the `PROVIDERS` mapping in the
script).

The hook injects the relevant manual's path into session context so the
agent consults it before making claims about that runtime's own structure,
packaging, hooks, skills, or configuration, and before fetching the remote
page again. It is scratch/cache material, not repository content — neither
manual is ever written into the repo, and both are safe to delete; they are
refetched on the next session.

Documented in
[`agent-assets/hooks/README.md`](../agent-assets/hooks/README.md), the
canonical source, since the same script backs both the Claude Code and Codex
adapters via the `--runtime` flag — each adapter invokes it with its own
runtime name and gets its own manual.

A repo-local symlink view at `.local-mirrors/provider-docs` (mirroring
`.local-mirrors/instruction-evidence`'s existing pattern) exposes this
directory from inside the repository. It's a legitimate `.local-mirrors/`
member despite its content being identical across every project on the
machine, not partitioned per repo the way `instruction-evidence` and
`show-me-captures` are: `.local-mirrors/` exists to make every local path
this repo's own tooling reads or writes reviewable in one place, and this
hook runs, and is consulted, every session in this repo — that it happens
to fetch the same bytes regardless of which project triggered it doesn't
make it any less relevant to this repo's function. It may be a broken
symlink until the first session in a fresh checkout runs the hook, the same
as `.local-mirrors/instruction-evidence` before its own first write.

## Artifact archive

`platform/agent-control-plane/scripts/archive_artifact_publish.py`, wired
in as a `PostToolUse` hook matching the `Artifact` tool in
`.claude/settings.json`, copies every file the `Artifact` tool publishes or
republishes to `$XDG_DATA_HOME/aep/artifact-archive/<project-slug>/<filename>`
(default `~/.local/share/aep/...`, override via `AEP_ARTIFACT_ARCHIVE_DIR`).
Republishing the same path overwrites the archive copy — it mirrors
current state, not a version history.

The destination is the same provider-neutral `aep` namespace every other
mechanism in this document uses, not `~/.claude/` — even though this
feature is Claude-specific today (Codex has no equivalent Artifact event
registration, so there's no cross-provider behavior to be agnostic
between), the storage location still shouldn't depend on a directory this
platform doesn't own and doesn't control the evolution of. `.claude/settings.json`
above is a different category entirely: that's Claude Code's own required
native config format for registering the hook, not a data-write location
this platform chose.

This exists because Artifacts otherwise live only in a session-scoped
scratchpad and disappear when the session ends, with nowhere durable for a
user to keep iterating on them by hand. It is deliberately scoped to
local-only persistence: it never writes into the repository. Tests live at
`platform/agent-control-plane/tests/test_archive_artifact_publish.py`.

## Artifact promotion

Some artifacts are worth keeping in the repository itself — for example,
diagrams referenced from documentation. There is no automated mechanism for
this step: a user manually copies a chosen file out of the local artifact
archive (or a `show-me` capture) into a tracked repository path, directly
under `docs/diagrams/` — no runtime-specific subdirectory. Promotion is a
deliberate human judgment that the file's quality merits being kept, at
which point which runtime originally produced it stops mattering: a
promoted diagram sits alongside human-authored ones indistinguishably.
`show-me`-captured filenames already carry the originating runtime (see
below), so that provenance isn't lost even without a subdirectory. This is
a one-off decision per file, distinct from the archive hook above, which
mirrors *every* published artifact regardless of whether it is ever meant
to be kept.

A promoted `.html` artifact is durable by placement. It does not need an
inbound link from prose to justify sitting in `docs/diagrams/`: the file
is a self-contained visual object that opens directly in a browser, and
being tracked there is itself the statement that it was worth keeping.
See `docs/diagrams/README.md` for the resulting index.

## Mermaid captures

Runtimes with no native artifact-creation tool (Codex, Copilot, or any
runtime without one; Claude Code's `Artifact` tool is the one native-tool
exception known today) express the diagram as Mermaid instead of
hand-composed inline SVG. This is an equal-standing path, not a degraded
one: a GitHub Copilot agent with no artifact tooling produced a
satisfactory diagram plus expository writing through it. Any runtime
without strong visualization tooling out of the box should reach for it
directly.

How the capture is written — a self-contained HTML page rendering the
Mermaid client-side, a Markdown file with a fenced ` ```mermaid ` block,
or whatever the session can actually render — is an execution decision
for the invoking agent, not a policy this document fixes in advance. The
general instruction is only that the capture stand on its own well enough
for a human to open and read later.

Promotion follows the same rule as above, with one added judgment: a
Mermaid diagram often means less on its own than next to the prose
explaining it. So promoting one may mean moving the capture file into
`docs/diagrams/`, or it may mean pasting the Mermaid source as a fence
inline into whichever doc already discusses that mechanism — whichever
leaves the reader with something that reads completely. Either way it is
the same deliberate, one-off, manual judgment call, with the same
no-attribution stance once promoted: no comment noting which runtime
generated it, since promotion already implies the quality bar for being
indistinguishable from human-authored content has been met.

## Show-me viewing cache

The `show-me` skill (`platform/agent-control-plane/agent-assets/skills/show-me/`)
writes the rendered explanation of a mechanism under discussion (and, when
produced, the published Artifact HTML) to a machine-local, provider-neutral
cache via `resolve_capture_root.py`, under
`$XDG_DATA_HOME/aep/show-me-captures/<project-slug>/` (default
`~/.local/share/aep/...`, override via `AEP_SHOW_ME_CAPTURE_DIR`). This
directory name is deliberately distinct from the Engineering Knowledge Base
(EKB) below — the two must not be confused with each other on disk.
This is deliberately **not** nested under any single runtime's own
directory (e.g. `~/.claude/`) — `show-me` is symlinked into `.claude/skills/`,
`.agents/skills/`, and `.github/skills/` alike, so its output location must
work the same way regardless of which runtime invoked it. It reuses the
same provider-neutral `aep` namespace `instruction_manifest_hook.py`'s
`storage_root()` already established for the instruction-evidence store.

This is the single, canonical destination `show-me` writes to — one write,
per capture, regardless of which runtime invoked the skill. It is purely a
local viewing convenience, never tracked in any repository. Each capture
gets its own `<date>-<runtime>-<topic-slug>.<ext>` filename, with a `-2`,
`-3` suffix on same-day collisions rather than overwriting — `.html` in
the common case, `.md` where the session writes a Mermaid fence instead
(see "Mermaid captures" above). A `latest.<ext>` symlink
pointer is refreshed on every capture, for opening the most recent one
from a terminal (e.g. `open -a Safari <path>/latest.html`) without needing
the current dated filename — this is a fallback for sidestepping an
editor's own local-file viewer restrictions (VS Code's Simple Browser only
trusts files inside the open workspace, which this provider-neutral cache
generally isn't), not the primary way to browse captures: the dated,
slug-named files themselves are more informative when browsed directly in
an editor's file explorer, since `latest.*` alone doesn't show which
capture you're about to open. A repo-local symlink view at
`.local-mirrors/show-me-captures` (mirroring
`.local-mirrors/instruction-evidence`'s existing pattern) exposes the same
files from inside the repository without a second write. Tests live at
`platform/agent-control-plane/tests/test_resolve_capture_root.py`.

An optional Engineering Knowledge Base (EKB) — a separate personal git
repository, adopted per-project via an ignored `engineering-knowledge-base`
symlink at the project root — can consume this cache's output later as a
downstream overlay. `show-me` itself never writes into EKB directly;
`scripts/append_inbox_entry.py` exists as a building block for that future
downstream consumer (resolving the adoption symlink, appending a notebook
cell), but nothing in this skill's own workflow calls it. EKB is not this
skill's concern.

## Session transcripts (already durable — no mirror needed)

Claude Code itself continuously persists the full session transcript as
JSONL at `~/.claude/projects/<project-slug>/<session-id>.jsonl`, written
incrementally as the session progresses rather than only at session end.
This is what backs `/resume` and cross-session continuation — the record
already exists, durably, at a stable path, independent of whether a
session is ever explicitly closed.

This matters because it rules out an otherwise-plausible fourth mechanism:
a `SessionEnd` hook that copies the transcript elsewhere would be
redundant (the durable copy already exists) and, for workflows that
resume old sessions across days rather than deliberately exiting, would
trigger unpredictably relative to actual work cadence. There is nothing
to build here.

Separately, `Ctrl+O` then `v` in the Claude Code TUI exports a
point-in-time, human-readable snapshot of the current session's
transcript to `/tmp/claude-501/cc-transcript-<timestamp>.txt` and opens it
in an editor. This is a manually triggered read of the same underlying
data, not a distinct persistence mechanism — it has no corresponding hook
event, is not reproducible on demand, and is not tracked by this
repository.

## Why the boundary matters

The provider-docs mirror, the artifact archive, and the show-me viewing
cache all write outside the repository on purpose: they are reproducible,
session-scoped, cache-refreshed, or purely-personal byproducts, and
committing them would mean tracking generated, machine-specific, or
frequently-churning content. Promoting an artifact into the repo is the
opposite case — a deliberate choice to make one specific, finished output
part of the tracked project. Treat the first three as ephemeral and safe to
regenerate or delete; treat promoted artifacts as authored content once
they land in the repo.
