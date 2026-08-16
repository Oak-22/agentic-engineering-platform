# Governed Repository Delivery

## Operating thesis

`workbench/local` is the private continuous capture-and-stewardship stream.
Coherent outcomes move from it, in dependency order, to Jira-keyed delivery
branches created from current `main`. Reviewed pull requests advance `main`;
the workbench does not.

## Why this exists

LLMs increase implementation throughput faster than they increase coordination
capacity. They can produce related edits across many files and modules before
their review and delivery boundaries become clear, shifting the expensive part
of engineering work:

```text
Before LLMs
understand -> implement -> review -> integrate
              ^ expensive step

With LLMs
understand -> generate many changes -> shape -> coordinate -> review -> integrate
                                       ^ new expensive step
```

The workbench buffers that evolving intent from the integration branch, giving
the developer room to checkpoint, separate, and order changes before they
become independently reviewable merges. Together, the workbench, shaping
workflow, Jira delivery units, runtime provenance, instruction boundaries, and
telemetry help maintain coherence at a change velocity that human memory and
informal coordination can no longer safely absorb.

Each repository retains its own workbench; cross-repository dependencies still
require explicit coordination.

## Delivery fundamentals

This buffering model extends rather than replaces established continuous
delivery practices. It inherits the DORA fundamentals of:

- working in small batches;
- integrating with `main` at least daily when practical;
- keeping delivery branches short-lived;
- maintaining few concurrently active delivery branches;
- running fast automated checks; and
- avoiding prolonged stabilization and integration phases.

The workbench may be long-lived; independently deliverable work within it
should not be. See DORA's guidance on
[trunk-based development](https://dora.dev/capabilities/trunk-based-development/)
and [continuous integration](https://dora.dev/capabilities/continuous-integration/).

## Three repository states

| State | Role | Expected contents |
| --- | --- | --- |
| `workbench/local` | Evolving developer-intent state | Atomic checkpoints for experiments, reports, semantic cleanup, and other continuous stewardship |
| `<category>/<JIRA-ISSUE-KEY>-<slug>` | Bounded delivery state | One Jira outcome assembled for verification and review |
| `main` | Reviewed integration state | Accepted outcomes merged through pull requests |

Use the primary developer-visible checkout for all three states by switching
its active branch. A second worktree is an explicit concurrency or isolation
exception, not the normal workflow.

## Normal flow

1. Capture each coherent idea as an atomic commit on `workbench/local`.
2. Shape the accumulated evidence into independently valuable outcomes and
   record their dependencies.
3. Deliver foundational semantic changes before outcomes that rely on them.
4. Create each Jira-keyed branch from current `main`, not from the workbench.
5. Transfer only the selected commits, files, or hunks for that outcome.
6. Verify, review, and merge the pull request before starting a dependent
   branch from the updated `main`.
7. Return the primary checkout to the private workbench after delivery cleanup.

Atomic workbench commits are capture boundaries, not guaranteed Jira or pull
request boundaries. Cherry-pick a commit when it maps cleanly to one outcome;
otherwise transfer selected paths or hunks and create a clean delivery commit.

## Reusable Codex delivery prompt

Use the following prompt when asking Codex to apply this repository's delivery
model:

```text
Use the repository's canonical governed-delivery workflow for this outcome.

First inspect the repository root, active branch, worktree, remotes, current
main, and existing delivery state. Preserve unrelated, user-authored,
generated, cache, scratch, and secret-like files unless they are explicitly
within scope.

Shape the work into bounded delivery units before changing Git or external
systems. Each unit must have one accountable outcome, explicit inclusions and
exclusions, dependencies, acceptance criteria, verification checks, and a
clear review boundary. Split independently valuable, reviewable, reversible,
or separately owned work into separate units.

Use the private `workbench/local` branch for continuous capture and
stewardship. Commit each coherent idea atomically there: one explainable
change per commit. Treat those commits as capture evidence, not automatically
as final delivery boundaries.

For each shaped repository outcome, use the default relationship:

1 Jira task : 1 Jira-keyed semantic feature branch : 1 pull request : X
coherent commits : Y tracked file changes

Keep `main` as the clean integration base. Run governed-task preflight before
creating or switching to a Jira-keyed branch. Create each delivery branch from
current `main`, using:

`<category>/<JIRA-KEY>-<outcome-slug>`

Transfer only the selected workbench commits, files, or hunks into that
branch. Preserve commit boundaries when they map cleanly to the outcome;
otherwise reconstruct focused delivery commits without rewriting or
discarding unrelated work. Deliver foundational outcomes before dependent
outcomes, preferably by merging the prerequisite and branching from updated
`main`.

Use explicit paths for staging. Keep commit subjects concise, imperative, and
outcome-oriented; do not put Jira keys or runtime identity in commit subjects.
Run the smallest relevant checks before committing and publishing.

Maintain traceability across Jira, Git, GitHub, Confluence, and telemetry:
outcome, acceptance criteria, owner, Jira key, durable authority, branch
names, commits, checks, pull request, review state, merge result, cleanup
state, and residual work.

Advance only through the gates authorized by the request:
Shape -> Isolate -> Implement -> Commit -> Publish -> Review -> Merge -> Clean up.

Do not infer authorization for commits, pushes, pull requests, merges, branch
deletion, worktree removal, Jira transitions, or external configuration
changes. Report the next unapproved gate instead.

Use the specialized repository skills for shaping, Jira/Confluence,
Git/GitHub, and cleanup. Stop for a human decision if scope, ownership,
dependency direction, safe isolation, target branch, or review authority is
ambiguous. After a verified merge and explicit cleanup authorization, use the
deterministic cleanup procedure, preserve dirty or mismatched state, restore
the primary checkout to `workbench/local` or `main`, and verify local ref
cleanup.
```

## Dependency example

```text
workbench/local
  A  rename telemetry directory
  B  update telemetry schema using the new path
  C  add an analysis report using the new path

delivery order
  PROJ-101  semantic naming cleanup: A                 -> main
  PROJ-102  telemetry schema: B, from updated main     -> main
  PROJ-103  experiment report: C, from updated main    -> main
```

After `PROJ-101` merges, `PROJ-102` and `PROJ-103` may proceed independently
if neither depends on the other. A transfer conflict is useful evidence that
an ordering constraint or an incomplete delivery boundary needs attention.

## Branch naming

Use the portable pattern:

```text
<category>/<JIRA-ISSUE-KEY>-<outcome-slug>
```

Choose `feature`, `fix`, `bugfix`, `hotfix`, `refactor`, `chore`, `docs`, or
`release` as the category. For example, this repository may use:

```text
refactor/AEPI-127-telemetry-layout
chore/MAPP-42-update-dependencies
```

The category communicates change intent; the full Jira issue key provides
project and delivery identity. Human, agent, and runtime contributions belong
in Jira, attempt records, telemetry, and review evidence rather than in the
branch namespace.

## Progressive detail

This guide owns the human operating model. Deeper layers have narrower jobs:

1. [Workbench-to-Delivery Branching](../../platform/agent-control-plane/docs/workbench-delivery-branching.md)
   owns exact Git branch, transfer, worktree, synchronization, and cleanup
   rules.
2. [`shape-repository-change`](../../platform/agent-control-plane/agent-assets/skills/shape-repository-change/SKILL.md)
   partitions observations and workbench evidence into bounded outcomes.
3. [`deliver-governed-change`](../../platform/agent-control-plane/agent-assets/skills/deliver-governed-change/SKILL.md)
   coordinates the Jira-to-branch-to-pull-request lifecycle.
4. [`manage-git-workflow`](../../platform/agent-control-plane/agent-assets/skills/manage-git-workflow/SKILL.md)
   and [`manage-jira-confluence`](../../platform/agent-control-plane/agent-assets/skills/manage-jira-confluence/SKILL.md)
   own destination-specific mechanics and authority checks.
5. Repository hooks, preflight checks, tests, and cleanup scripts enforce
   deterministic invariants.

Keep intent compact at the outer layers and mechanics canonical at the deepest
applicable layer. Link inward instead of copying procedures outward to avoid
scattering authority and breaking single sources of truth.
