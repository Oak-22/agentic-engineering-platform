# Claude Code Runtime Adapter

This scaffold owns Claude Code capability declarations, supported-version
ranges, mapping tests, and renderers when concrete runtime translation is
required.

Instruction-evidence citation rendering lives centrally in
[`render_citation`](../../../scripts/instruction_manifest_hook.py), not in a
per-runtime adapter file. Claude Code renders a structured instruction-evidence
location as a bare backticked `path:line` reference, matching Copilot; Codex
renders an absolute-path markdown link instead, since it has no
external-program handler forcing a URL scheme. Add a Claude-only renderer
here only if Claude Code's presentation needs diverge from this shared
function in a way a branch in `render_citation` cannot express.

List any checked-in generated installation files, one repository-relative path
per line, in `generated-projections.txt`.

Canonical behavior remains under `../../../agent-assets/`. Repository-native
installation files remain under the root `CLAUDE.md` and `.claude/` paths and
should contain only discovery links, canonical imports, generated projections,
or explicitly approved Claude Code configuration.

Do not place credentials, personal configuration, or portable workflow
instructions here.
