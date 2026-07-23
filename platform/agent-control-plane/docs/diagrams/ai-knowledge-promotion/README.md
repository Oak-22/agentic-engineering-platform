# AI Knowledge Promotion Diagram

This folder contains the canonical diagram sources and update briefs for the
AI knowledge promotion platform.

## Folders

- `predecessor/`: historical Draw.io source.
- `subcomponents/feedforward-feedback-change-lifecycle/`: detailed expansion
  of the full diagram's feedforward/feedback boundary.
- `promoted/`: reserved for the selected final diagram.

## Related Evidence

The [LLM diagram manipulation fidelity experiment](../../../../../evidence/experiments/llm-diagram-manipulation-fidelity/README.md)
uses this diagram family as its test subject. Its baselines, briefs, run modes,
comparisons, and model cards live under `evidence/` because they evaluate the
diagram-editing workflow rather than define the canonical architecture.

## Parent and Detail Views

`full-diagram.svg` is the system-level view. Its “Interface to Feedforward /
Feedback Lifecycle” section summarizes two boundary flows:

- governed instructions, prompts, skills, hooks, standards, and retrieval
  reminders feed forward into engineering work;
- diffs, validation failures, review findings, incidents, lessons, and
  retrieval performance feed back into capture and promotion.

The lifecycle subcomponent expands those boundary flows into the agent's
proposal and self-correction sequence, computational checks, human review,
promotion decision, and harness pipeline. Changes to either view should be
checked against the other for semantic consistency; their visual layouts do
not need to be identical.

The broader diagram covers personal, team, and organizational knowledge.
The learning retrieval layer is described in
`developer-learning-retrieval/design.md`.
