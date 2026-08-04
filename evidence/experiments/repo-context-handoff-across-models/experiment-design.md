# Experiment Design

## Question

Does a governed handoff derived from historical Codex sessions materially
improve a newly introduced Claude session's repository model, compared with
repository discovery alone?

## Why this matters to the platform

AEP's working claim is that model providers are becoming interchangeable while
the surrounding context system is not. A repository accumulates instruction
files, runtime adapters, delivery conventions, and a long tail of decisions that
exist only in session history. That history is provider-local: Codex sessions do
not transfer to Claude, and neither transfers to a new machine or a new
teammate.

If durable repository knowledge can be extracted, labelled as derived, and
injected into a different provider's memory channel, then context becomes a
governed artifact rather than a lock-in surface. The failure mode is equally
important: a handoff that promotes historical claims into apparent canonical
requirements, or that carries private transcript detail, is worse than no
handoff at all.

The experiment therefore measures two things at once — whether useful knowledge
transfers, and whether stale or contaminated authority transfers with it.

## Hypothesis

The treated answer retains the baseline's verified structural accuracy while
adding useful historical context about ownership decisions, workflow
constraints, active concerns, and unresolved questions. It does not promote
transcript claims into canonical requirements and does not become more
confidently wrong.

## Independent variable

Presence of one derived handoff document in Claude Code's repo-scoped auto
memory at session start.

## Controlled variables

- repository path, commit, and working-tree state
- exact prompt bytes
- Claude Code version, model alias, and resolved model id
- effort level, permission mode, and read-only tool set
- project instructions, hooks, and skills
- non-persistent session mode and suppressed prompt history
- provider-documentation cache contents

## Three separated roles

| Role | Provider | Sees the tested repo | Persists | Purpose |
| --- | --- | --- | --- | --- |
| Source corpus | Codex history | historical only | frozen snapshot | raw material |
| Handoff builder | Codex, ephemeral | no — empty cwd | no | corpus to `handoff.md` |
| Baseline subject | Claude, fresh | yes, clean snapshot | no | control arm |
| Treatment subject | Claude, fresh | same snapshot | no | treated arm |

The builder is Codex specifically so the source-to-target boundary is a provider
boundary rather than a self-summarization loop. It runs with
`--ephemeral --ignore-user-config --ignore-rules --sandbox read-only` from an
empty working directory, so no `AGENTS.md`, no `.codex/hooks.json`, and no MCP
server from the tested repository can reach it, and no builder session is ever
written to disk.

## Source eligibility

A Codex rollout is eligible when its recorded working directory is inside the
repository and its last timestamp is at or before the cutoff.

The cutoff is the committer timestamp of the snapshot commit
(`2026-07-31T17:37:14Z` for `5edc12cc`). This is not arbitrary: the experiment
scaffold was created after that commit, so the cutoff is simultaneously a
reproducibility control and the contamination fix. Verified at design time —
zero pre-cutoff sessions mention the harness; three post-cutoff sessions do and
are excluded.

Identity is `sha256(provider + realpath(source file))`. It is deliberately not
the session id: Codex subagent-spawn rollouts replay their parent's
`session_meta`, so reading the *last* such record makes distinct files claim the
same identity. Taking the *first* record and keying on the file yields 25 unique
sources where the superseded implementation produced three id collisions across
eight files.

Four of the 25 eligible files are subagent spawns. They are legitimate history
and stay in scope; their replayed parent turns are removed by message-hash
deduplication (103 of 1,717 messages) rather than by dropping the files.

The corpus is **frozen** into the run directory at inventory time. Everything
downstream reads the freeze, so a transcript that grows or changes mid-run
cannot alter the result. `recheck-sources` reports drift for the record.

## Quarantine

- Both subjects run with `--no-session-persistence` and
  `CLAUDE_CODE_SKIP_PROMPT_HISTORY=1`.
- Auto memory is always redirected to a run-scoped `autoMemoryDirectory`. The
  baseline additionally sets `autoMemoryEnabled: false` and
  `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`; the treatment explicitly unsets that
  variable so an inherited value cannot override the setting in either
  direction.
- The real project-memory directory is fingerprinted before and after and is
  never read, copied, moved, or written. There is no backup step because there
  is nothing to restore, which removes the crash window entirely.
- The treatment's tool set excludes `Write` and `Edit`, so the memory channel is
  read-only by construction.
- Baseline output and the handoff live outside the subject clone for the whole
  run, so neither subject's file tools can reach the other's answer.

### Why a clone rather than a worktree

Claude Code derives the auto-memory project key from the git *repository*, so
all worktrees of one repo share a single memory directory. A worktree therefore
provides no memory isolation. A worktree also presents a detached HEAD, which is
itself an unusual signal in the session's environment context. The harness
clones to a temporary path and checks out a branch named `main` at the snapshot
commit, which reproduces ordinary conditions exactly.

### Why `git status --porcelain` is not sufficient

`.gitignore` covers `product-demo` and `.aep/`, so scaffold placed there is
invisible to `--porcelain`. Snapshot integrity is checked with
`--ignored=matching` plus a tracked-file hash manifest taken before and after.
The only permitted addition is `.aep/`, which the instruction-manifest hook
creates as a symlink into the shared evidence store.

### Residual asymmetry

Auto-memory paths are part of Claude's dynamic system prompt, so a baseline with
auto memory *disabled* differs from the treatment by two things: the presence of
memory content and the presence of the memory subsystem. The optional
`--placebo` arm runs an otherwise identical session against an empty memory
directory, isolating content alone. The disabled baseline remains the primary
control.

## Handoff validation gate

The builder's output must pass every rule before it can reach a memory
directory. The rules exist because a summarizer will otherwise emit plausible
prose that fails silently.

| Rule | Checks |
| --- | --- |
| V1 | starts with the handoff heading |
| V2 | all eight sections present, in order |
| V3 | scope section declares derived, non-authoritative status |
| V4 | at least six concrete repository markers; no section under 200 characters |
| V5 | no meta-narration |
| V6 | no reference to the comparison harness |
| V7 | no transcript paths or raw session identifiers |
| V8 | no secrets, machine-specific absolute paths, or email addresses |
| V9 | within the 200-line / 25 KB `MEMORY.md` startup read limits |
| V10 | a human recorded reading the document in full |

V6 is deliberately narrow. `evidence/experiments/` is real tracked content at the
snapshot commit, so the bare word "experiment" stays allowed; only self-reference
to this harness is rejected. V5 likewise excludes bare "TODO" and "placeholder",
which are ordinary vocabulary for describing repository content.

V9 measures what Claude Code actually loads: frontmatter and block-level HTML
comments are stripped before the index is measured against its limits.

Applied to the earlier pilot's handoff, this gate fails on V6 and V8 — the
document referenced the experiment by name and carried a workstation-specific
absolute path into Claude's memory. That is the concrete case the gate exists
for.

## Measures

Score each answer from 1 to 5:

1. repository purpose
2. component and ownership-boundary accuracy
3. runtime-customization model accuracy
4. workflow and governance accuracy
5. evidence/history usefulness
6. uncertainty calibration
7. canonical-versus-derived source discipline
8. unsupported-claim penalty (reverse scored)

Scoring is blind: the harness writes `blind/A.md` and `blind/B.md` with a
randomized assignment sealed in `blind/key.json` (mode 0600). Also record word
count, headings, normalized similarity, resolved model ids, elapsed time, and
instruction-manifest evidence. Neither greater length nor lower textual
similarity is improvement by itself.

## Run status

`verify` evaluates 25 criteria and assigns one status.

- `INVALID` — any fatal criterion failed. Do not report a comparison.
- `INDETERMINATE` — the real memory directory changed during the run. The
  harness never writes there, so a delta means an external session did; the
  result is reported as unproven rather than as a mutation claim.
- `DEGRADED` — a non-fatal control failed, such as provider-doc cache drift, a
  source modified after the freeze, or an allowed concurrent Claude session.
  Reportable with the caveat stated inline.
- `VALID` — every criterion passed.

## Known measurement limits

Codex does not report a resolved model id through `codex exec --json`. Builder
provenance is therefore the pinned request (`-m` with `--ignore-user-config`, so
no profile or config default can override it) plus the CLI version, recorded as
`builder_model_requested` with `builder_model_resolved: null`. Claude's resolved
model id is available and is compared across arms.

## Interpretation

One A/B pair is a demonstration, not a causal estimate. Model sampling, different
file-reading choices, live hook output, and changing provider behavior remain
sources of variance. Repeat with reversed ordering and several fresh pairs before
calling the pattern a practice. Nothing in this design supports a claim about
providers other than the two tested.

The strongest positive result looks like:

- more relevant historical knowledge;
- equal or better verified structural accuracy;
- explicit separation of durable facts, historical observations, and open
  questions; and
- no leakage of the baseline response or private transcript detail.

## Prior pilot: exploratory evidence only

Run `20260731T180525Z` is retained as exploratory evidence and does not support
any conclusion about context portability.

- **Contaminated.** Claude Code injects `git status` into session context, and
  the scaffold was untracked in the tested working tree. Both subjects noticed:
  the baseline wrote *"This prompt is very likely the experiment"*
  (`baseline.md:54`) and the treatment wrote *"This response is plausibly the
  experiment's input"* (`treatment.md:49`).
- **Mixed provider corpus.** 10 Claude and 26 Codex sessions, so the Codex-only
  design was never exercised.
- **Broken source identity.** Three session ids claimed by eight files.
- **No cutoff.** Sources ran past the pilot itself.
- **Weak validation.** A single heading check and a length ceiling.
- **Mutated the real memory directory**, leaving a stale backup from an earlier
  partial run.
- **Leaked a workstation path** into the installed memory document.
- **Summarized with Claude**, not Codex, so the provider boundary the experiment
  is about was never crossed.
