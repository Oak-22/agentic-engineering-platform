# Jira/Confluence (Atlassian Rovo MCP Server)

## Identity

- **Upstream service**: Atlassian Cloud (Jira, Confluence), via Atlassian's
  own hosted Rovo MCP Server.
- **Purpose**: gives an agent read/write access to Jira work items and
  Confluence pages for governed delivery tracking and knowledge capture.

## Runtime surfaces

This definition covers two distinct ways a runtime reaches the same Atlassian
Cloud site. They are not interchangeable and neither is a fallback for the
other:

| Surface | Runtime | Repository config | Default |
| --- | --- | --- | --- |
| Codex Apps Atlassian Rovo connector | Codex | none — the connector is hosted and enabled outside this repo | enabled |
| Direct Atlassian MCP endpoint | Claude | `.mcp.json` `mcpServers.atlassian` | enabled for Claude, absent from `.codex/config.toml` |

Codex must not add an `atlassian` MCP server entry. Enabling a direct
`atlassian` server under Codex reproduces the incident referenced below.

## Transport

- **Authoritative**: streamable HTTP, at
  `https://mcp.atlassian.com/v1/mcp/authv2`.
- Atlassian operates this endpoint as a hosted proxy in front of each user's
  Atlassian Cloud site; there is no self-hosted or stdio variant to fall back
  to.

## Scopes and credentials

- **Auth method**: OAuth 2.1, authorized interactively through each runtime's
  own browser-consent flow (no static API token or credential value is
  stored in any adapter config).
- **Scope**: whatever Atlassian Cloud permissions the authorizing user's
  account already holds on the connected site — the server does not grant
  scopes beyond the user's own access.
- **Known operational risk**: a redundant *direct* `atlassian` MCP server
  under Codex has repeatedly held an invalid rotating OAuth refresh token and
  failed on startup while the Rovo connector kept working; see
  `docs/operations/incidents/atlassian-mcp-oauth-refresh-token-invalid-2026-07-24.md`.
  The documented recovery is to keep that direct server disabled under Codex
  and use the Rovo connector — not to re-run its OAuth login on each failure.
  Re-authorization (logout/login) applies only when the direct endpoint is
  deliberately enabled for Claude and its own health check fails.

## Dependent skills

- [`manage-jira-confluence`](../../skills/manage-jira-confluence/SKILL.md) —
  primary consumer; all Jira/Confluence read, create, update, link,
  transition, and verify operations route through this server.
- [`deliver-governed-change`](../../skills/deliver-governed-change/SKILL.md) —
  delegates Atlassian operations to `manage-jira-confluence`, and so depends
  on this server transitively.

## Capabilities beyond tools

None declared. Treat this as a tools-only server unless a future integration
need surfaces resource or prompt capabilities.
