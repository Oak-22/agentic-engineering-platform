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
- `gh` is an optional shell fallback, not a second primary protocol. A caller
  must record why MCP was unavailable and preserve the same semantic operation
  and permission action.
- GitHub remains authoritative for pull-request state, checks, reviews, and
  native URLs. AEP stores only the traceable references needed for governed
  execution evidence.

The provider mapping is [`github-delivery-mapping.json`](github-delivery-mapping.json).
The shared pinned-server definition is [`../../agent-assets/mcp-servers/github/server.md`](../../agent-assets/mcp-servers/github/server.md).

`deliver-governed-change` coordinates the lifecycle, while
[`manage-git-workflow`](../../agent-assets/skills/manage-git-workflow/SKILL.md)
owns this adapter's GitHub and local-Git procedure. Implementation and
documentation roles may prepare local changes and evidence; they do not gain
publication or merge authority through this adapter.
