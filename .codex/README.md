# Codex Runtime-Native Installation Surface

This directory contains only Codex-required project configuration. Canonical
instructions, skills, hook intent, policies, and role charters remain under
`platform/agent-control-plane/`; Codex capability mappings and renderers live
under `platform/agent-control-plane/adapters/runtimes/codex/`.

`hooks.json` injects the prompt-scoped instruction manifest contract at
`UserPromptSubmit`. The shared hook discovers the active `AGENTS.md` repository
baseline and stores a prompt snapshot outside the worktree.
