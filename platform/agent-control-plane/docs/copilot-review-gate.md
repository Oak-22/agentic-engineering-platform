# Ordered Copilot review gate

The repository uses two independent checks for a pull request targeting
`main`:

1. `control-plane-guards` runs first on the pull-request head.
2. `AEP Copilot Review Request` requests one Copilot review for that exact SHA
   once the guards pass for it.
3. `AEP Copilot Review Gate` evaluates Copilot's review of that SHA and reports
   `aep-copilot-review`.

The check is intentionally exact-head. A new push creates a new pending check;
an earlier review can never satisfy the new commit. The normalizer accepts
line comments, review summaries, suppressed findings, and explicit disputes.
An unclassified comment-only review is a failure, not evidence of cleanliness.
A duplicate finding identifier merges toward the more severe reading, both for
actionability and for disposition, so a suppressed copy cannot waive a dispute.

## Why the gate is triggered by the pull request

The gate waits rather than reacting to the review event, because two GitHub
behaviours make an event-driven gate unable to pass:

- A Copilot review that generates no comments does not create a
  `pull_request_review` workflow run at all.
- A check run produced by any trigger other than the pull request does not
  enter that pull request's status rollup, so the branch rule cannot read it.

Together those mean the review event arrives only when Copilot has findings,
which is exactly when the gate fails. Starting from the pull request and
waiting for the guards and then for the review makes every head produce one
gate run whose verdict the branch rule can see. Manual dispatch runs the same
evaluation for diagnosis, and its result cannot satisfy the required check.

| Conclusion | Meaning |
| --- | --- |
| `pending` | No completed Copilot review covers the current SHA. |
| `success` | The current review has no actionable or unrecognized findings. |
| `failure` | Findings remain actionable, the review is stale, or the provider payload cannot be normalized safely. |
| `neutral` | Remaining findings are explicitly disputed with evidence; the result remains visible for a human decision. |

The declarative target is checked in at
`.github/rulesets/protect-main.json`. Applying it to GitHub is a separate
repository-administration operation: the active ruleset requires exactly the
two checks above, keeps zero required approvals, disables review-thread
resolution enforcement, disables automatic Copilot requests/counting, and
does not grant AEP or Copilot approval, merge, close, or bypass authority.

Local normalization can be exercised with:

```bash
python platform/agent-control-plane/scripts/copilot_review_gate.py \
  --head-sha <sha> review.json
```

`evaluate_pull_request_readiness.py` consumes the normalized evidence only when
the review ID, head SHA, submission timestamp, status, findings, and disputes
are present. Thread disputes are emitted as `disputedThreads` and Copilot
finding disputes as `disputedFindings`. Jira alignment remains in that broader readiness declaration;
GitHub Actions never receives Atlassian credentials.
