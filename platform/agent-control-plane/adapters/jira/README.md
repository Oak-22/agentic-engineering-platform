# Jira Adapter

This adapter projects the portable Jira work-item metadata contract into a
specific Jira deployment.

## AEPI planning fields

Create these fields as single-select fields in the Agentic Engineering
Platform Implementation (`AEPI`) project:

| Portable property | Jira field name | Allowed values |
| --- | --- | --- |
| `executionMode` | Execution Mode | Agent, Human, Hybrid |
| `initiationMode` | Initiation Mode | Human, Scheduled, Event-driven, Agent-delegated |
| `approvalPolicy` | Approval Policy | Human required, Human on exception, Automated |

After Jira creates the fields, write their actual `customfield_*` identifiers
to `aepi-field-mapping.json` using
[`jira-field-mapping.schema.json`](jira-field-mapping.schema.json). Do not
invent IDs or commit authentication material.

Loose, multi-value Jira Labels remain available for search vocabulary. They
must not replace these governed fields.

Runtime outcome, failure, run, and attempt fields are intentionally postponed
until the inference telemetry subsystem can supply trustworthy projections.
