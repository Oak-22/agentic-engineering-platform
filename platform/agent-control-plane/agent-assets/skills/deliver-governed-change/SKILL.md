---
name: deliver-governed-change
description: Coordinate a traceable engineering outcome across Jira, Confluence, implementation, Git, GitHub, review, and closure while preserving each system's authority boundaries. Use for major repository changes that should follow the default Jira task to feature branch to pull request lifecycle; when the user asks to implement work as a tracked task; or when delivery state must remain synchronized across work management and source control.
---

# Deliver Governed Change

Coordinate the delivery unit. Use the specialized operational skills for
system-specific actions and preserve the user's authority boundary at every
phase.

Read
[the governed change delivery workflow](../../workflow-definitions/governed-change-delivery.md)
before planning or executing a delivery.

## Establish the delivery unit

1. Identify one accountable engineering outcome and its acceptance criteria.
2. Resolve an existing Jira work item or create one when the request
   authorizes tracked delivery.
3. Classify the system that owns the durable change and select its delivery
   path:

   - repository files: Jira plus Git branch, commits, pull request, and review;
   - Jira or Confluence configuration: Jira plus Atlassian artifact identifiers
     and audit evidence;
   - GitHub settings: Jira plus GitHub setting scope and audit evidence;
   - repository and external configuration: both evidence paths;
   - minor reversible operation: an existing work record, comment, or native
     audit log when it preserves accountability and intent.

4. For repository changes, apply the default relationship:

   ```text
   1 Jira task : 1 feature branch : 1 pull request : X commits : Y tracked file changes
   ```

5. Treat `X` as the number of coherent commits and `Y` as the number of
   tracked files changed by the outcome.
6. Do not create empty Git artifacts for changes owned entirely by another
   system.
7. Record a deliberate exception when the outcome needs a different
   relationship.

## Coordinate specialized operations

- Use `manage-jira-confluence` for Jira and Confluence reads, writes, links,
  transitions, and verification.
- Use `manage-git-workflow` for branches, staging, commits, pushes, pull
  requests, merges, and ref cleanup.
- Keep implementation and verification scoped to the Jira outcome and
  acceptance criteria.
- Preserve unrelated worktree changes outside the delivery unit.
- Keep detailed procedures in the specialized skills and canonical workflow;
  do not reconstruct them here.

## Advance through explicit gates

1. **Shape:** establish the outcome, scope, acceptance criteria, owner, and
   durable design location; classify the durable change authority and select
   the delivery path.
2. **Isolate:** create or select the Jira-keyed feature branch for repository
   changes when branch creation is authorized; resolve external configuration
   targets without creating empty Git artifacts.
3. **Implement:** make the bounded changes and run the smallest relevant
   checks; re-read external configuration after mutation.
4. **Commit:** partition the result into coherent commits when committing is
   authorized.
5. **Publish:** push and open one draft pull request when publication is
   authorized.
6. **Review:** synchronize evidence and move the work to review. Require an
   accountable human to approve governed work.
7. **Close:** merge, clean up refs, and complete the Jira work only when those
   actions are authorized and verified.

Complete only the phases authorized by the current request. Report the next
gate without treating it as approved.

## Maintain traceability

Keep these identifiers synchronized as they become available:

- Jira key, summary, status, accountable owner, and structured execution
  provenance;
- durable change authority and selected delivery path;
- Confluence design or decision link when durable documentation is needed;
- feature branch and target branch;
- commit identifiers and verification evidence;
- pull-request URL, review state, and required checks;
- merge result, cleanup state, and final Jira status.
- external configuration identifiers and native audit evidence when the
  durable change lives outside the repository.

Use the Jira key in the feature-branch name. Keep commit subjects and
pull-request titles focused on the engineering outcome. Record agent and
runtime provenance in structured work-item or telemetry metadata.

## Handle scope changes

- Add related changes to the delivery unit when they are necessary for its
  acceptance criteria.
- Create a separate Jira task and delivery unit for independently valuable or
  separately reviewable work.
- Stop for a human decision when scope expansion changes the outcome,
  authority, risk, or review boundary.
- Keep epics as containers for multiple task-level delivery units.

## Finish the active phase

Verify every mutated system before reporting completion. Return:

- the Jira and documentation records;
- the selected delivery path and durable change authority;
- branch, commits, pull request, and target branch when created;
- external configuration identifiers and audit evidence when applicable;
- checks and review state;
- excluded or residual work;
- the next unapproved delivery gate.
