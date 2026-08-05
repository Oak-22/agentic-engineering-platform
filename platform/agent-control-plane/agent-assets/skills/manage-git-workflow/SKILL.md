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

Read
[the workbench-to-delivery branching contract](../../../platform/agent-control-plane/docs/workbench-delivery-branching.md)
when exploratory capture, workbench commits, selective transfer, dependencies,
or stacked branches are in scope.

## Resolve scope first

1. Inspect the current branch, worktree, remotes, tracking state, and relevant
   diff.
2. Treat the session's primary workspace root as the developer-visible
   checkout unless the user explicitly identifies another open workspace.
   Report its path and branch before editing, and again whenever either
   changes.
3. Identify unrelated or user-authored changes and keep them unstaged.
4. Check whether the current branch already has a pull request before deciding
   whether to extend it or create a new branch.
5. Before creating or switching to a new Jira-keyed branch or worktree, run
   `python3 platform/agent-control-plane/scripts/governed_task_preflight.py`
   from the repository root. Stop on any reported blocker. The preflight is
   read-only and never authorizes automatically committing, stashing,
   discarding, merging, or deleting work.
6. State the intended branch and publication scope before performing an
   authorized delivery workflow.
7. Stop for direction when the current branch contains work that does not
   belong in the requested change and isolation would materially change the
   delivery plan.

## Separate capture from delivery

- Keep `main` as the clean integration base and ordinary pull-request target.
- Use a private, unpublished `workbench/local` branch in the primary checkout
  for exploratory capture. Commit each coherent idea atomically without
  assuming that capture commits are final delivery units.
- Use `shape-repository-change` to partition workbench evidence before
  delivery. Switch that same primary checkout to an ordinary Jira-keyed branch
  created from current `main`, then transfer only the selected commits, files,
  or hunks. `main` remains the base even when it is not checked out.
- Use a secondary worktree only for concurrent agents, genuinely parallel
  delivery, stable long-running processes, or unsafe branch switching caused
  by unrelated work. Before editing there, disclose its exact path, branch,
  owner, purpose, and IDE-visibility consequence. Never silently redirect work
  away from the primary checkout.
- Prefer merging a prerequisite first and deriving dependent work from the
  updated `main`. Use a stacked branch only when the dependency, temporary
  base, merge order, and later retargeting work are explicit.
- Stop when mixed workbench evidence cannot be separated safely, dependency
  direction remains ambiguous, two agents claim one worktree, or the developer
  expects files in a different checkout than the active execution directory.

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
- A request to create a private workbench authorizes its local branch or
  primary-checkout switch or creation. It does not authorize publishing it or
  treating it as a delivery branch. A separate worktree requires an identified
  isolation reason and visibility disclosure.
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
  switching a clean primary checkout away from its verified feature branch or
  removing its verified secondary worktree, deleting the local feature branch,
  and pruning stale worktree metadata. It does not authorize deleting the
  primary checkout directory, a remote branch, or any other worktree.
- Force pushes, history rewrites, ref deletion, and direct pushes to the
  default branch always require explicit authorization naming that operation
  and target. The local feature-branch deletion included in a named
  post-merge cleanup request is the narrow exception defined above.

The repository pre-commit guardrail blocks ordinary commits on checked-out
`main` when `.githooks` is configured. Its `AEP_ALLOW_MAIN_COMMIT=1` bypass is
an implementation mechanism, not authority; use it only after the user has
explicitly authorized that exceptional direct commit.

Do not ask repeatedly for an operation already authorized by the active
request. If the user expands or narrows the request, apply the newest scope.

## Publish a pull request

1. Prefer a focused feature branch based on current `main`. Use another base
   only for a recorded dependency exception.
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
- Prefer branch switching in the primary checkout. Use a separate worktree
  only when concurrency, a stable long-running process, or unrelated local
  changes make branch switching unsafe, and surface the resulting visibility
  split before implementation.
- Re-read remote or pull-request state after writes.
- Treat merge, force push, rebase of published history, and branch deletion as
  distinct operations with distinct authority.

## Clean up a merged delivery checkout

Resolve and verify the complete target before mutating local state:

1. From the disclosed primary workspace, run the bundled cleanup script without
   `--execute` to produce a verification plan:

   ```bash
   python3 .agents/skills/manage-git-workflow/scripts/delivery_cleanup.py pr \
     --pr <NUMBER> \
     --primary-workspace <REPOSITORY_ROOT>
   ```

2. When the user already requested local cleanup for that pull request or
   delivery unit, rerun the verified command with `--execute` without asking
   for redundant confirmation. Stop on any script blocker rather than
   reproducing the mutation sequence manually.
3. Treat the script as local-only. It fetches and prunes remote-tracking refs,
   but never deletes the remote feature branch or changes Jira.

The script applies the following contract:

1. Identify the pull request and confirm its head branch, base branch, head
   identifier, merged state, merge result, and merge time.
2. Fetch the remote base and verify the recorded merge result is reachable
   from it.
3. Resolve whether the feature branch is checked out in the primary checkout
   or a secondary worktree through Git metadata. Do not infer the directory
   from its name.
4. Require an empty status, including untracked files, and verify `HEAD`
   matches the pull request's published head identifier.
5. For the primary checkout, switch to local `main` and update it by
   fast-forward, then return the visible checkout to an existing clean
   `workbench/local` branch or leave `main` checked out when no workbench
   exists. Never delete the primary checkout directory.
6. For a secondary worktree, remove that verified worktree without force.
7. Delete the local feature branch normally when Git recognizes it as merged.
   After a squash merge, force-delete only when the pull-request, head, merge,
   and target-branch checks above all succeeded.
8. Prune stale worktree metadata and re-read the worktree and branch lists.
9. Report whether GitHub already deleted the remote branch. Delete it only
   when remote cleanup was explicitly authorized.

Stop without deletion when the pull request is open or unknown, the target
does not contain the merge result, the active checkout is dirty, its branch or
`HEAD` does not match the pull request, primary-versus-secondary ownership is
unclear, or more than one target remains plausible.

## Reconcile repository-wide local cleanup debt

Treat single-PR cleanup as the normal transactional workflow. Use the global
reconciler only as a backstop for Jira-keyed local branches whose cleanup was
skipped, interrupted, or predates the current workflow.

Run verification mode from the primary repository root:

```bash
python3 .agents/skills/manage-git-workflow/scripts/delivery_cleanup.py stale \
  --primary-workspace <REPOSITORY_ROOT>
```

The reconciler fetches and prunes remote-tracking refs, then classifies local
branches as:

- `safe-to-delete` when an exact-tip merged pull request exists, the remote
  branch is absent, the branch is not checked out, and its tip is reachable
  from updated `origin/main`;
- `manual-review` when the branch is already contained but no exact associated
  pull request proves its lifecycle; or
- `preserve` when the branch is checked out, still remote, unmerged, or owns
  commits outside the integration base.

After global cleanup is explicitly authorized, rerun the same command with
`--execute`. It deletes only the verified `safe-to-delete` set with
`git branch -d`, never force-deletes, never removes a worktree, never deletes a
remote branch, and verifies that every intended local deletion completed.

Governed-task preflight invokes the reconciler with `--no-fetch` and JSON
output. It reports safe stale branches as cleanup debt but never blocks the new
task or mutates branch state. Resolve `manual-review` entries deliberately;
their lack of pull-request evidence is not authority for automatic deletion.
