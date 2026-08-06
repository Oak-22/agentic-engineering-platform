# Agent Control Plane Scripts

Operational scripts in this directory implement deterministic Agent Control
Plane behavior. Runtime adapters and governed workflows invoke them; maintainers
can also run them directly when diagnosing or verifying that behavior.

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
- an `agent/` pull request remains open;
- a published feature branch has no pull request; or
- the current merged delivery still has a remote feature branch requiring
  authorized cleanup.

The command reports the exact remaining work and exits nonzero. It is read-only:
it never commits, stashes, discards, merges, or deletes anything automatically.

## Prompt instruction evidence

`instruction_manifest_hook.py` records typed, content-addressed instruction
evidence and renders a compact local-file citation for each hook-seeded row.
Canonical logs are partitioned by repository identity under
`$XDG_DATA_HOME/aep/instruction-evidence` (or
`~/.local/share/aep/instruction-evidence`) and exposed through the ignored
`.aep/instruction-evidence` project view. Set
`AEP_INSTRUCTION_MANIFEST_DIR` to move the canonical store or
`AEP_INSTRUCTION_EVIDENCE_VIEW` to provide another project-local view during
testing. The evidence label and citation are generated from the same record
defined by
`../contracts/instruction-evidence-record.schema.json`.
The generated `store-index.json` describes which files are metadata, indexes,
or session ledgers; see [`../docs/instruction-evidence-store.md`](../docs/instruction-evidence-store.md).
