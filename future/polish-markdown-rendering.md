# Polish markdown rendering

Status: to-do, not scheduled. Delete this file when the skill has landed.

## Context

A well-written `.md` file is frequently left at whatever formatting level it
was drafted at — flat headings, prose paragraphs, no tables, no diagrams —
even when GitHub's renderer supports far more. The gap is not writing quality;
it is that GitHub Flavored Markdown (GFM) has a specific, learnable ceiling of
structural features, and nobody re-passes a finished document against that
ceiling once the content is right.

End state: an invocable skill that takes a path to an already-written `.md`
file and transforms its *structure* — not its meaning or voice — up to the
maximum readability GitHub's renderer supports, leaving prose content
untouched except where a structural shift subsumes it (e.g. a paragraph of
comparisons becomes a table).

## What the transform does

Applies only the structural shifts below, only where the source content
already supports them (never invents facts, comparisons, or diagrams that
aren't implied by the existing prose):

- **Heading discipline** — ensure a clean `#`–`######` hierarchy so GitHub's
  auto-generated file TOC and anchor links work.
- **GitHub Alerts** — convert emphasized asides/warnings already in the prose
  (e.g. "Note:", "Warning:") into `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`,
  `> [!WARNING]`, `> [!CAUTION]` blocks.
- **Tables** — convert enumerated comparisons, option lists, or key/value
  prose into piped tables with alignment.
- **Task lists** — convert plain step lists that describe completable work
  into `- [ ]` / `- [x]`.
- **Code fences** — add language hints to unlabeled code blocks; convert
  before/after snippets into ` ```diff ` blocks where that's what they show.
- **Mermaid diagrams** — convert prose descriptions of flow, sequence, or
  dependency structure into ` ```mermaid ` blocks, only when the prose
  describes a real structure (not for decoration).
- **Math** — convert inline/display equations written in prose into KaTeX
  (`$...$`, `$$...$$`).
- **Collapsible detail** — wrap long optional/reference content (appendices,
  verbose logs, full option lists) in `<details><summary>`.
- **Reference-style links** — convert repeated inline links into
  reference-style link definitions to keep prose scannable.

## Constraints

- Content-preserving: no new claims, no invented diagrams, no tone changes.
  A structural shift is only valid if the source content already implies the
  target structure.
- Stays inside GitHub's sanitized HTML subset (`<details>`, `<summary>`,
  `<sub>`, `<sup>`, `<kbd>`, `<br>`, `<img>`, `<picture>`) — no custom
  CSS, `<script>`, `<style>`, or iframes.
- Idempotent: running the transform twice on already-polished output must be
  a no-op.
- Must not touch files under `evidence/` (dated observations, not documents
  meant for restructuring) or ADRs (records of a decision at a point in
  time).

## Promotion

To make this a skill, add a package under
`platform/agent-control-plane/agent-assets/skills/polish-markdown-rendering/`
with a `SKILL.md`, and its entry in
`agent-assets/skills/skills_registry.json` in the same change.
`platform/agent-control-plane/scripts/validate_asset_registries.py` requires
every directory under `skills/` to have a registry entry and every runtime
binding to be a resolving symlink, so a package added without its
registration fails validation immediately.
