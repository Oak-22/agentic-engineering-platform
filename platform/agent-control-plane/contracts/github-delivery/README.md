# GitHub delivery contracts

This package defines the portable boundary between AEP delivery governance
and GitHub's platform surface. It describes requests, results, and the
provider mapping; it does not own Git objects, worktrees, branches, or GitHub
metadata.

- `github-delivery-operation.schema.json` describes an operation request.
- `github-delivery-result.schema.json` describes the traceable result.
- `github-delivery-mapping.schema.json` describes the selected MCP provider,
  the ordered `fallbackOrder` a caller tries when a surface is unavailable,
  and the `gh` fallback tool for each operation.

The canonical provider is the pinned official GitHub MCP server, reached over
Docker `stdio`. When it is unavailable, callers follow `fallbackOrder`
(local MCP, then a Codex Apps GitHub surface, then `gh`) and record which tier
ran; every tier keeps the same semantic action and permission gate. Local Git
and git-over-SSH remain responsible for object/tree transport and worktree and
branch mechanics. Native GitHub pull-request IDs, URLs, and commit SHAs are
returned as evidence, not copied into a competing AEP state store.
