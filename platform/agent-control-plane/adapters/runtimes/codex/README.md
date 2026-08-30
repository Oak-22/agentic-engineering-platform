# Codex Runtime Adapter

This scaffold owns Codex capability declarations, supported-version ranges,
mapping tests, and renderers when concrete runtime translation is required.

Instruction-evidence citation rendering lives centrally in
[`render_citation`](../../../scripts/instruction_manifest_hook.py), not in a
per-runtime adapter file. Codex renders a structured instruction-evidence
location as an absolute-path markdown link with a one-based line anchor,
since Codex has no external-program handler forcing a URL scheme; Claude Code
and Copilot render a bare backticked `path:line` reference instead. Add a
Codex-only renderer here only if Codex's presentation needs diverge from this
shared function in a way a branch in `render_citation` cannot express.

List any checked-in generated installation files, one repository-relative path
per line, in `generated-projections.txt`.

Canonical behavior remains under `../../../agent-assets/`. Repository-native
installation files remain under the root `AGENTS.md`, `.agents/`, and
`.codex/` paths and should contain only discovery links, generated projections,
or explicitly approved Codex configuration.

Do not place credentials, personal `$CODEX_HOME` configuration, or portable
workflow instructions here.
