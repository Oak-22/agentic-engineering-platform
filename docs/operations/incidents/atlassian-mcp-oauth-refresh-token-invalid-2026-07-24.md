---
incident_id: atlassian-mcp-oauth-refresh-token-invalid-2026-07-24
status: investigating
severity: minor
component: codex-atlassian-mcp-integration
first_observed: 2026-07-24
last_observed: 2026-07-27
occurrence_count: 2
promotion_candidate: true
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

## Recurrence

On 2026-07-27, Atlassian MCP authentication failed again during Codex startup,
approximately three days after the first observed failure and subsequent
authorization attempt. Codex CLI `0.145.0`, running in a VS Code terminal,
reported:

```text
MCP client for `atlassian` failed to start: MCP startup failed:
failed to refresh OAuth tokens for server atlassian:
OAuth token refresh failed: Server returned error response:
unauthorized_client: refresh_token is invalid

MCP startup incomplete (failed: atlassian)
```

This recurrence occurred while testing whether the Atlassian MCP OAuth refresh
token would remain able to reauthenticate the client over time. Whether a
logout and fresh login restores access for this occurrence has not yet been
recorded. Concurrent client use, grant changes, password changes, and
permission changes also remain unverified.

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

Frequent interactive authorization is not expected. Atlassian uses rotating
refresh tokens, which should normally allow the client to refresh access
without repeating browser consent.

The investigation identifies stale refresh-token reuse after rotation as the
high-probability cause, but does not prove it. Atlassian disables a rotating
refresh token after a successful exchange and requires the client to persist
the replacement token. Codex has separately reported MCP OAuth failure modes
in which concurrent processes or sessions retain and later present stale
refresh tokens.

The short observed intervals make ordinary refresh-token inactivity expiry
unlikely. The remaining evidence does not identify the exact refresh request
that invalidated the credential, nor does it exclude a password change,
explicit grant revocation, permission or policy change, failure to persist a
rotated token, or another Atlassian or Codex integration defect.

## Investigation timeline

- Last confirmed successful Atlassian MCP call before the first occurrence:
  2026-07-23 at 16:49:30 PDT.
- First confirmed invalid-refresh-token response: 2026-07-24 at 11:32:59 PDT.
- The first invalidation therefore occurred within that 18-hour, 43-minute
  evidence window; its exact time is not recoverable from the available client
  logs.
- After reauthorization, the failure recurred during Codex CLI startup on
  2026-07-27, before the preserved session began at 09:52 PDT. The raw startup
  event timestamp was not retained, so a narrower recurrence window cannot be
  stated.

This timeline pins when invalidity was first observable, not when Atlassian
changed the server-side token state.

## Decision

Treat this as a recurring integration problem under active investigation.
Continue using OAuth while capturing authorization time, recurrence time, and
credential-refresh behavior. Do not switch authentication strategies until
the failure mechanism is identified.

## Recurrence evidence to capture

- occurrence date and elapsed time since authorization
- exact error text
- Codex version and surface
- whether multiple Codex sessions or clients used the Atlassian connection
- whether the Atlassian account password, grant, or permissions changed
- whether logout and fresh login restored access

## Resolution criteria

- Record whether `codex mcp logout atlassian` followed by
  `codex mcp login atlassian` restores access.
- Reauthorize, record the authorization time, and test after controlled elapsed
  intervals without concurrent clients.
- Compare the failure interval across another recurrence before concluding
  that the token has a fixed lifetime.
- Create or link a Jira defect for refresh-token rotation and credential
  persistence investigation.

## Reference

- [Atlassian OAuth 2.0 authorization-code grants](https://developer.atlassian.com/cloud/jira/software/oauth-2-3lo-apps/)
- [Atlassian rotating refresh-token flow and invalid-token causes](https://developer.atlassian.com/cloud/oauth/getting-started/refresh-tokens/)
- [Codex issue: refresh-token races across processes](https://github.com/openai/codex/issues/12755)
- [Codex issue: routed MCP OAuth tokens do not auto-refresh](https://github.com/openai/codex/issues/17265)
- [Atlassian Rovo MCP intermittent invalid-token fix](https://confluence.atlassian.com/cloud/blog/2026/01/atlassian-cloud-changes-jan-19-to-jan-26-2026)
