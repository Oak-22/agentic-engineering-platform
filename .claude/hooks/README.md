# Claude Code Hook Event Catalog

This directory is reserved for repository-owned Claude Code hook commands.
The event catalog below is exhaustive for the public Claude Code hook
reference as of 2026-07-30.

See the [official Claude Code hooks reference](https://code.claude.com/docs/en/hooks)
for matchers, handler types, input and output schemas, and current release
support.

- `SessionStart` — Run when a session begins or resumes.
- `Setup` — Prepare an environment for init-only or maintenance execution.
- `InstructionsLoaded` — Observe when `CLAUDE.md` or a path-specific rule enters context.
- `UserPromptSubmit` — Inspect, enrich, or block a submitted user prompt.
- `UserPromptExpansion` — Inspect or block expansion of a user-entered command.
- `MessageDisplay` — React while assistant message text is displayed.
- `PreToolUse` — Inspect or block a tool call before execution.
- `PermissionRequest` — Supply a decision when a tool call requires permission.
- `PermissionDenied` — React when auto mode denies a tool call and optionally allow a retry.
- `PostToolUse` — Inspect a successful tool result.
- `PostToolUseFailure` — Inspect a failed tool call.
- `PostToolBatch` — Inspect a completed batch of parallel tool calls.
- `Notification` — React when Claude Code sends a notification.
- `SubagentStart` — Run when a subagent starts.
- `SubagentStop` — Validate a subagent result when it finishes.
- `TaskCreated` — Validate or enrich task creation.
- `TaskCompleted` — Validate a task before it is marked complete.
- `Stop` — Validate a completed response and optionally request continuation.
- `StopFailure` — Observe a turn that ends because of an API error.
- `TeammateIdle` — Validate whether an agent-team teammate may go idle.
- `ConfigChange` — React when configuration changes during a session.
- `CwdChanged` — React when the working directory changes.
- `FileChanged` — React when a watched file changes on disk.
- `WorktreeCreate` — Replace the default behavior for worktree creation.
- `WorktreeRemove` — Run when Claude Code removes a managed worktree.
- `PreCompact` — Run before context compaction.
- `PostCompact` — Run after context compaction.
- `Elicitation` — Handle an MCP server's request for user input.
- `ElicitationResult` — Inspect a user's MCP elicitation response before delivery.
- `SessionEnd` — Record or clean up when a session terminates.

Catalog entries describe available extension points and do not activate hooks.
Project hooks become active only when registered in `.claude/settings.json` or
packaged through another supported configuration surface.
