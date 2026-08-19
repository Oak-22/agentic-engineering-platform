# Developer Learning Retrieval Service — Design Direction

This note defines the design direction for a planned platform service. It is an
architectural proposal, not a description of an implemented runtime.

## TL;DR

AI-assisted development improves short-term velocity, but it can reduce
long-term knowledge retention. A workflow-derived retrieval layer would turn
real engineering activity into spaced, targeted recall prompts so developers
retain deeper system understanding while keeping AI productivity gains.

## Why This Matters

Modern engineering workflows increasingly rely on AI for coding, debugging, and
refactoring.

That shift is powerful, but it introduces a tradeoff: developers can complete
tasks successfully without fully internalizing why the solution works.

Historically, most implementation reasoning happened in the developer's head,
and repetition naturally reinforced understanding. With AI assistance, more of
that reasoning can be externalized, which weakens reinforcement loops.

Long-term risks include:

- slower debugging when similar issues recur
- weaker mental models of system behavior
- increased reliance on rediscovering prior solutions
- loss of institutional knowledge over time

## Core Problem

In AI-assisted environments, task completion and knowledge retention can become
decoupled.

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

The service uses workflow telemetry from real engineering activity to generate
targeted retrieval prompts.

### Two Capture Surfaces

Signals divide into two layers that carry different evidence, and the pairing
between them is what makes a prompt worth asking.

- **Reasoning layer** — intent, architectural rationale, hypotheses, and
  assumptions, usually recorded before or during implementation.
- **Execution layer** — commit history and diffs, IDE and file activity,
  debugging and error-resolution events, command-line interactions, and
  agent-assisted sessions.

The execution layer alone shows what happened; the reasoning layer alone shows
what was believed. Held together they expose the gap between the two, which is
where a misconception becomes visible and worth reinforcing.

Capture stays on structured text streams rather than continuous screen or video
capture, so ingestion remains low-cost in CPU, memory, and storage and adds no
friction to ordinary work.

### Ingestion Cadence

Some sources emit events; others must be polled. A source without webhooks or
push notification cannot be streamed in real time, so ingestion assumes periodic
local polling over a recent activity window rather than continuous capture. This
is a constraint on the design, not a preference: the cadence a source supports
determines how promptly its signal can reach a session, and the service should
degrade to a scheduled sweep wherever push is unavailable.

### Prompt Generation

The service converts signals into retrieval prompts that ask the developer to
explain the underlying concept. Prompts target the distance between intent and
outcome rather than syntax recall.

Examples:

- signal: commit fixing a broken symlink
  prompt: "Why did the symbolic link fail after the directory move?"
- signal: debugging session resolving a dependency issue
  prompt: "Why does npm update not upgrade the npm binary itself?"
- signal: change to authentication logic
  prompt: "What role does a refresh token play in OAuth token rotation?"

The strongest prompts pair a recorded assumption against the observed result.
Where a developer's note states an expectation and the execution record shows a
different outcome, the prompt asks them to reconcile the two — which reinforces
the corrected model rather than testing recall of a fact.

### Scheduling

Prompts are delivered on spaced-repetition intervals so critical concepts are
revisited after increasing delays.

## Human-in-the-Loop Rule

To preserve the cognitive value of active recall, the workflow should enforce:

```text
Attempt retrieval before consulting AI.
```

When prompted, developers first answer from memory. Only afterward do they view
explanations or consult AI tools.

This aligns with learning principles such as retrieval practice and productive
struggle, both of which are associated with stronger long-term retention than
passive review.

## Visibility Boundaries

Signals are held in three stores with different audiences, established by
[ADR-0002](../../../docs/architecture/adr/0002-shield-personal-learning-signals-from-observation.md):

- the **personal store** holds weak signals and stays with its author
- the **nomination queue** carries candidates the author chooses to submit for
  review
- **aggregate recall telemetry** reports concept-level, person-anonymous
  statistics

The service defines and operates all three. Prompt generation and scheduling run
locally against the author's own signals; what reaches another person is limited
to what the author nominated and to anonymized aggregates.

## Relationship To The Platform

The platform provides the structural prerequisites for this service:

- `platform/agent-control-plane/agent-assets/` defines canonical reusable
  instructions, skill packages, colocated workflow references, and role charters
- `.agents/`, `.claude/`, and `.github/` expose those assets through
  runtime-native discovery adapters and enforcement surfaces
- `platform/inference-telemetry-observatory/` supplies workflow signals and
  receives aggregate recall statistics
- `docs/` holds higher-level rationale and design notes

The instruction control plane governs the interaction and the telemetry
observatory supplies workflow signals. This service coordinates those inputs
into short recurring retrieval sessions, and holds the durable learning material
it produces in the stores described above.

## Open Questions

- **Ingestion source selection.** Which reasoning-layer sources to support
  first, and on what authentication model. Any source requiring stored personal
  credentials needs its own decision before it is adopted, since it widens the
  service's exposure beyond the local machine.
- **Nomination friction.** Nomination must be a first-class, low-cost action
  inside the retrieval session; if it is laborious, the promotion path starves.
- **Session mechanics.** Prompt volume, session length, and how a declined or
  failed recall is recorded without turning the session into an assessment.
