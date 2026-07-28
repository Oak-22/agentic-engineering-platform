# Jira Adapter

This adapter projects the portable Jira work-item metadata contract into a
specific Jira deployment.

## AEPI accountability

Map portable `accountableHumanId` to Jira's standard `assignee` field. Every
governed AEPI work item must have one human assignee, including work with
`Execution Mode: Agent`. Jira Team may provide supplemental group ownership,
but it does not replace the accountable human.

## AEPI planning fields

Create these fields as single-select fields in the Agentic Engineering
Platform Implementation (`AEPI`) project:

| Portable property | Jira field name | Allowed values |
| --- | --- | --- |
| `executionMode` | Execution Mode | Agent, Human, Hybrid |
| `initiationMode` | Initiation Mode | Human, Scheduled, Event-driven, Agent-delegated |
| `approvalPolicy` | Approval Policy | Human required, Human on exception, Automated |

Record the standard accountability field and Jira-generated `customfield_*`
identifiers in `aepi-field-mapping.json` using
[`jira-field-mapping.schema.json`](jira-field-mapping.schema.json). Do not
invent IDs or commit authentication material.

Loose, multi-value Jira Labels remain available for search vocabulary. They
must not replace these governed fields.

Runtime outcome, failure, run, and attempt fields are intentionally postponed
until the inference telemetry subsystem can supply trustworthy projections.
