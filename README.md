# AI-Assisted Developer Workflow Platform Template

Reusable platform template for standardizing AI-assisted developer
workflows across repositories, including agent instruction layers,
prompt provenance, adoption models, and repo scaffolding.

## Purpose

This template defines a practical operating model for AI-human software
development.

It formalizes three core needs:

- clear operating context and constraints for AI-assisted execution
- durable capture of decisions, incidents, and implementation learning
- reusable workflow structure across repositories with scope-aware
  knowledge management

## Portfolio Role

This repository is part of my AI-native engineering methodology layer.

It is not a standalone portfolio product. It supports my project-facing
repositories by documenting reusable collaboration patterns, agent
workflows, and durable knowledge-capture practices.

Project-facing repositories include:

- `myHealth`
- `digital_asset_processing_pipeline`
- `ai-infrastructure-financial-warehouse`

## Methodology Role

This repository defines the reusable operating system for AI-assisted
development: prompts, workflow templates, agent instructions, review
rituals, and reusable project scaffolding.

It answers:

> How should an AI-native engineering workflow be run?

## Related Methodology Repository

For applied case studies and observations from real AI-human
engineering work, see
[`ai_human_engineering_collaboration_case_studies_and_best_practices`](https://github.com/Oak-22/ai_human_engineering_collaboration_case_studies_and_best_practices).

## Business Value

Structured knowledge capture reduces engineering costs through faster
onboarding, lower rework from repeated mistakes, and increased reuse of
proven practices.

### Why It Matters

1. Onboarding cost reduction
  Mature teams in large organizations carry high onboarding cost due to
  system complexity, service dependencies, and historical decisions.
  Structured knowledge artifacts reduce time-to-context for new and
  transferred engineers.

2. Throughput support as AI accelerates delivery
  AI increases implementation speed and expands the volume of shipped
  code. Teams need stronger context continuity to maintain quality
  while supporting faster feature cycles.

3. Context continuity and atrophy prevention
  Fast-moving codebases create risk of knowledge decay between work
  cycles. Capturing decisions, incidents, and reusable patterns helps
  teams re-enter complex areas quickly and sustain delivery tempo.

4. Risk and rework reduction
  Reusable incident learnings and decision trails reduce repeat
  mistakes, shorten debugging loops, and lower avoidable rework.

### Operational Outcome

Used consistently, this template improves delivery predictability by
lowering context-recovery overhead and increasing reuse of proven
engineering practices.

## Template Contents

- `AGENTS.md`
  Runtime-neutral repository entrypoint for AI coding agents.
- `.github/agent_instructions/`
  Layered AI-human workflow guidance, separating reusable global instructions from repository-specific constraints and context.
- `engineering_knowledge_base/`
  Structured locations for incident capture, learning notes, and other
  workflow-derived engineering knowledge.

## Why AGENTS.md Exists

In a public or developer-portable instruction control plane, `AGENTS.md`
solves three bootstrapping problems:

1. Discovery
  A generic AI coding agent entering the repository needs a conventional
  root-level file that says where repository instructions begin.

2. Bootstrapping
  `AGENTS.md` points the agent from the repository root into the
  instruction tree, such as `.github/agent_instructions/`, and defines
  the order in which instruction indexes should be loaded.

3. Runtime neutrality
  `AGENTS.md` is not tied to GitHub Copilot, Codex, Cursor, Claude Code,
  or any other single runtime. Runtime-specific adapters can still exist,
  but they should converge on the same instruction tree.

## Adoption Guidance

Use this template as checked-in repository structure.

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
[`docs/workflow_derived_retrieval_for_ai_assisted_development.md`](docs/workflow_derived_retrieval_for_ai_assisted_development.md).
That note explains how workflow telemetry and retrieval practice could
extend this template in future systems without changing the template's
core identity.
