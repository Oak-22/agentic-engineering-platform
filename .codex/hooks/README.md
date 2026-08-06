# Codex Hooks

This directory contains Codex-specific lifecycle hook commands.

## Diverges from Codex's default layout

Codex's documented convention saves a hook's script body directly under
`.codex/hooks/` (for example `.codex/hooks/pre_tool_use_policy.py`) and points
`hooks.json` at it, resolved from the git root rather than a bare relative
path. This repository does not follow that half of the convention: every hook
command actually registered here lives in
[`platform/agent-control-plane/scripts/`](../../platform/agent-control-plane/scripts/)
and is invoked from [`../hooks.json`](../hooks.json) by its full repository
path instead. This directory currently holds no scripts.

That's a deliberate centralization, not an oversight. The same script bodies
(`instruction_manifest_hook.py`, `provider_docs_session_start.py`) are also
invoked from [`../../.claude/settings.json`](../../.claude/settings.json);
each call selects its runtime with a `--runtime codex` / `--runtime claude`
flag. A script saved under this directory would be Codex-only and would have
to be duplicated under `.claude/hooks/` to reach Claude Code — keeping the
implementation in the provider-neutral `agent-control-plane/scripts/`
directory instead lets one script serve both. This directory stays reserved
for the case where a future hook is genuinely Codex-only, with no Claude Code
equivalent to share.

## Hook events

Hook event names, matcher config, trust behavior, and release support are
defined by OpenAI and change on OpenAI's schedule, not this repository's.
Rather than maintain a copy of that list here — which drifts the moment a new
event ships — consult the source directly:

- [Official Codex hooks reference](https://learn.chatgpt.com/docs/hooks)
- A local mirror refreshed once per session by
  [`provider_docs_session_start.py`](../../platform/agent-control-plane/scripts/provider_docs_session_start.py),
  for offline or greppable lookup

## Activation

This directory does not activate anything by itself. Project hooks become
active only when registered in [`../hooks.json`](../hooks.json) or a trusted
plugin-bundled equivalent — read that file directly for this repository's
actual hook registrations rather than relying on a description of them here.
