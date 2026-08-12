# Canonical Skills

This directory owns reusable Agent Skill packages. Each skill defines a
repeatable, task-oriented workflow with a trigger, procedure, boundaries, and
completion condition.

The exhaustive skill inventory is maintained in
[`skills_registry.json`](skills_registry.json). It records canonical package
paths, coordinator or operational classification, and runtime discovery
bindings.

## Skill-composition pattern

Classify each skill by its primary responsibility:

- **Coordinator skills** compose multiple operational skills into a larger
  outcome. They own sequencing, cross-system state, delegation boundaries,
  and end-to-end evidence without duplicating the detailed procedures of the
  skills they coordinate.
- **Operational skills** directly execute a bounded workflow. The work may be
  analytical, advisory, mutating, verifying, or handoff-oriented; it does not
  need to operate an external system.

Every skill is primarily one or the other. Calling a supporting script or tool
does not make an operational skill a coordinator. The distinction is whether
the skill's main responsibility is composing other skills or performing its
own bounded workflow.

In the current catalog, `deliver-governed-change` is a coordinator skill.
`manage-git-workflow`, `manage-jira-confluence`, `shape-repository-change`,
`shape-readme-entrypoint`, and `handoff-agent-work` are operational skills.

## Composition rules

- Coordinator skills delegate bounded operations through the owning
  operational skill and preserve its authority and safety rules.
- Operational skills remain independently invocable when their bounded
  workflow is the user's complete objective.
- Coordinators own the larger outcome and cross-skill handoffs; operational
  skills own the detailed procedure and verification for their boundary.
- Keep shared behavioral rules in `../instructions/`. A rule that applies
  across workflows is an instruction, not a skill category.

## Canonical-first standardization

New reusable workflows start here, before runtime registration:

1. Define the workflow in `skills/<skill-name>/SKILL.md`, including its
   trigger, procedure, boundaries, and completion condition.
2. Put supporting code beside the skill when it is intrinsic to that workflow;
   put it in `agent-control-plane/scripts/` when multiple assets or runtimes
   share it.
3. Add tests for the canonical workflow and its supporting code.
4. Add runtime discovery links or projections only after the canonical package
   exists.
5. Verify that each runtime adapter preserves the canonical behavior and
   reports unsupported capabilities instead of silently weakening it.

Provider-specific lifecycle automation is an explicit exception. If a
runtime exposes a trigger, payload, or capability with no portable equivalent,
it may begin in that runtime's native configuration. The implementation must
declare its supported runtime and must not imply cross-runtime parity.
