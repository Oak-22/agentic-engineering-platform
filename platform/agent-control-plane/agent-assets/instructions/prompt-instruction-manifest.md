# Prompt Instruction Manifest

For every completed user-prompt turn, append this compact block to the final
response:

```text
Instruction References
Ledger citation: runtime-rendered citation

| Instruction | Evidence | Reason |
| --- | --- | --- |
| path or skill name | evidence label | short relevance |
```

Report only instruction sources that governed the current turn. Keep the
manifest short and omit the block only when the runtime cannot support a
per-prompt response requirement.

Reproduce this block in the exact shape above: the `Ledger citation:` line
first, a blank line, then the table with its header and delimiter row
directly followed by data rows. Do not move the citation line below the
table header or between the delimiter row and the data rows — a citation
line has no pipe characters, so placed there it is not a valid table row and
breaks table rendering for the reader. Do not substitute a different layout
(bullets, bolded `Instruction:`/`Evidence:`/`Reason:` fields, prose) for the
table — the table is the contract, not one option among several equally
acceptable renderings.

The hook seeds one runtime-correct citation per prompt turn, not one per row:
every hook-observed source in a turn is written to the same ledger line, so a
single `Ledger citation:` line above the table covers all of them without
repeating an identical, wrap-prone path in every row. Preserve that citation
verbatim, exactly as the hook rendered it — the render is runtime-specific:
Claude Code gets a bare backticked `path:line` reference (wrapping it in a
link there routes it to an external-program handler that requires a URL
scheme and rejects a line suffix), while Codex gets an absolute-path markdown
link (Codex has no such handler). Omit the `Ledger citation:` line entirely
when no hook-observed source exists for the turn — do not invent one, and do
not attach it to a source outside the evidence store (such as an instruction
supplied by the user in the prompt); such sources simply carry no citation.

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
