---
title: Adopt LangGraph and LangSmith as orchestration and telemetry backends
summary: Narrow AEP to governance and delivery semantics, and delegate durable workflow orchestration to LangGraph and trace/evaluation observability to LangSmith.
adr: ADR-0003
status: proposed
date: 2026-08-26
scope: platform
affected_components:
  - platform/agent-control-plane
  - platform/inference-telemetry-observatory
related_jira: []
related_confluence: []
supersedes: []
---

# Adopt LangGraph and LangSmith as orchestration and telemetry backends

## Context

Two proposals were on the table for extending AEP's execution model:
augmenting the current runtime-adapter subagent definitions with a concrete
multi-agent orchestration framework (LangGraph and/or CrewAI), so that AEP
itself becomes an executable orchestration runtime rather than a set of
role charters translated by hand into each runtime's native subagents; and
building out `platform/inference-telemetry-observatory` toward the
"production-grade" scope its README describes — streaming ingestion,
warehousing, analytics APIs, dashboards, and evaluation.

Comparing AEP's actual implementation (not its roadmap prose) against
LangChain, LangGraph, and LangSmith surfaced a real risk: the intended shape
of `inference-telemetry-observatory` — traces, nested runs, datasets,
experiments, offline and online evaluation — is close to a duplicate of
LangSmith's documented feature set, while `inference-telemetry-observatory`'s
implemented state is a single `InferenceEvent` record, a best-effort HTTP
emitter, and a CLI-to-model adapter, tested against mocks. The gap between
described scope and implemented scope was the actual redundancy risk, not
duplicated code.

`platform/agent-control-plane` is not equivalently at risk. Its artifact
types — instructions, skills, execution policies, role charters, hooks, MCP
declarations, provenance, and provider adapters — are a governance and
distribution layer, not an agent-loop or workflow-runtime library. LangGraph
supplies exactly the durable-state, branching, checkpoint, retry, and
human-interruption machinery that role charters and skills would otherwise
need to acquire piecemeal to become genuinely executable, rather than only
translatable by hand per runtime.

The forces to reconcile:

- AEP's differentiated claim is governed, portable, traceable,
  attributable agent-assisted engineering execution — not a general-purpose
  agent framework or a general-purpose observability platform. Building
  either would compete with, rather than complement, established tools.
- Role charters and skills currently describe responsibility and procedure;
  nothing executes them as a durable, resumable workflow. That gap blocks
  using AEP itself, dogfooded, to orchestrate building a downstream
  application.
- `inference-telemetry-observatory`'s implemented telemetry is real but
  minimal, and its README scope is aspirational. Left as-is, the aspirational
  scope keeps inviting reimplementation of trace storage, evaluation
  datasets, and experiment comparison that LangSmith already provides.

## Decision

Adopt **LangGraph** as AEP's orchestration runtime and **LangSmith** as the
initial backend for AEP's telemetry and evaluation layer. Do not adopt
LangChain or CrewAI as core dependencies; add either only if a concrete
executor later needs LangChain's model/tool/agent-loop abstractions, or a
concrete workflow needs CrewAI's Crew/Flow abstractions instead of or
alongside LangGraph.

Ownership boundaries:

| Capability | Owner |
| --- | --- |
| Durable workflow state, branching, checkpoints, retries, human interrupts | LangGraph |
| Traces, nested runs, threads, datasets, experiments, evaluators | LangSmith |
| Role authority, permitted actions, evidence requirements, handoff rules | `platform/agent-control-plane` |
| Git/Jira/GitHub delivery semantics | `platform/agent-control-plane` |
| Instruction provenance and runtime-specific installation | `platform/agent-control-plane` |
| Engineering-domain trace enrichment (work item key, repo, branch, commit, PR, role, authority scope, instruction evidence, run/attempt id, delivery stage, verification result, human approval) | `platform/agent-control-plane`, emitted alongside LangGraph/LangSmith spans |
| Cost and quality per governed engineering outcome; cross-runtime (Codex/Claude/Copilot) comparison | `platform/inference-telemetry-observatory` |
| Model/provider abstractions and tool-calling agent loops | Coding-runtime executors (Codex, Claude, or another supported runtime) — not AEP |

Role charters remain framework-neutral; they describe responsibility, not
execution mechanics. LangGraph nodes call an `AgentExecutor`-shaped interface
that dispatches a role's task to a concrete coding-runtime adapter (Codex,
Claude, an API-backed agent, or a test/fake executor), so role meaning stays
independent of both the orchestration framework and the executing runtime.

`platform/inference-telemetry-observatory`'s existing implementation
(`InferenceEvent`, the HTTP emitter, the CLI adapter, and its mock-backed
tests) is retained, but reclassified as a contract fixture and local testing
adapter rather than the beginning of a competing trace/evaluation product.
Its README should be narrowed to its implemented MVP scope in a follow-up
change; this ADR records the ownership decision that change will implement.

## Consequences

- AEP gains a real orchestration runtime (LangGraph) instead of hand-written,
  per-runtime translation of role charters into subagent definitions,
  enabling AEP to actually execute — not merely describe — a governed
  delivery workflow.
- `inference-telemetry-observatory` stops competing with LangSmith's roadmap.
  Its README and implementation plan need a follow-up narrowing pass so the
  documented scope matches what the component actually owns after this
  decision.
- AEP takes on a new class of dependency (LangGraph, and a LangSmith
  integration) that did not previously exist in the repository. Runtime
  adapters, packaging, and the eventual plugin distribution unit need to
  account for this dependency surface.
- Coupling to LangSmith specifically is bounded by emitting a portable
  (OpenTelemetry-compatible) representation and treating LangSmith as one
  destination adapter, not the sole telemetry sink.
- The first concrete workflow (plan → approve → implement → verify → review)
  becomes the validation vehicle for this decision; if LangGraph's execution
  model does not fit AEP's authority/evidence requirements in practice, that
  vertical slice is the cheapest place to discover it, before more role
  charters are wired to graph nodes.
- CrewAI is deliberately deferred rather than rejected. If a concrete
  workflow later benefits from Crew/Flow-style role/team abstraction more
  than from LangGraph's explicit graph control, adding it as a second
  orchestration adapter remains open, per the runtime-adapter pattern already
  used for Codex/Claude/Copilot.

## Alternatives considered

### Build orchestration and observability natively in AEP

Rejected. AEP's differentiated value is governance, authority, evidence, and
cross-runtime delivery semantics for agent-assisted engineering — not a
generic agent loop, graph scheduler, checkpoint/resume infrastructure, or
generic tracing backend and trace-exploration UI. Building these natively
would reproduce LangGraph and LangSmith with less maturity and no
compensating advantage.

### Adopt CrewAI instead of, or before, LangGraph

Rejected as the first adapter. CrewAI's Crew/Flow model maps naturally to
role charters, but LangGraph's documented persistence, explicit control
flow, and human-in-the-loop support line up more directly with AEP's
governed execution, approval, retry, and evidence requirements. CrewAI
remains a candidate second orchestration adapter once one adapter has been
validated end-to-end.

### Adopt LangChain as a core dependency now

Rejected for the present. LangChain supplies model/tool/agent-loop
abstractions AEP does not currently need, since coding-runtime execution is
already supplied by Codex, Claude, or another supported runtime. Adding it
now to "complete the product family" would introduce the redundancy this
decision is meant to avoid; it remains available if a concrete executor
later needs its abstractions.

### Expand `inference-telemetry-observatory` toward its README's full scope

Rejected. The README's streaming, warehouse, analytics-API, dashboard, and
evaluation scope substantially overlaps LangSmith's documented, implemented
product. Pursuing it natively would consume effort duplicating a product
that already exists, instead of on AEP's differentiated governance and
delivery semantics.
