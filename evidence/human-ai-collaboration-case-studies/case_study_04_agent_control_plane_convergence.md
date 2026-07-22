# Case Study 03: Agent-Control Plane Convergence Through In-Repo Emergence

## Summary

This case study captures a practical pattern discovered while actively
building in `myHealth`: the repository's agent-control structure evolved
from a legacy instruction tree into a modern artifact-typed control
plane.

The key insight was emergent rather than pre-planned. Real AI-human
collaboration pressure, across multiple tasks and tool surfaces,
revealed that the original scaffolding model was still useful in intent
but no longer optimal in shape.

## Problem

The project started with an older instruction layout centered on:

```text
.github/agent_instructions/
  agent.md
  global/
  repo/
```

That model worked as an early control surface, but it mixed concerns
that later became distinct in practice:

- durable behavior rules
- specialist personas
- reusable prompts
- repeatable workflows
- guardrail hooks

As usage increased, this produced conceptual slippage and instruction
drift risk.

## Collaboration Signal

During iterative implementation, the AI and human repeatedly converged
on artifact-type separation without explicitly planning a full redesign
up front.

The resulting shape:

```text
.github/
  copilot-instructions.md
  instructions/
  agents/
  prompts/
  skills/
  hooks/
```

This was not arbitrary refactoring. It reflected repeated operational
needs observed during real work.

## Why This Is Emergence, Not Traditional Drift

Traditional architecture drift usually means accidental divergence from
design intent.

In this case, structure changed because real workflow constraints made a
better taxonomy visible. The older tree was not "wrong". It became a
compatibility layer while the active control plane moved to a clearer
artifact model.

## Design Outcome

The pattern was named **agent-control plane convergence**:

- a migration from monolithic instruction grouping
- toward artifact-typed control surfaces
- with explicit compatibility boundaries for legacy paths

This produced three stable layers:

1. Checked-in canonical agent controls (`.github/instructions`,
   `.github/agents`, `.github/prompts`, `.github/skills`, `.github/hooks`)
2. Local implementation overlays (ignored, optional, promotable)
3. Private learning capture (`engineering-knowledge-base/`)

## Human-AI Collaboration Lesson

The most valuable contribution from the AI was not a single perfect
proposal. It was iterative pressure that made latent structure visible.

The most valuable human contribution was recognizing that repeated local
fixes implied a higher-order pattern and then promoting that pattern
into durable repository guidance.

## Template Modernization Implication

Reusable workflow templates should default to artifact-typed agent
control planes and treat older instruction trees as migration shims,
not first-class active paths.

Recommended template baseline:

```text
.github/
  copilot-instructions.md
  instructions/
  agents/
  prompts/
  skills/
  hooks/

scripts/
  hooks/

docs/
  notes/

engineering-knowledge-base/
```

## Generalizable Principle

When a team repeatedly patches tooling structure during real delivery,
those patches may indicate an emergent architecture. Capture it as a
case study, then decide whether to promote it into a template or
canonical control layer.
