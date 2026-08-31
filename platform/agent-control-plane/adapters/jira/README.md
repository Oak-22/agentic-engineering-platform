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
| `class` | Class | Feature, Fix, Refactor, Chore, Docs |

`Class` records the delivery unit's primary change nature, using the same
vocabulary as `shape-repository-change`. It belongs on every non-subtask issue
type, including outcomes with no Git artifacts. The delivery branch category is
derived from it, so one classification decides both.

### Class is authoritative over issue type

Jira issue type describes where work sits in the hierarchy and how it is
reported on. `Class` describes what the change does. The two vocabularies
overlap by name — a `Feature` type and a `Feature` class, a `Bug` type and a
`Fix` class — but they answer different questions, and the overlap is not a
reason to collapse either one. A `Bug` may be resolved by a `Fix`, by a
`Refactor`, or by `Docs` alone; the type cannot express which.

Read `Class` and never issue type when deriving governed behavior, including
the delivery branch category. Issue type remains a Jira-native affordance for
boards, backlog, and reporting.

### Fields owned by the Jira vendor

A Jira deployment may expose vendor fields that resemble platform concepts,
such as a field recording the vendor's own agent sessions. Those record
activity in the vendor's runtime, not this platform's. Execution evidence is
owned by
[`agent-run-attempt.schema.json`](../../contracts/agent-run-attempt.schema.json)
and the telemetry observatory.

Leave such fields out of the portable contract and out of this mapping, and do
not make them required: nothing outside the vendor's runtime can populate
them, so a required vendor field rejects every programmatic create.

Record the standard accountability field and Jira-generated `customfield_*`
identifiers in `aepi-field-mapping.json` using
[`jira-field-mapping.schema.json`](jira-field-mapping.schema.json). Do not
invent IDs or commit authentication material.

Loose, multi-value Jira Labels remain available for search vocabulary. They
must not replace these governed fields. Use labels for concise
business-relevant classification and retrieval.

Record human-agent collaboration lineage through constrained structured
metadata such as issue history metadata, governed custom fields, execution
attempt records, and telemetry identifiers. Keep actor, model, runtime, and
generation details out of summaries, descriptions, and labels unless they
materially affect a business decision, accountability boundary, review, or
audit requirement.

Runtime outcome, failure, run, and attempt fields are intentionally postponed
until the inference telemetry subsystem can supply trustworthy projections.
