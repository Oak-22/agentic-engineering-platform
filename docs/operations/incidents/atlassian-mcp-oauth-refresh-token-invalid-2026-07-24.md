---
incident_id: atlassian-mcp-oauth-refresh-token-invalid-2026-07-24
status: resolved
severity: minor
component: codex-atlassian-mcp-integration
first_observed: 2026-07-24
last_observed: 2026-08-16
occurrence_count: 3
promotion_candidate: true
---

# Redundant Atlassian MCP server reported an invalid OAuth refresh token

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

The failing server was the separately configured `atlassian` MCP server, not
the plugin-backed Atlassian Rovo connector that Codex was already using. The
Codex startup warning therefore made Atlassian access appear unavailable even
while read/write Jira operations continued through the Rovo connector.

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

The startup symptom was reproduced on 2026-08-16 by toggling the `atlassian`
server in Codex settings. Enabling it produced the yellow OAuth refresh-token
and incomplete-startup warnings shown below; disabling it removed the
warnings.

![Codex terminal showing the separately enabled atlassian MCP server failing to
refresh its OAuth token during
startup.](assets/atlassian-mcp-oauth-refresh-token-invalid-codex-startup.png)

## Recovery

Disable the separately configured `atlassian` MCP server in Codex settings.
It is not required for the plugin-backed Atlassian Rovo connector used by
Codex in this environment. With the redundant server disabled, Codex starts
without the warning and Jira access through Rovo remains available.

![Codex terminal starting without an MCP warning after the redundant atlassian
server was disabled.](assets/atlassian-mcp-codex-startup-without-warning.png)

The Codex configuration confirms the two integration surfaces are independent:
the separately configured direct `atlassian` MCP server is disabled, while the
Atlassian Rovo plugin remains configured.

![Codex MCP settings showing the separately configured direct atlassian server
disabled.](assets/atlassian-direct-mcp-disabled.png)

![Codex plugin settings showing Atlassian Rovo configured as a
plugin.](assets/atlassian-rovo-plugin-configured.png)

During the earlier investigation, removing the stale local OAuth credential
and starting a fresh authorization flow was considered as a direct-server
recovery step:

```sh
codex mcp logout atlassian
codex mcp login atlassian
```

That reauthorization is unnecessary when the direct server is not intended to
be used. If it is deliberately enabled in the future, the browser consent flow
authorizes Codex to use the selected Atlassian site through the user's existing
permissions. Do not record access tokens, refresh tokens, authorization codes,
or other credentials in this report.

## Current assessment

This incident was a configuration and observability problem, not an outage of
the connector Codex was actually using. A redundant direct `atlassian` MCP
server held an invalid OAuth refresh token and attempted to start in every
Codex session. Its failure produced a visible warning, while the separate
plugin-backed Atlassian Rovo connector continued to provide Jira access.

The controlled settings toggle establishes which configured server emitted
the warning. It does not establish why that direct server's refresh token was
invalid, but that question is no longer operationally relevant while the
unused server remains disabled.

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

Close the incident as resolved. Keep the redundant direct `atlassian` MCP
server disabled and use the plugin-backed Atlassian Rovo connector. Reopen the
investigation only if the Rovo connector itself fails or there is a deliberate
need to use the direct server.

## Evidence to capture if reopened

- occurrence date and elapsed time since authorization
- exact error text
- Codex version and surface
- whether multiple Codex sessions or clients used the Atlassian connection
- whether the Atlassian account password, grant, or permissions changed
- whether logout and fresh login restored access

## Resolution evidence

- Enabling the direct `atlassian` MCP server reproduces the startup warning.
- Disabling that server removes the warning.
- With the direct server disabled, the plugin-backed Atlassian Rovo connector
  exposes read/write Jira operations; a read-only AEPI query provided
  non-mutating verification.

## Reference

- [Atlassian OAuth 2.0 authorization-code grants](https://developer.atlassian.com/cloud/jira/software/oauth-2-3lo-apps/)
- [Atlassian rotating refresh-token flow and invalid-token causes](https://developer.atlassian.com/cloud/oauth/getting-started/refresh-tokens/)
- [Codex issue: refresh-token races across processes](https://github.com/openai/codex/issues/12755)
- [Codex issue: routed MCP OAuth tokens do not auto-refresh](https://github.com/openai/codex/issues/17265)
- [Atlassian Rovo MCP intermittent invalid-token fix](https://confluence.atlassian.com/cloud/blog/2026/01/atlassian-cloud-changes-jan-19-to-jan-26-2026)
