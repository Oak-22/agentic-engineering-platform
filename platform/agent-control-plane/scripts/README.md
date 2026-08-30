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

- the working tree has staged, unstaged, untracked, or conflicted changes;
- an intent-categorized Jira-keyed pull request remains open;
- a published feature branch has no pull request; or
- the current merged delivery still has a remote feature branch requiring
  authorized cleanup.

The command reports the exact remaining work and exits nonzero. It is read-only:
it never commits, stashes, discards, merges, or deletes anything automatically.

The same script also runs as a `PreToolUse` hook (`--hook`, registered in
[`hooks_registry.json`](../agent-assets/hooks/hooks_registry.json)) on both
Claude Code and Codex. It denies a matched `git checkout -b` / `git switch -c`
Bash call when the blockers above apply, and stays silent for every other
command. This makes the check an enforced gate rather than a step someone has
to remember to run. The match is literal: a wrapped, aliased, or subshelled
branch-creation command is not recognized.

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
