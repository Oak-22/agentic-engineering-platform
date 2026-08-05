# Workbench-to-Delivery Branching

## Purpose

Keep exploratory capture easy without allowing repository history to outrun
the delivery model or the agent's edits to outrun the developer's visible
filesystem. Treat `main`, a private workbench, and delivery branches as three
different Git roles while using one primary checkout by default.

```text
one primary IDE checkout

  workbench/local       A ─ B ─ C ─ D       capture and shape
                          \   \     /
                           selected evidence
                                  │
  main ref              M0 ───────┼──────── M1 ───────── M2
                           \       │          \
  agent/AEPI-101          delivery A ─ PR ────┘
                                           \
  agent/AEPI-102                          delivery B ─ PR ─┘

  visible branch: workbench/local ⇄ agent/AEPI-101 ⇄ agent/AEPI-102
```

The IDE and agent operate on the same primary checkout and switch its visible
branch as work changes. Both delivery branches derive from current `main` at
their start. The workbench supplies selected evidence; it is not their
ancestry base or merge target.

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
- Do not use `main` for exploratory capture or leave it checked out merely to
  prove that it is the integration base. A clean ref can be the base without
  being the visible branch.

### Private workbench: capture stream

- Use one unpublished local branch in the primary checkout for low-friction
  observations, renames, experiments, and chore-like discoveries. Use
  `workbench/local` as the default name when no other name is required.
- Keep the workbench private. Pushing it changes its role and requires an
  explicit publication decision.
- Commit each coherent captured idea atomically. Atomic means one explainable
  idea, not that the final delivery boundary is already known.
- Do not treat time, directory proximity, or a workbench commit boundary as
  proof that changes belong in one delivery unit.

### Jira-keyed branch: delivery unit

- Create each ordinary delivery branch from current `main`, not from the
  workbench or another feature branch.
- Switch the primary checkout to the delivery branch before implementation so
  the IDE immediately reflects the selected delivery unit.
- Use `shape-repository-change` to partition workbench commits, files, or hunks
  into independently reviewable outcomes.
- Transfer only the selected evidence. A full commit may be cherry-picked when
  it maps cleanly to one outcome; otherwise restore selected paths or apply
  selected hunks and create new delivery commits.
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

## Primary-checkout transitions

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
   `.agents/skills/manage-git-workflow/scripts/cleanup_merged_delivery.py` from
   the disclosed primary workspace;
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

Run
`.agents/skills/manage-git-workflow/scripts/reconcile_local_deliveries.py`
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
