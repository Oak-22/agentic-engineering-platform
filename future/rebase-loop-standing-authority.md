# Standing authority for the rebase loop

Status: draft, not activated as Jira work. Delete this file when the delivery
pull request lands the unit below.

## Context

The `Protect main` ruleset sets `strict_required_status_checks_policy: true`,
so a pull request merges only when its head contains the tip of `main`, and
every merge leaves the other open pull requests behind. The standard way to
bring one current — and the one the co-developed CameraTether repository
documents in `.github/CONTRIBUTING.md` — is an author-side loop:

```
git fetch origin && git rebase origin/main && git push --force-with-lease
```

`manage-git-workflow` makes that loop a human prompt every time: its
authority rules require explicit authorization naming the operation and
target for every force push and history rewrite. An agent that has published
a feature branch cannot re-sync it after an unrelated merge without asking.

End state: an agent re-syncs the feature branch it published for the active
delivery unit on its own, and every other force push still needs explicit
authorization. The rules match CameraTether's, so one git habit holds in both
repositories.

This plan is independent of
[rebase-without-re-review.md](rebase-without-re-review.md). Without that plan
each re-sync still triggers a fresh Copilot review; with it, a rebase-only
re-sync costs one guard run.

## How to read this plan

The single unit states **Touches**, **Mechanism**, **Claim**, and
**Trace check**, and is separately revertible.

## Unit 1 — Rebase-loop exception

**Touches**
- `platform/agent-control-plane/agent-assets/skills/manage-git-workflow/SKILL.md`
- `platform/agent-control-plane/agent-assets/skills/deliver-governed-change/references/governed-change-delivery.md`

**Mechanism** — Add a narrow exception beside the existing post-merge cleanup
exception in `SKILL.md`'s authority rules, which already carve a named local
branch deletion out of the general ref-deletion rule. During "Publish a pull
request" step 8 (synchronize current `main`), an agent may
`git rebase origin/main` and `git push --force-with-lease` the feature branch
it published for the active delivery unit. Three limits: never `main`, never
a branch the agent did not publish, never bare `--force`. A rebase that stops
on a conflict ends the exception: the agent aborts the rebase and reports it
rather than resolving the conflict under standing authority, because a
resolution changes reviewed content. `governed-change-delivery.md` gains one
sentence pointing its synchronize step at the exception instead of restating
it.

**Claim** — An agent following the skill brings its own behind pull request
current without asking, and still asks before any other force push or any
conflict resolution.

**Trace check** —
`grep -n "force-with-lease" platform/agent-control-plane/agent-assets/skills/manage-git-workflow/SKILL.md`
returns the exception naming its three limits and the conflict stop, and the
general rule still lists force pushes and history rewrites as requiring
explicit authorization.
`python platform/agent-control-plane/scripts/validate_asset_registries.py`
passes.

## Verification

```
python platform/agent-control-plane/scripts/validate_asset_registries.py
python -m unittest discover -s platform/agent-control-plane/tests
```

Then a drill: with two open delivery pull requests, merge one and ask an agent
to bring the other ready for human review. Expected: it rebases and pushes
with lease without an authorization prompt, and the pull request's
`mergeStateStatus` leaves `BEHIND`.

## Risks

- **Approval dismissal.** `dismiss_stale_reviews_on_push` dismisses human
  approvals on every re-sync. It costs nothing while
  `required_approving_review_count` is 0; raising that count makes every
  re-sync cost a re-approval, the same tension CameraTether's
  `CONTRIBUTING.md` names.
- **Lease scope.** `--force-with-lease` without an explicit expected SHA
  compares against the local remote-tracking ref, which a background
  `git fetch` can advance. The exception relies on a single agent owning the
  branch; a branch shared with another writer is outside it.
