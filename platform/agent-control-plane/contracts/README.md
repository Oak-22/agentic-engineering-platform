# Agent Control Plane Contracts

This directory owns portable contracts for governed agent work. Runtime and
tool adapters may project these contracts into Jira, telemetry stores, or
other systems, but vendor-specific identifiers do not belong in the portable
schemas.

## Jira work-item and attempt model

- [`jira-work-item-metadata.schema.json`](jira-work-item-metadata.schema.json)
  defines governed planning metadata shown on a Jira work item.
- [`agent-run-attempt.schema.json`](agent-run-attempt.schema.json) defines the
  immutable record for one execution attempt.
- [`instruction-evidence-record.schema.json`](instruction-evidence-record.schema.json)
  binds each instruction evidence type to the citation fields capable of
  proving that claim. Its compact citation label links to the structured
  project-scoped evidence log containing the record identified by `recordId`.
- [`instruction-evidence-store.schema.json`](instruction-evidence-store.schema.json)
  describes the generated project partition, its session-ledger files, and
  their retention classes. See the [instruction evidence store guide](../docs/instruction-evidence-store.md).

## Instruction evidence and citations

Instruction evidence is a discriminated record rather than an independently
selected label and citation. Each evidence type has a distinct proof contract:

- `Observed` requires an authoritative runtime event observation.
- `Runtime baseline` requires a named runtime discovery mechanism and scope.
- `Explicitly invoked` requires a captured skill or instruction invocation.
- `Read during turn` requires a runtime tool-read event.
- `Declared` requires the adapter that made the declaration.

Every variant also cites the project-qualified source using repository
identity, base revision, repository-relative path, SHA-256 digest, Git blob
identity, and worktree state. Consumers render `citation.label` as a local file
link to `citation.href`; both values come from the same validated record as
`evidenceType`, preventing unsupported evidence-citation combinations.
`activeRepositoryId` identifies the governed project while `repositoryId`
identifies the instruction source, so a source loaded from another repository
cannot appear project-local merely because its content hash is valid.

The canonical logs live outside the working tree in a directory partitioned by
repository identity. The hook creates an ignored `.local-mirrors/instruction-evidence`
view in the active repository that points to only that project's partition.
Clicking a citation therefore opens the relevant local JSONL log without
publishing prompt history or machine-specific paths.

A work item represents the desired outcome. An attempt represents one effort
to achieve that outcome. The current Jira contract deliberately contains only
planning semantics that can be selected without runtime instrumentation:

```text
executionMode
initiationMode
approvalPolicy
accountableHumanId
```

`accountableHumanId` is required even when `executionMode` is `agent`.
Execution describes who performs the work; accountability identifies the
natural person responsible for it. A team may provide supplemental ownership
context but does not replace the accountable human.

This is not a durable `humanId -> agentId` ownership mapping. One work item has
one accountable human and may have many attempt records; each attempt records
its executor independently. A human may oversee many work items, and the same
agent executor may participate in work overseen by different humans. The
resulting human-agent participation is many-to-many through work items and
attempts, while accountability remains singular at the work-item boundary.

The attempt store remains authoritative for attempt history. Runtime outcomes,
failure classifications, and attempt identifiers must not be projected into
Jira until the telemetry subsystem can supply them from trustworthy evidence.
Jira remains authoritative for work state and human-visible planning metadata.

Jira-generated `customfield_*` identifiers belong in a deployment-specific
adapter mapping, not in these schemas.

See [`examples/attempt-partitioning/`](examples/attempt-partitioning/) for a
concrete run with two observable attempts and its derived Jira projection.
