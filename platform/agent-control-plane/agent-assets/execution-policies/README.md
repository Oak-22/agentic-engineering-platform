# Canonical Execution Policies

This directory owns provider-neutral bounded-execution policy instances. A
policy defines the resource boundary, approval and escalation strategy, bypass
rules, and intended enforcement tier without embedding provider configuration
syntax.

JSON Schemas that validate these portable policies belong in
[`../../contracts/`](../../contracts/). Provider capability mappings,
supported versions, and renderers belong in
[`../../adapters/runtimes/`](../../adapters/runtimes/).

Generated provider configuration must preserve the canonical security intent.
An adapter must reject or explicitly report unsupported requirements instead
of silently weakening them.

## Asset index

- [`governed-repository-change.md`](governed-repository-change.md) — action
  tiers, authorization and evidence requirements, and fail-closed handling
  for repository and linked external-system (Jira, Confluence, GitHub
  configuration) mutation. Implemented for by `deliver-governed-change`,
  `manage-git-workflow`, and `manage-jira-confluence`.
- [`permissions/`](permissions/) — one IAM-style permission-policy document
  per Agent Registry agent type, validated against
  [`../../contracts/agent-permission-policy.schema.json`](../../contracts/agent-permission-policy.schema.json).
  Adds the principal axis this tier policy does not cover: which agent
  identity may perform an action, not only how reversible the action is.
  Enforced by
  [`../../scripts/agent_permission_gate.py`](../../scripts/agent_permission_gate.py).

## Placement guidance

A policy states the boundary a skill's procedural instructions must operate
inside — resource boundaries, authorization tiers, bypass restrictions, and
evidence requirements that would otherwise be silently re-derived by each
skill that needs them. It does not restate a skill's steps, tool-specific
mechanics, or anything true of one workflow but not the domain generally;
that content stays in the skill. Add a new policy instance only when a
boundary is genuinely cross-cutting across more than one skill or is likely
to be — a boundary used by exactly one skill and unlikely to be reused
belongs in that skill instead.
