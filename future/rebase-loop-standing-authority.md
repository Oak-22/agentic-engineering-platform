# Standing authority for the rebase loop

Status: draft, not activated as Jira work. Delete this file when the delivery
pull request lands the units below.

## Context

The `Protect main` ruleset sets `strict_required_status_checks_policy: true`,
so a pull request merges only when its head contains the tip of `main`, and
every merge leaves the other open pull requests behind. The standard way to
bring one current — and the one the co-developed CameraTether repository
documents in `.github/CONTRIBUTING.md` — is an author-side loop:

```
git fetch origin && git rebase origin/main && git push --force-with-lease
```

CameraTether uses the bare lease; this plan admits only the explicit-SHA
form, for the reason unit 1 gives.

Two layers make that loop unavailable to an agent. `manage-git-workflow`
requires explicit authorization naming the operation and target for every
force push. Beneath it, the mechanical permission gate classifies every force
push — `--force`, `-f`, and `--force-with-lease` alike — as a global deny
(`platform/agent-control-plane/scripts/agent_permission_gate.py`,
`global_deny_reason`), a class its docstring defines as one no principal may
Allow, and `test_history_rewriting_push_stays_globally_denied` pins that. A
skill-level exception alone would be refused at runtime.

End state: an agent re-syncs the feature branch it published for the active
delivery unit on its own, through one narrowly shaped push the gate can
recognize, and every other force push stays denied. This plan narrows a
global-deny class; that is the decision it asks a reviewer to accept, and the
units are split so the gate change is reviewed on its own.

This plan is independent of
[rebase-without-re-review.md](rebase-without-re-review.md). Without that plan
each re-sync still triggers a fresh Copilot review; with it, a rebase-only
re-sync costs one guard run.

## How to read this plan

Each unit states **Touches**, **Mechanism**, **Claim**, and **Trace check**,
and is separately revertible. Unit 2 depends on unit 1: without the gate
change, the skill would authorize a push the gate refuses.

## Unit 1 — Admit one explicit-lease push in the gate

**Touches**
- `platform/agent-control-plane/scripts/agent_permission_gate.py`
- `platform/agent-control-plane/tests/test_agent_permission_gate.py`

**Mechanism** — `global_deny_reason` keeps denying bare `--force`, `-f`, and
bare `--force-with-lease`, and any force push whose target is `main`. It
exempts exactly one shape: `git push --force-with-lease=<branch>:<sha> origin
<branch>`, where `<branch>` equals the checked-out branch (`current_branch`,
already used by the gate) and matches the Jira-keyed delivery pattern
`<category>/<KEY>-<slug>`, and `<sha>` is a full 40-hex object name. The
exempted command falls through to the ordinary push classification, as a
non-force push to the same branch does. Bare `--force-with-lease` stays
denied because its lease is the local remote-tracking ref, which any fetch
between synchronization and push advances, so it can accept an intervening
writer's update; an explicit expected SHA cannot. The docstring changes from
"no principal may Allow" to name the one admitted shape.

**Claim** — The only force push the gate can admit is an explicit-SHA lease
onto the checked-out Jira-keyed delivery branch.

**Trace check** — The test file gains cases: the admitted shape on the
checked-out delivery branch is not globally denied; bare `--force-with-lease`,
`--force`, and `-f` stay denied; the admitted shape targeting `main`, a
branch other than the checked-out one, or an abbreviated SHA stays denied.
Falsification: remove the checked-out-branch comparison and the
other-branch case must fail.

## Unit 2 — Rebase-loop exception in the skill

Depends on unit 1.

**Touches**
- `platform/agent-control-plane/agent-assets/skills/manage-git-workflow/SKILL.md`
- `platform/agent-control-plane/agent-assets/skills/deliver-governed-change/references/governed-change-delivery.md`

**Mechanism** — Add a narrow exception beside the existing post-merge cleanup
exception in `SKILL.md`'s authority rules, which already carve a named local
branch deletion out of the general ref-deletion rule. During "Publish a pull
request" step 8 (synchronize current `main`), an agent may rebase the feature
branch it published for the active delivery unit onto `origin/main` and push
it with `--force-with-lease=<branch>:<sha>`, where `<sha>` is the remote head
`publish_delivery_branch.py` last reported as verified for that branch —
recorded before any fetch, so a later fetch cannot move the lease. Limits:
never `main`, never a branch the agent did not publish, never bare `--force`
or bare `--force-with-lease`. A rebase that stops on a conflict ends the
exception: the agent aborts the rebase and reports it rather than resolving
the conflict under standing authority, because a resolution changes reviewed
content. A rejected lease also ends it: someone else wrote the branch.
`governed-change-delivery.md` gains one sentence pointing its synchronize
step at the exception instead of restating it.

**Claim** — An agent following the skill brings its own behind pull request
current without asking, and still asks before any other force push, any
conflict resolution, or any push after a rejected lease.

**Trace check** —
`grep -n "force-with-lease" platform/agent-control-plane/agent-assets/skills/manage-git-workflow/SKILL.md`
returns the exception naming its limits, the conflict stop, and the
rejected-lease stop, and the general rule still lists force pushes and
history rewrites as requiring explicit authorization.
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
- **Global-deny precedent.** Unit 1 is the first exception to a class defined
  as unconditional. The next proposed exception will cite it; each should
  carry its own threat argument rather than inherit this one.
- **Shared branches.** The exception assumes one agent owns the delivery
  branch. A rejected lease is the signal that assumption broke, and it stops
  the loop rather than retrying.
