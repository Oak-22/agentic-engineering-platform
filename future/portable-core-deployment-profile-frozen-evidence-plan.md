# Portable Core, Deployment Profile, and Frozen Evidence Pass

## Summary

Separate the repository into four explicit artifact classes:

1. **Portable core** — reusable schemas, adapters, skills, tests, and product
   documentation.
2. **Deployment profile** — maintained configuration for this repository's AEP
   installation.
3. **Frozen evidence** — curated, immutable snapshots and reports from real
   development activity.
4. **Runtime state** — live transcripts, telemetry sinks, caches, and generated
   local views that remain untracked.

Deliver this as four ordered Jira units. Each branch starts from updated
`main`; foundational units merge before their dependents.

## Implementation Changes

### 1. Establish the artifact lifecycle vocabulary

- Tighten `docs/glossary.md` around the four artifact classes and replace
  "deployment-specific adapters" with "deployment profiles."
- Define the governing rule: portable layers use placeholders; deployment
  profiles use real configuration; frozen evidence preserves observed
  identifiers; runtime state remains external.
- Add the four classes to the repository structure and placement guidance.
- Preserve the compact delivery and Jira terminology already added.
- Classification: `docs`.
- Acceptance: every top-level artifact class has one canonical definition,
  owner, retention behavior, and portability rule.

### 2. Extract the maintained AEP deployment profile

- Introduce `deployments/aep/` as the cross-pillar self-hosting profile.
- Add a small machine-readable profile declaring `AEPI`, `AEPD`, and `AEP` as
  this installation's Jira Software, Jira Product Discovery, and Confluence
  identifiers.
- Move the concrete AEPI field mapping and AEP Atlassian information model into
  the profile.
- Keep the Jira mapping schema and destination-adapter behavior portable under
  the Agent Control Plane.
- Make the Jira adapter README generic and point to the AEP profile only as a
  concrete implementation example.
- Remove the AEP-specific reference from the portable Jira/Confluence skill;
  repository guidance will route AEP operations to the active deployment
  profile.
- Add a portability check that reads identifiers from the profile and rejects
  them in portable contracts, schemas, generic tests, diagrams, and skills.
  Allow them only in the profile, glossary definitions, frozen evidence, and
  explicitly contextualized public examples.
- Classification: `refactor`.
- Acceptance: removing `deployments/aep/` leaves a coherent portable platform
  without breaking generic schemas or tests.

### 3. Freeze development telemetry as evidence

- Add `evidence/telemetry-snapshots/` with a dataset-manifest schema and one
  directory per immutable dataset.
- Require each manifest to record dataset ID, frozen status, capture window,
  runtime/source class, schema references, redaction policy, record count,
  checksums, transformations, limitations, and derived artifacts.
- Exclude prompt and response content by default. Retain event structure,
  metrics, identifiers needed for correlation, and hashes where useful. Never
  commit credentials, machine paths, raw session archives, or private
  reasoning.
- Move the real manual `single-prompt-turn.json` observation out of component
  `examples/` into a frozen snapshot. Remove prompt text through a documented
  transformation while preserving its original provenance and limitations.
- Keep only synthetic, product-neutral fixtures under component `examples/`
  and `tests/`.
- Create a frozen pilot dataset for the original Claude/Codex efficiency
  investigation using normalized aggregates, extraction/query provenance, and
  explicit limitations. Mark the rotating Codex SQLite sample as non-equivalent
  to transcript telemetry.
- Do not fabricate the corrected experiment dataset. Create it only after the
  rollout-JSONL experiment runs.
- Classification: `refactor`.
- Acceptance: observatory code and tests run without frozen evidence; every
  report identifies an immutable dataset or clearly states that results are
  not yet available.

### 4. Reclassify reports and complete the repository audit

- Move the runtime-efficiency DOCX artifacts from observatory product
  documentation into a cross-runtime efficiency experiment under `evidence/`.
- Retain the naive report as a labeled pilot interpretation and the
  experiment-setup report as the current design artifact.
- Exclude the Word lock file.
- Keep the three generic observatory SVGs with the telemetry pillar because
  they explain reusable product architecture.
- Audit all pillars for concrete Jira keys, account identifiers, local paths,
  connector wiring, generated outputs, and captured runtime data.
- Classify each finding as portable core, AEP deployment profile, frozen
  evidence, runtime state, or generated projection; move only when ownership
  is incorrect.
- Preserve real identifiers in telemetry and historical evidence rather than
  rewriting the record.
- Classification: `refactor`.
- Acceptance: all remaining concrete deployment identifiers have an
  explainable location, and no product capability depends on AEP-specific
  evidence or configuration.

## Interfaces and Validation

- New deployment interface: `deployments/aep/profile.json`, schema version 1,
  containing profile identity and external-system identifiers but no
  credentials.
- New evidence interface: frozen telemetry dataset manifests with checksummed
  file inventories and explicit redaction metadata.
- Validate all new and moved JSON against their schemas.
- Run Agent Control Plane and Telemetry Observatory test suites.
- Run agent-discovery, Markdown-link, JSON-format, and portability-boundary
  checks.
- Test that arbitrary Jira keys such as `PROJ-123` and `TEAM-42` remain
  accepted.
- Test that `AEPI` and `AEPD` are rejected in portable fixture paths but
  accepted in the AEP profile and frozen evidence.
- Verify that reports reference existing dataset IDs and that live local
  telemetry remains ignored.

## Assumptions

- `deployments/aep/` is a maintained self-hosting profile, not merely
  historical evidence.
- Curated snapshots are committed; raw telemetry remains local and ignored.
- Prompt and response content is excluded unless a future dataset explicitly
  justifies reviewed excerpts.
- The current workbench contains unrelated user-authored moves and deletions;
  implementation transfers only explicitly classified files and hunks.
- The four delivery units are merged in order. Telemetry freezing depends on
  the taxonomy; report reclassification depends on the evidence structure.
