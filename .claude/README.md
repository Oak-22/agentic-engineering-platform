# Claude Code Discovery Adapters

- `skills/` links Claude Code skill discovery to canonical shared skills.
- `rules/` contains path selectors that route to shared instruction bodies.
- `hooks/` documents Claude Code lifecycle events and holds project hook
  commands when the repository adopts them.
- `settings.json` observes loaded instructions and injects the prompt-scoped
  instruction manifest contract.

Claude-specific settings, permissions, and hooks belong in this namespace.

Reference inventories:

- [`skills/README.md`](skills/README.md) lists the repository skills and
  Anthropic's official reference catalog.
- [`hooks/README.md`](hooks/README.md) lists every supported Claude Code hook
  event.
