# Agent Control Plane

A repo-portable architecture for governing AI-assisted engineering
behavior through layered instructions, runtime adapters, provenance logs,
selective context loading, and auditable task execution.

## Purpose

This repository provides a reusable scaffold for installing an
instruction-control plane into software repositories.

Within the larger platform feedback loop, the control plane owns the
transformation from intention into governed execution:

```text
human intention
  -> governed instructions and skills
  -> runtime discovery and context loading
  -> authorized agent behavior
```

Inference Telemetry and Developer Learning remain peer platform pillars that
observe outcomes and feed validated lessons back into this control surface.
Shared contracts and schemas define concrete interfaces between the three
pillars without becoming another control plane.

The control plane organizes agent customization from governing intent through
runtime operation:

```text
Responsibility → assumed roles / role charters
Authority      → execution policies
Behavior       → instructions
Procedure      → skills
Capability     → MCP server declarations
Lifecycle      → hooks
```

It formalizes five core needs:

- deterministic instruction discovery for AI coding agents
- scoped guidance layers for global, agent-level, and repo-local rules
- runtime-specific adapters that converge on the same instruction tree
- provenance from human observation to durable instruction
- auditable task execution through explicit load reports

Portable work-governance contracts live in [`contracts/`](contracts/).
The Jira work-item contract keeps board-facing operational metadata separate
from immutable agent-run attempt history and detailed telemetry.

## Contract validation environment

Contract validation uses `jsonschema` so the schema files under
[`contracts/`](contracts/) stay the single source of truth. Hooks run under the
runtime's bare `python3`, so they import no third-party package; validation runs
from the test suite and the registry validator instead.

```bash
cd platform/agent-control-plane
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[validation]"

.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/validate_asset_registries.py
```

`validate_asset_registries.py` is the broad check: it resolves every registry
path, compiles every schema, validates a store index, and requires each
declared evidence type to have a producer. To ask the narrower question of
whether the schemas themselves are well-formed, run the contract compiler on
its own:

```bash
.venv/bin/python scripts/validate_contracts.py
```

## Governed action safety

The control plane owns routing and authorization for governed engineering
actions while each destination system remains authoritative for its own data.
Its workflows:

- read current destination state before mutation;
- suppress duplicate or already-satisfied actions;
- retain Jira keys, run and attempt identifiers, and native audit evidence;
- stop, replan, or escalate repeated failures instead of looping; and
- keep detailed observation streams behind the `telemetryRef` on an immutable
  agent-run attempt.

These rules do not require a generalized work-event, routing-decision, or
delivery-receipt schema. Add a shared schema only when a concrete producer and
consumer need a versioned cross-pillar interface.

The monorepo installs runtime-native discovery and configuration surfaces at
repository root. Run
[`../../scripts/check-agent-discovery-layout.sh`](../../scripts/check-agent-discovery-layout.sh)
to verify that they have not drifted back into the component directory.

## Prompt instruction manifests

Each completed prompt response includes a compact list of the instructions
that governed that turn. The canonical response contract lives in
[`agent-assets/instructions/prompt-instruction-manifest.md`](agent-assets/instructions/prompt-instruction-manifest.md).

Runtime evidence retains its source:

- Claude Code records authoritative `InstructionsLoaded` observations and
  injects them at `UserPromptSubmit`.
- Codex discovers the applicable `AGENTS.md` repository baseline at
  `UserPromptSubmit`, then asks the model to add instructions and skills used
  during the turn.
- GitHub Copilot receives the durable response requirement through its
  instruction adapter. Its entries remain `Declared` unless the runtime
  supplies authoritative load evidence.

The shared hook writes a session ledger with one snapshot per prompt to a
canonical local-data store partitioned first by repository identity and then by
runtime. Codex and Claude Code never append to the same JSONL ledger even if
they supply the same session identifier. An ignored
`.local-mirrors/instruction-evidence` symlink exposes only the active project's logs so
citation clicks open the relevant runtime ledger directly. Evidence records
retain structured path and line fields; runtime adapters render those fields in
the provider-correct citation form. Set
`AEP_INSTRUCTION_MANIFEST_DIR` to choose another canonical location. Prompt
text is excluded from the ledger.

## Provider documentation bootstrap

Codex and Claude Code run a shared `SessionStart` hook that makes current
provider documentation available through a local-first cache. The hook stores
the comprehensive provider corpus outside the repository, refreshes it only
when missing or stale, and injects a compact lookup path rather than loading
the full manual into the context window.

Set `AEP_PROVIDER_DOCS_DIR` to choose another cache directory and
`AEP_PROVIDER_DOCS_TTL_SECONDS` to change the default 24-hour freshness
window. Network failures do not block session startup; a stale local manual
remains available when refresh fails.

It answers:

> How should an AI coding agent discover, load, and apply repository
> instructions without collapsing local context, runtime adapters, and
> reusable rules into one undifferentiated prompt?

## Documentation

Documentation for strategy, applied validation, diagrams, and related
future directions lives in [`docs/`](docs/).

Contributor automation and operational commands are documented in
[`scripts/README.md`](scripts/README.md).

The repository branching contract is documented in
[`docs/workbench-delivery-branching.md`](docs/workbench-delivery-branching.md).


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

- [`../../AGENTS.md`](../../AGENTS.md)
  Shared repository guidance for Codex and compatible agents.
- [`../../CLAUDE.md`](../../CLAUDE.md)
  Root Claude Code routing adapter.
- [`../../.github/copilot-instructions.md`](../../.github/copilot-instructions.md)
  Root GitHub Copilot routing adapter.
- [`agent-assets/`](agent-assets/)
  Canonical shared instructions, skill packages, hook definitions, execution
  policies, and role charters.
- [`adapters/runtimes/`](adapters/runtimes/)
  Provider capability declarations, version support, and native renderers.
- [`../../.agents/`](../../.agents/)
  Codex Agent Skill discovery links.
- [`../../.codex/`](../../.codex/)
  Codex-native project configuration and lifecycle hooks.
- [`../../.claude/`](../../.claude/)
  Claude Code-native installation surface.
- [`../../.github/instructions/`](../../.github/instructions/)
  Path-specific GitHub Copilot adapters.
- [`../../.github/agents/`](../../.github/agents/)
  GitHub Copilot agent adapters.
- [`../../.github/prompts/`](../../.github/prompts/)
  GitHub Copilot prompt adapters.
- [`../../.github/skills/`](../../.github/skills/)
  GitHub Copilot skill adapters.
- [`../../.github/hooks/`](../../.github/hooks/)
  GitHub-native mechanical guardrails.
- `engineering-knowledge-base/` (optional local overlay)
  A machine-local location for private incident capture, learning notes,
  and other workflow-derived knowledge. It is not part of the portable
  checked-in template.

## Docs Layout

- [`docs/README.md`](docs/README.md)
  Documentation map and placement rules.
- [`docs/diagrams/`](docs/diagrams/)
  Source and exported diagrams.
- [`docs/strategy/`](docs/strategy/)
  Domain-agnostic strategic rationale.

## Runtime-native installation boundary

Repository-discovered files must be installed relative to the adopting
repository's Git or workspace root. Keep entrypoints and runtime-native
installation surfaces light: they may contain provider-required locators,
selectors, links, generated projections, and explicitly approved native
configuration, but they do not own portable behavior. Store canonical skill
packages, shared instructions, and role charters under `agent-assets/`; store
canonical hooks and execution policies there as they are implemented. Expose
those assets through each runtime's native root-level paths and provider
adapter.

## Adoption Guidance

Use this template as checked-in repository structure when the instruction
control plane should be portable to other developers or automation
environments.

For an existing repository, start with the smallest useful checked-in
surface:

1. Add root `AGENTS.md` for shared agent guidance.
2. Add root `CLAUDE.md` and `.github/copilot-instructions.md` as lightweight
   runtime entrypoints.
3. Add canonical skill packages and other reusable content under
   `agent-assets/`.
4. Add `.agents/`, `.codex/`, `.claude/`, and agent-related `.github/`
   installation surfaces only for supported runtimes.
5. Keep provider-specific hook registration, permissions, and enforcement
   configuration runtime-native while keeping portable intent under
   `agent-assets/`.
6. Add task-relevant artifacts only when they describe reusable
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
[`../developer-learning-retrieval/docs/design.md`](../developer-learning-retrieval/docs/design.md).
That note explains how workflow telemetry and retrieval practice could
extend this template in future systems without changing the template's
core identity.

## Strategic Notes

High-level rationale for the control-plane pattern lives in
[`docs/strategy/`](docs/strategy/).

Domain-specific extensions, such as biohealth governance and clinical
translation boundaries, should live in the downstream repository that
owns that domain surface.
