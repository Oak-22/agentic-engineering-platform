# Hooks

Place GitHub-native machine guardrails here as runtime configuration.

Examples include pre-tool checks, post-edit validation, and
pre-response gating.

Hook installation remains runtime-native because lifecycle events, tool names,
and permission semantics differ across agent surfaces. Portable hook intent
and resources remain canonical under
`platform/agent-control-plane/agent-assets/hooks/`; runtime capability mappings
and renderers belong under
`platform/agent-control-plane/adapters/runtimes/github-copilot/`.

The prompt instruction manifest currently uses a durable Copilot instruction
adapter because this repository does not claim an authoritative
instruction-loaded event for that runtime.
