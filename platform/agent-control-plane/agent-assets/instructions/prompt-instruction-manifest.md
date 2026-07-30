# Prompt Instruction Manifest

For every completed user-prompt turn, append this compact block to the final
response:

```text
Instruction References
| Instruction | Evidence | Reason |
| --- | --- | --- |
| path or skill name | evidence label | short relevance |
```

Report only instruction sources that governed the current turn. Keep the
manifest short and omit the block only when the runtime cannot support a
per-prompt response requirement.

Use these evidence labels precisely:

- `Observed`: the runtime emitted an authoritative instruction-load event.
- `Runtime baseline`: the runtime's documented discovery rules identify the
  instruction as active for the current repository scope.
- `Explicitly invoked`: the user named a skill or instruction for this turn.
- `Read during turn`: the agent opened and applied the instruction during this
  turn.
- `Declared`: a runtime adapter requires the instruction, but the runtime does
  not expose an authoritative load event.

An injected hook seed is a starting point. Add explicitly invoked skills and
instructions read later in the turn. Do not upgrade inferred evidence to
`Observed`.

Do not include chain-of-thought, prompt contents, ordinary source files,
documentation consulted as subject matter, web citations, or tool output.
Use repository-relative paths where possible and `~/` for paths under the
user's home directory.
