# session-title (Claude Code, user scope)

Names each Claude Code tab `<model> | <branch>` — or `<model> | <folder>` when the
working directory is not a git repository or has no branch — and keeps it current across
model switches and branch changes. When the session owns an active governed-delivery
worktree, the title is `<model> | <JIRA-KEY> | #<pr> <gate> | <branch>` instead, where
`<gate>` is `⏳` (checks pending), `✓` (all passed) or `✗` (any failed) from the PR's
checks; the PR segment is omitted until one exists. Yields permanently to a tab the user
has renamed.

Runtime-owned: `sessionTitle` is a Claude Code `hookSpecificOutput` field with no
portable equivalent. User-scope: registered in the machine-local `~/.claude/settings.json`,
so it fires in every session on the machine regardless of repository.

## Implementation

`platform/agent-control-plane/scripts/session_title_hook.sh <subcommand>`, one subcommand
per event:

| Event | Subcommand | Does |
| --- | --- | --- |
| `SessionStart` (startup, resume, fork) | `start` | Sets the title; establishes or restores ownership. |
| `UserPromptSubmit` | `refresh` | Re-derives the title once per prompt so a branch or model change reaches the tab on the next turn; detects a user rename. |
| `PostModelSwitch` | `model-switch` | Records the new model (this event cannot set a title). |
| `SessionEnd` | `cleanup` | Removes the session's state file. |

State: `~/.claude/hooks/state/<session_id>.json` =
`{model, title, userOwned, prBranch, pr, gatePr, gate, gateAt}`. Runtime output, not source.

## Delivery-aware title

During governed delivery the primary checkout stays pinned to `workbench/local`, so the
working directory's branch says nothing about what the session is delivering. The
worktree claim registry does: `delivery_worktrees.py list` reports each active claim with
its owning agent, and that owner id is `claude:<first 8 chars of session_id>`. On every
`start` and `refresh` the hook looks up this session's claim (local read, ~120 ms) and,
when one exists, titles the tab with the Jira key (the branch's second segment), the pull
request, and the branch.

The pull request number is the one input that costs a network round-trip
(`gh pr list --head <branch>`), so it is resolved once per claimed branch and cached in
the state file as `prBranch`/`pr`. A later refresh re-queries only when the claimed
branch changes or no PR was found last time — so a PR opened after the first lookup is
picked up on the next prompt, and once found it never costs another call.

The gate glyph exists because a delivery session waiting on its PR is idle at the prompt
behind a monitor, and the tab's own activity glyph reports only the main turn — so from
the tab strip an in-flight delivery and a finished one look the same. The PR's check
state lives in GitHub, not in the session, so the hook can show it regardless. One
`gh pr checks` call costs about a second, so it is cached as `gatePr`/`gate`/`gateAt`
and re-queried only when there is no cached state, when the cached state is pending or
unknown and older than 60 s, or when it is settled and older than 10 min (a new push
reopens the gate). An unknown state — no checks yet, or GitHub unreachable — is cached
like a pending one. While a gate is in flight that bounds the cost to one call per minute
per session; once green it is near zero.

The lookup runs the `delivery_worktrees.py` that sits next to the hook script, against the
current repository's toplevel. It never executes the copy the current repository ships:
the hook fires in every repository the user opens, so running repository-local code would
let any cloned repository execute code on session start. The current repository's copy is
only tested for existence, as the signal that it carries a claim registry.

Sessions with no claim, and repositories without the registry script, fall back to the
branch-or-folder title unchanged.

## Ownership latch

`session_title` in the hook payload reports whatever title is already set. On a resume or
fork that is the title this hook set earlier, so it is not evidence of a `/rename` on its
own. Ownership is tracked explicitly: a title equal to the one last written by the hook is
still the hook's; any other non-empty title means the user renamed the tab, and
`userOwned: true` makes every later invocation a no-op for that session.

## Registration (`~/.claude/settings.json`)

```json
"hooks": {
  "SessionStart":     [{"matcher": "startup|resume|fork", "hooks": [{"type": "command", "command": "<repository-root>/platform/agent-control-plane/scripts/session_title_hook.sh start"}]}],
  "UserPromptSubmit": [{"matcher": "*", "hooks": [{"type": "command", "command": "<repository-root>/platform/agent-control-plane/scripts/session_title_hook.sh refresh"}]}],
  "PostModelSwitch":  [{"matcher": ".*", "hooks": [{"type": "command", "command": "<repository-root>/platform/agent-control-plane/scripts/session_title_hook.sh model-switch"}]}],
  "SessionEnd":       [{"matcher": "*", "hooks": [{"type": "command", "command": "<repository-root>/platform/agent-control-plane/scripts/session_title_hook.sh cleanup"}]}]
}
```

`<repository-root>` stands for the developer's local checkout of this repository; each
developer substitutes their own path when adding the block to `~/.claude/settings.json`,
which is why the registration is user-scope and never committed. The command references
the canonical script path directly, per the hook adapter rule in
`../instructions/agent-context-routing.md`. Guards (`verify_hook_registrations.py`,
`validate_asset_registries.py`) check this registration on a machine where
`~/.claude/settings.json` exists and report it as unconfirmed elsewhere.
