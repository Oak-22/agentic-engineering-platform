# Shared Shell Assistance Gradient

Status: **Deferred feature concept**

## Goal

Let a developer move between raw shell use, inline AI assistance, and full
conversational assistance without losing terminal state. The assistance level
changes; the underlying shell session does not.

## User Experience

Expose three views over one host shell:

| View | Intended use |
| --- | --- |
| Raw zsh | Default interface for unaided recall and familiar commands |
| Copilot inline | Lightweight scaffolding when the developer partly knows the command |
| GitHub Copilot | Full assistance for genuinely novel or complex shell work |

Moving between views should preserve the current directory, environment,
history, virtual environment, background jobs, and command output.

## Learning Value

The three views create an observable assistance gradient:

```text
full assistance -> inline scaffolding -> unaided execution
```

Over repeated tasks, needing less assistance can serve as evidence of
retention. Escalation can identify a knowledge gap worth turning into a future
retrieval exercise. AI usage is not treated as failure; the signal is the
minimum assistance needed for a task at a point in time.

## Technical Shape

Use one authoritative shell process attached to a pseudoterminal and place a
session broker between it and the three UI views.

- Only one view owns input at a time.
- All attached views may receive the same output stream.
- Draft input remains private to its originating view until submission.
- Submitted commands are tagged with the active assistance level.
- Full-screen programs and interactive subprocesses receive exclusive control.

A `tmux`-backed prototype could test the interaction model. A purpose-built
PTY broker would provide stronger input ownership and telemetry guarantees.

## Candidate Signals

- shell session and command identifiers
- assistance level: `raw`, `inline`, or `conversational`
- command category and intent
- suggestion accepted, edited, or rejected
- escalation or de-escalation between views
- exit status and validation outcome
- later success on a similar task with less assistance

Raw commands and terminal output may contain credentials or private data, so
capture should default to redacted categories and derived signals rather than
verbatim content.

## Lean Prototype

1. Attach three terminal views to one host session.
2. Enforce a single active input owner.
3. Record the assistance level for submitted commands.
4. Demonstrate state continuity while switching views.
5. Test whether repeated command categories migrate toward less assistance.

## Non-Goals

- autonomously executing AI-proposed commands
- scoring all AI use as negative
- implementing the complete retrieval scheduler or quiz engine
- retaining secrets or unrestricted terminal transcripts

## Open Questions

- Can existing VS Code terminal and Copilot extension APIs support shared PTY
  attachment and attribution, or is a custom extension required?
- What task representation is useful for learning without retaining raw command
  content?
- How should canceled commands, pipelines, aliases, and interactive programs be
  attributed?
- Which assistance transitions are strong enough to schedule retrieval practice?
