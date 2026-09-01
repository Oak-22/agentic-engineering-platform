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
`.mcp.json` adapter. Jira remains on the configured hosted Rovo connector; the
direct Atlassian endpoint is a separate optional surface.
