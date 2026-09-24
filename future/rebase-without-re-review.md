# Rebase without re-review

Status: draft, not activated as Jira work. Delete this file when the delivery
pull request lands the units below; promote the carry-forward rule into
`platform/agent-control-plane/adapters/github/README.md` in that same change.

## Context

The `Protect main` ruleset sets `strict_required_status_checks_policy: true`,
so a pull request merges only when its head contains the tip of `main`. Every
merge therefore leaves each other open pull request behind, and the author
must bring it current before it can merge.

The standard way to do that — and the one the co-developed CameraTether
repository already documents in `.github/CONTRIBUTING.md` — is an author-side
loop:

```
git fetch origin && git rebase origin/main && git push --force-with-lease
```

Adopting that loop here — its agent authority is planned separately in
[rebase-loop-standing-authority.md](rebase-loop-standing-authority.md) —
keeps one git habit across both repositories while strict mode keeps its
guarantee: `control-plane-guards` validates the registries, mappings, and
contracts against the combined state that will land.

What makes the loop expensive today is not the guards (recent runs: 30–43s)
but the Copilot leg. `aep-copilot-review-request.yml` requests a new Copilot
review on every `synchronize`, and `aep-copilot-review.yml` accepts only a
review whose `commit_id` equals the new head (recent gate runs: 125–256s).
A rebase that changes nothing in the pull request's own diff thus costs a
full second review — the wall-clock between consecutive merges and a second
round of review tokens — to re-judge input identical to what was already
reviewed. The output is not identical: Copilot is a sampled reviewer, so a
second review is a second draw, not a repeat. PR #113 shows it. Its update
from `main` left the change fingerprint unchanged (`d87c39c56e13` before and
after) and brought in nothing touching its files, yet the new review posted a
finding that the previous review had mentioned only in its summary ("Align
the README diagram/accessibility text", no line comment, so the gate passed).
Carry-forward gives up that extra draw on purpose: under strict mode, which
pull requests get one depends on merge order, not on risk.

End state: a push whose change relative to its merge base is byte-identical to
an already-reviewed head carries that review forward. The guards still re-run
on every head; Copilot runs only when the pull request's own content changed.
Consecutive merges of independent pull requests are paced by the guards, not
by Copilot.

## How to read this plan

Each unit states **Touches**, **Mechanism**, **Claim**, and **Trace check**.
Units are independently reviewable. Units 2 and 3 depend on unit 1, and unit
2 depends on unit 3: with unit 2 alone, a rebase-only push requests no review
while the gate still waits for one, so every re-synced pull request fails the
gate. Land the three in one pull request, or unit 3 before unit 2.

## Unit 1 — Change fingerprint

**Touches**
- `platform/agent-control-plane/scripts/pr_change_fingerprint.py`
- `platform/agent-control-plane/tests/test_pr_change_fingerprint.py`
- `platform/agent-control-plane/scripts/README.md`

**Mechanism** — Compute
`git diff --no-color --full-index --binary <merge-base(base, head)> <head> | git patch-id --verbatim`
and return the patch id, or a fixed sentinel for an empty diff. Two flags
carry the byte-identity claim. `--verbatim` is required because the default
`patch-id` ignores whitespace, which would let a whitespace-only edit inherit
a review it never had. `--binary` puts a binary file's content into the
hashed input. Without it `git diff` prints only "Binary files differ"; under
git 2.48, `--verbatim` still hashes the `index` line's blob ids, so two
different binary edits already fingerprint differently, but that rests on how
`patch-id` treats a header line rather than on the content itself. The whole-branch diff is
fingerprinted rather than per-commit patch ids, because Copilot reviews the
pull request's diff, and a rebase that squashes or reorders commits without
changing that diff should still carry. Pure transformation is split from the
`git` subprocess calls, per `agent-assets/instructions/python.md`.

**Claim** — Two heads share a fingerprint exactly when their changes relative
to their respective merge bases are byte-identical.

**Trace check** — The test builds a temporary repository: branch `b` off
`main`, advance `main` with an unrelated commit, rebase `b`. Expected: equal
fingerprints before and after the rebase. Falsification: change one byte in
`b`'s file, only its indentation, or the bytes of a committed binary file —
the fingerprints must differ. Drop `--verbatim` and the whitespace case must
fail. The binary case guards content and header together: fingerprint a
diff made without `--binary` and with its `index` lines removed, and it must
fail.

## Unit 2 — Do not request Copilot for a rebase-only head

Depends on units 1 and 3.

**Touches**
- `.github/workflows/aep-copilot-review-request.yml`
- `platform/agent-control-plane/tests/test_aep_copilot_review_request_workflow.py`

**Mechanism** — Before the `requested_reviewers` POST, list the pull
request's Copilot reviews, take the newest reviewed head whose
`aep-copilot-review` check concluded `success` or `neutral`, fetch it by SHA,
and compare its fingerprint against the live head's. On a match, log the
carry-forward and exit without requesting. On a failed fetch (a force-pushed
commit can be garbage-collected) or any mismatch, request as today — the
fallback is the current behaviour, never a skip. This workflow runs on
`workflow_run` with `pull-requests: write`, so the fingerprint tooling is
checked out from the default branch and pull-request commits are only ever
read as git objects; no script from the pull-request head executes.

**Claim** — A rebase-only push produces no new Copilot review request, and a
push that changes the pull request's diff still does.

**Trace check** — On a throwaway pull request with a passing review: rebase
onto a newer `main`, push, and run
`gh api repos/{owner}/{repo}/issues/<n>/timeline --jq '[.[] | select(.event=="review_requested")] | length'`
before and after. Expected: unchanged count, and the run log names the
carried head. Falsification: amend one byte and push — the count increments.

## Unit 3 — Accept carried-forward review evidence

Depends on unit 1.

**Touches**
- `platform/agent-control-plane/contracts/github-delivery/copilot-review-evidence.schema.json`
- `platform/agent-control-plane/scripts/copilot_review_gate.py`
- `platform/agent-control-plane/tests/test_copilot_review_gate.py`
- `.github/workflows/aep-copilot-review.yml`
- `platform/agent-control-plane/scripts/evaluate_pull_request_readiness.py`
- `platform/agent-control-plane/tests/test_evaluate_pull_request_readiness.py`

**Mechanism** — The evidence gains an optional
`carriedForward: {fromHeadSha, changeFingerprint}`. `headSha` stays the
current head, so the exact-head comparisons in the gate and in
`evaluate_pull_request_readiness.py` (line 242) keep their meaning: evidence
always names the head it vouches for. `copilot_review_gate.py` takes
`--carried-from` and `--fingerprint`; it validates the review's `commit_id`
against `--carried-from` instead of `--head-sha` and emits the record. In
`aep-copilot-review.yml`, after the guard wait and before the review wait, the
same lookup as unit 2 runs; on a match it normalizes the prior review and
skips the up-to-15-minute review wait. The lookup, the fingerprint
comparison, and the carried-forward normalization all run from tooling
checked out at the default branch, and the pull-request commits are read only
as git objects — the same boundary unit 2 draws. Today the gate checks out
`HEAD_SHA` and runs that head's `copilot_review_gate.py`; for a fresh review
that only lets a pull request judge its own review, but for carry-forward it
would let a pull request edit the code that decides whether an older review
still applies to it. Thread and dispute state are read live,
as today, so a thread reopened after the original review still blocks.
Rejected alternative: letting the gate accept any earlier review by the same
author — that drops the proof that the reviewed content is what will merge.

**Claim** — The required `aep-copilot-review` check passes on a rebase-only
head without a new Copilot review, and cannot pass on a changed head without
one.

**Trace check** — `python -m unittest` over the two test files covers: a
carried record with a matching fingerprint passes; a mismatched fingerprint
is a normalization error (exit 2); a record whose `carriedForward.fromHeadSha`
has a failed gate is rejected. End to end, the rebase from unit 2's check
yields a green gate in roughly guard time, and its job summary names the
carried head. Falsification: push a content change with Copilot review
disabled for the repository — the gate must fail at the review wait.

## Verification

```
python -m unittest discover -s platform/agent-control-plane/tests
```

Then the timed drill: open two throwaway pull requests touching disjoint
files, let both pass, merge the first, run the rebase loop on the second, and
record the wall clock from push to a mergeable state. Expected: about one
guard run plus gate overhead, no new Copilot review on the second pull
request, and a job summary naming the carried head.

## Risks

- **The chain stays serial.** Strict mode means N independent pull requests
  still need N−1 rebase-and-guard cycles; this plan shrinks each cycle to
  guard time, not to zero. Only a merge queue — unavailable to a user-owned
  repository — tests the queued combination for you.
- **Copilot never sees the new base.** A carried review judged the diff
  against the old base. That is already true of what Copilot reviews; the
  combined-state check is the guards, which still run on every head.
- **One fewer sample per re-sync.** A carried review forgoes the second
  draw that a re-review would have taken, so a finding a second draw would
  surface — as on PR #113 — waits for the next content change or for a human.
  More than one sample per pull request is a gate-policy decision in
  `aep-copilot-review.yml`, to be made for every pull request alike, not
  something inherited from merge order.
- **Conflict-resolved rebases pay full price.** Resolving a conflict changes
  the diff, so the fingerprint differs and a fresh review runs. That is
  correct, and it is the case in which a second review earns its cost.
- **Garbage-collected heads.** If GitHub no longer serves the reviewed head,
  the lookup fails and the workflows fall back to a fresh review. The failure
  mode is today's cost, never a missing review.
