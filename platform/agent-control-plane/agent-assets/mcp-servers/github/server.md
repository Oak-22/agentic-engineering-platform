# GitHub MCP Server

## Identity

- **Upstream service**: GitHub, through GitHub's official
  [`github-mcp-server`](https://github.com/github/github-mcp-server).
- **Purpose**: gives AEP agents a shared, allowlisted tool surface for GitHub
  platform metadata, pull requests, reviews, and workflow inspection.
- **Pinned image**:
  `ghcr.io/github/github-mcp-server@sha256:fbec75de11c255213fa08d80fb166abe73d851fff631c51c0079872967720699`

The digest is the reviewed multi-architecture image reference used by the
Codex and Claude project configurations. Update it only with a deliberate
dependency review and synchronized runtime configuration change.

## Transport and credentials

- **Authoritative transport**: local stdio through Docker so Codex and Claude
  invoke the same server build and tool configuration.
- **Credential reference**: `GITHUB_PERSONAL_ACCESS_TOKEN`, resolved from the
  runtime environment. The token value must never appear in this repository.
- **Local server flags**: use `stdio` and the explicit `--tools` allowlist;
  do not rely on the server's broader default toolsets.

## Prerequisites and readiness

Because the transport is a Docker `stdio` process, the server is unavailable
until all three of these hold:

| Prerequisite | Ready when | Checked without exposing |
| --- | --- | --- |
| Docker daemon | `docker` can start a container | — |
| Pinned image | the digest above is present locally or pullable | — |
| Access token | `GITHUB_PERSONAL_ACCESS_TOKEN` is set in the environment | its value — only presence is checked |

A failed startup identifies **this** server by name. It is a separate
condition from an Atlassian OAuth failure: the two servers share no transport,
credential, or lifecycle, and a message about one carries no information about
the other. Do not report a GitHub outage on the strength of an Atlassian
warning, or vice versa.

## Fallback order

When the local server is unavailable, callers fall back in this fixed order
and stop at the first surface that can perform the operation:

1. **local GitHub MCP** (this definition) — primary;
2. **Codex Apps GitHub surface** — where the runtime provides one;
3. **`gh` CLI** — explicit, evidenced fallback only.

Every tier performs the same semantic operation and the same
`github:pull_request:*` permission action. The caller records which tier ran
and why each earlier tier was unavailable. The machine-readable order is
`fallbackOrder` in
[`adapters/github/github-delivery-mapping.json`](../../../adapters/github/github-delivery-mapping.json).

## Tool boundary

The shared allowlist is:

`get_me`, `get_file_contents`, `get_commit`, `list_commits`,
`list_pull_requests`, `search_pull_requests`, `pull_request_read`,
`actions_get`, `actions_list`, `get_job_logs`, `create_pull_request`,
`update_pull_request`, `pull_request_review_write`, `merge_pull_request`.

The server is not configured here for issue mutation, repository Git API file
or ref writes, repository settings, or workflow triggers. Read tools are
available without a delivery approval; mutation tools remain subject to the
runtime approval and AEP permission policy.

## Dependent assets

- [`adapters/github/`](../../../adapters/github/) — destination mapping and role
  boundary.
- [`manage-git-workflow`](../../skills/manage-git-workflow/SKILL.md) — local Git
  and GitHub delivery procedure.
- [`deliver-governed-change`](../../skills/deliver-governed-change/SKILL.md) —
  cross-system delivery lifecycle.

`gh` may be used only as the documented optional fallback when this MCP
surface cannot provide the required operation. It has the same semantic
permission action and must preserve the native GitHub evidence.
