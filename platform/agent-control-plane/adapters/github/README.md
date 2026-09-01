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

The shared GitHub MCP server is a Docker `stdio` process. Its prerequisites
(Docker daemon, pinned image, `GITHUB_PERSONAL_ACCESS_TOKEN` presence) and the
independence of its failures from Atlassian's are in the
[shared pinned-server definition](../../agent-assets/mcp-servers/github/server.md).

When it is unavailable, callers fall back in the fixed order recorded as
`fallbackOrder` in [`github-delivery-mapping.json`](github-delivery-mapping.json):
the local MCP server, then a Codex Apps GitHub surface where the runtime
provides one, then `gh`. `gh` is a shell fallback, not a second primary
protocol. At every tier the caller performs the same semantic operation and
`github:pull_request:*` permission action, and records which tier ran and why
each earlier tier was unavailable.

The provider mapping is [`github-delivery-mapping.json`](github-delivery-mapping.json).
The shared pinned-server definition is [`../../agent-assets/mcp-servers/github/server.md`](../../agent-assets/mcp-servers/github/server.md).

`deliver-governed-change` coordinates the lifecycle, while
[`manage-git-workflow`](../../agent-assets/skills/manage-git-workflow/SKILL.md)
owns this adapter's GitHub and local-Git procedure. Implementation and
documentation roles may prepare local changes and evidence; they do not gain
publication or merge authority through this adapter.
