# Agent Context Routing

## Purpose

Define an artifact-typed control plane for repository-aware AI agents while
preserving safe migration semantics.

## Layer model

1. Lightweight repository entrypoints load shared, always-applicable rules.
2. Canonical provider-neutral skill packages live under
   `platform/agent-control-plane/agent-assets/skills/`.
3. Lightweight Codex, Claude Code, and GitHub Copilot installation surfaces
   satisfy native discovery contracts.
4. Shared agent assets hold reusable instructions, skill packages, hook
   definitions, execution policies, and role charters.
5. Provider runtime adapters map canonical intent into native discovery,
   lifecycle, and permission configuration.
6. Runtime-native enforcement, CI, rulesets, and IAM enforce mechanical
   boundaries.

## Discovery boundary

Runtime-discovered entrypoints and runtime-native installation surfaces belong
at the repository root. Those surfaces contain only provider-required
locators, selectors, links, generated projections, or explicitly approved
native configuration; they do not own portable behavior.
Canonical reusable instructions, skill packages, hook definitions, execution
policies, and role charters belong under
`platform/agent-control-plane/agent-assets/`. Provider capability mappings and
renderers belong under `platform/agent-control-plane/adapters/runtimes/`.

## Adapter mechanism by asset type

Every asset type under `agent-assets/` has exactly one canonical source. The
*mechanism* an installation surface uses to reference that source is not
uniform — it is chosen per asset type based on whether the runtime-facing
format is identical across runtimes or must diverge. Do not treat "symlink"
as the required convention; treat "single canonical source, referenced
correctly for the format" as the convention, and pick the mechanism below
that fits the asset type.

| Asset type | Mechanism | Why |
| --- | --- | --- |
| Skills | Bare symlink (e.g. `.claude/skills/<name>` → `agent-assets/skills/<name>`) | `SKILL.md` frontmatter (`name`, `description`) is identical across every runtime — nothing runtime-specific lives in the file, so a symlink loses nothing. |
| Instructions | Thin per-runtime file with runtime-correct frontmatter, plus a single `@`-import line for the canonical body (e.g. `.claude/rules/<name>.md`'s `paths:` vs. `.github/instructions/<name>.instructions.md`'s `description:`/`applyTo:`) | Each runtime requires a different frontmatter schema to preserve conditional scoping (which files/paths trigger the rule). A bare symlink cannot carry two different frontmatter blocks for one file, so the body is single-sourced via import while frontmatter stays adapter-local, generated from the registry's `scopeGlobs`/`copilotDescription` fields (`scripts/generate_instruction_adapters.py`) rather than hand-duplicated. |
| Hooks | Direct path reference embedded in runtime-native registration config (e.g. `.claude/settings.json`, `.codex/hooks.json` `command` fields invoking `platform/agent-control-plane/scripts/<script>.py` directly) | There is no separate adapter file to symlink — the registration entry itself must be native JSON in each runtime's required hook schema. The canonical script path is referenced directly, which is already as non-duplicated as this mechanism allows. |
| Role charters | Reference or translation from runtime-specific subagent definitions | A runtime's native subagent-definition schema does not structurally match a neutral role-charter document closely enough to share a file, even via import — the runtime-specific definition must be authored to reflect the charter's intent, not mirror its text. |

If a new asset type is added, decide its mechanism by asking: is the
runtime-facing file format identical across every consuming runtime? If yes,
symlink. If only the body is shared but discovery metadata must differ,
wrapper file plus import. If there is no separate adapter file, reference the
canonical path directly from native config. If even the body must diverge
structurally, translate rather than mirror.

## Local overlay rule

Optional local overlays may hold personal workflow behavior. They cannot
define canonical product requirements or runtime contracts.
