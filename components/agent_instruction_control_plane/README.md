# Agent Instruction Control Plane

A repo-portable architecture for governing AI-assisted engineering
behavior through layered instructions, runtime adapters, provenance logs,
selective context loading, and auditable task execution.

## Purpose

This repository provides a reusable scaffold for installing an
instruction-control plane into software repositories.

It formalizes five core needs:

- deterministic instruction discovery for AI coding agents
- scoped guidance layers for global, agent-level, and repo-local rules
- runtime-specific adapters that converge on the same instruction tree
- provenance from human observation to durable instruction
- auditable task execution through explicit load reports

It answers:

> How should an AI coding agent discover, load, and apply repository
> instructions without collapsing local context, runtime adapters, and
> reusable rules into one undifferentiated prompt?

## Documentation

Documentation for strategy, applied validation, diagrams, and related
future directions lives in [`docs/`](docs/).


## Repository Identity

Use **Agent Instruction Control Plane** as the project name.

Use `agent_instruction_control_plane` as the repository slug for
local directories, remotes, package references, and generated examples.

This name describes the reusable system boundary: it is a control plane
for how AI coding agents discover, load, and apply repository
instructions. It is broader than a single developer workflow template,
but still narrow enough to remain adoptable by another team.

## Business Value

Structured agent instructions reduce engineering friction by making AI
assistant behavior easier to discover, constrain, audit, and reuse across
repositories.

### Why It Matters

1. Onboarding cost reduction
  Mature teams in large organizations carry high onboarding cost due to
  system complexity, service dependencies, and historical decisions.
  Structured instruction artifacts reduce time-to-context for new
  engineers, transferred engineers, and AI coding agents entering a repo.

2. Throughput support as AI accelerates delivery
  AI increases implementation speed and expands the volume of proposed
  changes. Teams need stronger instruction boundaries to maintain quality
  while supporting faster feature cycles.

3. Context continuity and atrophy prevention
  Fast-moving codebases create risk of knowledge decay between work
  cycles. Capturing decisions, instruction provenance, and reusable
  patterns helps teams re-enter complex areas quickly and sustain
  delivery tempo.

4. Risk and rework reduction
  Reusable instructions and decision trails reduce repeat mistakes,
  shorten debugging loops, and lower avoidable rework.

### Operational Outcome

Used consistently, this template improves delivery predictability by
lowering context-recovery overhead, making agent behavior more
inspectable, and increasing reuse of proven engineering practices.

## Template Contents

- `.github/copilot-instructions.md`
  Repository entrypoint and routing adapter for repository-aware agents.
- `.github/instructions/`
  Durable agent behavior rules.
- `.github/agents/`
  Specialist agent personas.
- `.github/prompts/`
  Reusable task prompts.
- `.github/skills/`
  Repeatable workflow playbooks.
- `.github/hooks/`
  Mechanical guardrails for task execution.
- `engineering_knowledge_base/`
  Structured locations for incident capture, learning notes, and other
  workflow-derived engineering knowledge.

## Optional Reference Tools

- `tools/folder_structure_visualizer/`
  Independently packageable Python CLI for mapping repository hierarchy
  and rendering reviewable semantic descriptions of component
  responsibilities. The tool supports repository orientation for humans
  and agents but is not a runtime dependency of the portable control
  plane scaffold.

## Docs Layout

- [`docs/README.md`](docs/README.md)
  Documentation map and placement rules.
- [`docs/applied-validation-through-myhealth.md`](docs/applied-validation-through-myhealth.md)
  Applied validation relationship between this control plane and
  `myHealth`.
- [`docs/diagrams/`](docs/diagrams/)
  Source and exported diagrams.
- [`docs/strategy/`](docs/strategy/)
  Domain-agnostic strategic rationale.

## Legacy Migration Note

Earlier versions used `AGENTS.md` and `.github/agent_instructions/`.
Those paths are now deprecated in favor of an artifact-typed `.github/`
control plane.

Do not include legacy `AGENTS.md` or `.github/agent_instructions/`
paths in this template. Repositories still migrating may keep temporary
references in their own migration branches, but the reusable control
plane should expose only the modern artifact-typed surface.

## Adoption Guidance

Use this template as checked-in repository structure when the instruction
control plane should be portable to other developers or automation
environments.

For an existing repository, start with the smallest useful checked-in
surface:

1. Add `.github/copilot-instructions.md` as routing adapter.
2. Add `.github/instructions/` for durable rules.
3. Add `.github/agents/`, `.github/prompts/`, `.github/skills/`, and
  `.github/hooks/` as needed.
4. Add task-relevant artifacts only when they describe reusable
  behavior.

This intrinsic adoption path keeps the control plane inside the repo
where agents already work. Separate methodology notes can live in
`docs/` when they explain why the pattern exists without becoming part
of the minimum install surface.

The structure is portable. The knowledge content should use two axes:

- `audience`: `personal` or `shared`
- `scope`: `repo`, `domain`, or `global`

This keeps personal learning flexible while preserving strong governance
for shared team knowledge.

### Two-Axis Model

- `personal` entries are capture notes for an individual developer.
  They may be exploratory and are not authoritative.
- `shared` entries are team-facing guidance and should be curated.
- `shared` entries usually start at `repo` scope.
- Promote from `repo` to `domain` or `global` only when patterns are
  reused and stable.

In enterprise microservice environments, this model avoids forcing
everything into one hierarchy while still enabling organization-wide
learning.

If a team also maintains centralized canonical assets, those may be
linked into a live repository through symlinks. Keep this template
copyable without machine-specific dependencies.

## Local Personalization

This template should remain copyable without machine-specific paths,
private instructions, or personal repository references.

For local personal workflows, a developer may symlink selected
configuration layers into a private configuration directory.

That local symlink model is useful for private portability. It should
not replace public checked-in scaffold files.

## Promotion Workflow

Use this lightweight process to avoid both duplication and overfitting:

1. Capture quickly in `personal` notes.
2. Publish useful items as `shared` + `repo`.
3. Promote to `shared` + `domain` or `shared` + `global` after reuse
  evidence exists (signed off by senior/leads)
4. Keep bidirectional links between promoted guidance and source repo
  evidence.

This preserves local relevance while building organization-wide
engineering memory over time.

## Enterprise Knowledge System Integration

This template is designed to complement, not replace, enterprise
knowledge systems (Confluence, SharePoint, Notion, internal wikis, or
GitHub Pages).

**Code-adjacent advantage**: Implementation-level knowledge stays near
code where change frequency is highest, reducing update latency and
staleness as AI-accelerated delivery increases code volume and change
pace.

**Promotion and export**: `shared` + `global` scope entries are
candidates for export to centralized systems:

- Policy-driven globals (architecture standards, compliance rules,
  deployment gates) → enterprise portal (Confluence, SharePoint, etc.)
- Implementation guides (debugging playbooks, observability patterns,
  runbooks) → wiki near source (GitHub wiki, docs/ folder link)
- Architecture decisions → both (linked bidirectionally)

This creates a single source of truth per artifact, reduces copy-paste
drift, and maintains fast feedback for technical details while
supporting slower-moving organizational policies.

## Related Design Direction

This repository is a template scaffold, not a full implementation of
workflow-derived retrieval.

A related design direction is documented in
[`docs/periodic_learning_retrieval_system.md`](docs/periodic_learning_retrieval_system.md).
That note explains how workflow telemetry and retrieval practice could
extend this template in future systems without changing the template's
core identity.

## Strategic Notes

High-level rationale for the control-plane pattern lives in
[`docs/strategy/`](docs/strategy/).

The broad thesis is documented in
[`docs/strategy/invisible-systems-thesis.md`](docs/strategy/invisible-systems-thesis.md).
Domain-specific extensions, such as biohealth governance and clinical
translation boundaries, should live in the downstream repository that
owns that domain surface.
