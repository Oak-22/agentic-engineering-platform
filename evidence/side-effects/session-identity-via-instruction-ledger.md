# Session identity travelled through the instruction-evidence ledger

**Observed:** 2026-08-19, during a session building the
`capture-session-trail` skill.
**Component:** `platform/agent-control-plane/scripts/instruction_manifest_hook.py`
**Depended on by:** `capture-session-trail`, resolving "this session" to a
transcript filename.
**Resolution:** declared. See [What changed](#what-changed).

## How it surfaced

The user asked the agent to capture "this session." That requires mapping
the phrase to one file under `~/.claude/projects/<slug>/<uuid>.jsonl`. The
agent produced the correct file immediately, and the user asked the right
question: where did that come from? They had not supplied it.

Neither had the skill. `locate_sessions` enumerates candidate transcripts
and sorts them by modification time; it has no concept of which session is
live. The runtime does expose a session identifier to the agent — the
`session_...` value in the git-trailer instructions — but that is a
different namespace from the transcript UUID and does not resolve a
filename.

## The mechanism

Traceable in three hops, all verifiable from source:

1. Claude Code passes `session_id` to the hook in its `UserPromptSubmit`
   payload; `handle()` reads it via `payload.get("session_id")`.
2. `ledger_path()` composes the evidence ledger's location as
   `<runtime>/<session-id>.jsonl`.
3. `additional_context()` injects a `Ledger citation:` line naming that
   path into the agent's context on every prompt.

The agent read the session UUID back out of the filename. Session identity
reached it through the instruction-evidence ledger — a component built for
governance traceability, with no identity responsibility whatsoever —
because a path built to be unique per session is, incidentally, an
announcement of which session this is.

## Classification

A **side effect**: it follows directly from the path format plus the
injection site, and one reading of `ledger_path()` predicts it exactly.

The useful name is [Hyrum's Law](https://www.hyrumslaw.com/) — with enough
consumers, every observable behavior of a system acquires a dependent,
regardless of what the contract promises. The session UUID's legibility in
the citation path was never promised. It acquired a dependent anyway.

The warning that framing carries is the operative part: **undeclared
interfaces break while the declared contract is still being honored.**
Hashing the session ID, or restructuring the ledger to
`<date>/<counter>.jsonl`, would be an unremarkable refactor that satisfies
every stated requirement and silently removes a capability something else
was using.

## Why it was worse than merely undeclared

`additional_context()` set `citation_line` to `""` when a turn had no
hook-observed sources. The session UUID was therefore **conditionally
present**, not merely undeclared.

This repository never hit that case, because `.claude/rules/` guarantees
at least one `Declared` source every turn. A consuming repository without
those rules would get no citation — and the agent would fall back to
`resolve_session_path`'s "most recently modified transcript" heuristic.

That heuristic is correct whenever the live session is the one being
appended to, and wrong in two ordinary situations:

- resuming an older session, where a more recently touched transcript wins
- two sessions open on one project, where the other one wins

Both fail silently. The capture succeeds, against the wrong session, and
produces a plausible artifact attributed to the wrong work.

## What changed

Declared, rather than removed. The hook now states session identity
explicitly in the injected context, unconditionally — alongside the
`Runtime:` declaration that was already there and already served exactly
this role for a different fact.

Removing the dependency instead (requiring `--session` on every capture)
was rejected: the capability is genuinely useful, an agent that cannot
identify its own session cannot act on "this session" at all, and pushing
that onto the user every time trades a silent failure for a permanent
papercut. Declaring it costs one line and converts an accident into a
contract that a future refactor will see.

The `Ledger citation:` line still carries the session UUID in its path.
That is now redundant rather than load-bearing, which is the point:
nothing depends on it being legible any more.
