# Codex Runtime-Native Installation Surface

This directory contains only Codex-required project configuration. Canonical
instructions, skills, hook intent, policies, and role charters remain under
`platform/agent-control-plane/`; Codex capability mappings and renderers live
under `platform/agent-control-plane/adapters/runtimes/codex/`.

`hooks.json` injects the prompt-scoped instruction manifest contract at
`UserPromptSubmit`. The shared hook discovers the active `AGENTS.md` repository
baseline and stores a prompt snapshot outside the worktree.

The repository-scoped `config.toml` declares the shared official GitHub MCP
server. It forwards `GITHUB_PERSONAL_ACCESS_TOKEN` by name only, pins the
server image by digest, and uses the same explicit tool allowlist as Claude's
`.mcp.json` adapter.

That GitHub server runs as a Docker `stdio` process. When Docker is
unavailable it fails on startup, independently of any Atlassian condition —
the failure names the `github` server, and an Atlassian OAuth warning is not
evidence about it. Prerequisites, readiness checks, and the
local-MCP → Codex Apps GitHub → `gh` fallback order are documented in
`platform/agent-control-plane/agent-assets/mcp-servers/github/server.md`.

Jira stays on the hosted Codex Apps Atlassian Rovo connector, which needs no
entry in this file. Do **not** add an `atlassian` MCP server here: a direct
`atlassian` server under Codex holds an invalid OAuth refresh token and fails
on every startup while Rovo keeps working (see
`docs/operations/incidents/atlassian-mcp-oauth-refresh-token-invalid-2026-07-24.md`).
If that startup warning appears, the fix is to remove the direct server, not
to re-run `codex mcp login atlassian`. The direct Atlassian endpoint is a
Claude-only optional surface, declared in `.mcp.json`.
