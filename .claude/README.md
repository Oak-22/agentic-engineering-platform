# Claude Code Discovery Adapters

- `skills/` links Claude Code skill discovery to canonical shared skills.
- `rules/` contains path selectors that route to shared instruction bodies.
- `settings.json` observes loaded instructions and injects the prompt-scoped
  instruction manifest contract.

Claude-specific settings, permissions, and hooks belong in this namespace.
