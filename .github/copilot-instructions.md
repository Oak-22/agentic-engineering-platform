# GitHub Copilot Repository Adapter

The shared repository guidance is in `AGENTS.md`.

@AGENTS.md

Apply matching files under `.github/instructions/` based on their `applyTo`
frontmatter. Those lightweight adapters route to canonical content under
`platform/agent-control-plane/agent-assets/`. Use custom agents, prompts,
skills, and hooks only when the task calls for those runtime-specific assets.
