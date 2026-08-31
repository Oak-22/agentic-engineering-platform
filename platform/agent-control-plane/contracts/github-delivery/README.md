# GitHub delivery contracts

This package defines the portable boundary between AEP delivery governance
and GitHub's platform surface. It describes requests, results, and the
provider mapping; it does not own Git objects, worktrees, branches, or GitHub
metadata.

- `github-delivery-operation.schema.json` describes an operation request.
- `github-delivery-result.schema.json` describes the traceable result.
- `github-delivery-mapping.schema.json` describes the selected MCP provider
  and the optional `gh` fallback for each operation.

The canonical provider is the pinned official GitHub MCP server. Local Git and
git-over-SSH remain responsible for object/tree transport and worktree and
branch mechanics. Native GitHub pull-request IDs, URLs, and commit SHAs are
returned as evidence, not copied into a competing AEP state store.
