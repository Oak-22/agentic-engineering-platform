# GitHub delivery contracts

This package defines the portable boundary between AEP delivery governance
and GitHub's platform surface. It describes requests, results, and the
provider mapping; it does not own Git objects, worktrees, branches, or GitHub
metadata.

- `github-delivery-operation.schema.json` describes an operation request.
- `github-delivery-result.schema.json` describes the traceable result.
- `github-delivery-mapping.schema.json` describes the selected MCP provider,
  the ordered `fallbackOrder` a caller tries when a surface is unavailable,
  the `gh` fallback tool where one exists, and the operation's
  `agent-autonomous`, `human-authorized-agent`, or `human-only` class.

The canonical provider is GitHub's hosted official MCP server, reached over
HTTP (ADR-0004). Authentication is runtime-specific: Claude Code uses OAuth,
while Codex uses the interim PAT path documented by the server definition.
When the hosted server is unavailable, callers follow `fallbackOrder` (hosted
server, then `gh`) and record that `gh` ran; both
tiers keep the same semantic action and permission gate. Local Git and git-over-SSH remain responsible for object/tree
transport and worktree and branch mechanics. Native GitHub pull-request IDs,
URLs, and commit SHAs are returned as evidence, not copied into a competing
AEP state store.

Schema version 2 splits the earlier broad pull-request update and review
operations into readiness, Copilot-review, review-thread, and human-acceptance
actions. This lets adapters permit fixed-thread resolution without also
granting approve, request-changes, unresolve, retarget, close, or merge.
