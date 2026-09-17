# Parallel Delivery Waves

Dated records of governed deliveries run as a wave: one coordinating session
spawns several subagents, each delivering one Jira task through
`deliver-governed-change` to ready-for-human-review in its own claimed
worktree, and the human merges. One file per wave.

Each record carries the same fields so waves can be compared:

| Field | Source |
| --- | --- |
| Coordinator model, effort, usage over the wave window | `read_usage` in `platform/agent-control-plane/scripts/session_transcript_reader.py` on the coordinator's transcript, filtered to the window; model and effort from the per-message `"model"` and `"effort"` fields (see *Model and effort verification*) |
| Per-subagent model, effort, usage | `read_usage` on the subagent's own output JSONL (see *Token measurement*); model and effort from the same per-message fields, every sample at the definition's values |
| Per-subagent tool uses, duration, final context | The harness task-completion notification (`tool_uses`, `duration_ms`, `total_tokens`) |
| Per-task Jira key, PR, Copilot reviews, pushes, scope drift | GitHub API counts as defined under *Operational definitions*; the subagent's hand-back report is the narrative, never the number |
| Instrument hash and spawn prompts | `shasum -a 256 .claude/agents/deliver-unit.md` and the four one-line prompts verbatim, both recorded before the first spawn |
| Pre-registration | The commit of this README whose predictions were live at spawn time |
| Wall clock | spawn → last hand-back; spawn → cleanup complete; per-PR `mergedAt` from `gh pr view` |

## Measurement

### Model and effort verification

Model and effort are read from transcripts, never taken on anyone's word.
Every assistant message in a Claude Code transcript carries `"model"` and
`"effort"`:

```sh
# coordinator: before the first spawn and again after the last hand-back
F=~/.claude/projects/<project-slug>/<session>.jsonl
grep -o '"model":"claude-[a-z0-9-]*"' "$F" | sort | uniq -c
grep -o '"effort":"[a-z]*"' "$F" | sort | uniq -c
echo "$CLAUDE_EFFORT"          # the level in effect for the next request

# each subagent: every sample at the definition's model and effort
grep -o '"model":"claude-[a-z0-9-]*"\|"effort":"[a-z]*"' <agent>.output | sort | uniq -c
```

A coordinator sample at another model or level inside the window means the
session was changed mid-wave and its row is not a held constant. A subagent
with any sample off the definition's values invalidates that task's row.

Rules that make this hold:

- The definition pins `model:` by full ID (`claude-opus-5`, `claude-sonnet-5`).
  `inherit` is never used: it takes the coordinator's model, so a `/model`
  switch in the coordinator would silently move the subagent variable.
- Frontmatter `effort:` overrides the session level but not the
  `CLAUDE_CODE_EFFORT_LEVEL` environment variable, so confirm that variable
  is unset before spawning and that no `maxEffortLevel` cap is configured.
  `CLAUDE_EFFORT` is different: the harness sets it in Bash subprocesses to
  the level in effect, which makes it the live readout used above.
- Saved defaults: `modelSettings.<model>.effortLevel` beats the top-level
  `effortLevel`, so a `/model` switch also changes the effort to that
  model's saved entry. Verify both after any switch.

### Token measurement

The harness notification's `total_tokens` is the footprint of the
subagent's final API request — that one call's input, cache creation, cache
read, and output — which is the context size at completion. It is not a sum
across the run. Wave 1 confirmed this against the transcripts: reported
103,257 against a final-request footprint of 101,282, and the other three
within 2% likewise. Record it as **final context**.

Spend comes from `read_usage` on the subagent's output JSONL at
`/private/tmp/claude-501/<project-slug>/<coordinator-session>/tasks/<agent-id>.output`.
That directory does not survive a reboot, so copy each file to
`.local-mirrors/parallel-delivery-waves/wave-NN/` (gitignored) as its agent
hands back. Report per agent: output tokens, thinking tokens, cache
creation, cache read, and sample count (one sample per model call). Thinking
tokens are the direct effort signature; at `low`, wave 1 recorded between
104 and 5,869 per agent.

The coordinator row uses the same fields from the same reader, so the two
rows are comparable.

### Operational definitions

Counted from the GitHub API on the merged PR, so a later wave can recount:

| Quantity | Definition | Command |
| --- | --- | --- |
| Copilot reviews | Review submissions by `copilot-pull-request-reviewer[bot]` | `gh api repos/<owner>/<repo>/pulls/N/reviews --jq '[.[]\|select(.user.login\|test("copilot";"i"))]\|length'` |
| Finding reviews | Copilot reviews that produced ≥ 1 generated line comment | `gh api repos/<owner>/<repo>/pulls/N/comments --jq '[.[]\|select(.user.login\|test("copilot";"i"))]\|group_by(.pull_request_review_id)\|length'` |
| Generated comments | Line comments by the Copilot reviewer | the same call without `group_by` |
| Pushes | Commits on the PR | `gh pr view N --json commits --jq '.commits\|length'` |
| Scope drift, file set | PR files outside the scope brief's paths | `gh pr view N --json files --jq '.files[].path'` against the brief |
| Scope drift, hunk | A named path whose merged content differs from the workbench hunk | `git diff <workbench-commit> <merge-commit> -- <path>` non-empty |

"Round" in wave 1's prose meant a finding review followed by a fix push.
Predictions use **finding reviews**: a clean review triggered by a sync push
is not the task's cost. Both counts are recorded.

Wave-1 recount from the API (docs tasks first):

| Task | PR | Copilot reviews | Finding reviews | Generated comments | Pushes | Files | Drift |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| AEPI-161 | #105 | 1 | 0 | 0 | 1 | 3 | none |
| AEPI-163 | #104 | 2 | 1 | 1 | 3 | 1 | hunk |
| AEPI-160 | #106 | 5 | 4 | 6 | 8 | 2 | hunk |
| AEPI-162 | #103 | 4 | 2 | 3 | 5 | 2 | file set (+1 test) |

Scope drift is recorded because it is the quantity the wave design is meant
to control: a task that leaves review with more than its scope brief named
is the signal that Copilot-loop compliance, not the task, set the boundary.

### Confounds recorded, not controlled

- Concurrent merges. Four PRs target `main`; each merge forces the others to
  sync, and a sync push can trigger a Copilot review. Record merge order and
  times. Finding reviews are the task's count; total reviews include this
  effect.
- Copilot is a moving reviewer. Its findings vary run to run and its quota
  state varies by day. Record review timestamps and any quota text verbatim.
- Docs tasks are not one weight. Record the scope brief's size per task
  (files, lines added and removed on the workbench commit) so per-task rows
  can be read against it. In wave 2, AEPI-156 makes decisions the draft left
  open while AEPI-157 is a bulk publish.
- The spawn prompt is composed by the coordinator. Record all four verbatim.

### Exclusion and stop rules

- A task whose Copilot review body reports a quota limit is recorded and
  excluded from review counts (the AEPI-144 fail-open condition).
- A task blocked at preflight is recorded as not run.
- A subagent with any transcript sample off the definition's model or effort
  invalidates its row.
- Fewer than two docs tasks completing leaves the wave's docs-class
  predictions untested; the wave is still recorded.

## Experiment design

Preliminary, not controlled: n = 4 per wave, task mix differs by wave, the
human's merge cadence is uncontrolled. One variable changes per wave;
predictions are written before the run so a later wave can say which
results were surprising.

### Held constant

- The coordinator: Opus 5, effort `low`, same session role in every wave
  (spawn, relay, verify merges with `gh pr view`, clean up, sync, transition
  Jira). Its row is a baseline, not a variable. Verified from `$CLAUDE_EFFORT`
  and the transcript before the first spawn.
- The spawn instrument: the `deliver-unit` subagent definition at
  `.claude/agents/deliver-unit.md` (local, not tracked). Its body is the
  wave-1 prompt with the key and scope brief as placeholders. Only its
  `model:` and `effort:` fields change between waves, to the values in the
  table below; its hash is recorded in each wave file before spawning.
- Four fresh, non-fork subagents per wave, one claimed worktree each.
- The skill chain. `deliver-governed-change` and its delegates are not
  edited during the series; the dispute-reply plan stays captured until the
  series ends so it is not a second variable.

### Comparison unit

The task class, not the wave. Docs tasks appear in every wave (wave 1:
AEPI-160, 161, 163; wave 2: 156, 157; wave 3: 164, 165, 166) and are the
comparable series. Feature tasks begin at wave 2 and set their own baseline.
Report per task, not only means; one bad Copilot day moves a mean of four.
Only spawn → hand-back wall clock is comparable; spawn → cleanup includes
human review time.

### Waves

| Wave | Coordinator | Subagents | Definition fields | Variable | Tasks |
| --- | --- | --- | --- | --- | --- |
| 1 | Opus 5 / low | Opus 5 / low (inherited) | none — `general-purpose` agents, prompt inline | baseline | 160, 161, 162, 163 |
| 2 | Opus 5 / low | Opus 5 / **high** | `model: claude-opus-5`, `effort: high` | effort | 152, 158, 156, 157 |
| 3 | Opus 5 / low | **Sonnet 5** / high | `model: claude-sonnet-5`, `effort: high` | model | 159, 164, 165, 166 |
| 4 | Opus 5 / low | Opus 5 / high | `model: claude-opus-5`, `effort: high` | none — the gate must be right | 167, 168 |

### Wave 2 predictions (docs-class tasks)

Written before the run. The token row was first stated as 140k–180k on the
harness figure, believed to be spend; it is restated here on what that
figure measures, keeping its reasoning (more per turn, fewer turns).

| Metric | Wave 1 (161, 163, 160) | Prediction |
| --- | --- | --- |
| Finding reviews per task | 0, 1, 4 (mean 1.7) | ≤ 1 each |
| Copilot reviews per task | 1, 2, 5 (mean 2.7) | ≤ 2 each |
| Output tokens per task | 11.0k, 11.9k, 31.5k | up — 20k–60k, thinking ≥ 5k each (was 104, 1,347, 5,869) |
| Final context per task | 101k, 109k, 144k | similar or lower — fewer turns |
| Duration, spawn → hand-back | 6.6, 12.5, 39.6 min | down, because finding reviews dominate |
| Scope drift | 2 of 3 (163 hunk, 160 hunk) | unchanged — ≥ 1 of the 2 docs tasks |

The scope-drift row is the test. The diagnosis behind
`future/copilot-dispute-reply-operation.md` is that drift comes from the
skill's compliance rule, not from reasoning depth. Drift persisting at
`high` confirms it; drift vanishing falsifies it. Feature tasks (152, 158)
carry no prediction; their rows are the feature-class baseline.

### Wave 3 predictions (vs wave 2)

| Metric | Prediction |
| --- | --- |
| Docs-task finding reviews | +0 to +1 per task |
| Output tokens per task | similar count, at Sonnet's rate |
| Duration | similar or slightly longer |
| Scope drift | unchanged |
| AEPI-159 | ≥ 1 extra push — a test failure caught in CI rather than locally |

If wave 3's docs rows match wave 2's within one finding review, Sonnet
becomes the sweep-lane default and Opus is reserved for feature and gate
tasks.
