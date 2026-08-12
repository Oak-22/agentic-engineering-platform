# Hook Registry

This directory owns the canonical hook inventory and portable lifecycle
guidance.
The exhaustive inventory is maintained in
[`hooks_registry.json`](hooks_registry.json), which records centralized and
runtime-owned hooks, implementations, registrations, events, and documentation
paths.

Runtime-native configuration remains authoritative for activation. The
registry is used for discoverability, review, and validation; provider files do
not import it at runtime.

## Canonical hook model

Add a canonical hook definition when a concrete lifecycle action has portable
intent. The registry records the hook's lifecycle intent, ownership,
implementation, runtime registrations, and documentation. Detailed timeout,
payload, context, and failure semantics belong with the implementation or
runtime adapter that owns them.

Provider event names, configuration syntax, supported versions, and renderers
belong in [`../../adapters/runtimes/`](../../adapters/runtimes/).

Keep general control-plane executables in [`../../scripts/`](../../scripts/).
Colocate a script here only when it is an intrinsic, portable resource of one
hook package. Hooks support lifecycle automation and observation; they do not
replace sandboxing, managed execution policy, CI, IAM, or other enforcement
boundaries.

Reusable workflows follow the canonical-first skill flow described in
[`../skills/README.md`](../skills/README.md). A provider-specific lifecycle
feature may remain runtime-native when its event, payload, or capability has no
portable equivalent. Each runtime-owned registry entry must identify its owner
and link to the runtime-native documentation; it must not imply cross-runtime
parity.
