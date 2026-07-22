# Copilot Instructions

This is the checked-in discovery adapter for repository-aware agents.

Before making code, documentation, data-layout, architecture, or Git
changes, load relevant checked-in instruction files and report what was
loaded.

## Active Context Surface

```text
.github/copilot-instructions.md
  -> .github/instructions/*.instructions.md
  -> .github/agents/*.agent.md when a specialist role is relevant
  -> .github/prompts/*.prompt.md when an explicit reusable prompt fits
  -> .github/skills/*/SKILL.md when an explicit skill workflow fits
```

## Required Baseline

For repository work, load task-relevant files under
`.github/instructions/`.

Always include `.github/instructions/agent-context-routing.instructions.md`
so migration and layering rules are respected.

## Legacy Compatibility

Legacy paths such as `AGENTS.md` and `.github/agent_instructions/` are
deprecated for this template. Keep migration references only when a
specific adopting repository still requires them.
