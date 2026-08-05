---
name: deliver-governed-change
description: Coordinate a traceable engineering outcome across Jira, Confluence, implementation, Git, GitHub, review, and closure while preserving each system's authority boundaries. Use for major repository changes that should follow the default Jira task to feature branch to pull request lifecycle; when the user asks to implement work as a tracked task; or when delivery state must remain synchronized across work management and source control.
---

# Deliver Governed Change

Coordinate the delivery unit. Use the specialized operational skills for
system-specific actions and preserve the user's authority boundary at every
phase.

Read
[the governed change delivery workflow](references/governed-change-delivery.md)
before planning or executing a delivery.

## Establish the delivery unit

1. Accept one bounded outcome from `shape-repository-change`, or use that skill
   when observations, working-tree changes, or local commits still need to be
   grouped. Confirm the accountable outcome and acceptance criteria before
   creating delivery artifacts.
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

- Use `shape-repository-change` to identify and classify coherent outcomes,
  dependencies, exclusions, acceptance criteria, and verification
  expectations without initiating delivery.
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

1. **Shape:** use `shape-repository-change` to establish the bounded outcome,
   scope, dependencies, exclusions, acceptance criteria, and verification
   expectations. Then resolve the accountable owner and durable design
   location, classify the durable change authority, and select the delivery
   path.
2. **Isolate:** switch the primary developer-visible checkout to a Jira-keyed
   feature branch from current `main` when branch creation is authorized, then
   transfer only shaped workbench evidence when applicable. Use a secondary
   worktree only for an explicit concurrency or isolation exception and expose
   its visibility boundary. Resolve external configuration targets without
   creating empty Git artifacts. Use another branch base only for an explicit
   dependency exception.
3. **Implement:** make the bounded changes and run the smallest relevant
   checks; re-read external configuration after mutation.
4. **Commit:** partition the result into coherent commits when committing is
   authorized.
5. **Publish:** push and open one draft pull request when publication is
   authorized.
6. **Review:** synchronize evidence and move the work to review. Require an
   accountable human to approve governed work.
7. **Merge:** merge only when the requested method, approval, and required
   checks are authorized and verified.
8. **Clean up:** after a verified merge, restore the primary checkout or remove
   an exceptional secondary worktree, then delete the delivery refs only when
   cleanup is authorized. Synchronize the cleanup evidence and complete the
   Jira work.

Complete only the phases authorized by the current request. Report the next
gate without treating it as approved.

## Backfill completed work

When the user explicitly asks to backfill a governed-change run, delivery, or
record for work already performed, treat that request as authority to
reconstruct the delivery unit through verified **Implement** state. The user
does not need to enumerate the routine reversible operations inside that
reconstruction.

For a repository change, the backfill includes:

1. Resolve or create the Jira task and record that the delivery record is
   retrospective.
2. Reconstruct the outcome, acceptance criteria, accountable owner, scope,
   existing evidence, and actual delivery state. Use
   `shape-repository-change` when repository evidence still needs to be
   partitioned into a bounded outcome, while preserving this backfill
   workflow's authority and cross-system reconstruction responsibilities.
3. Inspect current Git and GitHub state for existing branches, commits, pull
   requests, or merge evidence before creating anything.
4. Create or select the Jira-keyed local feature branch needed by the default
   delivery relationship in the primary developer-visible checkout. Use a
   separate worktree only when concurrency or unrelated user-authored changes
   make branch switching unsafe, and disclose that visibility boundary.
5. Transfer only the bounded change into the delivery unit, run the smallest
   relevant checks, and synchronize the branch and verification evidence back
   to Jira.
6. Set Jira status from verified reality. Do not mark work complete solely
   because its record was created retrospectively.

For a change owned by Jira, Confluence, GitHub configuration, or another
external system, reconstruct the selected durable-authority evidence path and
do not create empty Git artifacts.

A backfill request does not authorize creating commits, pushing branches,
opening pull requests, advancing review state, merging, deleting refs or
worktrees, or rewriting history. Record existing identifiers when they can be
verified, then report the next unapproved gate.

Stop for a human decision when the outcome boundary is ambiguous, safe
isolation would require discarding or rewriting work, the correct base or
target branch cannot be resolved, or reconstruction would expand permissions,
sharing, review scope, or delivery risk.

## Clean up completed delivery units

Treat a natural-language request such as “clean up the local checkout and
branch for AEPI-21 after verifying its pull request was merged” as authority
for local cleanup of that named delivery unit. It does not authorize merging,
deleting the primary checkout directory, deleting another worktree, or
deleting a remote branch.

Delegate cleanup mechanics to `manage-git-workflow` and require it to:

1. resolve the Jira key, pull request, feature branch, target branch, and
   primary or secondary checkout as one delivery unit;
2. verify the pull request is merged and the target contains its merge result;
3. verify the active checkout is clean and its `HEAD` matches the published
   feature tip;
4. restore the primary checkout to its clean workbench (or `main` fallback),
   or remove the verified secondary worktree, before deleting the local feature
   branch;
5. verify squash merges from pull-request and target-branch evidence instead
   of branch ancestry alone;
6. prune stale worktree metadata and report the remote branch's disposition;
7. verify that the local feature branch is absent; and
8. preserve and report any dirty, unmerged, ambiguous, or mismatched target.

Use the deterministic cleanup script bundled with `manage-git-workflow`
instead of reconstructing these mutations from memory.

GitHub cannot switch a developer's visible checkout or delete local worktrees
and refs. Run this phase from a local agent session after the GitHub merge, or
through separately authorized local automation.

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
