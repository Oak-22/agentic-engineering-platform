---
title: Move the GitHub MCP surface to a remote transport
summary: Replace the local digest-pinned Docker GitHub MCP server with a remote OAuth transport — the GitHub-hosted server near-term, a self-hosted remote deployment behind a GitHub App at enterprise scale.
adr: ADR-0004
status: accepted
date: 2026-08-31
scope: integration
affected_components:
  - platform/agent-control-plane
related_jira: [AEPI-119, AEPI-120, AEPI-121, AEPI-123]
related_confluence: []
amended: 2026-09-01
supersedes: []
---

# Move the GitHub MCP surface to a remote transport

## Context

AEP reaches GitHub platform operations through the official
`github-mcp-server`, currently run as a Docker image pinned by digest and
invoked over local stdio by both Codex (`.codex/config.toml`) and Claude
(`.mcp.json`). AEPI-119 established this shared, allowlisted surface; AEPI-120
added a Docker/pinned-image/token readiness check and a
`local MCP -> Codex Apps GitHub -> gh` fallback order because the local
transport fails whenever Docker is unavailable.

The stated benefit of the local pinned build is cross-runtime consistency: a
byte-identical server and identical tool allowlist for every runtime. Three
forces work against it:

- **Consistency is mostly a tool-surface property, not a binary property.**
  Two runtimes calling the same tool names against the same GitHub API
  converge regardless of transport, unless the server's tool surface drifts.
  AEPI-119 already guards that with a contract test
  (`configured_tools == mapping_tools`). The digest pin narrowly protects
  against an unannounced semantic change to a tool AEP already uses.
- **The pin is a standing security liability.** AEP now owns tracking
  upstream fixes to a process that holds a GitHub credential and can merge
  pull requests. A hosted server patches itself.
- **Docker-daemon dependency scales badly for AEP's stated direction.**
  Unsupervised and cloud agents need Docker-in-Docker or a mounted socket
  (a root-equivalent surface); every developer endpoint and CI runner needs a
  daemon; each session pays container cold-start latency. The three-deep
  fallback ladder in AEPI-120 is a symptom of a primary path that is not
  dependable.

The credential model is the larger concern behind all of this. A local
transport places a GitHub personal access token on every laptop and every CI
runner. A remote OAuth transport keeps the token off the endpoint, scoped to
the authorizing user's own permissions and centrally revocable; a self-hosted
remote service fronted by a GitHub App can broker short-lived installation
tokens so no human holds a PAT at all. A remote transport also gives one
place to log, allowlist, rate-limit, and kill-switch every MCP tool call,
which the local processes scatter.

"Codex Apps GitHub" already sits in the AEPI-120 fallback order, so AEP has
implicitly accepted a hosted-remote GitHub surface as a backup path.

## Decision

Move the GitHub MCP surface off the local pinned Docker transport to a remote
transport reached over HTTP with OAuth.

- **Near-term:** adopt GitHub's hosted remote MCP server with
  runtime-specific authentication: per-user OAuth for Claude Code and a
  dedicated fine-grained PAT for Codex until Codex supports the required
  confidential-client exchange.
  Both runtimes point at the same HTTPS endpoint — more uniform than the
  Docker path, not less. Accept that GitHub rolls the server version, with the
  existing tool-surface contract test as the drift guard.
- **Target state at enterprise scale:** a self-hosted remote deployment of the
  digest-pinned `github-mcp-server`, fronted by a GitHub App issuing
  short-lived installation tokens and an MCP gateway enforcing allowlist,
  audit, and per-principal policy. This keeps the pinned build and the central
  audit point while removing the per-endpoint daemon and the PAT-at-rest
  problem.

The local Docker image remains a supported developer-loop bootstrap while the
near-term migration is in progress; it is not the platform's primary path
after that.

## Consequences

- The AEPI-120 readiness check and fallback ladder collapse: the primary path
  no longer depends on Docker, and the fallback reduces toward `gh` for true
  outages.
- `github-delivery-mapping.json` gains a remote transport for the primary
  provider; the digest pin moves from a runtime-config concern to a
  deployment concern of the self-hosted service (target state) or disappears
  (near-term hosted).
- New shared dependency: the hosted server is an availability single point for
  every runtime. The self-hosted target replaces GitHub's SLO with one AEP
  owns.
- OAuth authorization and health-check procedures must be documented per
  runtime, mirroring the Atlassian direct-vs-Rovo split — the transports
  differ by runtime capability, and that is expected (ADR alignment with the
  destination-communication boundary work in AEPI-120).
- Credential rotation and revocation move from "reissue a PAT on every
  endpoint" to a central operation.

## Alternatives considered

- **Keep the local digest-pinned Docker image.** Rejected as the primary
  path: it does not scale to unsupervised agents or a large endpoint fleet,
  and it keeps a PAT on every endpoint. Retained only as a dev-loop bootstrap.
- **Local pinned Go binary, vendored and checksum-pinned, no Docker.** Removes
  the daemon dependency but keeps the PAT-at-rest and scattered-audit
  problems. A reasonable interim if the near-term hosted move stalls.
- **Self-hosted remote as the immediate step.** Rejected as the first move
  only because it front-loads the GitHub App and gateway build; the hosted
  server delivers most of the credential and daemon benefit sooner. It
  remains the target state.

## Amendment — 2026-09-01

Clarifies, does not reverse, the near-term decision. Connectivity to GitHub's
hosted server was verified from Claude Code on this date (the original record
noted it was not). Codex verification remains pending on MCP-client support for
supplying the pre-registered client secret during token exchange and a
successful `get_me` health check.

### "Hosted OAuth" means a pre-registered OAuth App

GitHub's authorization server (`https://github.com/login/oauth`, discovered via
the endpoint's RFC 9728 protected-resource metadata) supports the
authorization-code grant with PKCE and refresh tokens, but exposes **no
Dynamic Client Registration endpoint and no Client ID Metadata Document
(CIMD)**. A client cannot self-register. Every runtime that reaches the hosted
server must therefore carry a **pre-registered OAuth client** — a GitHub OAuth
App (or GitHub App) whose `client_id`, secret, and one registered loopback
redirect URI are provisioned out of band. There is no zero-configuration path.

### Near-term client model: per-developer, local

Until org-wide rollout, each contributor uses a user-owned OAuth App for each
runtime capable of completing the flow. Claude Code and Codex do not share a
client registration; the Codex registration remains inactive during its PAT
interim:

- each redirect URI exactly matches that runtime's loopback callback;
- the runtime adapter may identify the registration mechanism, but a
  developer-specific `client_id` belongs in machine-local config rather than
  committed shared config;
- Codex must not carry an incomplete active registration until its MCP client
  can supply the pre-registered client secret; released CLIs 0.151.0 and
  0.152.0 do not expose that input;
- no client secret is committed;
- the issued user token is scoped to that developer's own GitHub permissions
  and is centrally revocable by revoking the App authorization.

This is a deliberately local, single-developer credential. It is not shared
infrastructure.

### Trigger for re-registration

Org-wide adoption — more than one person relying on the surface, or use from
unsupervised / cloud agents — requires replacing the per-developer App with an
**org-owned OAuth App or GitHub App** that has a hosted (non-loopback) redirect
URI and a managed secret. That step is the on-ramp to the self-hosted target
state already described under *Decision*; it does not change the target.

### Local Docker tier removed

The original decision retained the digest-pinned Docker `github-mcp-server`
"while the near-term migration is in progress." The hosted transport is
verified on Claude Code and selected as the Codex target; the local tier is
removed rather than left disabled. Codex readiness is not claimed until its
MCP client supports the required client secret and the separate OAuth
registration passes `get_me`.

- `fallbackOrder` in `github-delivery-mapping.json` is now `["github-mcp",
  "gh"]`; the `github-mcp-local` provider and the commented Docker block in
  `.codex/config.toml` are deleted.
- The operational ladder is **hosted MCP → `gh`**. This is deliberate for an
  AI-first workflow: the MCP surface is the working path, and `gh` is the
  single evidenced fallback for a true outage — not a co-equal tier.
- The pinned Docker invocation is recoverable from Git history if the
  self-hosted target state under *Decision* is built. That target is unchanged;
  it would be a fresh deployment concern, not a restoration of the dev-loop
  bootstrap.

### Consequence for the drift guard

The tool-surface contract test remains the drift guard for the hosted server's
version. The new standing operational task is tracking OAuth App registrations:
one per developer today, consolidating to one org-owned registration at
rollout.

### Codex interim authentication path

The hosted endpoint and HTTP transport remain the selected near-term path, but
authentication cannot yet be uniform. GitHub's Codex installation guide
documents the hosted remote server with PAT authentication; it does not claim
that Codex can use hosted OAuth without a PAT. The live 0.151.0 exchange and
the released 0.152.0 configuration contract confirm that Codex cannot supply
the client secret GitHub requires for a pre-registered OAuth client.

Until that runtime capability lands:

- Claude Code continues using per-user OAuth against the hosted endpoint.
- Codex uses a dedicated fine-grained, least-privilege PAT against the same
  hosted endpoint, resolved from `GITHUB_MCP_PAT`; only the variable name is
  committed.
- The separately registered Codex OAuth App is retained but inactive.
- `get_me` is the readiness gate before the Codex MCP surface is considered
  operational.
- The PAT is an explicit interim exception to the no-PAT goal, not a reversal
  of the self-hosted GitHub App target state. Remove it once Codex can complete
  the confidential-client exchange.
