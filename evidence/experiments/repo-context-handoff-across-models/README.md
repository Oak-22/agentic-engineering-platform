# Repository Context Handoff Experiment

> **Status: deferred.** This experiment is not part of normal contributor
> onboarding and is not required before Claude works in this repository. Run
> Claude directly from the current checkout; resume this harness only when a
> task explicitly reopens the experiment and its comparison questions.

Model providers are increasingly interchangeable. Session memory, instruction
systems, and local histories are not. This experiment tests whether a governed
handoff built from historical **Codex** sessions improves a fresh **Claude**
session's repository understanding — without transferring stale claims,
contaminated authority, or private transcript detail.

Three roles stay separated by construction:

```text
Codex history (frozen at a cutoff)
  -> ephemeral Codex builder, run outside the repository
  -> handoff.md, validated before it touches anything
  -> fresh Claude treatment session, isolated temporary auto memory
```

The baseline runs first, with auto memory off, over the same clean snapshot.
Both subjects are non-persistent and share one recorded control set.

Read [experiment-design.md](experiment-design.md) before interpreting a run.

## Run

Each phase is a subcommand. Run them in order; each verifies its predecessor.

```bash
HARNESS=evidence/experiments/repo-context-handoff-across-models/run_experiment.py

# 1. Initialize. Fails if a live Claude session has this repo as its cwd.
python3 $HARNESS preflight --repo "$PWD"
RUN_DIR=~/.local/share/aep/experiments/repo-context-handoff-across-models/<run-id>

# 2. Clone the clean snapshot to a temporary path, on a branch named main.
python3 $HARNESS snapshot   --run-dir "$RUN_DIR"
python3 $HARNESS trust-probe --run-dir "$RUN_DIR"
python3 $HARNESS probe-memory --run-dir "$RUN_DIR"

# 3. Freeze the Codex-only corpus at the snapshot commit's timestamp.
python3 $HARNESS inventory --run-dir "$RUN_DIR" --cutoff commit

# 4. Baseline, then handoff, then treatment. Order is enforced.
python3 $HARNESS baseline  --run-dir "$RUN_DIR"
python3 $HARNESS build     --run-dir "$RUN_DIR"
python3 $HARNESS validate  --run-dir "$RUN_DIR"
# Read handoff.md in full, then record the human gate:
#   $RUN_DIR/handoff-review.json  {"reviewed_by": "...", "reviewed_at": "..."}
python3 $HARNESS treatment --run-dir "$RUN_DIR"

# 5. Compare, verify, tear down.
python3 $HARNESS report  --run-dir "$RUN_DIR"
python3 $HARNESS verify  --run-dir "$RUN_DIR"
python3 $HARNESS cleanup --run-dir "$RUN_DIR"
```

`verify` prints the acceptance table and sets `run_status` to `VALID`,
`DEGRADED`, `INDETERMINATE`, or `INVALID`. Score `blind/A.md` and `blind/B.md`
against the rubric in `comparison.md` before opening `blind/key.json`.

Optional third arm, isolating handoff *content* from the presence of a memory
subsystem:

```bash
python3 $HARNESS treatment --run-dir "$RUN_DIR" --placebo
```

Recovery: `build` reuses non-empty partials, so an interrupted builder resumes
where it stopped. `recheck-sources` reports whether live transcripts drifted
since the freeze; the frozen corpus stays authoritative either way.

## Controls

| Parameter | Value |
| --- | --- |
| Snapshot commit | `5edc12cc` |
| Source cutoff | committer time of the snapshot commit |
| Source provider | Codex only |
| Builder | `codex exec --ephemeral`, `gpt-5.6-sol`, effort `high` |
| Target | `claude`, `opus`, effort `high`, `--permission-mode plan`, tools `Read,Glob,Grep` |

Run artifacts default to
`~/.local/share/aep/experiments/repo-context-handoff-across-models/`.

## Privacy boundary

The collector reads only user-visible user and assistant text from local Codex
transcripts whose working directory is inside this repository. It excludes
system and developer instructions, hidden reasoning, tool calls, tool results,
attachments, runtime boilerplate, and known credential patterns. Transcript
text is treated as untrusted data by the builder.

`validate` blocks any handoff containing secrets, machine-specific absolute
paths, email addresses, transcript paths, or raw session identifiers. Nothing
reaches `product-demo/RAW/` without a completed `privacy-review.json` and an
explicit `publish --confirm-privacy-review`.

The real Claude project-memory directory is never read, copied, moved, or
written. Both subjects use isolated run-scoped memory directories.
