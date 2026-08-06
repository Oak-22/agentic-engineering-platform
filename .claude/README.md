# Claude Code Runtime-Native Installation Surface

- `skills/` links Claude Code skill discovery to canonical shared skills.
- `rules/` contains path selectors that route to shared instruction bodies.
- `hooks/` documents Claude Code lifecycle events and holds project hook
  commands when the repository adopts them.
- `settings.json` observes loaded instructions and injects the prompt-scoped
  instruction manifest contract.

Claude-specific settings, permissions, and hook registration belong in this
namespace. Canonical behavior remains under `platform/agent-control-plane/`,
with provider mappings and renderers under
`platform/agent-control-plane/adapters/runtimes/claude/`.

Reference inventories:

- [`skills/README.md`](skills/README.md) lists the repository skills and
  Anthropic's official reference catalog.
- [`hooks/README.md`](hooks/README.md) lists every supported Claude Code hook
  event.
