# Local documentation and artifact mirrors

This repository has six distinct mechanisms that keep content on local disk
outside the repository. They look similar — all six exist
because session-scoped content (fetched docs, published Artifacts,
in-session understanding, an agent's own working trail, cross-project
skills) would otherwise be lost, unreadable, or trapped in one repository —
but they differ in trigger, scope, and whether the result is tracked here.

| Mechanism | Trigger | Destination | Tracked in repo? |
| --- | --- | --- | --- |
| [Provider-docs mirror](#provider-docs-mirror) | `SessionStart` hook, automatic | `$TMPDIR/aep-provider-docs/claude-code-manual.md` (OS per-user temp dir; **not** `/tmp/` on macOS) | No |
| [Artifact archive](#artifact-archive) | `PostToolUse` hook on the `Artifact` tool, automatic | `$XDG_DATA_HOME/aep/artifact-archive/<repository-name>--<identity-hash>/` | No |
| [Artifact promotion](#artifact-promotion) | Manual, deliberate | `docs/diagrams/` | Yes |
| [Show-me viewing cache](#show-me-viewing-cache) | Manual, deliberate — the `show-me` skill | `$XDG_DATA_HOME/aep/show-me-captures/<repository-name>--<identity-hash>/` | No |
| [Session snapshots](#session-snapshots) | Manual, deliberate — the `capture-session-trail` skill | `$XDG_DATA_HOME/aep/session-snapshots/<repository-name>--<identity-hash>/` | No |
| [Public-skills store](#public-skills-store) | Manual, deliberate — authored or installed by the developer | `$XDG_DATA_HOME/aep/skills/` | No |
| [Experiment runs](#experiment-runs) | Manual, deliberate — an evaluation harness | `$XDG_DATA_HOME/aep/experiments/<repository-name>--<identity-hash>/` | No |
| [Workbench dispositions](#workbench-dispositions) | Manual, deliberate — reconciling workbench evidence | `$XDG_DATA_HOME/aep/workbench-dispositions/<repository-name>--<identity-hash>/` | No |

## What `.local-mirrors/` is for

One decision governs the whole directory:

> Where does this platform, and the models it governs, put machine-local
> state — and how is it exposed back into the repository?

Stated precisely: **state the platform authors, plus platform-shaped
derivations of state it does not own.** Every member sits in one of two
columns.

| Authored by the platform | Derived from something the platform does not own |
| --- | --- |
| `instruction-evidence` — ledgers the hook writes | `session-snapshots` — rendered from the runtime's raw transcript |
| `show-me-captures` — captures the skill composes | `provider-docs` — fetched from a vendor URL |
| `public-skills` — skills the developer authors | |

`session-snapshots` is the clearest case of the second column: the platform
does not own the transcript, it owns the **rendering** of it.

### The invariant

**`.local-mirrors/` exposes what the platform is responsible for.**

No member is a view onto a runtime's own native store, and none should be.
Pointing a symlink at `~/.claude/projects/` would claim responsibility for a
file the runtime owns and rewrites on its own schedule.

`provider-docs` does not break this rule. It is fetched from a vendor URL and
cached, making it a platform-owned **cache of a remote** rather than a view
onto native local state. It is unusual for a different reason: it caches under
the OS temp directory, outside the `aep` namespace, because it holds
refetchable scratch rather than retained state.

The corollary decides every future case: **mirror a rendering, never the raw
source.** A derivative the platform authored belongs here; the durable file it
was derived from does not.

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
republishes to `$XDG_DATA_HOME/aep/artifact-archive/<repository-name>--<identity-hash>/<filename>`
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
`$XDG_DATA_HOME/aep/show-me-captures/<repository-name>--<identity-hash>/` (default
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

## Session snapshots

The `capture-session-trail` skill
(`platform/agent-control-plane/agent-assets/skills/capture-session-trail/`)
renders one session's message text **and** per-turn tool-call summaries
into a Markdown snapshot at
`$XDG_DATA_HOME/aep/session-snapshots/<repository-name>--<identity-hash>/<runtime>-<session-id>.md`
(override via `AEP_SESSION_SNAPSHOT_DIR`), with a repo-local view at
`.local-mirrors/session-snapshots` following the same symlink pattern as
the show-me cache above.

This is not a fifth copy of the transcript. The raw JSONL is already
durable (see the next section); what does not exist without this skill is
a *readable* form of it — text alone reads as a monologue with silent gaps
exactly where the agent acted, because most assistant lines carry only
`tool_use`/`tool_result` blocks. The snapshot's audience is a human
teammate reviewing what an agent actually did, which is why it renders
both fields per turn and why it is manual: capture is the redaction review
gate, and a `Stop`/`SessionEnd` trigger would remove the human judgment
point before content becomes readable by someone else.

Re-invoking appends only turns recorded since the last capture. The cutoff
is a trailing `<!-- aep-session-snapshot turns-consumed=N -->` comment
inside the snapshot itself rather than a sidecar file, so the snapshot is
the complete state and deleting it fully resets capture. It reads through
`scripts/session_transcript_reader.py` — the one shared reader per
producer — and never modifies the source. Tests live at
`platform/agent-control-plane/tests/test_render_session_snapshot.py`.

Every snapshot opens with a plain-language fidelity legend, because the
content below it is not uniformly trustworthy and a reviewer has no other
way to tell. Tool calls and message text are exact, 1:1 copies of the log.
Raw reasoning is absent — the provider strips it — and the header says so
while reporting the session's real billed reasoning-token count, so the
gap reads as *withheld* rather than as *the agent didn't think*. A
thinking summary, where a user has enabled one, is labelled as the model's
own paraphrase rather than the reasoning itself. That distinction lives in
the artifact, not just in the skill's documentation, because the artifact
is the part that travels to someone who never read the skill.

Making a snapshot visible to anyone else is the separate, manual
[artifact promotion](#artifact-promotion) decision — writing the snapshot
does not share it, since `.local-mirrors/` is gitignored.

## Public-skills store

Skills that travel **across projects** — personal capabilities not owned by
any one repository — live at `$XDG_DATA_HOME/aep/skills/` (override via
`AEP_SKILLS_DIR`), with a repo-local view at `.local-mirrors/public-skills`.

The boundary matters: `agent-assets/skills/` holds skills that encode *this
repository's* governance and delivery conventions and ship to everyone who
clones it. The public-skills store holds capabilities that are useful in any
project and belong to the developer, not the repo. A skill referencing this
repo's paths, Jira project, or branch conventions belongs in `agent-assets/`;
one repairing a video export does not.

This store is deliberately **view-only**. Unlike `agent-assets/skills/`, it is
not symlinked into `.claude/skills/`, `.agents/skills/`, or `.github/skills/`,
so no runtime discovers its contents as project skills. `.local-mirrors/` is
gitignored, so the mirror exposes the files to a human or an agent working
inside the checkout without making them part of this repository or its
runtime-native discovery surfaces.

## Experiment runs

Raw per-run output from platform evaluation experiments lives at
`$XDG_DATA_HOME/aep/experiments/<repository-name>--<identity-hash>/` (override
via `AEP_EXPERIMENT_RUNS_DIR`), with a repo-local view at
`.local-mirrors/experiment-runs`.

A run is bulky, machine-specific, and mostly uninteresting once its conclusion
is drawn: transcripts, per-variant raw answers, session inventories, and the
comparison that summarizes them. The store keeps that volume out of the
repository while leaving it browsable. **Curated results are promoted into
tracked `evidence/experiments/`** — that is where a conclusion belongs, and
where the reader looks for one.

Registering the store fixes where runs land. Before it, output accumulated
directly under `experiments/<experiment-name>/<run-id>/` with no partition
segment, so two repositories' runs would have shared one directory.

Because that layout carries no partition, migrating it cannot use the
repository-identity probes the other stores rely on. Each run records the
repository it ran against in its own `run.json`, and migration attributes runs
from that record alone: a run naming another repository, a run with no readable
manifest, and runs that disagree with each other all stop the migration for a
human decision. Assuming unattributed content belongs to whoever happens to be
migrating is the misattribution this partitioning exists to prevent, and it
cannot be undone once two repositories' runs are merged.

## Workbench dispositions

Decisions to park or supersede workbench-only evidence live at
`$XDG_DATA_HOME/aep/workbench-dispositions/<repository-name>--<identity-hash>/`
(override via `AEP_WORKBENCH_DISPOSITION_DIR`), with a repo-local view at
`.local-mirrors/workbench-dispositions`.

`workbench_evidence.py` classifies what `workbench/local` still holds that
`main` does not. Most of it resolves automatically: work whose paths no longer
differ between the branches has been delivered, however it travelled. What
remains needs a human judgment — deliver it, park it as capture work, or record
that later work superseded it — and this store is where the second and third
answers are kept.

They are kept here rather than in tracked content because a disposition is one
developer's judgment about their own capture stream, not a repository fact.
Committing it would publish machine-specific state and make every other
checkout inherit a decision it never made. The record keys each decision by
patch identity rather than commit SHA, so it survives the workbench being
re-merged or rebased from `main`.

Only `parked` and `superseded` are recordable. `represented` and `in-delivery`
are observed from the repository on each run and cannot be asserted by hand,
and an observation always outranks a stale recording: work that has since been
delivered reports as delivered even if someone once parked it.

## Resolving these paths

`scripts/local_store.py` is the single definition of both halves of this
convention: the provider-neutral `aep` namespace, and the
`.local-mirrors/<name>` view.

```python
canonical, view = ensure_store("public-skills", repo_root=repo, create=True)
```

Its `STORES` registry is the canonical inventory — each entry declares its
directory, environment override, and whether it is scoped per project. Stores
holding per-project output are scoped; stores whose content travels across
projects are not.

Every view follows one create-if-absent shape:

1. If the symlink does not exist, create it pointing at the canonical root.
2. If it exists and resolves to that same root, return it.
3. If it exists and resolves elsewhere — stale from a prior relocation —
   return the canonical root instead. Never silently overwrite an existing
   symlink, and never raise.

Note that these symlinks are a different mechanism from the ones under
`.claude/skills/`, `.agents/skills/`, and `.github/skills/`, which are
relative, tracked, and satisfy each runtime's native discovery contract. The
views here are absolute, gitignored, and machine-specific: they make local
state visible from inside a checkout, and nothing scans them.

This exists because four mechanisms independently re-derived
`$XDG_DATA_HOME/aep` and four wrote their own `.local-mirrors` symlink helper.
That is the shape
[`native-provider-state-ports.md`](strategy/native-provider-state-ports.md)
names and
[`session-transcript-reader.md`](strategy/session-transcript-reader.md)
argues against for session transcripts: one shared definition per concern,
with purpose-built consumers on top. `resolve_capture_root.py`,
`render_session_snapshot.py`, and `archive_artifact_publish.py` are migrated
onto `local_store.py`, alongside the view-only public-skills store.
`instruction_manifest_hook.py` remains: it scopes by sha256 of the git
remote, treats its env var as a full store path rather than a namespace
base, and is live-writing on every prompt, so migrating it needs
`StoreSpec` extended first — a separate, deliberate change.
`provider_docs_session_start.py` is out of scope either way: it caches under
the OS temp directory rather than this namespace, because it holds
refetchable scratch rather than retained state.

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
to build here — *copying* this data is what has no value, which is
distinct from [rendering it readable](#session-snapshots), the one thing
the durable JSONL genuinely does not provide.

Separately, `Ctrl+O` then `v` in the Claude Code TUI exports a
point-in-time, human-readable snapshot of the current session's
transcript to `/tmp/claude-501/cc-transcript-<timestamp>.txt` and opens it
in an editor. This is a manually triggered read of the same underlying
data, not a distinct persistence mechanism — it has no corresponding hook
event, is not reproducible on demand, and is not tracked by this
repository.

## Why the boundary matters

The provider-docs mirror, the artifact archive, the show-me viewing cache,
and session snapshots all write outside the repository on purpose: they are
reproducible, session-scoped, cache-refreshed, or purely-personal
byproducts, and committing them would mean tracking generated,
machine-specific, or frequently-churning content. Promoting an artifact or
a snapshot into the repo is the opposite case — a deliberate choice to make
one specific, finished output part of the tracked project. Treat the first
four as ephemeral and safe to regenerate or delete; treat promoted files as
authored content once they land in the repo.
