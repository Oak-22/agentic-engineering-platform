# AEP Atlassian Information Model

Use this reference only for the Agentic Engineering Platform Atlassian site.
Resolve current names and keys from live Atlassian data before writing because
administrators can rename projects and spaces.

## Canonical surfaces

| Surface | Current name | Current key | Owns |
| --- | --- | --- | --- |
| Jira Product Discovery | Agentic Engineering Platform Discovery | `AEPD` | opportunities, hypotheses, prioritization, roadmap, and investment decisions |
| Jira Software | Agentic Engineering Platform Implementation | `AEPI` | epics, features, stories, tasks, defects, testing, and delivery status |
| Confluence | Agentic Engineering Platform | `AEP` | architecture, research, decisions, runbooks, experiment designs, and evidence-backed conclusions |

## Relationship model

```text
                         AEP Confluence
                       /                \
        evidence and rationale          design and outcomes
                     /                    \
            AEPD Discovery ----------> AEPI Implementation
                    native delivery relationship
```

The shorthand `AEPD -> AEPI -> AEP` describes promotion, not a one-way
information flow. Confluence supports both discovery and implementation.

## Promotion rule

Promote an AEPD idea into AEPI when it has:

1. a clear problem or opportunity;
2. enough evidence to justify evaluation or investment;
3. an expected outcome;
4. an explicit priority or roadmap horizon; and
5. delivery scope that can be expressed as an epic, feature, or task.

Create the AEPI artifact, attach it through Jira Product Discovery's native
delivery relationship, and link the canonical AEP page when a design,
decision, or experiment record exists.

## Duplication rule

- Keep strategic scoring and roadmap placement in AEPD.
- Keep execution state and acceptance criteria in AEPI.
- Keep durable reasoning and evidence in AEP.
- Summarize and link across surfaces; do not maintain three full copies.

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
