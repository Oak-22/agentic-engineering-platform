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

### 7. Close

- Merge only after approval and required checks.
- Verify the target branch contains the intended result.
- Clean up local and remote feature refs when authorized.
- Record the merge and verification evidence for repository changes.
- Record native configuration identifiers and audit evidence for external
  changes.
- Move the Jira task to its completed status only after delivery is verified.

## Authority gates

Each gate requires the authority applicable to its system and impact:

| Gate | Required authority |
|---|---|
| Create or update work records | Jira or Confluence mutation request |
| Modify repository files | Implementation request |
| Modify external configuration | Mutation request for the owning system and scope |
| Create or switch branches | Branch operation request |
| Stage and commit | Commit request |
| Push or open a pull request | Publication request |
| Approve or request changes | Review authority |
| Merge | Merge request |
| Delete refs | Cleanup request naming the target |

Authority for one gate does not approve later gates.

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
