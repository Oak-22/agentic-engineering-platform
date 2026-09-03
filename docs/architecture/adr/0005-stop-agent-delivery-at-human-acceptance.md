---
title: Stop agent delivery at human acceptance
summary: Let a governed coordinator prepare a Copilot-clean pull request autonomously while reserving acceptance and merge for a human identity.
adr: ADR-0005
status: accepted
date: 2026-09-03
scope: platform
affected_components:
  - platform/agent-control-plane
related_jira:
  - AEPI-128
related_confluence: []
supersedes: []
---

# Stop agent delivery at human acceptance

## Context

AEP originally asked for human approval at every shared-state delivery step.
That improved traceability but made Codex delivery unusable: Codex cannot turn
the permission gate's `ask` response into a supported approval prompt, so the
gate correctly converted it to a denial. Operators repeatedly had to push a
branch, return to the agent for review remediation, and repeat the handoff.

The actual acceptance boundary is later. A delivery branch, draft pull
request, Jira update, base synchronization, and Copilot remediation remain
correctable. Accepting the result into `main` is the consequential decision.
Repository policy should preserve that decision without imposing a human turn
on every correctable operation leading to it.

## Decision

An explicit `deliver-governed-change` invocation authorizes the generalist
coordinator to carry a bounded outcome through a pull request ready for human
review. Ordinary implementation requests remain local.

The autonomous path includes scoped Jira delivery mutations, deterministic
same-branch publication, draft pull-request creation and maintenance, current
`main` synchronization, required-check and Copilot remediation, fixed-thread
reply and resolution, and the ready-for-review transition. Specialists retain
their destination-write denials.

Agents may never approve, request changes, merge, close, reopen, retarget, or
unresolve the pull request. The accountable human reviews and merges directly
in GitHub. After GitHub records that human merge, the coordinator may verify
it, perform deterministic local cleanup without deleting the remote branch,
record cleanup debt, and align Jira with the merged truth.

Direct `git push` remains approval-gated. The autonomous path uses
`publish_delivery_branch.py`, which accepts no arbitrary refspec and permits
only a clean Jira-keyed current branch, non-rewriting integration, and a push
to the identically named remote branch.

This is the immediate workflow boundary, not the final identity boundary. The
target state uses a repository-scoped GitHub App with short-lived installation
tokens. GitHub rules prevent that App from updating `main`, and agent runtimes
receive no human PAT, SSH, or `gh` credential. The target is not considered
active until its negative verification proves the App cannot push, merge, or
otherwise update `main`.

## Consequences

- Governed delivery no longer incurs a prompt turn for each branch, Jira, PR,
  or Copilot-remediation write.
- The merge click becomes the single intentional human acceptance point.
- Tool names alone are insufficient authorization: multi-purpose GitHub tools
  are classified from their arguments before policy evaluation.
- Phase 1 still relies on repository policy and deterministic wrappers around
  a human credential; it is a workflow guardrail, not hard identity isolation.
- Phase 2 requires a separately authorized GitHub App and ruleset rollout.

## Alternatives considered

- **Keep approval on every shared write.** Rejected because it turns Codex's
  unsupported approval state into repeated hard stops and adds prompt latency
  without improving the final acceptance boundary.
- **Allow unrestricted feature-branch push and PR writes.** Rejected because
  arbitrary refspecs and broad review methods erase the distinction between
  delivery preparation and human acceptance.
- **Let the agent merge after checks pass.** Rejected because CI and Copilot
  evidence support a human decision; they do not replace accountable human
  acceptance.
