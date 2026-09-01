# GitHub Adapter

This is AEP's GitHub destination boundary. It translates the portable GitHub
delivery contracts in [`../../contracts/github-delivery/`](../../contracts/github-delivery/)
into the official GitHub MCP server's tools and, only when explicitly
justified by an unavailable MCP surface, the equivalent `gh` fallback.

## Responsibility split

- Local Git and git-over-SSH own Git objects, trees, worktrees, branches,
  commits, fetches, and pushes.
- GitHub MCP owns GitHub platform metadata and operations such as pull-request
  reads, creation, review, update, merge, and workflow inspection.
- GitHub remains authoritative for pull-request state, checks, reviews, and
  native URLs. AEP stores only the traceable references needed for governed
  execution evidence.

## Availability and fallback

The shared GitHub MCP surface is GitHub's hosted remote server at
`https://api.githubcopilot.com/mcp/`, reached over HTTP with per-user OAuth
(ADR-0004). Its authorization procedure, health check, and the independence of
its failures from Atlassian's are in the
[shared server definition](../../agent-assets/mcp-servers/github/server.md).

When it is unavailable, callers fall back in the fixed order recorded as
`fallbackOrder` in [`github-delivery-mapping.json`](github-delivery-mapping.json):
the hosted server, then the dated local Docker server (`github-mcp-local`,
disabled by default), then `gh`. `gh` is a shell fallback, not a second
primary protocol. At every tier the caller performs the same semantic
operation and `github:pull_request:*` permission action, and records which
tier ran and why each earlier tier was unavailable.

The provider mapping is [`github-delivery-mapping.json`](github-delivery-mapping.json).
The shared server definition is [`../../agent-assets/mcp-servers/github/server.md`](../../agent-assets/mcp-servers/github/server.md).

`deliver-governed-change` coordinates the lifecycle, while
[`manage-git-workflow`](../../agent-assets/skills/manage-git-workflow/SKILL.md)
owns this adapter's GitHub and local-Git procedure. Implementation and
documentation roles may prepare local changes and evidence; they do not gain
publication or merge authority through this adapter.
