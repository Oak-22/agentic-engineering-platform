---
incident_id: atlassian-mcp-oauth-refresh-token-invalid-2026-07-24
status: monitoring
severity: minor
component: codex-atlassian-mcp-integration
first_observed: 2026-07-24
occurrence_count: 1
promotion_candidate: false
---

# Atlassian MCP OAuth refresh token became invalid

## Observation

On 2026-07-24, a Jira metadata read through the Atlassian MCP connection
failed after the connection had worked the previous day. The connector
reported:

```text
OAuth token refresh failed:
unauthorized_client: refresh_token is invalid
```

Codex `/mcp` subsequently showed the `atlassian` server with OAuth
authentication but no available tools.

## Recovery

Remove the stale local OAuth credential and start a fresh authorization flow:

```sh
codex mcp logout atlassian
codex mcp login atlassian
```

The browser consent flow authorizes Codex to use the selected Atlassian site
through the user's existing permissions. Do not record access tokens, refresh
tokens, authorization codes, or other credentials in this report.

## Current assessment

Daily interactive authorization is not expected. Atlassian uses rotating
refresh tokens, which should normally allow the client to refresh access
without repeating browser consent.

One occurrence is insufficient to establish a structural defect. Plausible
causes include an isolated credential-state problem, failure to persist a
rotated refresh token, concurrent reuse of an invalidated token, revocation,
or an integration defect.

## Decision

Treat this as a potentially recurring integration problem in monitoring state.
Continue using OAuth and do not switch authentication strategies based on one
occurrence.

Escalate to an active defect investigation if the failure recurs.

## Recurrence evidence to capture

- occurrence date and elapsed time since authorization
- exact error text
- Codex version and surface
- whether multiple Codex sessions or clients used the Atlassian connection
- whether the Atlassian account password, grant, or permissions changed
- whether logout and fresh login restored access

## Resolution criteria

- **No recurrence:** retain as a minor operational observation.
- **Recurrence:** create a Jira defect, preserve the new evidence, and
  investigate refresh-token rotation and credential persistence.

## Reference

- [Atlassian OAuth 2.0 authorization-code grants](https://developer.atlassian.com/cloud/jira/software/oauth-2-3lo-apps/)
