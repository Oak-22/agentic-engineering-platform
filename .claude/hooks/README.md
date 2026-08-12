# Claude Code Hooks

This directory documents Claude-specific lifecycle hook commands.

The centralized hook registry is
[`platform/agent-control-plane/agent-assets/hooks/README.md`](../../platform/agent-control-plane/agent-assets/hooks/README.md).
This runtime README owns only Claude-specific activation, payload, and
provider-capability details.

## Runtime-owned hooks

### Artifact archive

Claude Code's `PostToolUse` event with the `Artifact` matcher invokes
[`archive_artifact_publish.py`](../../platform/agent-control-plane/scripts/archive_artifact_publish.py)
from [`settings.json`](../settings.json). The hook copies the exact published
file to a local archive outside the repository so it survives session end.

This is intentionally Claude-only. Codex has no corresponding `Artifact`
event contract, so it has no registration or claimed parity for this hook.
The archive is a local convenience mirror, not a portable skill or a
repository-write hook.


## Diverges from Anthropic's default layout

Anthropic's documented convention saves a hook's script body directly under
`.claude/hooks/` (for example `.claude/hooks/block-rm.sh`) and points
`settings.json` at it with `${CLAUDE_PROJECT_DIR}/.claude/hooks/...`. This
repository does not follow that half of the convention: every hook command
actually registered here lives in
[`platform/agent-control-plane/scripts/`](../../platform/agent-control-plane/scripts/)
and is invoked from [`../settings.json`](../settings.json) by its full
repository path instead. This directory currently holds no scripts.

That's a deliberate centralization. The same script bodies
(`instruction_manifest_hook.py`, `provider_docs_session_start.py`) are also
invoked from [`../../.codex/hooks.json`](../../.codex/hooks.json); each call
selects its runtime with a `--runtime claude` / `--runtime codex` flag. A
script saved under this directory would be Claude-only and would have to be
duplicated under `.codex/hooks/` to reach Codex — keeping the implementation
in the provider-neutral `agent-control-plane/scripts/` directory instead lets
one script serve both. This directory stays reserved for the case where a
future hook is genuinely Claude-only, with no Codex equivalent to share.

## Hook events

Hook event names, matchers, input/output schemas, and release support are
defined by Anthropic and change on Anthropic's schedule, not this
repository's. Rather than maintain a copy of that list here — which drifts
the moment a new event ships — consult the source directly:

- [Official Claude Code hooks reference](https://code.claude.com/docs/en/hooks)
- A local mirror refreshed once per session by
  [`provider_docs_session_start.py`](../../platform/agent-control-plane/scripts/provider_docs_session_start.py),
  for offline or greppable lookup

## Activation

This directory does not activate anything by itself. Project hooks become
active only when registered in [`../settings.json`](../settings.json) or
packaged through another supported configuration surface — read that file
directly for this repository's actual hook registrations rather than relying
on a description of them here.
