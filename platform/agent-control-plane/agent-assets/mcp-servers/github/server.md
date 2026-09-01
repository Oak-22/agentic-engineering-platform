# GitHub MCP Server

## Identity

- **Upstream service**: GitHub, through GitHub's official
  [`github-mcp-server`](https://github.com/github/github-mcp-server).
- **Purpose**: gives AEP agents a shared, allowlisted tool surface for GitHub
  platform metadata, pull requests, reviews, and workflow inspection.
- **Authoritative transport**: GitHub's hosted remote server at
  `https://api.githubcopilot.com/mcp/`, reached over HTTP with per-user OAuth
  (ADR-0004). Codex and Claude both point at this one endpoint.

## Authorization

The hosted server authenticates each user through their own GitHub OAuth
consent; no personal access token is held on any endpoint or in this
repository. Scope is whatever the authorizing user's account already grants.

GitHub's endpoint does **not** support OAuth dynamic client registration, so a
first authorization needs an explicit client-registration strategy:

| Runtime | Command | Notes |
| --- | --- | --- |
| Codex | `codex mcp login github --oauth-client-registration cimd` | Falls back to a registered `--oauth-client-id` if CIMD is rejected. |
| Claude Code | authorize on first use of a `github` tool | Claude Code runs the browser consent itself for an `http` server in `.mcp.json`. |

**Health check** — the server is ready when `get_me` returns the authorizing
user. A failure here identifies **this** server by name; it is a separate
condition from an Atlassian OAuth failure (different endpoint, credential, and
lifecycle), and a message about one carries no information about the other.

## Fallback order

When the hosted server is unavailable, callers fall back in the fixed order
recorded as `fallbackOrder` in
[`adapters/github/github-delivery-mapping.json`](../../../adapters/github/github-delivery-mapping.json),
stopping at the first surface that can perform the operation:

1. **hosted GitHub MCP** (`https://api.githubcopilot.com/mcp/`) — primary;
2. **local GitHub MCP** — the dated Docker fallback below;
3. **`gh` CLI** — explicit, evidenced fallback only.

Every tier performs the same semantic operation and the same
`github:pull_request:*` permission action. The caller records which tier ran
and why each earlier tier was unavailable. `gh` is not an alternate authority
or protocol.

## Local Docker fallback (dated)

Superseded as the primary transport on 2026-08-31 by ADR-0004. Retained as a
dev-loop bootstrap and an offline fallback, not a default.

- **Pinned image**:
  `ghcr.io/github/github-mcp-server@sha256:fbec75de11c255213fa08d80fb166abe73d851fff631c51c0079872967720699`
- **Transport**: local `stdio` through Docker.
- **Credential**: `GITHUB_PERSONAL_ACCESS_TOKEN`, resolved from the runtime
  environment; its value never appears in this repository.
- **Prerequisites**: Docker daemon running, the pinned image present or
  pullable, and `GITHUB_PERSONAL_ACCESS_TOKEN` set (presence only — never the
  value).
- **Enabling it**: uncomment the `[mcp_servers.github-local]` block in
  `.codex/config.toml` (renaming it to `[mcp_servers.github]`), or restore the
  `stdio` `github` entry in `.mcp.json` from version history. Keep exactly one
  `github` server active per runtime.

Update the digest only with a deliberate dependency review.

## Tool boundary

The semantic surface is the same fourteen tools on every transport:

`get_me`, `get_file_contents`, `get_commit`, `list_commits`,
`list_pull_requests`, `search_pull_requests`, `pull_request_read`,
`actions_get`, `actions_list`, `get_job_logs`, `create_pull_request`,
`update_pull_request`, `pull_request_review_write`, `merge_pull_request`.

The hosted and local servers run the same `github-mcp-server` codebase, so the
tool names and behaviour match. The allowlist **mechanism** differs: the local
server takes an explicit `--tools=` flag, while the hosted server is scoped by
toolset (URL path segment or `X-MCP-Toolsets` header). AEP does not rely on the
transport-level filter for safety — the AEP permission policy gates every
mutation (`create_pull_request`, `update_pull_request`,
`pull_request_review_write`, `merge_pull_request`) regardless of which tools a
transport exposes. Read tools need no delivery approval; mutation tools remain
subject to the runtime approval and AEP permission policy.

## Dependent assets

- [`adapters/github/`](../../../adapters/github/) — destination mapping and role
  boundary.
- [`manage-git-workflow`](../../skills/manage-git-workflow/SKILL.md) — local Git
  and GitHub delivery procedure.
- [`deliver-governed-change`](../../skills/deliver-governed-change/SKILL.md) —
  cross-system delivery lifecycle.

`gh` may be used only as the documented optional fallback when the MCP surface
cannot provide the required operation. It has the same semantic permission
action and must preserve the native GitHub evidence.
