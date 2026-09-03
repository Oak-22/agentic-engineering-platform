# GitHub MCP Server

## Identity

- **Upstream service**: GitHub, through GitHub's official
  [`github-mcp-server`](https://github.com/github/github-mcp-server), run by
  GitHub as a hosted service.
- **Purpose**: gives AEP agents a shared, allowlisted tool surface for GitHub
  platform metadata, pull requests, reviews, and workflow inspection.
- **Authoritative transport**: GitHub's hosted remote server at
  `https://api.githubcopilot.com/mcp/`, reached over HTTP (ADR-0004). Codex and
  Claude both point at this one endpoint; authentication is runtime-specific.

## Authorization

The hosted server accepts a GitHub access token. Claude Code obtains one through
the user's GitHub OAuth consent. Codex temporarily supplies a dedicated
fine-grained, least-privilege PAT by environment-variable reference because its
current hosted-OAuth client
cannot complete GitHub's confidential-client exchange. No credential value is
stored in this repository.

GitHub's endpoint does **not** support OAuth dynamic client registration or a
Client ID Metadata Document. A runtime using OAuth must therefore use a
pre-registered OAuth client (a GitHub OAuth App or GitHub App) provisioned out
of band. Claude Code uses that model today. Codex's separate registration is
retained but inactive while its interim PAT path is in force. See the ADR-0004
amendment (2026-09-01) for the client model and retirement trigger.

| Runtime | First authorization | Client registration |
| --- | --- | --- |
| Claude Code | authorize on first use of a `github` tool; Claude Code runs the browser consent itself | a pre-registered OAuth client is configured in Claude Code's machine-local runtime settings; its registration values are not committed |
| Codex | start Codex with `GITHUB_MCP_PAT` available, then verify `get_me` | `.codex/config.toml` names the variable; the PAT value stays in a local credential store |

**Codex readiness note (2026-09-01).** A live authorization with Codex CLI
0.151.0 reached the registered loopback callback, then failed at GitHub's token
exchange because no access token was returned. The released 0.151.0 and 0.152.0
configuration types expose `client_id`, `callback_url`, and `callback_port`, but
no client-secret input. GitHub requires the client secret at its token endpoint,
so a pre-registered GitHub OAuth App cannot yet complete this Codex flow. Do not
add an undocumented `client_secret_env_var` setting: these releases do not wire
it into the OAuth exchange.

The separately registered Codex OAuth App may be retained for a future Codex
release that adds confidential-client support. Its title is descriptive only;
it is not the MCP server name. The MCP server remains `github`.

### Codex interim path: hosted remote plus PAT

The interim path preserves the selected hosted transport and changes only the
Codex authentication mechanism:

1. Create a dedicated fine-grained, least-privilege GitHub PAT for this MCP
   surface.
2. Store it in a local credential store; never put the value in TOML, `.env`,
   repository files, or shell history.
3. Make it available to the Codex process as `GITHUB_MCP_PAT`. The checked-in
   config contains only `bearer_token_env_var = "GITHUB_MCP_PAT"`.
4. Start a fresh Codex process and verify readiness by calling `get_me`.
5. Retire the PAT path when a released Codex MCP client can send the registered
   OAuth client secret and the separate OAuth App passes the same health check.

Credential creation and process injection are operator actions, not implied by
this documentation change. The PAT should grant only the repository and
organization permissions needed by the configured MCP tools.

**Health check** — the server is ready when `get_me` returns the authorizing
user. A failure here identifies **this** server by name; it is a separate
condition from an Atlassian OAuth failure (different endpoint, credential, and
lifecycle), and a message about one carries no information about the other.

## Fallback

When the hosted server is unavailable, the only fallback is the `gh` CLI,
recorded as the terminal entry in `fallbackOrder` in
[`adapters/github/github-delivery-mapping.json`](../../../adapters/github/github-delivery-mapping.json).
`gh` performs the same semantic operation and the same `github:pull_request:*`
permission action; it is an explicit, evidenced fallback, not an alternate
authority or protocol. The caller records that `gh` ran and why the MCP
surface was unavailable.

There is no local MCP tier. The pinned Docker `github-mcp-server` invocation
that preceded ADR-0004 is recoverable from Git history if a self-hosted
deployment is ever built (the ADR-0004 target state).

## Tool boundary

The provider capability map is seventeen tools:

`get_me`, `get_file_contents`, `get_commit`, `list_commits`,
`list_pull_requests`, `search_pull_requests`, `pull_request_read`,
`actions_get`, `actions_list`, `get_job_logs`, `create_pull_request`,
`update_pull_request`, `update_pull_request_branch`, `request_copilot_review`,
`add_reply_to_pull_request_comment`, `pull_request_review_write`,
`merge_pull_request`.

The hosted server is scoped to this set by toolset (URL path segment or
`X-MCP-Toolsets` header). AEP does not rely on that transport-level filter for
safety: the AEP permission policy classifies every mutation by its semantic
action regardless of which tools the transport exposes.

Codex exposes the read and governed-delivery subset explicitly and omits
`merge_pull_request`. Its approved delivery tools avoid redundant runtime
prompts only after the AEP hook classifies their arguments. Claude may see the
provider's wider surface, so the permission gate permits known reads, maps
known mutations, and denies unclassified GitHub tools. Transport exposure is
never acceptance authority.

Agent-autonomous operations cover draft creation, maintenance, current-base
sync, Copilot review requests, replies, fixed-thread resolution, and readiness.
Approve, request-changes, create-ready, close, reopen, retarget, unresolve, and
merge remain human-only. The mapping and gate apply the same semantic actions
to the evidenced `gh` fallback.

GitHub rolls the hosted server's version. The tool-surface contract test
(`configured_tools == mapping_tools`) is the drift guard against an
unannounced change to a tool AEP already uses.

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
