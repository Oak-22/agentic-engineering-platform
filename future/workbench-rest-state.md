# Define and gate the workbench rest state

Status: captured, not scheduled. Delete this file when the gate lands on
`main`.

## Context

`workbench/local` merges `main` into itself after every delivery and never
merges the other way. Delivery moves a *selection* of workbench evidence onto
a Jira-keyed branch. Nothing asks what remains. The result, measured at every
`main → workbench/local` merge since the branch was created:

```text
2026-08-05   0 files   (workbench newly created)
2026-08-31   1 file    (one future/ plan)
2026-09-03  42 files
2026-09-16  26 files   (4 future/ plans, 22 other)
```

Equality has occurred once, by accident. Every branching-hygiene unit since
(AEPI-31, 97, 105, 142, 143, 154 and their siblings) enforced a
delivery-side invariant and all of them hold; none defined what the workbench
should look like *after* a delivery cycle. `governed_task_preflight.py`
checks only that `main` is contained in the workbench, never the reverse. The
sentence "the workbench may be long-lived" in
`docs/operations/governed-repository-delivery.md:60` was read by each
subsequent unit as permission for unbounded residue, though it only describes
the branch's lifespan.

The cost is working-memory strain: four states must be held at once (`main`,
designed residue in `future/`, undesigned residue, Jira). A report of the
residue keeps that count the same. Only a gate reduces it.

End state: after post-merge cleanup, `git diff --quiet main..workbench/local`
exits 0. `future/` plans reach `main` through their own small pull requests,
so captured intent is not residue. The next governed task cannot begin while
residue exists. Rejected alternatives: allowlisting `future/**` as permitted
residue keeps a rule the reader must know; ignoring `future/` in Git removes
history, review, resolvable citations, and visibility to linked worktrees.

## How to read this plan

Units are ordered by dependency. Each states what it touches, the mechanism,
a single claim that becomes true, and a check a skeptic can run. Each unit is
independently reviewable and separately revertible.

## Unit 1 — Route `future/` captures to `main`

**Touches**
- `future/README.md`
- `docs/architecture/adr/0007-define-the-lifecycle-of-deferred-intent-in-future.md`
- `docs/operations/governed-repository-delivery.md`

**Mechanism** — State in `future/README.md` that a captured plan is committed
on the workbench and delivered to `main` as its own pull request before it
counts as captured; a plan present only on `workbench/local` is undelivered
work like any other. Close ADR open decision 2 ("must a future artifact
reach `main` before Jira activation") with that rule. In the delivery doc,
replace the "may be long-lived" sentence with the rest-state definition from
*Context* so the lifespan claim no longer implies a residue policy. The pull
request for a `future/` capture is docs-only and passes the existing gates
without special handling.

**Claim** — Captured intent is visible from `main`, so a linked delivery
worktree and a second machine see the same set of plans as the primary
checkout.

**Trace check** — `git ls-tree --name-only origin/main future/` lists every
file that `git ls-tree --name-only workbench/local future/` lists. Break it
by adding a file under `future/` on the workbench only: the Unit 3 gate must
block the next governed task and name the path.

## Unit 2 — Drain the current residue once

**Touches** — the non-`future/` paths in `git diff --name-only
main..workbench/local` at the time the unit runs; enumerate them in the Jira
task, not here.

**Mechanism** — Run `shape-repository-change` over `origin/main..HEAD` on
the workbench to partition the residue into bounded units. Deliver each
through `deliver-governed-change`; drop what is not worth delivering with a
workbench commit whose message names why. Do this before Unit 3 lands, or
Unit 3 blocks every governed task on day one.

**Claim** — `git diff --quiet main..workbench/local` exits 0 immediately
after the last of those units is cleaned up.

**Trace check** — the command above. Also confirm no plan was dropped from
the workbench on the way: every path in
`git ls-tree -r --name-only workbench/local -- future/` appears in
`git ls-tree -r --name-only origin/main -- future/`. A plan absent from both
was deleted by the delivery pull request that realized it;
`git log origin/main --diff-filter=D --name-only -- future/` is the
historical record of those deletions.

## Unit 3 — Gate governed tasks on an empty residue

**Touches**
- `platform/agent-control-plane/scripts/governed_task_preflight.py`
- `platform/agent-control-plane/tests/test_governed_task_preflight.py`
- `platform/agent-control-plane/agent-assets/skills/manage-git-workflow/SKILL.md`
  (cleanup step 10)

**Mechanism** — Add `workbench_residue(root) -> tuple[str, ...]` beside
`workbench_commits_behind_main`, returning `git diff --name-only
main..workbench/local`. In `blockers_for`, a non-empty result blocks with the
same fail-closed posture as the behind-main count and prints the paths. No
tolerance threshold and no allowlist, for the reason the behind-main
docstring already gives: a count is not a proxy for the judgment. In
`manage-git-workflow` step 10, after the sync, run the same diff and report
its result as the last line of cleanup; cleanup itself does not fail on it,
because the residue may legitimately be the next unit's evidence, but the
next governed task cannot start until it is resolved.

The block message names, beside each residue path, any `future/*.md` on
`main` whose body cites that path's basename. Residue that matches a plan is
a plan someone began implementing without activating it; the resolution is
to activate the plan and link it from the Jira task as scope brief. Residue
that matches nothing is unplanned work; the resolution is a new task or a
drop. The gate cannot tell those apart from the diff alone, and the two
resolutions differ, so it prints the correlation at the point of failure.

**Claim** — A governed task cannot begin while `workbench/local` holds
tracked content that `main` lacks.

**Trace check** — On a clean workbench, `python
platform/agent-control-plane/scripts/governed_task_preflight.py` passes.
Touch and commit any tracked file on the workbench without delivering it;
the same command must exit nonzero and print that path. Commit a change to
a path that a `future/` plan cites; the block message must print that
plan's filename on the same line. The new test asserts all three outcomes
with a fixture repository.

## Verification

```sh
python -m pytest platform/agent-control-plane/tests/test_governed_task_preflight.py
python platform/agent-control-plane/scripts/governed_task_preflight.py
git diff --quiet main..workbench/local && echo rest-state
git ls-tree --name-only origin/main future/
```

## Risks

- Every `future/` capture becomes a pull request. The gates make that cheap,
  but the habit changes: a plan is not captured until it is on `main`.
- Unit 3 without Unit 2 blocks all governed work. Order is not optional.
- Copilot review on docs-only `future/` PRs may raise style findings on
  plans that are deliberately rough. The corroboration posture from ADR-0006
  applies; a plan does not need a clean review to be captured.
- The workbench still accumulates its own merge commits. History never
  converges; only the tree does. Preflight compares trees, so this is not a
  gate failure, but readers of `git log workbench/local` should expect it.
