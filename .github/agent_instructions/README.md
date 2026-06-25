# Agent Instructions

This README defines the purpose of the repository's agent-instructions
layer.

This directory contains instruction assets that support disciplined
human plus AI collaboration in a repository.

## Layer Model

- `agent.md`
  General AI agent working principles
- `global/`
  Reusable guidance that can move across repositories
- `repo/`
  Repository-specific context, boundaries, and operating constraints

`agent.md` defines general collaboration behavior. Global guidance
supplies default decision rules. Repo guidance supplies local facts and
constraints that shape or override those defaults.

## Usage

Start here, then load only the instruction files relevant to the task.
