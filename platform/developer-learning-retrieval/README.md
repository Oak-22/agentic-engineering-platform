# Developer Learning Retrieval Service

Status: **Planned — design only**

This service will turn real AI-assisted engineering activity into short,
targeted retrieval-practice sessions. Its primary interaction is a daily
five-to-ten-minute developer quiz conducted through Codex or another
compatible agent surface.

## Intended Responsibilities

- consume learning signals from commits, debugging sessions, agent runs,
  and telemetry
- select concepts that merit reinforcement
- generate questions grounded in the developer's actual work
- schedule questions using spaced-repetition intervals
- require an unaided recall attempt before revealing explanations
- record confidence, misconceptions, and later retrieval outcomes
- promote durable insights into the engineering knowledge base

## Platform Relationships

```text
AI-assisted engineering activity
  -> telemetry observatory
  -> developer learning retrieval service
  -> 5–10 minute active-recall session
  -> engineering knowledge base
  -> instruction and workflow improvement
```

The service design is documented in [`design.md`](design.md).

Deferred feature concepts:

- [Shared Shell Assistance Gradient](features/shared-shell-assistance-gradient.md)
  explores three assistance interfaces over one continuous shell session as a
  source of learning and retention signals.

## Implementation Boundary

No scheduler, quiz engine, Codex automation, persistence layer, or user
interface has been implemented yet. This directory establishes the
planned service boundary without overstating its maturity.
