---
name: capture-session-trail
description: Capture what an agent actually said and did during a session — message text plus tool-call summaries, per turn — into a reviewable, machine-local Markdown snapshot a human teammate can read. Use when someone needs to review an agent's real working trail rather than its summary, or asks to capture, snapshot, or share a session. Never fires automatically at session end.
---

# Capture Session Trail

Turn a live session transcript into something a *human teammate* can read
and judge. The audience is the distinction: `handoff-agent-work` packages
authored intent and authority so another **agent** can continue work;
this skill exposes the raw working trail so a **person** can review what an
agent actually did. Link out to a handoff packet when one exists for the
same work rather than restating it here.

Every capture reads the live producer through the one shared reader at
`platform/agent-control-plane/scripts/session_transcript_reader.py`. Never
re-derive session path discovery or JSONL parsing — a second parser against
the same producer is the drift this reader exists to prevent.

## What this surface can and cannot show

Read
`platform/agent-control-plane/docs/strategy/session-transcript-reader.md`
before promising a reviewer anything. Not everything in a snapshot carries
the same weight, and the difference is the whole point:

| Layer | Fidelity | Notes |
| --- | --- | --- |
| Tool calls and results (`tool_calls`) | Exact, 1:1 | Copied from the log; results truncate at 400 chars |
| Message text (`text`) | Exact, 1:1 | Verbatim, per turn |
| Reasoning-token count (`thinking_tokens`) | Exact | Proves reasoning happened; says nothing about its content |
| Raw reasoning | **Absent** | The provider strips it; no code change recovers it |
| Thinking summary, if enabled | **Paraphrase** | The model's own gloss on its reasoning, not the reasoning |

Reasoning is the one that surprises people. A Claude transcript proves
reasoning happened — `usage.output_tokens_details.thinking_tokens` carries
a real count, six figures on a long session — while the matching
`content[].thinking` is `""` with only an opaque signature. That gap is
expected: closed-source providers withhold the underlying chain-of-thought
by design.

`showThinkingSummaries: true` is worth knowing about and genuinely useful
to a reviewer — it surfaces a paraphrased summary for sessions run
**after** it is enabled, and cannot backfill an already-written
transcript. Two rules hold regardless: never flip that setting, or any
other runtime setting, on the user's behalf — it is theirs to turn on; and
never present a summary as the underlying reasoning. It is a lead worth
checking, not evidence of what the agent actually thought. Every snapshot
says so in its own header, so a reviewer who never reads this file still
gets the distinction.

## Workflow

1. Confirm which session to capture. `--list` prints recent candidates for
   a runtime, most recent first; the default with no `--session` is the
   most recently modified transcript. "This session" is declared in the
   context the instruction-manifest hook injects each prompt — see
   [Resolving "this session"](../../../docs/strategy/session-transcript-reader.md#resolving-this-session).
   Do not treat the most-recent default as identification when resuming an
   older session or running two sessions in one project; name the session
   explicitly instead.
2. Run the capture in `--dry-run` first. This is the redaction review
   gate and the reason this skill is manual: a snapshot is raw session
   content, and a human decides whether it is fit to be read by someone
   else *before* it is written anywhere.

   ```bash
   python3 platform/agent-control-plane/agent-assets/skills/capture-session-trail/scripts/render_session_snapshot.py \
     --runtime claude --dry-run
   ```
3. Review the dry-run output with the user for credentials, private
   overlays, machine-specific paths, or anything else that should not be
   read by a teammate. If any appears, stop and resolve it with the user —
   do not silently strip content and present the result as complete.
4. Write the snapshot, passing `--repo-root` to create the repo-local view:

   ```bash
   python3 .../render_session_snapshot.py --runtime claude \
     --project-dir . --repo-root .
   ```
5. Re-invoke at any later point to append only turns recorded since the
   last capture. The cutoff is a trailing watermark comment inside the
   snapshot itself, not a sidecar — the file is the whole state, and
   deleting it fully resets the capture. If the transcript was truncated or
   rewritten the script refuses to append and says so; delete and
   re-capture rather than forcing it.
6. Tell the user the exact path written, and that this location is
   machine-local and **not** visible to anyone else yet.

## Making a snapshot teammate-visible

Writing the snapshot does not share it. `.local-mirrors/` is gitignored,
so the repo-local view is a convenience for opening the file from inside
the editor — nothing more.

Sharing requires the existing manual promotion convention in
[`docs/local-doc-mirrors.md`](../../../docs/local-doc-mirrors.md#artifact-promotion):
a deliberate, one-off human decision to copy one reviewed file into a
tracked repository path. Do not invent a new promotion mechanism, do not
automate this step, and confirm the destination path with the user — a
promoted snapshot is raw session content becoming permanent repository
history.

## Boundaries

- Manual invocation only. Never wire this to `Stop`, `SessionEnd`, or any
  other automatic trigger: continuous capture removes the human review
  point before content becomes visible to someone else, which is the
  entire safety property of this design.
- Never write tracked repository content. The snapshot root is outside
  version control, and its repo-local view is a symlink into an
  already-gitignored path.
- Never modify the source transcript. The reader is read-only and this
  skill keeps it that way.
- Never flip `showThinkingSummaries`, or any other runtime setting, to
  widen what a snapshot can show. Explaining what it would do is helpful;
  turning it on is the user's call, not yours.
- Never let a thinking summary read as the agent's actual reasoning, in a
  snapshot or in conversation. Label it as a paraphrase every time.
- Do not capture a session the user has not identified when more than one
  plausible candidate exists — ask which one.
