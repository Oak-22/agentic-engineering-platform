# Workflow-Derived Retrieval for AI-Assisted Development

This note describes a related design direction for this repository.
It is not the current product scope of
`agent_instruction_control_plane`.

The current repository provides a reusable scaffold for AI-human
workflow artifacts. The concept described below explains one possible
future extension: deriving retrieval prompts from real engineering work
so teams retain more understanding over time.

## TL;DR

AI-assisted development improves short-term velocity, but it can reduce
long-term knowledge retention. A workflow-derived retrieval layer would
turn real engineering activity into spaced, targeted recall prompts so
developers retain deeper system understanding while keeping AI
productivity gains.

## Why This Matters

Modern engineering workflows increasingly rely on AI for coding,
debugging, and refactoring.

That shift is powerful, but it introduces a tradeoff: developers can
complete tasks successfully without fully internalizing why the
solution works.

Historically, most implementation reasoning happened in the developer's
head, and repetition naturally reinforced understanding. With AI
assistance, more of that reasoning can be externalized, which weakens
reinforcement loops.

Long-term risks include:

- slower debugging when similar issues recur
- weaker mental models of system behavior
- increased reliance on rediscovering prior solutions
- loss of institutional knowledge over time

## Core Problem

In AI-assisted environments, task completion and knowledge retention can
become decoupled.

Traditional pattern:

```text
learning -> practice -> application -> reinforcement
```

Common AI-assisted pattern:

```text
task -> AI assistance -> task completion
```

The reinforcement step is often missing.

## Design Goal

Restore reinforcement without disrupting the productivity benefits of
AI-assisted development.

## Proposed Approach

The idea is to use workflow telemetry from real engineering activity to
generate targeted retrieval prompts.

### Learning Signals

Rather than relying on external study material, the system derives
signals directly from day-to-day development events:

- git commit history and diffs
- IDE activity and file changes
- debugging and error-resolution events
- command-line interactions
- agent-assisted development sessions

These events often indicate moments where a developer learned
something new, corrected a misconception, or refined a system-level
mental model.

### Prompt Generation

The system converts those events into retrieval prompts that ask the
developer to explain the underlying concept.

Examples:

- signal: commit fixing a broken symlink
  prompt: "Why did the symbolic link fail after the directory move?"
- signal: debugging session resolving a dependency issue
  prompt: "Why does npm update not upgrade the npm binary itself?"
- signal: change to authentication logic
  prompt: "What role does a refresh token play in OAuth token rotation?"

### Scheduling

Prompts are delivered on spaced-repetition intervals so critical
concepts are revisited after increasing delays.

## Human-in-the-Loop Rule

To preserve the cognitive value of active recall, the workflow should
enforce:

```text
Attempt retrieval before consulting AI.
```

When prompted, developers first answer from memory. Only afterward do
they view explanations or consult AI tools.

This aligns with learning principles such as retrieval practice and
productive struggle, both of which are associated with stronger
long-term retention than passive review.

## Relationship To This Repository

This repository provides the structural prerequisites for that broader
direction:

- `.github/instructions/`, `.github/agents/`, `.github/prompts/`,
  `.github/skills/`, and `.github/hooks/` define an artifact-typed
  AI-human operating control plane
- `engineering_knowledge_base/` provides durable capture locations for
  workflow-derived learning artifacts
- `docs/` can hold higher-level rationale and design notes

In other words, this template is the scaffold. Workflow-derived
retrieval is one future-facing system that could be built on top of it.
