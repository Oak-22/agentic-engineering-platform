# TODO: Rebalance governed-delivery cardinality for traceability and latency

Status: proposed capture only. This is not yet an accepted architecture
decision, Jira delivery, or canonical skill change.

Primary classification: architecture/docs

## Context

The governed-delivery workflow currently presents this relationship as its
default repository shape:

```text
1 Jira task : 1 feature branch : 1 pull request : X coherent commits : Y tracked file changes
```

The original rationale was stronger implementation traceability. The
operational trade-off is that every extra governed unit can add cross-boundary
prompt-turn work: model-to-IDE interaction and model-to-Atlassian-Rovo calls,
including both egress and ingress. The relevant cost is cumulative prompt-turn
latency, not only individual network milliseconds.

The repository also has a prior conceptual distinction between atomic
implementation/capture checkpoints and delivery boundaries. That distinction
needs to be made explicit enough that agents do not turn every implementation
step, TODO, file, hunk, or acceptance-criteria bullet into a Jira/branch/PR
triple.

## Intended outcome

Establish one cross-runtime policy that preserves implementation traceability
while choosing external delivery artifacts by accountable outcome, authority,
review, verification, and revert boundaries. Implementation detail remains
traceable in commits, structured evidence, and telemetry; external system
calls are batched at workflow gates where practical.

## Proposed delivery units

### Unit 1 — Record the architectural decision

**Touches**

- `docs/architecture/adr/0005-governed-delivery-cardinality-and-prompt-turn-latency.md`
- `docs/architecture/adr/README.md`

**Mechanism** — Add the next ADR after resolving whether the repository should
retain `1:1:1` as a common case or replace it with variable cardinalities such
as `J Jira tasks : B branches : P pull requests`, and define the latency and
batching consequences.

**Claim** — The repository has one authoritative decision separating
traceability detail from external delivery-artifact cardinality.

**Trace check** — Validate the ADR frontmatter and confirm the ADR index links
the record as the next unique sequence.

### Unit 2 — Align the cross-runtime workflow guidance

**Touches**

- `platform/agent-control-plane/agent-assets/skills/shape-repository-change/SKILL.md`
- `platform/agent-control-plane/agent-assets/skills/deliver-governed-change/SKILL.md`
- `platform/agent-control-plane/agent-assets/skills/deliver-governed-change/references/governed-change-delivery.md`
- `docs/operations/governed-repository-delivery.md`

**Mechanism** — Encode the accepted ADR rule in the canonical sources only;
runtime discovery surfaces continue to reference those sources through the
existing cross-runtime projection mechanism.

**Claim** — Codex, Claude, and Copilot are instructed to preserve local
implementation traceability without multiplying Jira, branch, pull-request,
or connector operations solely because implementation is detailed.

**Trace check** — Run the asset-registry, discovery-layout, and focused
control-plane tests; verify the three runtime skill links resolve to the same
canonical package.

## Explicit exclusions

- Do not create or update Jira, Confluence, Git branches, pull requests, or
  commits as part of this TODO capture.
- Do not delete or rewrite `prompt-scratch.md`.
- Do not introduce a new self-evolving skill until the policy owner and
  regression/evaluation mechanism are established.

## Dependencies and open decisions

- The ADR must settle whether `1:1:1` is merely a common topology or a
  required invariant for some classes of governed work.
- The decision must define where implementation-level traceability lives when
  multiple outcomes share a task or a pull request.
- Latency measurement should use prompt-turn observations and connector-call
  counts; millisecond-level network benchmarking is not sufficient by itself.
- After the ADR is accepted, deliver the two units through the normal Jira
  workflow, with the ADR preceding the canonical skill changes.

