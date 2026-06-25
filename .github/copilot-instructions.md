# Copilot Instructions

This is the GitHub Copilot-specific discovery adapter for the repository
instruction system.

Before making code, documentation, data-layout, or Git changes, converge
on the same instruction tree used by generic repo-first agents and
report what was loaded.

## Discovery Path

```text
.github/copilot-instructions.md
  -> AGENTS.md
  -> .github/agent_instructions/agent.md
  -> .github/agent_instructions/README.md
  -> .github/agent_instructions/global/README.md
  -> .github/agent_instructions/repo/README.md
  -> task-relevant instruction files
```

## Required Load Sequence

1. Read `AGENTS.md`.
2. Read `.github/agent_instructions/agent.md`.
3. Read `.github/agent_instructions/README.md`.
4. Read `.github/agent_instructions/global/README.md`.
5. Read `.github/agent_instructions/repo/README.md`.
6. Read task-relevant files referenced by those indexes.

## Required First Response Block

Start change-making turns with an instruction load report:

```md
Instruction Load Report

- [x] `AGENTS.md`
- [x] `.github/agent_instructions/agent.md`
- [x] `.github/agent_instructions/README.md`
- [x] `.github/agent_instructions/global/README.md`
- [x] `.github/agent_instructions/repo/README.md`
- [x] `path/to/relevant-instruction.md` (Trigger: brief reason)
- [ ] `path/to/skipped-instruction.md` (Skipped: brief reason)
```

If instruction files cannot be read, say which files were unavailable
and continue only when the task can still be handled safely.

## Audit Boundary

The load report is an operational audit artifact. It should list files
read for the task, not expose hidden chain-of-thought or private
reasoning.
