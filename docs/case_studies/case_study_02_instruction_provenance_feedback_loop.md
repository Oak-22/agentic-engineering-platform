# Case Study 02: Prompt-to-Instruction Provenance and Recursive Refinement

## Summary

This case study documents an AI-human collaboration pattern where a
human proposes a reusable agent-state feature, the AI implements an
initial version, and the human then interrogates the design until the
feature is refined into a more durable instruction-management pattern.

The specific feature was a **prompt-to-instruction log**: a global agent
state artifact that records the original prompt or observation that led
to a reusable instruction. The first implementation preserved the raw
prompt and added a compact runtime rule (a prompt-to-instruction pair).
The LLM-proposed refinement clarified that the prompt log should not be treated as
supplementary, always-loaded context for the instruction. Instead, it should act as
provenance and selective retrieval material, similar to an ADR for agent instructions.


## Problem

Reusable agent instructions tend to lose their origin story.

Over time, a compact rule such as "standardize related artifact names"
may remain useful, but future agents and humans may forget:

- what observation produced the rule
- whether the rule was generalized correctly
- whether the rule came from one repository or a cross-project pattern
- when the rule should be revised, retired, or moved to repo-specific
  guidance

The initial human hypothesis was that preserving prompt-to-instruction
pairs might strengthen runtime agent behavior by expanding available
context.


## Initial Feature Idea

The human proposed logging pairs such as:

```text
Prompt:
Naming convention observation: Stage1 output file naming is slightly
unstandardized. `extracted_stage1_metadata.json` vs
`stage1_manifest.json` and `stage1_metadata_validation_report.json`

Instruction:
When creating or reviewing related artifacts, check whether file names
share a consistent scope, stage, artifact type, and ordering convention.
```

The AI implemented:

- a `prompt-instruction-log.md` file
- a first prompt-log entry preserving the raw observation
- a compact artifact-naming rule in the relevant global agent instruction
  file
- a back-reference from the instruction to the prompt-log entry


## Human Interrogation

After implementation, the AI's summary **implicitly** treated the compact
instruction as the runtime artifact and the prompt log as supporting
context. It did not directly validate the initial, human-derived theory that preserving
more prompt context should automatically strengthen runtime inference.

That omission became part of the collaboration signal. The human noticed
that the implementation and explanation favored a smaller always-loaded
rule over an expanded always-loaded prompt history. From that, the human
inferred an **unstated design tension**: richer historical context can help
maintenance and retrieval, but excessive always-loaded context can
weaken inference by adding noise, conflict, and attention dilution.

The human then challenged the underlying theory in response to what the
AI response implied but did not explicitly validate:

> If only the compact rule should be loaded at runtime, and excessive
> rules or context can weaken inference, what is the value of preserving
> the raw prompt?

This question exposed a design flaw in the initial framing. The value
was not simply "more tokens at runtime." Loading every historical prompt
would create noise, increase conflict surface, and encourage the agent
to overfit to old examples.

This illustrates an important collaboration requirement: successful
AI-human work depends on the human operator noticing the **implicit
position** carried by each prompt-turn, not only the explicit answer. The
signal is bidirectional because both the human and the AI introduce
assumptions through what they say, omit, emphasize, or implement.
However, the responsibility is asymmetric. The human remains the
operator who identifies those implications, challenges them when needed,
and decides whether the resulting pattern should become durable
instruction.

In practice, the AI will try to meet the operator where they are and may
extend beyond the literal request by introducing structure, defaults, or
**unstated design preferences**. The human operator must recognize that
"reach" and decide how to use it. The value of the loop increases when the
human treats the AI's extension as material for interrogation rather
than as either automatic truth or irrelevant surplus.


## Refined Pattern

The AI reframed the feature as **instruction provenance and selective
retrieval**.

The refined model:

```text
global/*.md
  compact runtime instructions

prompt-instruction-log.md
  provenance, examples, original prompts, rationale

repo/*.md
  local constraints that affect how global rules apply
```

The prompt log becomes useful when:

- a rule is ambiguous
- a rule is being edited
- a rule appears to conflict with repo-specific constraints
- a future agent needs to understand why the rule exists
- a repeated pattern should be promoted into a stronger instruction

It does not need to be loaded for every task.


## Collaboration Pattern

This produced a recursive human-AI refinement loop:

```text
human proposes feature idea
  ↓
AI implements initial version
  ↓
human interrogates the assumptions
  ↓
AI reframes the pattern
  ↓
human evaluates the tradeoffs
  ↓
AI refines the feature and documentation
```

The important behavior is not that the AI's first implementation was
perfect. The important behavior is that the human used the
implementation as a concrete object to first reason against, and then 
constructively build from it.


## Design Lesson

Prompt logs are most valuable as **retrievable provenance**, not as
unbounded runtime context.

This distinction preserves the benefit of richer historical context
without forcing every agent session to carry the full weight of that
history.

The resulting pattern is stronger than the initial idea:

- compact instructions remain efficient at runtime
- raw prompts preserve context for future maintenance
- references connect rules to their originating observations
- instruction evolution becomes inspectable
- human feedback remains part of the durable system design


## Generalizable Principle

Human-AI collaboration improves when intermediate AI outputs become
objects of critique rather than final answers.

A strong workflow does not require the first implementation to be
complete. It requires the system to preserve enough structure for the
human to challenge assumptions, refine the model, and promote the
better pattern back into persistent instructions.
