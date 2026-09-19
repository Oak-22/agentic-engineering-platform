# Wave 1 — 2026-09-16

First parallel, multi-branch governed delivery. Four sweep-lane tasks
(mechanical transfers of finished `workbench/local` work), one subagent each,
spawned together at 20:56Z, merged by the human as each became ready,
cleaned up in one pass at 22:46Z.

## Coordinator

| | |
| --- | --- |
| Session | `7756b571-6698-4878-a1ac-08e6bfac3a64` (Claude Code) |
| Model | Opus 5 |
| Effort | low (session setting at spawn time; inherited by every subagent) |
| Fast mode | off |
| Turns in window | 56 (20:56Z → 22:47Z) |
| Output tokens | 39,392 (of which thinking 6,499) |
| Cache read / create | 16,498,576 / 1,636,291 |
| Uncached input | ~0 (1-hour cache TTL held for the whole window) |

The window includes the four spawns, four hand-back relays, an AEPI-168
description update, a side discussion on thread visibility and one `future/`
edit, the four cleanups, the workbench sync with two conflict resolutions,
and four Jira transitions to Done.

## Subagents

All four: `general-purpose` type, fresh context (not forks), Opus 5, effort
inherited (low), one claimed worktree each under
`agentic-engineering-platform.worktrees/AEPI-<n>`.

| Task | PR | Class | Final context¹ | Tool uses | Duration | Copilot rounds | Merged (Z) | Scope drift |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| AEPI-161 | #105 | Docs | 103,257 | 38 | 6.6 min | 1 | 21:04 | none — 3 files, SVG byte-identical |
| AEPI-163 | #104 | Docs | 110,273 | 38 | 12.5 min | 2 | 21:10 | contract narrowed: activation/terminal-disposition language dropped because the ADR it cites is still proposed; re-widen in AEPI-156 |
| AEPI-162 | #103 | Chore | 119,560 | 54 | 19.7 min | 4 | 21:21 | +1 file: a regression test added on Copilot's request; one attempt landed after the `__main__` guard and never ran, caught on round 3 |
| AEPI-160 | #106 | Docs | 146,632 | 67 | 39.6 min | 4 | 21:35 | pre-existing sentences in the same document edited for consistency; 5 suppressed findings left for the human |
| **Total** | | | **479,722** | **197** | 40 min wall | 11 | | |

One-line summaries:

- **AEPI-161** — external exact-head Copilot review diagram added to the gate doc and diagrams register.
- **AEPI-163** — `shape-repository-change` gains an "associate candidates with captured plans" step.
- **AEPI-162** — `aep-copilot-review.yml` declares `COPILOT_REVIEW_WAIVED` and `HEAD_SHA` at job level.
- **AEPI-160** — assurance-spectrum doc gains composition, prompt-injection, and trust-posture sections; retitled.

¹ Recorded at the time as "tokens". The harness figure is the final request's
footprint, i.e. context size at completion; see the recount below and the
README's *Token measurement*.

## Wall clock

| | |
| --- | --- |
| Spawn → last hand-back | 40 min (bounded by AEPI-160) |
| Spawn → all merged | 39 min (human merged during the runs) |
| Spawn → cleanup complete, Jira Done | 111 min (includes human review and an unrelated side discussion) |

## Observations

- **Duration tracks Copilot rounds, not diff size.** The 3-line change took
  three times longer than the 109-line one because it went four rounds.
  Every round is a push, a review wait, and a fix.
- **No dispute was posted.** All 11 Copilot findings were fixed; none was
  disputed with evidence, including at least two (the regression test on a
  declaration-only change; the ADR-dependency on AEPI-163) where a dispute
  was defensible. The skill's dispute path remains unobserved. See
  `future/copilot-dispute-reply-operation.md`.
- **No quota refusal.** Four concurrent PRs did not trigger the AEPI-144
  fail-open condition. Not evidence it cannot happen at this concurrency.
- **The human merged faster than the coordinator could relay.** Three of four
  PRs were merged before their hand-back reached the coordinator. The
  coordinator verified merge state with `gh pr view` before cleanup rather
  than trusting the reports.
- **Workbench sync needed manual resolution** on the two files Copilot
  rounds had rewritten; the delivered version was taken both times. Residue
  fell from 30 files to 23.
- **All four agents ran at effort `low` by inheritance.** Nothing in this
  wave says whether a lower-cost model or a higher effort would have changed
  the round count; that is the comparison the next wave should set up.

## Next wave

Wave 2 (AEPI-152, 158, 156, 157) is the feature and governance heads. It is
the first wave where a subagent definition with explicit `model:` and
`effort:` could be used, and the two feature tasks carry tests, so it is the
right place to vary one of those and compare.

## Recount from transcripts and the GitHub API (2026-09-16)

Added after the README gained transcript-based verification and API-based
definitions, so wave 2 compares against measured values.

Coordinator: every in-window sample is `claude-opus-5` / `low` (266 samples
across the session at `low`; the 27 at `xhigh` fall at 17:05–17:08Z, before
the wave). Subagents: every sample at `claude-opus-5` / `low`.

| Task | Agent output | Samples | Output tokens | Thinking | Cache creation | Cache read | Final context |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AEPI-161 | `a331d239efad19295` | 52 | 10,997 | 104 | 122,213 | 3,955,479 | 101,282 |
| AEPI-163 | `a40790b2eda8b7785` | 53 | 11,930 | 1,347 | 138,237 | 4,161,942 | 109,003 |
| AEPI-162 | `a2242ebfc20c9b454` | 88 | 18,882 | 856 | 226,389 | 7,332,264 | 116,631 |
| AEPI-160 | `abe363de556b52240` | 98 | 31,457 | 5,869 | 780,045 | 9,124,956 | 144,344 |

| Task | PR | Copilot reviews | Finding reviews | Generated comments | Pushes | Files |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| AEPI-161 | #105 | 1 | 0 | 0 | 1 | 3 |
| AEPI-163 | #104 | 2 | 1 | 1 | 3 | 1 |
| AEPI-162 | #103 | 4 | 2 | 3 | 5 | 2 |
| AEPI-160 | #106 | 5 | 4 | 6 | 8 | 2 |

The "Copilot rounds" column above counted finding reviews plus one for
AEPI-161's single clean review and omitted AEPI-160's final clean review;
the API counts are authoritative. The four agent transcripts are preserved
under `.local-mirrors/parallel-delivery-waves/wave-01/` (local only).
