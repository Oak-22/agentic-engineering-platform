# Destination communication boundaries

AEP coordinates governed work across Git, GitHub, and Jira. It does not
replace the systems that own the records being coordinated.

| Surface | Owns | AEP's role |
| --- | --- | --- |
| AEP control plane | portable intent, authorization, execution evidence, and role/policy routing | validates, gates, and links the work |
| Local Git / git-over-SSH | objects, trees, worktrees, branches, commits, fetches, and pushes | uses governed local mechanics and records commit evidence |
| GitHub | repositories' pull requests, reviews, checks, merge state, and native URLs | communicates through GitHub's hosted MCP server with runtime-specific authentication; falls back only to an evidenced `gh` |
| Jira | issue identity, workflow status, assignee, and human-visible planning fields | treats Jira as execution system of record and projects portable metadata through the Jira adapter |
| Atlassian Rovo MCP | Codex's default Jira/Confluence agent communication surface | provides the primary configured Jira tool path; needs no repository-checked-in server entry |
| Direct Atlassian MCP | a separate optional runtime surface, checked in for Claude only and disabled by default for Codex | may be used only after its own authentication and permission path is verified; it is not silently interchangeable with Rovo |

## What standardized communication means

Standardized here means one portable contract, one set of semantic actions,
one permission-gate namespace, one evidence shape, and one authority boundary
per destination — not one identical transport or one identical authentication
method across every runtime.

- **Shared:** the delivery operation and result contracts, the
  `github:*` / `jira:*` permission actions the gate enforces, the native
  identifiers recorded as evidence, and which system stays authoritative.
- **Runtime-specific and allowed to differ:** the concrete MCP server entry,
  its transport, and its credential flow. Codex reaches Jira through the
  hosted Codex Apps Atlassian Rovo connector; Claude reaches it through the
  direct Atlassian MCP endpoint in `.mcp.json`. Both satisfy the same
  contract; neither is a fallback for the other. GitHub, by contrast, is one
  hosted OAuth endpoint for both runtimes (ADR-0004) — uniform where it can
  be, divergent where a runtime's capability or incident history requires it.

Making two runtimes' transports identical is fine when it is the better design
— GitHub's hosted endpoint is shared deliberately — but it is not *required*
by this document, and must never be bought at the cost of reintroducing a
surface a runtime's incident history has already ruled out.

## Role routing

| Role or skill | May communicate with | Boundary |
| --- | --- | --- |
| `deliver-governed-change` | all surfaces through the owning skill | coordinates the lifecycle; it does not create a second transport |
| `manage-git-workflow` | local Git, git-over-SSH, GitHub MCP, and the evidenced `gh` fallback | owns branches, commits, bounded publication, pull-request preparation, review remediation, and cleanup; merge remains human |
| `manage-jira-confluence` | Jira/Rovo, optional direct Atlassian MCP, and the Jira UI fallback | owns work-item state, planning fields, links, transitions, and verification |
| implementation/documentation agents | local repository files and local verification | do not publish GitHub or mutate Jira unless the governing delivery gate and policy allow it |
| release-operations agent | read-only delivery evidence by default | does not push, merge, or delete refs; a human release gate remains separate |

The role charters and permission policies are the identity-specific controls;
this document is the cross-system map they implement.

## GitHub communication

Codex and Claude reach GitHub through GitHub's hosted MCP server at
`https://api.githubcopilot.com/mcp/` over HTTP with runtime-specific
authentication: Claude Code uses per-user OAuth, while Codex uses a dedicated
fine-grained PAT via `GITHUB_MCP_PAT`
([ADR-0004](adr/0004-move-github-mcp-to-a-remote-transport.md)). The MCP layer
owns GitHub platform operations: pull-request reads, creation, updates,
Copilot-review remediation, and workflow inspection. Git-over-SSH remains the
transport for Git objects and tree mechanics. The generalist may prepare a
governed pull request, but agent policies deny approval and merge.
[ADR-0005](adr/0005-stop-agent-delivery-at-human-acceptance.md) defines the
later GitHub App identity boundary.

### Readiness

The hosted server is ready when Claude Code has completed its first-use OAuth
consent or Codex has started with `GITHUB_MCP_PAT` available, and `get_me`
returns the authorizing user. Only authorization state is checked — no token
value is read into logs, evidence, or this repository. GitHub does not support
OAuth dynamic client registration, so the Claude Code authorization needs a
pre-registered OAuth client;
[`mcp-servers/github/server.md`](../../platform/agent-control-plane/agent-assets/mcp-servers/github/server.md)
carries the per-runtime procedure.

A failure names the server that failed. An Atlassian OAuth failure and a
GitHub authorization failure are independent conditions with independent
recovery against different endpoints; neither implies the other, and a message
about one is not evidence about the other.

### GitHub fallback order

When the hosted server is unavailable, callers fall back in this fixed order,
stopping at the first surface that can perform the operation:

1. the hosted GitHub MCP server with runtime-specific authentication (primary);
2. the `gh` CLI, as an explicit, evidenced fallback only.

There is no local MCP tier — the pinned Docker `github-mcp-server` that
preceded ADR-0004 was removed once the hosted transport was verified
(ADR-0004 amendment, 2026-09-01). Both tiers perform the same semantic
operation and the same `github:pull_request:*` permission action. The caller
records that `gh` ran and why the MCP surface was unavailable. `gh` is not an
alternate authority or protocol, and skipping straight to it without recording
the reason is not permitted.

## Jira communication

Jira is the authority for work-item state and human-visible planning fields.
The Jira adapter maps portable fields to deployment-specific Jira field IDs;
the state projection contract does not contain those IDs. AEP attempt and
telemetry evidence remains separate from Jira until a trustworthy telemetry
projection exists.

Codex reaches Jira through the hosted Codex Apps Atlassian Rovo connector.
Rovo needs no server entry in this repository; `.codex/config.toml` therefore
declares no `atlassian` MCP server. Claude reaches Jira through the direct
Atlassian endpoint in `.mcp.json`. The direct endpoint and Rovo are distinct
integration surfaces with separate authentication, availability, and
permissions, and must not be conflated or treated as fallbacks for each other.

The direct Atlassian MCP server is disabled by default for Codex. Enabling it
there reproduces the invalid-OAuth-refresh-token incident in
[`incidents/atlassian-mcp-oauth-refresh-token-invalid-2026-07-24.md`](../operations/incidents/atlassian-mcp-oauth-refresh-token-invalid-2026-07-24.md):
a failing redundant server that adds a startup warning while Rovo keeps
working. The resolution to that startup warning is to keep the direct server
disabled, not to re-run its OAuth login. A human Jira UI is the fallback when
the configured agent surface cannot complete an authorized operation.

## Traceability rule

Keep native identifiers native: Jira issue keys and URLs, GitHub pull-request
numbers and URLs, branch names, and commit SHAs are evidence references. AEP
contracts may carry them in requests or results, but no adapter may create a
second authoritative copy of destination state.
