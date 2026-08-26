# AEP Atlassian Information Model

Use this reference only for the Agentic Engineering Platform Atlassian site.
Resolve current names and keys from live Atlassian data before writing because
administrators can rename projects and spaces.

## Canonical surfaces

| Surface | Current name | Current key | Owns |
| --- | --- | --- | --- |
| Jira Software | Agentic Engineering Platform Implementation | `AEPI` | opportunities, epics, features, stories, tasks, defects, testing, and delivery status |
| Confluence | Agentic Engineering Platform | `AEP` | organizational policy, authorization and exception process, cross-system proposals, and governance or decision records that evolve independently of any one repository |

There is no separate Jira Product Discovery project. Early-stage ideas and
opportunities live directly in AEPI (for example as `Task` issues) rather
than in a dedicated discovery surface; promote them to more specific issue
types as scope and evidence firm up.

Per [ADR-0001](../../../../../../docs/architecture/adr/0001-separate-implementation-knowledge-from-organizational-governance.md),
Confluence does not own implementation architecture, ADRs, role charters that
control runtime behavior, technical runbooks, or execution evidence — those
live in Git, where they change with the code. Create or update a Confluence
page only when the content is cross-repository, organizational, independently
governed, or meant for a non-code contributor; otherwise the canonical home is
the repository.

## Relationship model

AEPI tracks execution of decisions recorded in AEP. Link an AEPI issue to its
AEP page when a durable decision exists; do not duplicate the reasoning into
the issue, and do not require AEP pages to reference open issues.

## Human-agent collaboration lineage

Keep Jira summaries, descriptions, and labels focused on the business outcome,
work classification, ownership, and delivery state.

Capture collaboration lineage through the narrowest structured backend
surface that supports the intended use:

- Jira history metadata for the actor and generator behind a mutation;
- governed custom fields when provenance changes accountability, approval, or
  audit behavior;
- execution-attempt records for agent, model, runtime, prompt, and tool
  lineage;
- telemetry correlation identifiers for detailed operational investigation;
- Git and GitHub integration records for branch, commit, pull-request, review,
  and automation lineage.

Surface provenance to business users when it changes a decision, review
boundary, compliance obligation, or accountable ownership. Routine agent
participation remains available through backend evidence without becoming
business-facing taxonomy.
