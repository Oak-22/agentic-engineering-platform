# Instruction evidence store

The instruction-evidence store is generated local runtime evidence. It is not
an authored repository knowledge base and it does not contain prompt text.
Canonical data is kept outside the repository, partitioned by repository
identity. The ignored `.aep/instruction-evidence` path is a project-local view
of that partition.

The generated `store-index.json` is the machine-readable description of this
layout and is validated by
[`instruction-evidence-store.schema.json`](../contracts/instruction-evidence-store.schema.json).

## Record taxonomy

| Path pattern | Kind | Scope | Runtime source | Lifecycle |
| --- | --- | --- | --- | --- |
| `repository.json` | Generated metadata | Project | Hook storage initialization | Safe to recreate; safe to retain or delete with the partition |
| `store-index.json` | Generated index | Project | Hook storage initialization | Safe to recreate; safe to retain or delete with the partition |
| `<session-id>.jsonl` | Generated session ledger | Session | Runtime is recorded in each event | Append-only during a session; safe to rotate or delete after citation-dependent work is complete |

The session identifier may be a UUID or a human-readable diagnostic name.
That naming difference does not imply a different authority or retention class.

Each session ledger may contain multiple events:

- `instruction_loaded`: a runtime observation of an instruction load. Claude
  Code emits these through its `InstructionsLoaded` hook event; the event may
  carry a prompt identifier when the runtime supplies one.
- `prompt_manifest`: one compact instruction-reference manifest for a submitted
  prompt or turn. It records the runtime and the typed evidence records used to
  render the response contract.

Therefore, a JSONL file is session-scoped, while `prompt_manifest` events are
prompt-scoped. The filename alone cannot identify the runtime or the number of
prompts it contains; inspect its events.

No authored artifacts are expected in this store. Tests and diagnostics may
use human-readable session identifiers, but those files remain generated
runtime evidence.

## Retention guidance

Retain a session ledger while a response citation, incident investigation, or
reproducibility record depends on it. Rotate or delete ledgers when that
dependency has ended. The project view is disposable: removing it does not
remove canonical data, and removing the canonical partition removes only local
runtime evidence, not repository source or prompt text.

The store index is descriptive metadata, not an audit record. It may always be
regenerated from the hook implementation and the schema.
