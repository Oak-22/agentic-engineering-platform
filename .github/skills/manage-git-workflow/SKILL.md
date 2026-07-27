---
name: manage-git-workflow
description: Govern local Git and GitHub delivery operations through explicit authority, scoped staging, feature branches, commits, pushes, pull requests, merges, and branch cleanup. Use whenever work may create or switch a branch, stage or commit changes, modify a remote, open or update a pull request, merge work, or delete Git refs.
---

# Manage Git Workflow

Keep implementation authority separate from publication authority. Infer only
the operations necessarily implied by the user's request, and do not treat file
editing as permission to change Git history or remote state.

## Resolve scope first

1. Inspect the current branch, worktree, remotes, tracking state, and relevant
   diff.
2. Identify unrelated or user-authored changes and keep them unstaged.
3. Check whether the current branch already has a pull request before deciding
   whether to extend it or create a new branch.
4. State the intended branch and publication scope before performing an
   authorized delivery workflow.
5. Stop for direction when the current branch contains work that does not
   belong in the requested change and isolation would materially change the
   delivery plan.

## Authority boundaries

Apply the narrowest matching authorization:

- Requests to inspect, explain, diagnose, review, or report status authorize
  read-only Git and GitHub operations only.
- Requests to edit, fix, implement, or build authorize working-tree changes
  and relevant local verification. They do not authorize staging, commits,
  branch changes, pushes, pull requests, merges, or branch deletion.
- A request to create or switch to a named branch authorizes only that local
  branch operation unless publication is also requested.
- A request to commit authorizes staging the scoped changes and committing
  them on the current non-default branch. On the default branch, ask whether
  to commit there or create a feature branch because neither choice is
  implicit. It does not authorize a push.
- A request to push authorizes pushing the scoped commits from the current
  approved branch. It does not authorize opening or merging a pull request.
- A request to open, create, publish, or submit a pull request authorizes the
  working-tree changes required by the stated outcome plus the necessary
  feature-branch creation or reuse, checkout, scoped commit, push, and pull
  request creation or update. Extend an existing pull request only when it
  already represents the same scoped outcome. It does not authorize merging
  or deleting branches.
- A request for a pull request from a specific branch requires using that
  branch rather than creating another one.
- A request to merge authorizes only the specified pull request and merge
  method. It does not authorize branch deletion unless cleanup is explicit.
- Force pushes, history rewrites, ref deletion, and direct pushes to the
  default branch always require explicit authorization naming that operation
  and target.

Do not ask repeatedly for an operation already authorized by the active
request. If the user expands or narrows the request, apply the newest scope.

## Publish a pull request

1. Prefer a focused feature branch based on the intended target branch.
2. Stage explicit paths; never use a broad staging command in a mixed
   worktree.
3. Review the staged diff and run the smallest relevant checks.
4. Commit with a concise outcome-oriented message.
5. Push the feature branch with upstream tracking.
6. Open a draft pull request unless the user explicitly requests
   ready-for-review status.
7. Include what changed, why, impact, and verification in the pull request.
8. Return the branch, commit, target, pull-request link, checks, and any
   unsubmitted work.

## Preserve recoverability

- Never discard unrelated modifications to obtain a clean worktree.
- Preserve generated or cache files created by verification unless they are
  known disposable outputs within the requested scope; do not stage them
  merely because a check created them.
- Prefer a separate worktree or another non-destructive isolation method when
  an authorized change must start from a different base.
- Re-read remote or pull-request state after writes.
- Treat merge, force push, rebase of published history, and branch deletion as
  distinct operations with distinct authority.
