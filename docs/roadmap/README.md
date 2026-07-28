# Roadmap

Planned cross-platform capabilities and sequencing decisions belong here.

## Deferred

- Move canonical agent instructions and skills from runtime-specific discovery
  roots into a vendor-neutral, platform-owned store only after the full
  cross-runtime migration surface is inventoried and prioritized. Until then,
  keep `.github/skills/` canonical and expose each skill to Codex through a
  matching relative symlink under `.agents/skills/`.
