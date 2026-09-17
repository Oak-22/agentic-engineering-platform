# Make the Copilot dispute reply a governed operation

Status: captured, not scheduled. Delete this file when Unit 2 lands on
`main`.

## Context

`deliver-governed-change` step 6 (`SKILL.md:159-162`) instructs the agent to
fix an actionable Copilot finding, publish the fix, then reply and resolve
the thread; and to leave a disputed finding unresolved with an
evidence-backed reply for human judgment. The gate is built to consume that
reply: `evaluate_pull_request_readiness.py:144-150` reads
`copilotReview.disputedFindings`, and `copilot_review_gate.py:31` maps a
disputed review to `neutral` so the human sees the disagreement instead of a
silent pass. `github-delivery-mapping.json` declares `review-thread-reply`
and `review-thread-resolve` as governed operations.

No merged pull request carries such a reply. The agent's reasoning about a
finding reaches the human in the terminal and stops there. The originating
instance, from the first run of the exact-head gate on PR #10 (AEPI-129):

> Copilot's two findings — one real, one wrong.
>
> Real — `aep-copilot-review.yml:110`, no pagination. `gh api …/comments`
> returns 30 items by default; a PR with more review comments would have its
> later comments silently dropped from `line_comments`, undercounting
> actionable findings — a fail-open path on exactly the PRs where the gate
> matters most. This is a defect in code I shipped and I'd fix it.
>
> Wrong — `aep-copilot-review.yml:88`, "`[bot]` is a glob class." True for an
> unquoted pattern; this one is single-quoted, and bash matches quoted case
> patterns literally. The run itself is the proof: step 3 passed with REST
> login `copilot-pull-request-reviewer[bot]`, which the glob reading could
> not match.

That is an evidence-backed dispute. It was never posted, so the review
thread shows an unanswered Copilot finding, the gate never saw a
`disputedFindings` entry, and the `neutral` path has no observed instance.

This is the same family as AEPI-137 (Copilot hook legs declared, never
observed) and AEPI-144 (review liveness assumed, never attested): a
governance mechanism whose success path exists in prose and code but has
never fired. The cause here is that the reply is an instruction the agent
may skip, while publishing is a deterministic script it cannot. Text
instructions are the interpretive end of the assurance spectrum; the reply
belongs at the mechanical end beside `publish_delivery_branch.py`.

End state: every Copilot finding on a delivered pull request is fixed,
replied-and-resolved, or disputed with a posted reply, and the readiness
declaration refuses a finding in none of those states. A reader of the pull
request sees the agent's reasoning where the human decides.

## How to read this plan

Units are ordered by dependency. Each states what it touches, the mechanism,
one claim that becomes true, and a check a skeptic can run.

## Unit 1 — A deterministic thread-reply operation

**Touches**
- `platform/agent-control-plane/scripts/reply_review_thread.py` (new)
- `platform/agent-control-plane/tests/test_reply_review_thread.py` (new)
- `platform/agent-control-plane/scripts/README.md`

**Mechanism** — A script taking a pull-request number, a thread or comment
identifier, a disposition (`fixed` or `disputed`), and a body file. For
`fixed` it posts the reply and resolves the thread through the mapping's
`review-thread-reply` and `review-thread-resolve` operations; for
`disputed` it posts the reply and leaves the thread open. It emits one JSON
line naming the disposition, thread, comment URL, and head SHA, appended to
the same evidence store the publisher writes. It refuses a `disputed` body
that cites no path or line, since a dispute without evidence is an opinion
and the human cannot check it. Structure follows
`publish_delivery_branch.py`: plan without `--execute`, mutate with it.

**Claim** — A reply to a Copilot thread is an auditable operation with a
recorded disposition, not a free-text action the agent may or may not take.

**Trace check** — Run without `--execute` against an open pull request and
confirm the plan names the thread and disposition. Run with `--execute` on
a throwaway thread; the reply appears on GitHub and the evidence line
records its URL. Pass a `disputed` body with no path citation; the script
must refuse before any network call.

## Unit 2 — The review step requires a disposition per finding

**Touches**
- `platform/agent-control-plane/agent-assets/skills/deliver-governed-change/SKILL.md`
  (step 6)
- `platform/agent-control-plane/scripts/evaluate_pull_request_readiness.py`
- `platform/agent-control-plane/tests/test_evaluate_pull_request_readiness.py`
- `platform/agent-control-plane/docs/copilot-review-gate.md`
- `platform/agent-control-plane/scripts/publish_delivery_branch.py` (body
  section rewrite) and `.github/workflows/aep-copilot-review.yml` (check-run
  summary)

**Mechanism** — Step 6 invokes Unit 1 for every actionable finding rather
than describing the reply in prose. Readiness gains a per-finding
disposition check: each entry in `normalizedFindings` must match a
`fixed` or `disputed` evidence line for the current head SHA, and a
finding with neither fails readiness with the finding identifier named.
`disputedFindings` is populated from the `disputed` evidence lines, so the
gate's existing `neutral` path is reached by construction. The gate doc's
disposition table gains the row for a posted dispute and states that an
unreplied finding is a readiness failure.

Readiness also renders a **Review dispositions** section into the pull
request body: one row per Copilot finding with its identifier, disposition,
the fixing commit or the dispute reply, and a link to the thread. GitHub
collapses a resolved thread and there is no setting or API that prevents it,
so a fixed finding's reply disappears from the default view the moment it is
resolved; the body is the surface the reviewer sees first and it never
collapses. The section is rewritten, not appended, on every readiness run
so it reflects the current head, and the same table is written to the
`aep-copilot-review` check-run summary, which is what the ruleset gates on.
An agent-authored reply says so in its first line, since the reply posts
under the accountable human's login and the thread cannot otherwise
distinguish the two.

**Claim** — A pull request cannot be marked ready while a Copilot finding
has no recorded disposition, and every disposition is visible in the pull
request body without expanding a resolved thread.

**Trace check** — On a pull request with one actionable finding, run
readiness before replying: it must fail and name the finding. Reply as
`disputed` through Unit 1 and rerun: readiness passes with the finding in
`disputedFindings` and the gate reports `neutral`. Break it by deleting the
evidence line; readiness must fail again. On a pull request with a fixed and
resolved finding, open the *Conversation* tab without expanding anything: the
body's *Review dispositions* row for that finding names the fixing commit
and links the collapsed thread.

## Verification

```sh
python -m pytest platform/agent-control-plane/tests/test_reply_review_thread.py \
  platform/agent-control-plane/tests/test_evaluate_pull_request_readiness.py
python platform/agent-control-plane/scripts/reply_review_thread.py --pr <N> --thread <ID> --disposition disputed --body <file>
python platform/agent-control-plane/scripts/evaluate_pull_request_readiness.py --pr <N>
```

Then one delivered pull request whose Copilot thread carries an agent reply
and whose readiness JSON has a non-empty `disputedFindings`.

## Risks

- Copilot's reviewer account may not resolve threads it did not open, and
  thread resolution needs the GraphQL mutation `pull_request_review_write`
  wraps. Confirm the MCP scope covers it before Unit 1 relies on it.
- A disputed finding that the human then agrees with has no return path
  here; the human requests changes and the ordinary fix loop runs. State
  that in the gate doc so `disputed` is not read as final.
- The body section is agent-maintained text in a human-editable field. A
  human edit to the body between readiness runs is overwritten only inside
  the section's markers; anything outside them is preserved.
- Reply volume: a PR with many findings produces many comments. That is the
  intended visibility; do not batch replies into one comment, because the
  gate correlates disposition per finding identifier.
- ADR-0006 frames Copilot as contextual corroboration. Posting disputes
  does not reopen it; it makes the corroboration visible to the accountable
  human, which is the ADR's stated purpose.
