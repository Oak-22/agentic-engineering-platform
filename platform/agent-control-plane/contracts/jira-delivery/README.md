# Jira delivery contracts

This package defines the portable boundary between AEP delivery governance
and Jira. Jira remains authoritative for work-item state and human-visible
planning metadata; AEP owns the portable contract and execution evidence.

- `jira-delivery-operation.schema.json` describes a work-item operation.
- `jira-delivery-result.schema.json` describes a traceable result.
- `jira-delivery-mapping.schema.json` describes the Atlassian/Rovo primary
  surface and explicit human/UI fallback.
- `jira-work-item-metadata.schema.json` is the Jira state projection contract.

Deployment field IDs stay in [`adapters/jira/`](../../adapters/jira/), and
runtime attempt history stays in `agent-run-attempt.schema.json`. The direct
Atlassian MCP configuration and the hosted Rovo connector are separate
surfaces; a deployment may use either only when its runtime authentication and
permissions are verified.
