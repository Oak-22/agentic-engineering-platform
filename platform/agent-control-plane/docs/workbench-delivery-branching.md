# Workbench-to-Delivery Branching

## Purpose

Make the private workbench a recommended, first-class path for ongoing agent
co-programming while preserving the conventional direct-delivery path for
bounded work. Keep repository history from outrunning the delivery model or
the agent's edits from outrunning the developer's visible filesystem. Treat
`main`, delivery branches, and the optional workbench as different Git roles
while using one primary checkout by default.

```text
one primary IDE checkout

  workbench/local       A ─ B ─ C ─ D       recommended agent capture and shaping
                          \   \     /
                           selected evidence
                                  │
  main ref              M0 ───────┼──────── M1 ───────── M2
                           \       │          \
  fix/PROJ-101            direct outcome ─ PR ───┘
                                           \
  feature/PROJ-102                        selected B ─ PR ─┘

  visible branch: main or workbench/local ⇄ Jira-keyed delivery branch
```

The IDE and agent operate on the same primary checkout and switch its visible
branch as work changes. Bounded work may proceed directly from current `main`
to its delivery branch. When used, the workbench supplies selected evidence;
it is not a delivery branch's ancestry base or merge target. Every delivery
branch derives from current `main` at its start.

## Visibility invariant

- Treat the session's primary workspace root as the developer-visible checkout
  unless the developer explicitly identifies another open workspace.
- Perform ordinary capture and delivery in that checkout so the IDE Explorer,
  terminal, tests, and agent all observe the same files.
- Before editing, report the active repository root and branch. Report them
  again whenever either changes.
- Never silently redirect implementation to a secondary worktree. If the
  active execution directory differs from the primary workspace, disclose the
  exact path, branch, purpose, and expected visibility difference before
  editing there.
- Stop when the developer expects primary-checkout visibility but cannot see
  the active worktree. Either return execution to the primary checkout or have
  the developer intentionally open the secondary worktree.

## Branch roles

### `main`: integration base

- Keep local `main` clean and synchronized with `origin/main`.
- Derive ordinary delivery branches from current `main`.
- Merge reviewed delivery branches back into `main`.
- Do not use `main` for continuous capture or leave it checked out merely to
  prove that it is the integration base. A clean ref can be the base without
  being the visible branch.

### Private workbench: capture-and-stewardship stream

- Prefer the workbench for ongoing agent co-programming when observations,
  experiments, context switches, or changes across files and modules may
  alter the eventual delivery boundaries. When a Jira outcome is already
  bounded and this shaping buffer adds no value, create its delivery branch
  directly from current `main`.
- Use one unpublished local branch in the primary checkout for low-friction
  capture. Use `workbench/local` as the neutral persistent name.
- Keep the workbench private. Pushing it changes its role and requires an
  explicit publication decision.
- Commit each coherent captured idea atomically. Atomic means one explainable
  idea, not that the final delivery boundary is already known.
- Treat the workbench as evolving developer-intent state, not as an alternate
  integration branch. Regularly incorporate current `main` into it; never
  advance `main` by mirroring the workbench wholesale.
- Do not treat time, directory proximity, or a workbench commit boundary as
  proof that changes belong in one delivery unit.

### Jira-keyed branch: delivery unit

- Create each ordinary delivery branch from current `main`, not from the
  workbench or another feature branch.
- Name it `<category>/<JIRA-ISSUE-KEY>-<outcome-slug>`, deriving the category
  from the work item's governed `Class` field: `feature`, `fix`, `refactor`,
  `chore`, or `docs`. Use the full issue key and keep actor or runtime identity
  in structured provenance rather than the branch name.
- Switch the primary checkout to the delivery branch before implementation so
  the IDE immediately reflects the selected delivery unit.
- Use `shape-repository-change` to partition workbench commits, files, or hunks
  into independently reviewable outcomes.
- Transfer only the selected evidence. A full commit may be cherry-picked when
  it maps cleanly to one outcome; otherwise restore selected paths or apply
  selected hunks and create new delivery commits.
- Deliver foundational semantic changes before branches that rely on them.
  After a prerequisite merges, create dependent branches from the resulting
  updated `main`; independent successors may then proceed in parallel.
- Verify the assembled result against its Jira acceptance criteria. Workbench
  commits are capture checkpoints, while delivery commits describe the final
  implementation structure.

## Secondary worktree exceptions

Use another worktree only when one checkout cannot safely represent the active
work, such as:

- concurrent agents that must not write into the same filesystem;
- genuinely parallel delivery units that must remain independently runnable;
- a long-running experiment, server, or verification process that requires a
  stable checkout; or
- unrelated or user-authored changes that make branch switching unsafe.

For every exception:

1. assign one owner and one purpose to the worktree;
2. disclose its absolute path and branch before editing;
3. state whether the developer must open it in another IDE window or accepts
   that the primary Explorer will not show intermediate edits;
4. repeat the path and branch when reporting intermediate results;
5. do not transfer unrelated changes between worktrees; and
6. remove only the secondary worktree after its merge is verified and local
   cleanup is authorized.

Do not create a secondary worktree merely to keep `main` visibly frozen. Stop
when concurrent agents claim the same path, ownership is unclear, the target
worktree is dirty with unrelated work, or the developer cannot establish which
filesystem view is authoritative.

### Parallel governed delivery

Concurrent Jira deliveries are the one exception with tooling behind it. Claim
each through `delivery_worktrees.py` rather than by hand, so the Jira key,
branch, worktree path, base commit, and owning agent are recorded and a second
claim on either the branch or the directory is refused:

```bash
python3 platform/agent-control-plane/scripts/delivery_worktrees.py \
  create <category>/<JIRA-ISSUE-KEY>-<slug> --agent <opaque-agent-id>
python3 platform/agent-control-plane/scripts/delivery_worktrees.py list
python3 platform/agent-control-plane/scripts/delivery_worktrees.py overlap
```

Branches still come from the governed preparation operation, so a worktree
never starts from an unverified `main`. Integration stays serialized and
independently verified per delivery; only execution is parallel.

### Switching windows is not switching branches

The practical pattern is one stable editor window per worktree:

- a primary window stays on `workbench/local` for capture and stewardship;
- each concurrent delivery gets its own window on its own worktree and branch;
- the operator moves attention between windows while agents keep working.

The distinction matters because the two look similar and behave nothing alike.
Switching a window changes which delivery you are looking at and changes
nothing on disk. Switching a branch inside a worktree rewrites that worktree's
files underneath whatever is running in it, which is exactly the interference
separate worktrees exist to prevent. Make each window's Jira key, branch, and
worktree distinguishable — through its title, workspace name, or color — so the
two are never confused.

An agent must not modify another agent's worktree or change its checked-out
branch without explicit coordination.

## Primary-checkout transitions

### Main to direct delivery

1. Start from a bounded Jira outcome with explicit acceptance criteria.
2. Run the governed-task preflight.
3. Fetch the remote, switch the primary checkout to `main`, and update it by
   fast-forward only.
4. Create and switch to the Jira-keyed delivery branch from that current
   `main`.
5. Implement and verify only the selected delivery outcome.

### Workbench to delivery

1. Commit each coherent workbench idea and require a clean status before
   switching branches.
2. Run `shape-repository-change` against the bounded workbench evidence.
3. Fetch the remote, switch the primary checkout to `main`, and update it by
   fast-forward only.
4. Create and switch to the Jira-keyed delivery branch from that current
   `main`.
5. Transfer only the selected workbench commits, files, or hunks and verify the
   result against the delivery acceptance criteria.

Stop instead of stashing, discarding, or carrying dirty changes across the
switch automatically. Those actions change recoverability or scope and require
their own deliberate decision.

### Delivery cleanup

After a verified merge and authorized local cleanup:

1. run the verification and execution modes of
   `platform/agent-control-plane/agent-assets/skills/manage-git-workflow/scripts/delivery_cleanup.py pr` from the
   disclosed primary workspace;
2. require a clean delivery checkout whose `HEAD` matches the published pull
   request head;
3. fetch and fast-forward local `main` to the verified merge result;
4. return the primary checkout to the existing clean `workbench/local` branch,
   or leave `main` checked out when no workbench exists;
5. delete and verify the absence of the merged local delivery branch; and
6. remove a worktree directory only when it was an explicitly identified
   secondary-worktree exception.

Never delete the primary checkout directory during delivery cleanup.

### Repository-wide cleanup reconciliation

Per-delivery cleanup remains mandatory after each merge. Repository-wide
reconciliation is a safety net for local Jira-keyed branches left behind by a
skipped or interrupted cleanup or by work that predates the current workflow.

Run `platform/agent-control-plane/agent-assets/skills/manage-git-workflow/scripts/delivery_cleanup.py stale`
without `--execute` to fetch current remote state and classify every candidate.
Only branches with an exact-tip merged pull request, no live remote branch, no
worktree checkout, and no commits outside `origin/main` are safe automatic
cleanup candidates. Contained branches without matching pull-request evidence
require manual review. Checked-out, remote, unmerged, or uniquely committed
branches must be preserved.

An explicitly authorized `--execute` run deletes only the verified safe set by
normal branch deletion and verifies final absence. It never force-deletes,
removes worktrees, deletes remote branches, or changes Jira. Governed-task
preflight may report safe cleanup debt, but it remains read-only and does not
block task isolation solely because historical local branches exist.

## Dependencies and stacked branches

Prefer sequencing over stacking: merge the prerequisite delivery, update
`main`, and derive the dependent branch from that new base.

Use a deliberately stacked branch only when all of these are true:

1. the dependent outcome cannot be implemented or reviewed meaningfully
   against current `main`;
2. waiting for the prerequisite would impose a material cost;
3. the dependency and temporary pull-request base are explicit in Jira and
   GitHub; and
4. the owner accepts that the branch must be rebased or retargeted after the
   prerequisite merges.

Stop and request a human decision when dependency direction is ambiguous, a
selected commit mixes delivery units that cannot be separated safely, or a
stack would obscure the intended merge order.

## Local `main` guardrail

Enable the repository-owned pre-commit hook once per clone:

```bash
git config --local core.hooksPath .githooks
```

The hook rejects ordinary commits while `main` is checked out. It permits
commits on workbench and delivery branches. For a direct-to-`main` commit that
has been explicitly authorized, invoke the narrow bypass deliberately:

```bash
AEP_ALLOW_MAIN_COMMIT=1 git commit
```

Git hooks are local guardrails, not access control. Git's own `--no-verify`
option can skip them, and protected-branch rules remain the appropriate remote
enforcement surface.

## Remote enforcement on `main`

The `main` branch ruleset requires a pull request and the
`control-plane-guards` status check, produced by
`.github/workflows/control-plane-guards.yml`. A delivery branch therefore
reaches `main` only after the control-plane guards pass on its head commit and
an accountable human reviews it. The same ruleset requests an automatic GitHub
Copilot code review, which is advisory: it comments, and it neither approves
the pull request nor satisfies the required check.

This is the enforcement layer the local guardrail above cannot provide. See
[Control Plane Guards in CI](control-plane-guards-ci.md).
