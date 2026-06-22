# Recursive Artifact-Derived Prompting

## Core Idea

Recursive artifact-derived prompting is the practice of using prior
agent-produced artifacts as evidence for the next agent instruction.

Instead of writing a prompt only from intent, the engineer asks:

```text
What structure did previous successful work already converge on?
Can that structure become input to the next instruction?
```

This creates a recursive loop:

```text
agent helps produce artifact
human observes stable structure in artifact
human asks agent to extract the structure
structure becomes new instruction
future artifacts inherit the refined pattern
```

The output of one agent-assisted workflow becomes training evidence for
the next workflow inside the same repo or methodology system.


## Why It Matters

Many durable engineering preferences are discovered through iteration,
not known up front.

Examples:

- documentation spacing that improves readability in large repos
- section order that best reveals a workflow
- manifest field order that matches conceptual progression
- script naming that encodes execution order
- diagram boundaries that reveal responsibility handoff

Once these patterns stabilize across accepted artifacts, they should not
remain private operator taste. They can be promoted into explicit agent
guidance.


## Relationship To Structural Sensemaking

This technique is an instance of agent-assisted structural
sensemaking.

The engineer notices that prior artifacts contain latent structure. The
agent helps inspect, name, and formalize that structure. The refined
structure is then encoded as a reusable instruction.

The recursion is important:

```text
artifact -> observation -> rule -> future artifact -> refined rule
```

The repository gradually teaches its own operating model back to the
agent.


## Example

An engineer notices that three long pipeline-stage Markdown files share
a readable structure:

- clear major `##` narrative sections
- additional vertical spacing before major sections
- separators around major transitions
- governing-principle callouts
- semantic rather than alphabetical ordering

Rather than relying on memory, the engineer asks the agent to inspect
those files and codify the formatting pattern into a global agent
instruction.

The previous artifacts become input evidence for the next prompt.


## Useful Prompt Shape

```text
Inspect these accepted artifacts.
Identify the structure they share.
Separate durable formatting rules from one-off content choices.
Write a reusable agent instruction that preserves the discovered style
without overfitting to the examples.
```


## Guardrails

- Do not promote a pattern from a single artifact unless the user says
  it is intentional.
- Distinguish stable style from accidental formatting drift.
- Prefer local repository evidence over generic style rules.
- Do not overfit: extract the principle, not every incidental detail.
- Keep the resulting instruction small enough for future agents to
  follow.
- Treat user intent as authoritative when it conflicts with inferred
  artifact patterns.


## Decision Rubric

Codify an artifact-derived pattern when:

- it appears across multiple accepted artifacts
- it reduces cognitive friction for future readers
- it clarifies responsibility, order, or meaning
- it helps future agents avoid repeating settled decisions
- it can be expressed as a reusable rule rather than a one-off note

Leave it uncodified when:

- the pattern is accidental
- the pattern is purely aesthetic
- the repo has conflicting examples
- the rule would be too narrow to reuse


## Working Definition

Recursive artifact-derived prompting is an AI-assisted workflow in
which previously accepted outputs are inspected as evidence, distilled
into explicit rules, and fed back into future agent instructions so the
repository's learned structure becomes durable.

