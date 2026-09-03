# Codex Runtime-Native Installation Surface

This directory contains only Codex-required project configuration. Canonical
instructions, skills, hook intent, policies, and role charters remain under
`platform/agent-control-plane/`; Codex capability mappings and renderers live
under `platform/agent-control-plane/adapters/runtimes/codex/`.

`hooks.json` injects the prompt-scoped instruction manifest contract at
`UserPromptSubmit`. The shared hook discovers the active `AGENTS.md` repository
baseline and stores a prompt snapshot outside the worktree.

The repository-scoped `config.toml` declares the shared official GitHub MCP
server as GitHub's hosted remote endpoint (`https://api.githubcopilot.com/mcp/`)
over HTTP (ADR-0004). Codex's current hosted-OAuth client cannot supply the
client secret required by GitHub's token endpoint, so the Codex adapter follows
GitHub's documented interim PAT path. The config stores only
`bearer_token_env_var = "GITHUB_MCP_PAT"`; the token value remains outside the
repository. Claude Code continues to use OAuth against the same endpoint.

A GitHub authorization failure names the `github` server and is independent of
any Atlassian condition — an Atlassian OAuth warning is not evidence about it.
The per-runtime authorization procedure, health check, and the single `gh`
fallback are documented in
`platform/agent-control-plane/agent-assets/mcp-servers/github/server.md`.

The GitHub server is allowlisted to the read and governed-delivery tools. Its
delivery writes use per-tool `approval_mode = "approve"` so Codex does not add
a second prompt-turn gate after AEP has classified the operation. The
repository PreToolUse policy still inspects multi-purpose tool arguments;
`merge_pull_request` is not exposed, and human-acceptance methods remain
denied. A new Codex session is required after this configuration changes.

Jira stays on the hosted Codex Apps Atlassian Rovo connector, which needs no
entry in this file. Do **not** add an `atlassian` MCP server here: a direct
`atlassian` server under Codex holds an invalid OAuth refresh token and fails
on every startup while Rovo keeps working (see
`docs/operations/incidents/atlassian-mcp-oauth-refresh-token-invalid-2026-07-24.md`).
If that startup warning appears, the fix is to remove the direct server, not
to re-run `codex mcp login atlassian`. The direct Atlassian endpoint is a
Claude-only optional surface, declared in `.mcp.json`.
