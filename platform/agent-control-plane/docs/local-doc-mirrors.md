# Local documentation and artifact mirrors

This repository has three distinct mechanisms that copy content out of a
live agent session onto local disk. They look similar — all three exist
because session-scoped content (fetched docs, published Artifacts) would
otherwise be lost when the session ends — but they differ in trigger,
scope, and whether the result is tracked in this repository.

| Mechanism | Trigger | Destination | Tracked in repo? |
| --- | --- | --- | --- |
| [Provider-docs mirror](#provider-docs-mirror) | `SessionStart` hook, automatic | `/tmp/aep-provider-docs/claude-code-manual.md` (OS temp dir) | No |
| [Artifact archive](#artifact-archive) | `PostToolUse` hook on the `Artifact` tool, automatic | `~/.claude/artifact-archive/<project-slug>/` | No |
| [Artifact promotion](#artifact-promotion) | Manual, deliberate | `docs/diagrams/claude-artifacts/` | Yes |

## Provider-docs mirror

`platform/agent-control-plane/scripts/provider_docs_session_start.py` runs
on every session start. It takes a `--runtime` flag and fetches that
runtime's own aggregated manual — the script does not share one manual
across runtimes, only its fetch/cache/TTL logic is shared:

| Runtime | Source URL | Cached filename |
| --- | --- | --- |
| `claude` | `https://code.claude.com/docs/llms-full.txt` (Anthropic's aggregated Claude Code documentation) | `claude-code-manual.md` |
| `codex` | `https://developers.openai.com/codex/codex-manual.md` (OpenAI's aggregated Codex documentation) | `codex-manual.md` |

Each manual is written under the same OS temp directory
(`aep-provider-docs/`), refreshed once its cached copy is older than
`AEP_PROVIDER_DOCS_TTL_SECONDS` (default 24 hours; see
`DEFAULT_TTL_SECONDS` and the `PROVIDERS` mapping in the script).

The hook injects the relevant manual's path into session context so the
agent consults it before making claims about that runtime's own structure,
packaging, hooks, skills, or configuration, and before fetching the remote
page again. It is scratch/cache material, not repository content — neither
manual is ever written into the repo, and both are safe to delete; they are
refetched on the next session.

Documented in [`.claude/hooks/README.md`](../../../.claude/hooks/README.md)
and the equivalent `.codex/hooks/README.md`, since the same script backs
both the Claude Code and Codex adapters via the `--runtime` flag — each
adapter invokes it with its own runtime name and gets its own manual.

## Artifact archive

`platform/agent-control-plane/scripts/archive_artifact_publish.py`, wired
in as a `PostToolUse` hook matching the `Artifact` tool in
`.claude/settings.json`, copies every file the `Artifact` tool publishes or
republishes to `~/.claude/artifact-archive/<project-slug>/<filename>`
(override via `AEP_ARTIFACT_ARCHIVE_DIR`). Republishing the same path
overwrites the archive copy — it mirrors current state, not a version
history.

This exists because Artifacts otherwise live only in a session-scoped
scratchpad and disappear when the session ends, with nowhere durable for a
user to keep iterating on them by hand. It is deliberately scoped to
local-only persistence: it never writes into the repository. Tests live at
`platform/agent-control-plane/tests/test_archive_artifact_publish.py`.

## Artifact promotion

Some artifacts are worth keeping in the repository itself — for example,
diagrams referenced from documentation. There is no automated mechanism for
this step: a user manually copies a chosen file out of the local artifact
archive into a tracked repository path, such as
`docs/diagrams/claude-artifacts/`. This is a deliberate, one-off decision
per file, distinct from the archive hook above, which mirrors *every*
published artifact regardless of whether it is ever meant to be kept.

## Why the boundary matters

The provider-docs mirror and the artifact archive both write outside the
repository on purpose: they are reproducible, session-scoped or
cache-refreshed byproducts, and committing them would mean tracking
generated, machine-specific, or frequently-churning content. Promoting an
artifact into the repo is the opposite case — a deliberate choice to make
one specific, finished output part of the tracked project. Treat the first
two as ephemeral and safe to regenerate or delete; treat the third as
authored content once it lands in the repo.
