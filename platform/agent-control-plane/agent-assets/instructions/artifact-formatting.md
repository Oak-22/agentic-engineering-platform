# Artifact Formatting Preferences

## Core Rule

Prefer formatting that reveals conceptual structure.

When human interpretation is part of an artifact's purpose, preserve semantic
structure during mechanical formatting.

## Documentation

- Use clear heading hierarchy and scannable section order.
- Preserve existing local style where one exists.
- Avoid decorative churn unrelated to requested changes.

## Separate content by decay rate

Prose in one file should go stale at one speed. Mixing speeds forces a full
re-read to find what rotted, which is the main source of documentation churn.

| Goes stale | Examples | Belongs in |
| --- | --- | --- |
| On another machine | absolute paths, content hashes, local identifiers | a gitignored personal note |
| On the next commit | implementation status, counts, "four copies of X" | the code itself, or a plan |
| When the work lands | migration steps, sequencing, prerequisites | `future/`, deleted on completion |
| Rarely | decisions, invariants, rationale | `docs/`, `docs/strategy/` |

Apply it as four rules:

- **State status once, at the top.** Hedging scattered through prose
  ("planned", "not yet built", "currently") turns one status change into a
  dozen edits, and one will be missed.
- **Describe what is.** Record a decision with its reasoning rather than a
  prediction: "the reader re-reads live, so a mirror would duplicate durable
  state" stays true; "there will never be a mirror here" becomes false the
  moment something adjacent ships.
- **Keep migration language out of reference docs.** A reference describes
  the current state. The transition belongs in a plan that is deleted when
  the work completes — otherwise it lingers as an instruction to a reader
  who missed the transition entirely.
- **Do not mix machine-specific traces with portable explanation.** They
  differ in audience *and* in decay rate; splitting on either is right.

This is why `future/` holds plans, `docs/strategy/` holds durable reasoning,
`evidence/` holds dated observations, and instruction files stay normative
and present-tense. Placing a file is choosing its decay rate.

## Generated Artifacts

For human-reviewed manifests or reports, preserve semantic field order when
ordering communicates workflow meaning.
