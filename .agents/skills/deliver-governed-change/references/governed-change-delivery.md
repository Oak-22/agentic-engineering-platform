# Governed Change Delivery

## Purpose

Define the canonical lifecycle for carrying one accountable engineering
outcome from work definition through implementation, review, and closure.

## Select the delivery path

Classify the system that owns the durable change before choosing delivery
artifacts. Every material change requires a Jira work item. Git artifacts are
required when the outcome modifies repository-tracked content.

| Durable change authority | Required delivery record |
|---|---|
| Repository files | Jira task, Jira-keyed feature branch, commits, pull request, and GitHub review evidence |
| Jira or Confluence configuration | Jira task plus the changed artifact, configuration identifiers, and Atlassian audit evidence |
| GitHub repository or organization settings | Jira task plus the changed setting, repository or organization scope, and GitHub audit evidence |
| Repository files and external configuration | Jira task plus both the Git delivery record and the external system's configuration and audit evidence |
| Minor reversible operation | Existing work record, comment, or native audit log sufficient to preserve accountability and intent |

Create a separate delivery unit when independently valuable changes belong to
different authorities or review boundaries. Record a deliberate exception
when one delivery unit spans them.

## Repository delivery unit

```text
1 Jira task
  -> 1 Jira-keyed feature branch
    -> 1 pull request
      -> X coherent commits
        -> Y tracked file changes
```

- The Jira task defines the accountable outcome, scope, acceptance criteria,
  owner, and delivery state.
- The feature branch isolates work for that outcome.
- The pull request is the review and merge unit.
- Commits are coherent implementation checkpoints. Their number follows the
  work's internal structure.
- Tracked file changes are the files added, modified, renamed, or deleted to
  produce the outcome.

This relationship is the default for repository changes. It makes
traceability easy to inspect and does not serve as a numerical quality target.

## Lifecycle

### 1. Shape

- Establish the engineering outcome and acceptance criteria.
- Resolve or create the Jira task.
- Classify the durable change authority and select the delivery path.
- Identify the required native configuration identifiers and audit evidence
  for changes outside the repository.
- Record available collaboration lineage through structured backend metadata.
- Link durable architecture, decisions, or operating guidance from
  Confluence when needed.
- Identify the accountable human and review boundary.

### 2. Isolate

- For repository changes, inspect repository, branch, worktree, remotes,
  tracking state, and existing pull requests.
- Before creating or switching to a new Jira-keyed branch or worktree, run
  `python3 platform/agent-control-plane/scripts/governed_task_preflight.py`
  from the repository root. Stop when it reports uncommitted changes, an open
  governed pull request, an unpublished feature branch, or required cleanup
  for the current merged delivery.
- Treat this preflight as read-only. Never satisfy it by automatically
  committing, stashing, discarding, merging, or deleting work.
- Create a feature branch named `agent/<JIRA-KEY>-<outcome-slug>` when
  repository-tracked content will change.
- For external configuration changes, identify the target site, project,
  space, repository, organization, rule, or setting without creating an empty
  Git branch.
- Preserve unrelated and user-authored changes outside the delivery unit.

### 3. Implement and verify

- Make only the changes required by the outcome.
- Run the smallest checks that provide useful evidence.
- Re-read external configuration and its native audit record after mutation.
- Classify newly discovered work as required scope, follow-up work, or a
  separate delivery unit.

### 4. Commit

- Skip this phase when no repository-tracked content changed.
- Stage explicit paths.
- Group changes into one or more coherent commits.
- Use concise, imperative, outcome-oriented commit subjects.
- Keep Jira keys and agent-runtime names out of commit subjects.

### 5. Publish

- Skip Git publication when no repository-tracked content changed.
- Push the feature branch with upstream tracking.
- Open one draft pull request against the intended target branch.
- Include outcome, scope, impact, verification, and review boundaries.
- Record the branch, commits, and pull request in Jira.

### 6. Review

- Compare the pull request with the Jira outcome and acceptance criteria.
- Inspect commits, tracked file changes, required checks, security results,
  and unresolved review comments.
- Move the Jira task to `In Review` when implementation evidence is ready.
- Require an accountable human to approve governed work.

### 7. Merge

- Merge only after approval and required checks.
- Verify the target branch contains the intended result.
- Record the merge and verification evidence for repository changes.
- Record native configuration identifiers and audit evidence for external
  changes.

### 8. Post-merge cleanup

- Start cleanup only from a request that identifies the delivery unit or the
  exact local targets.
- Resolve the Jira key, pull request, feature branch, target branch, and linked
  worktree before deleting anything.
- Confirm the pull request is merged and its merge result is reachable from
  the updated target branch.
- Confirm the worktree has no tracked, untracked, staged, or conflicted
  changes and that its `HEAD` matches the published pull-request head.
- Remove the linked worktree before deleting its local feature branch.
- For squash merges, use the verified pull-request state, head identifier,
  merge identifier, and target-branch reachability as evidence. Branch
  ancestry alone cannot establish that the squash result was preserved.
- Prune stale worktree administration records after the intended worktree is
  removed.
- Read the remote branch state after cleanup. Delete a surviving remote branch
  only when remote cleanup is separately authorized.
- Preserve the worktree and refs when state is dirty, unmerged, ambiguous, or
  mismatched.
- Record cleanup evidence, then move the Jira task to its completed status.

GitHub-side merge and branch settings cannot remove a developer's local
worktree directory or local branch. Local cleanup requires a later local agent
run or separately authorized local automation.

## Authority gates

Each gate requires the authority applicable to its system and impact:

| Gate | Required authority |
|---|---|
| Create or update work records | Jira or Confluence mutation request |
| Modify repository files | Implementation request |
| Modify external configuration | Mutation request for the owning system and scope |
| Create or switch branches | Branch operation request |
| Backfill completed repository work | Retrospective delivery request; includes work-record mutation and local isolation through verified Implement state |
| Stage and commit | Commit request |
| Push or open a pull request | Publication request |
| Approve or request changes | Review authority |
| Merge | Merge request |
| Remove a local worktree and branch | Local cleanup request naming the delivery unit or targets |
| Delete a remote branch | Remote cleanup request naming the branch |

Authority for one gate does not approve later gates.

## Retrospective backfill

An explicit request to backfill a governed-change run authorizes the routine,
reversible reconstruction needed to represent already-performed work through
verified Implement state.

For repository changes:

1. Resolve or create the Jira task and mark the record as retrospective.
2. Reconstruct the outcome, acceptance criteria, ownership, bounded file
   scope, verification evidence, and actual delivery state.
3. Inspect existing branches, commits, pull requests, merges, and target-branch
   state before creating new artifacts.
4. Create or select the Jira-keyed local branch required by the delivery unit.
   Prefer a separate worktree when the source worktree contains another
   outcome or unrelated user changes.
5. Move only the bounded changes into the isolated delivery unit, verify them,
   and synchronize the branch and evidence to Jira.
6. Set Jira status to the verified phase. Retrospective task creation alone
   does not prove review, merge, delivery, or completion.

For external-system changes, reconstruct the selected durable-authority path
using the external artifact identifiers and native audit evidence. Do not
create a branch, commit, or pull request without repository-tracked changes.

The backfill request does not authorize new commits, pushes, pull requests,
review decisions, merges, history rewrites, or cleanup. Existing durable
identifiers may be recorded after read-only verification. Stop when the
outcome boundary, base or target branch, safe isolation method, permission
scope, sharing boundary, or review risk cannot be resolved without a human
decision.

## Deliberate exceptions

Use another relationship when the delivery structure benefits from it:

- One epic may contain many task-level delivery units.
- One large task may use multiple pull requests for incremental review.
- Several tiny changes may share one task and pull request when they form one
  inseparable outcome.
- A follow-up defect or independently valuable improvement receives its own
  task, branch, and pull request.

Record the reason for the exception in the Jira task or pull request.

## Evidence record

Keep these fields available across Jira, Confluence, Git, GitHub, and
telemetry:

- outcome and acceptance criteria;
- durable change authority and selected delivery path;
- accountable human and agent/runtime provenance;
- Jira key and current status;
- durable design or decision links;
- source and target branches;
- commit identifiers;
- verification commands and results;
- pull-request URL and review state;
- merge identifier and cleanup state;
- external configuration identifiers and native audit evidence;
- residual work and follow-up tasks.
