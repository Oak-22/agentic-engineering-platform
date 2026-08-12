# Glossary

Use portable placeholders in shared contracts, schemas, tests, and generic
workflow documentation. Use concrete identifiers only when documenting this
platform's deployed systems, adapters, telemetry, or historical evidence.

## Platform terms

### AEP

Agentic Engineering Platform: the platform and this canonical repository.

### AEPI

Agentic Engineering Platform Implementation: this platform deployment's Jira
Software project. `AEPI` is a concrete project key, not a portable schema
default.

### AEPD

Agentic Engineering Platform Discovery: this platform deployment's Jira
Product Discovery project for opportunities, hypotheses, and promotion into
implementation work.

### Jira issue key

A Jira-native identifier in `PROJECT-NUMBER` form. Portable artifacts represent
it as `<JIRA-ISSUE-KEY>` or use a neutral example such as `PROJ-123`.

## Agent-context terms

### Runtime

The agent host product executing an agent in this repository — for example
Claude Code, Codex, or GitHub Copilot. This is distinct from other common
senses of "runtime": it does not mean an inference/model-serving runtime, nor
a language execution engine (Bun, Node, the JVM, etc.). Compound terms follow
the same sense: a `runtime adapter` maps canonical intent into one runtime's
native discovery and configuration; `runtime-native` describes a surface only
that runtime's installation contract requires; the `--runtime` flag on shared
scripts (for example `provider_docs_session_start.py`) selects which
runtime's own resources to act on. See
[Agent Context Routing](../platform/agent-control-plane/agent-assets/instructions/agent-context-routing.md)
for how runtime adapters fit the layer model.

## Delivery terms

### `workbench/local`

The private continuous capture-and-stewardship branch where evolving developer
intent can be checkpointed, separated, and ordered before delivery.

### Delivery branch

A short-lived, intent-categorized branch created from current `main` for one
bounded Jira outcome:

```text
<category>/<JIRA-ISSUE-KEY>-<outcome-slug>
```

### `main`

The clean integration branch containing outcomes accepted through the
repository's review and merge process.

## Identifier boundary

- Portable contracts, schemas, tests, and generic diagrams use placeholders or
  neutral examples such as `PROJ-123` and `TEAM-42`.
- Deployment-specific adapters and information models use real identifiers
  such as `AEPI` and `AEPD` when those identifiers are the subject being
  documented.
- Telemetry and historical evidence preserve the identifiers actually emitted
  or recorded; they are not rewritten for presentation consistency.
- Public explanations may include a small number of clearly contextualized
  repository examples after introducing the portable form.
