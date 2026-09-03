# GitHub App publisher rollout

## Purpose

Turn ADR-0005's agent-versus-human boundary into GitHub-enforced identity.
This is the separately authorized Phase 2 rollout. Repository policy must not
claim it is active merely because Phase 1 is installed.

## Publisher identity

Create one organization-owned GitHub App installed only on
`Oak-22/agentic-engineering-platform`. Grant the minimum repository
permissions needed by the verified delivery tool surface:

| Permission | Access | Purpose |
| --- | --- | --- |
| Metadata | Read | Resolve repository and pull-request identity |
| Contents | Read and write | Publish Jira-keyed delivery branches |
| Pull requests | Read and write | Create and maintain draft pull requests and review threads |
| Checks | Read | Verify required-check state |
| Actions | Read | Inspect workflow runs and job logs |

Do not grant administration. Do not install the App organization-wide. Add a
permission only after a failing readiness check proves the listed surface is
insufficient.

Issue short-lived installation tokens in a credential broker outside model
context. Agent runtimes receive only the installation token required for the
current run. Remove the human PAT, SSH identity, and authenticated `gh`
fallback from those runtimes before calling the boundary active.

## GitHub enforcement

Keep the existing `Protect main` ruleset independent and bypass-free. Add a
second active ruleset, `Human-only main updates`, targeting the default branch:

- restrict updates to `main`;
- give the accountable human administrator bypass only for pull requests;
- give the publisher App no bypass;
- prohibit force pushes and deletion;
- retain the existing required pull request, current-branch, required-check,
  and thread-resolution rules.

The publisher App may update only Jira-keyed delivery refs. GitHub owns the
hard denial on `main`; repository instructions and hooks are defense in depth.

## Activation verification

Record the App installation ID, App slug, repository, ruleset ID, and audit-log
links in the governing Jira delivery. Use a disposable Jira-keyed branch and
test pull request, then verify all of the following with an App installation
token:

1. `get_me` or the equivalent identity response names the App installation,
   not the human account.
2. A delivery-branch push succeeds and the App can create, update, synchronize,
   and mark its pull request ready.
3. The App can read checks, request Copilot review, reply to a review thread,
   and resolve a thread after publishing its fix.
4. A non-force push targeting `main` is rejected by GitHub.
5. Pull-request approve, request-changes, close, retarget, unresolve, and merge
   attempts are rejected or unavailable to the App.
6. The human account can review and merge the ready pull request through the
   normal GitHub UI.
7. Agent runtime inspection finds no human PAT, SSH, or authenticated `gh`
   credential path.

Use no-op or disposable targets for negative tests and preserve the returned
GitHub request identifiers. If any forbidden action succeeds, immediately
disable the App installation and keep Phase 2 inactive.

## Rollback

Disable the App installation, revoke outstanding installation tokens, and
remove only the `Human-only main updates` ruleset after recording its native
audit evidence. Do not weaken or remove `Protect main`. Restore a human
credential to an agent runtime only as an explicitly documented temporary
exception; otherwise return to the manual publication boundary.
