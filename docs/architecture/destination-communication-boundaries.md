# Destination communication boundaries

AEP coordinates governed work across Git, GitHub, and Jira. It does not
replace the systems that own the records being coordinated.

| Surface | Owns | AEP's role |
| --- | --- | --- |
| AEP control plane | portable intent, authorization, execution evidence, and role/policy routing | validates, gates, and links the work |
| Local Git / git-over-SSH | objects, trees, worktrees, branches, commits, fetches, and pushes | uses governed local mechanics and records commit evidence |
| GitHub | repositories' pull requests, reviews, checks, merge state, and native URLs | communicates through the official GitHub MCP; uses `gh` only as an evidenced fallback |
| Jira | issue identity, workflow status, assignee, and human-visible planning fields | treats Jira as execution system of record and projects portable metadata through the Jira adapter |
| Atlassian Rovo MCP | the current Codex Jira/Confluence agent communication surface | provides the primary configured Jira tool path |
| Direct Atlassian MCP | a separate optional runtime surface | may be used only after its own authentication and permission path is verified; it is not silently interchangeable with Rovo |

## Role routing

| Role or skill | May communicate with | Boundary |
| --- | --- | --- |
| `deliver-governed-change` | all surfaces through the owning skill | coordinates the lifecycle; it does not create a second transport |
| `manage-git-workflow` | local Git, git-over-SSH, GitHub MCP, and evidenced `gh` fallback | owns branches, commits, pushes, pull requests, reviews, merges, and cleanup |
| `manage-jira-confluence` | Jira/Rovo, optional direct Atlassian MCP, and the Jira UI fallback | owns work-item state, planning fields, links, transitions, and verification |
| implementation/documentation agents | local repository files and local verification | do not publish GitHub or mutate Jira unless the governing delivery gate and policy allow it |
| release-operations agent | read-only delivery evidence by default | does not push, merge, or delete refs; a human release gate remains separate |

The role charters and permission policies are the identity-specific controls;
this document is the cross-system map they implement.

## GitHub communication

Codex and Claude use the same pinned official GitHub MCP server over local
stdio and the same explicit tool allowlist. The MCP layer owns GitHub platform
operations: pull-request reads, creation, updates, review writes, merges, and
workflow inspection. Git-over-SSH remains the transport for Git objects and
tree mechanics. The `gh` CLI is an optional fallback for an unavailable MCP
operation, not an alternate authority or protocol; the caller must preserve
the same semantic permission action and record the fallback reason.

## Jira communication

Jira is the authority for work-item state and human-visible planning fields.
The Jira adapter maps portable fields to deployment-specific Jira field IDs;
the state projection contract does not contain those IDs. AEP attempt and
telemetry evidence remains separate from Jira until a trustworthy telemetry
projection exists.

This repository's active Codex path uses the hosted Atlassian Rovo connector.
The checked-in `.mcp.json` preserves the direct Atlassian endpoint for Claude,
but the direct endpoint and Rovo are distinct integration surfaces. Their
authentication, availability, and permissions must not be conflated. A human
Jira UI is the fallback when the configured agent surface cannot complete an
authorized operation.

## Traceability rule

Keep native identifiers native: Jira issue keys and URLs, GitHub pull-request
numbers and URLs, branch names, and commit SHAs are evidence references. AEP
contracts may carry them in requests or results, but no adapter may create a
second authoritative copy of destination state.
