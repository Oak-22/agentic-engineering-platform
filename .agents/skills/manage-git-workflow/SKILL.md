---
name: manage-git-workflow
description: Govern local Git and GitHub delivery operations through explicit authority, scoped staging, feature branches, commits, pushes, pull requests, merges, and branch cleanup. Use when work may create or switch a branch, stage or commit changes, modify a remote, publish or update a pull request, merge work, delete Git refs, or when deliver-governed-change delegates a source-control operation.
---

# Manage Git Workflow

Keep implementation authority separate from publication authority. Infer only
the operations necessarily implied by the user's request, and do not treat file
editing as permission to change Git history or remote state.

## Coordination boundary

Own Git and GitHub operations. When `deliver-governed-change` coordinates the
larger delivery unit, accept its resolved Jira key, outcome, scope, and current
delivery phase as inputs. Preserve this skill's authority checks for every Git
mutation.

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

## Run an interactive preflight

Before an authorized commit or publication workflow, summarize:

- repository, branch, upstream, and requested operations;
- changes proposed for inclusion and any exclusions;
- proposed commit boundaries and concise messages;
- checks to run before publication.

Proceed without another question when the request already authorizes the
operations, the scope is coherent, the branch is permitted, and publication
is non-destructive. When clarification is necessary, ask the smallest set of
material questions together and recommend a default for each. Do not ask the
user to reconfirm facts or operations already established by the request.

Clarify when:

- the repository is ambiguous or the request spans multiple repositories;
- the active branch is the default branch and a commit or push would require a
  choice between direct work and a feature branch;
- changes represent unrelated outcomes that should not share a commit;
- untracked, generated, secret-like, or unexpectedly large files make
  inclusion uncertain;
- the remote, upstream, divergence, or existing pull request changes the safe
  publication path.

Interpret “all” or “everything” as all appropriate current changes in the
named repository, not permission to cross repository boundaries, include
credentials or disposable output, collapse unrelated outcomes into one
commit, or perform operations beyond those explicitly requested.

## Link Jira work through branch names

When a Jira work item governs the change, include its key in the feature
branch name:

```text
agent/AEPI-16-neutral-agent-assets
```

Keep commit subjects concise, imperative, and outcome-oriented. Leave Jira
keys and model or runtime names out of commit subjects unless the user
explicitly requests them.

Record agent provenance as structured execution metadata in the governed
work-item, telemetry, or attempt-history system. Preserve human accountability
through assignment, review, and approval records.

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
- A request to clean up a named local delivery unit after merge authorizes
  removal of its verified linked worktree, deletion of its local feature
  branch, and pruning of stale worktree metadata. It does not authorize
  deleting a remote branch or any other worktree.
- Force pushes, history rewrites, ref deletion, and direct pushes to the
  default branch always require explicit authorization naming that operation
  and target. The local feature-branch deletion included in a named
  post-merge cleanup request is the narrow exception defined above.

Do not ask repeatedly for an operation already authorized by the active
request. If the user expands or narrows the request, apply the newest scope.

## Publish a pull request

1. Prefer a focused feature branch based on the intended target branch.
2. Stage explicit paths; never use a broad staging command in a mixed
   worktree.
3. Review the staged diff and run the smallest relevant checks.
4. Commit with a concise, outcome-oriented message.
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

## Clean up a merged delivery worktree

Resolve and verify the complete target before mutating local state:

1. Identify the pull request and confirm its head branch, base branch, head
   identifier, merged state, merge result, and merge time.
2. Fetch the remote base and verify the recorded merge result is reachable
   from it.
3. Resolve the feature branch's linked worktree through Git metadata. Do not
   infer the directory from its name.
4. Require an empty worktree status, including untracked files, and verify
   `HEAD` matches the pull request's published head identifier.
5. Remove the linked worktree without force.
6. Delete the local feature branch normally when Git recognizes it as merged.
   After a squash merge, force-delete only when the pull-request, head, merge,
   and target-branch checks above all succeeded.
7. Prune stale worktree metadata and re-read the worktree and branch lists.
8. Report whether GitHub already deleted the remote branch. Delete it only
   when remote cleanup was explicitly authorized.

Stop without deletion when the pull request is open or unknown, the target
does not contain the merge result, the worktree is dirty, its branch or `HEAD`
does not match the pull request, or more than one target remains plausible.
