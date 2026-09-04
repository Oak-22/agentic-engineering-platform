# Ordered Copilot review gate

The repository uses two independent checks for a pull request targeting
`main`:

1. `control-plane-guards` runs first on the pull-request head.
2. After that run succeeds, `AEP Copilot Review Gate` requests one Copilot
   review for that exact SHA and reports `aep-copilot-review`.

The check is intentionally exact-head. A new push creates a new pending check;
an earlier review can never satisfy the new commit. The normalizer accepts
line comments, review summaries, suppressed findings, and explicit disputes.
An unclassified comment-only review is a failure, not evidence of cleanliness.

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
are present. Jira alignment remains in that broader readiness declaration;
GitHub Actions never receives Atlassian credentials.
