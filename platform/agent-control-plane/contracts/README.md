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

A work item represents the desired outcome. An attempt represents one effort
to achieve that outcome. The current Jira contract deliberately contains only
planning semantics that can be selected without runtime instrumentation:

```text
executionMode
initiationMode
approvalPolicy
```

The attempt store remains authoritative for attempt history. Runtime outcomes,
failure classifications, and attempt identifiers must not be projected into
Jira until the telemetry subsystem can supply them from trustworthy evidence.
Jira remains authoritative for work state and human-visible planning metadata.

Jira-generated `customfield_*` identifiers belong in a deployment-specific
adapter mapping, not in these schemas.

See [`examples/attempt-partitioning/`](examples/attempt-partitioning/) for a
concrete run with two observable attempts and its derived Jira projection.
