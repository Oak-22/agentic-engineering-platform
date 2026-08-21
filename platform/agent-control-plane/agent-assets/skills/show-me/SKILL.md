---
name: show-me
description: Capture a diagram and written explanation of a mechanism under discussion — whether fully resolved or still being worked through — into a durable, machine-local viewing cache. Use only when the user deliberately asks to save, capture, diagram, or "show me" the mechanism at hand. Never fires automatically after routine technical explanations.
---

# Show Me

Turn a mechanism under discussion into a durable artifact, before the
understanding is lost when the session ends. Works both retrospectively,
after reaching understanding, and in-flight, to externalize current
thinking on a mechanism still being worked through.

Every capture writes once, to one single stable, model-agnostic location —
not nested under any one runtime's own directory, so the same behavior
works whether `show-me` was invoked from Claude Code, Codex, or any other
runtime. `.local-mirrors/show-me-captures` is a repo-local view of that
same location, nothing more.

## Workflow

1. Identify the specific mechanism under discussion — the question that was
   asked and the understanding reached so far. If the preceding discussion
   covered more than one mechanism, confirm scope with the user before
   proceeding.
2. Derive a short kebab-case topic slug (3-6 words) from that mechanism.
3. Produce the explanation + diagram, using whatever native artifact/
   diagram-creation tool the current session actually exposes; use Mermaid
   when it doesn't:
   - If this session natively exposes an artifact-creation tool (e.g. Claude
     Code's `Artifact` tool): load the `artifact-diagramming` and
     `artifact-design` skills, produce a diagram (inline SVG, per
     `artifact-diagramming` guidance) plus a short written explanation, and
     publish it through that native tool.
   - Otherwise (no native artifact-creation tool exposed in this session):
     express the diagram as Mermaid alongside a written explanation. The
     default form is a self-contained standalone HTML page composed by
     hand — the explanation as plain HTML prose, the diagram as a
     `<pre class="mermaid">` block, with a `<script type="module">`
     that imports Mermaid from a CDN (e.g.
     `https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs`)
     and calls `mermaid.initialize({ startOnLoad: true })`. This is not a
     published Claude Artifact, so it carries none of the Artifact
     sandbox's no-external-resources constraint — a CDN script tag is fine
     for a plain local file opened in a real browser with internet access.
     Where the session renders Markdown better than a local HTML file (an
     integrated viewer that previews Mermaid fences directly, for
     instance), a Markdown file with a ` ```mermaid ` fence is an equally
     acceptable form — judge by what the user can actually open and read.
     The mechanical difference from the native-tool path is only that the
     diagram renders client-side from Mermaid source rather than as
     composed inline SVG; treat it as a different form, not a lesser one.
4. Resolve the capture root by calling `resolve_capture_root` from
   `scripts/resolve_capture_root.py` with the current project directory.
5. Resolve the repo-local view by calling `capture_project_view` with the
   repository root and the resolved capture root.
6. Compute the shared filename stem via `capture_filename(slug=..., runtime=...)`
   — `<date>-show-me-<runtime>-<slug>`. The `show-me` marker makes the
   producing workflow explicit in every capture filename, while runtime is
   whichever runtime is invoking the skill (`claude`, `codex`, etc.), so the
   originating model is visible without opening the file.
   - If a native-tool artifact was published (e.g. a Claude Artifact): copy
     the published HTML file into the capture root with that stem via
     `copy_capture`, sourced from the file `show-me` itself just wrote —
     never sourced from another mechanism's own copy of the same file.
   - If no native-tool artifact was published (no native artifact-creation
     tool exposed in this session, so the Mermaid path ran instead): write
     the page composed in step 3 to `<capture-root>/<stem>.<ext>` via
     `write_capture` — `extension="html"` for the default self-contained
     HTML page, or `extension="md"` for the Markdown-with-Mermaid form.
   Write exactly one file per capture. The capture is self-contained
   (diagram + explanation already composed into one file), so do **not**
   also write a second copy in the other format alongside it; a parallel
   copy would just be a redundant duplicate. Either way, collision-safe
   naming, write once, to the canonical capture root — the repo-local
   `.local-mirrors/show-me-captures` view exposes the same files
   automatically; do not write the content a second time.
7. Call `write_latest_pointer` for the file written in step 6, so
   `<capture-root>/latest.<ext>` always resolves to this capture (the
   pointer takes the written file's own extension). This is for opening
   the capture from a terminal (e.g.
   `open -a Safari <path>/latest.html`) without needing the current dated
   filename — useful for sidestepping an editor's own local-file viewer
   restrictions (e.g. VS Code's Simple Browser only trusts files inside the
   open workspace, which this provider-neutral cache generally isn't). It
   is not a substitute for browsing the dated files directly in an editor's
   file explorer, where the per-capture slug and date are more informative
   than a generic `latest` name.
8. Confirm to the user the exact path(s) written, and that this location is
   machine-local and not tracked in any repository.

## Boundaries

- Only invoke on deliberate request ("show me", "capture this", "diagram
  this", "save an explanation of this") — never trigger automatically after
  an ordinary technical answer.
- Never write tracked content into this repository. The capture location is
  always outside version control, and its repo-local view is a symlink into
  an already-gitignored path (`.local-mirrors/`), not a tracked copy.
- Do not write into the Engineering Knowledge Base (EKB), even when a
  project has adopted it. EKB is an optional, separate overlay that
  consumes this skill's output downstream — not a destination this skill
  writes to directly. (`scripts/append_inbox_entry.py` exists as a building
  block for that future downstream consumer, but nothing currently calls
  it from this skill's workflow.)
- Do not attempt spaced-repetition scheduling, quizzing, or telemetry
  ingestion — those belong to the unimplemented rest of
  `platform/developer-learning-retrieval/` and are out of scope for this
  skill.
- If the mechanism in question is ambiguous or spans multiple unrelated
  topics from the conversation, ask the user to confirm scope before
  capturing.
