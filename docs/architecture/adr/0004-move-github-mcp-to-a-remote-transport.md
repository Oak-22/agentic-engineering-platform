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

- **Near-term:** adopt GitHub's hosted remote MCP server with per-user OAuth.
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
