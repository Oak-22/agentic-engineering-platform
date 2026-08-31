# Agent Control Plane Scripts

Operational scripts in this directory implement deterministic Agent Control
Plane behavior. Runtime adapters and governed workflows invoke them; maintainers
can also run them directly when diagnosing or verifying that behavior.

## Continuous enforcement

`.github/workflows/control-plane-guards.yml` runs the control-plane guards on
every pull request to `main`, on pushes to `main`, and on manual dispatch. Its
job ID, `control-plane-guards`, is the required status check that the `main`
branch ruleset enforces, so a guard failure blocks merge rather than depending
on someone remembering a local command.

Each guard's local equivalent runs from the repository root, where `$P` is the
maintainer interpreter `platform/agent-control-plane/.venv/bin/python`:

| Guard | Local equivalent |
| --- | --- |
| Agent discovery layout | `scripts/check-agent-discovery-layout.sh` |
| Control-plane tests | `$P -m unittest discover -s platform/agent-control-plane/tests` |
| Asset registries | `$P platform/agent-control-plane/scripts/validate_asset_registries.py` |
| Contract schemas | `$P platform/agent-control-plane/scripts/validate_contracts.py` |
| Instruction adapter freshness | `$P platform/agent-control-plane/scripts/generate_instruction_adapters.py --check` |

Use the maintainer virtualenv described in the
[component README](../README.md) to run these locally. The workflow's job
summary pairs each guard's outcome with the command that reproduces it.

[`../docs/control-plane-guards-ci.md`](../docs/control-plane-guards-ci.md)
explains the workflow's triggers, permissions, caching, concurrency, required
check, Copilot advisory review, and troubleshooting commands.

## Protect the integration branch

Enable the repository-owned Git hooks once per clone:

```bash
git config --local core.hooksPath .githooks
```

The pre-commit hook invokes `protect_main_commit.py` and rejects ordinary
commits while `main` is checked out. An explicitly authorized exception can be
invoked with `AEP_ALLOW_MAIN_COMMIT=1 git commit`. See
[`../docs/workbench-delivery-branching.md`](../docs/workbench-delivery-branching.md)
for the complete branching contract and the limits of local hook enforcement.

## Governed task-start preflight

Run this check before creating or switching to another Jira-keyed branch or
worktree:

```bash
python3 platform/agent-control-plane/scripts/governed_task_preflight.py
```

The preflight blocks task isolation when:

- local `main` is behind, ahead of, or divergent from `origin/main`, so a
  branch cut from it would not start from the reviewed integration baseline;
- `workbench/local` exists and is behind `main`, so its remaining changes
  cannot be told apart from main content it has not seen yet;
- the working tree has staged, unstaged, untracked, or conflicted changes;
- an intent-categorized Jira-keyed pull request remains open;
- a published feature branch has no pull request; or
- the current merged delivery still has a remote feature branch requiring
  authorized cleanup.

Each baseline blocker names its own recovery, and they differ: a `main` that is
merely behind is fast-forwardable, while one carrying unique local commits is
not something this tooling will resolve for you. The workbench check has no
tolerance threshold — one missing commit is the same defect as fifty, because a
commit count is not a substitute for judging what the workbench still holds.
A repository with no `workbench/local` is on the direct-delivery path and is
never held to the workbench invariant.

The command reports the exact remaining work and exits nonzero. It is read-only:
it never commits, stashes, discards, merges, or deletes anything automatically.
The `main` comparison reads the remote-tracking ref as it stands rather than
fetching, so it is only as current as the last fetch.

The same script also runs as a `PreToolUse` hook (`--hook`, registered in
[`hooks_registry.json`](../agent-assets/hooks/hooks_registry.json)) on both
Claude Code and Codex. It denies a matched `git checkout -b` / `git switch -c`
Bash call when the blockers above apply, and stays silent for every other
command. This makes the check an enforced gate rather than a step someone has
to remember to run. The match is literal: a wrapped, aliased, or subshelled
branch-creation command is not recognized.

## Governed delivery-branch preparation

Create a Jira-keyed branch as one verified operation rather than a check
followed by a separate shell command:

```bash
python3 platform/agent-control-plane/scripts/prepare_delivery_branch.py \
  refactor/PROJ-12-telemetry-layout            # plan; changes nothing
python3 platform/agent-control-plane/scripts/prepare_delivery_branch.py \
  refactor/PROJ-12-telemetry-layout --execute
```

Stages, in order:

1. fetch `origin`, so the comparison is not made against a stale ref;
2. require a clean working tree, since branches cannot be switched safely otherwise;
3. verify local `main` against `origin/main`, fast-forwarding when that is safe
   and blocking when `main` is ahead or divergent;
4. merge `main` into `workbench/local` when one exists and trails;
5. require every workbench-only outcome to have a disposition;
6. re-read the `main` commit and cut the branch from that exact commit.

Step 6 is the point of the whole thing. Previously the state a check verified
and the state a branch was cut from were separated by a shell command, so they
could differ. Re-reading the baseline immediately before use closes that
window; if it moved during preparation, the run stops rather than silently
branching from something else.

The branch name is validated before anything else runs. The category must be
one of the five change classes derived from the work item's `Class` field —
`bugfix`, `hotfix`, and `release` are rejected with the reason they were
retired, so a contradiction between the field and the ref is not constructible
by following the contract.

Read-only until `--execute`. The only two mutations it will ever make are the
fast-forward and the workbench merge, both named in the plan before they
happen. It never commits, stashes, discards, rebases, force-updates, or
resolves a conflict; a conflicting workbench merge is aborted and reported. On
any failure the original checkout is restored, so a stopped preparation does
not leave the repository parked mid-operation.

The `PreToolUse` hook denies a bare `git switch -c` / `git checkout -b` for a Jira-keyed
branch when blockers apply, and its denial names this operation as the recovery
path.

## Workbench evidence reconciliation

Classify what `workbench/local` still carries that `main` does not:

```bash
python3 platform/agent-control-plane/scripts/workbench_evidence.py
python3 platform/agent-control-plane/scripts/workbench_evidence.py --format json
```

Each non-merge workbench-only commit lands in one of five states:

| State | Meaning | Blocks? |
| --- | --- | --- |
| `represented` | Every path it touched is now identical between `main` and the workbench | No |
| `in-delivery` | An identical patch, or full path coverage, exists on a live Jira-keyed branch | No |
| `parked` | Recorded as intentionally retained capture work | No |
| `superseded` | Recorded as replaced by later work | No |
| `unresolved` | Absent from integration and delivery, with no recorded disposition | Yes |

The audit compares content, not commit identity. Cherry-picking, squashing,
hunk-level reshaping, and rewriting during review all change a SHA without
changing whether the outcome arrived, so asking whether a SHA is on `main`
reports delivered work as missing. Asking whether its paths still differ does
not. On this repository that distinction takes the raw count from dozens of
commits down to the handful that genuinely need a decision.

Path coverage is deliberately weaker than patch identity: a delivery branch
touching the same files is not proof it carries the same change, so coverage
only ever routes an outcome to review on that branch and never marks it
delivered.

Record a judgment on what remains:

```bash
python3 platform/agent-control-plane/scripts/workbench_evidence.py \
  --park <evidence-id> --reason "still exploring the approach"
python3 platform/agent-control-plane/scripts/workbench_evidence.py \
  --supersede <evidence-id> --reason "replaced by PROJ-9"
```

A reason is required, and dispositions are stored machine-locally — see
[workbench dispositions](../docs/local-doc-mirrors.md#workbench-dispositions)
for why. Exits 1 while any evidence is unresolved, 0 otherwise.

## Instruction adapter generation

Instruction frontmatter for `.claude/rules/<id>.md` and
`.github/instructions/<id>.instructions.md` is generated from
`instructions_registry.json`'s `scopeGlobs` and `copilotDescription` fields
rather than hand-duplicated. Edit the registry, then regenerate:

```bash
python3 platform/agent-control-plane/scripts/generate_instruction_adapters.py
```

- Renders both adapters' frontmatter from one canonical glob list per
  instruction; the shared `@`-import body line is unchanged.
- Only rewrites files whose rendered content differs from what's on disk.
- Skips instructions with empty `runtimeAdapters` (e.g.
  `prose-writing-rules`) rather than erroring.
- `--check` renders without writing and exits nonzero if any adapter file is
  stale relative to the registry.

## Prompt instruction evidence

`instruction_manifest_hook.py` records typed, content-addressed instruction
evidence and renders a compact local-file citation for each hook-seeded row.
Canonical logs are partitioned by repository identity under
`$XDG_DATA_HOME/aep/instruction-evidence` (or
`~/.local/share/aep/instruction-evidence`) and exposed through the ignored
`.local-mirrors/instruction-evidence` project view. Set
`AEP_INSTRUCTION_MANIFEST_DIR` to move the canonical store or
`AEP_INSTRUCTION_EVIDENCE_VIEW` to provide another project-local view during
testing. The evidence label and citation are generated from the same record
defined by
`../contracts/instruction-evidence-record.schema.json`.
The generated `store-index.json` describes which files are metadata, indexes,
or session ledgers; see [`../docs/instruction-evidence-store.md`](../docs/instruction-evidence-store.md).

All retained project-scoped stores use
`<repository-name>--<identity-hash>`. Preview migration from older hash-only or
slug-only partitions with:

```bash
python3 migrate_local_stores.py --repo-root ../../..
```

After reviewing the JSON plan, add `--execute` to copy and verify content and
repoint safe `.local-mirrors/` views. The command never deletes legacy sources.
