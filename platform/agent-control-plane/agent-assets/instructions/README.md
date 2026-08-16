# Shared Instructions

These files contain reusable instruction bodies. Runtime adapters attach the
path selectors and discovery metadata required by each agent surface.

The exhaustive instruction inventory is maintained in
[`instructions_registry.json`](instructions_registry.json). It records each
canonical instruction, the runtime adapters expected to import it, its
`kind`, and its `trigger`.

`kind` distinguishes two different things this directory holds:

- `map` — describes repository or system structure (where things live, how
  discovery works). Read when reasoning about the structure itself, not
  applied on ordinary tasks.
- `behavior` — prescribes what an agent should do while performing a task.

`trigger` says when an instruction is relevant: `always`, or a short
description of the condition (a language, a tool, a subsystem) that makes it
apply. This is orthogonal to `kind` — a `map` file can be conditionally
triggered, and a `behavior` file can apply unconditionally.

`scopeGlobs` and `copilotDescription` (present only on instructions with
non-empty `runtimeAdapters`) are not free-form metadata like `kind`/`trigger`
— they're the canonical source `scripts/generate_instruction_adapters.py`
renders into each runtime's adapter frontmatter. Edit them, then regenerate;
don't hand-edit adapter frontmatter directly.

Other distinctions (audience, mechanical enforcement vs. convention, whether
an instruction is about the instruction system itself vs. ordinary task
work) are real but currently exercised by only one file each; they're
documented in prose within the file itself rather than tracked as registry
fields. Promote one to a field if a second instruction starts varying along
it.
