# Prompt Instruction Manifest

For every completed user-prompt turn, append this compact block to the final
response:

```text
Instruction References
| Instruction | Evidence | Citation | Reason |
| --- | --- | --- | --- |
| path or skill name | evidence label | `evidence-log-path:line` | short relevance |
```

Report only instruction sources that governed the current turn. Keep the
manifest short and omit the block only when the runtime cannot support a
per-prompt response requirement.

The hook seeds a citation for every evidence type as a workspace-relative
`path:line` reference to the evidence log. Preserve that citation verbatim with
its evidence label, and keep it a bare reference: wrapping it in a link routes
it to an external-program handler instead of opening the log. Both fields derive from the same
validated instruction-evidence record; do not pair a citation with a different
evidence type. Use `Unavailable` in the Citation column only for a source
outside the evidence store, such as an instruction supplied by the user in the
prompt, rather than inventing proof.

Use these evidence labels precisely:

- `Observed`: the runtime emitted an authoritative instruction-load event.
- `Runtime baseline`: the runtime's documented discovery rules identify the
  instruction as active for the current repository scope.
- `Explicitly invoked`: a skill or instruction was named for this turn, whether
  the user typed it or the agent invoked it.
- `Read during turn`: the agent opened and applied the instruction during this
  turn.
- `Declared`: a runtime adapter requires the instruction, but the runtime does
  not expose an authoritative load event.

The hook seeds the manifest from evidence recorded before the prompt was
submitted. Skills invoked and instructions read after that point are recorded
too, but reach the seed on the following turn, so add them yourself for the
current turn. Do not upgrade inferred evidence to `Observed`.

Do not include chain-of-thought, prompt contents, ordinary source files,
documentation consulted as subject matter, web citations, or tool output.
Use repository-relative paths where possible and `~/` for paths under the
user's home directory.
