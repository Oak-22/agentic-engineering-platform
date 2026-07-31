# Codex Hook Event Catalog

This directory contains Codex-specific lifecycle hook commands. The event
catalog below is exhaustive for the public Codex hook reference as of
2026-07-30.

See the [official Codex hooks reference](https://learn.chatgpt.com/docs/hooks)
for matchers, input and output schemas, trust behavior, and current release
support.

- `SessionStart` — Run when a main session starts, resumes, clears, or compacts.
- `SubagentStart` — Add context when a subagent starts.
- `UserPromptSubmit` — Inspect, enrich, or block a submitted user prompt.
- `PreToolUse` — Inspect, rewrite, or deny a supported tool call before execution.
- `PermissionRequest` — Allow or deny a tool call that requires approval.
- `PostToolUse` — Inspect a supported tool result and add feedback after execution.
- `PreCompact` — Run before manual or automatic conversation compaction.
- `PostCompact` — Run after manual or automatic conversation compaction.
- `SubagentStop` — Validate a subagent result and request another pass.
- `Stop` — Validate the main turn result and request continuation.
- `SessionEnd` — Record or clean up when the main session ends.

The repository currently configures one `SessionStart` hook in
`../hooks.json`. It loads current artifact-authoring guidance. Catalog entries
describe available extension points and do not activate hooks by themselves.
