# Agent Control Plane Scripts

Operational scripts in this directory implement deterministic Agent Control
Plane behavior. Runtime adapters and governed workflows invoke them; maintainers
can also run them directly when diagnosing or verifying that behavior.

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
