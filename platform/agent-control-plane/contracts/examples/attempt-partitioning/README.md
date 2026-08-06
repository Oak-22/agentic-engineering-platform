# Attempt Partitioning Example

This example shows one Jira work item, one externally initiated agent run, and
two attempts. It deliberately contains no hidden model reasoning.

## Boundary rule

Model requests, tool calls, and validations are events inside an attempt. A new
attempt begins only when the host or orchestrator emits an explicit retry after
the previous attempt reaches a terminal outcome.

```text
PROJ-10
└── run-aepi-10-001
    ├── attempt-001: tool failure
    └── attempt-002: explicit retry, then pass
```

The observable event sequence is in [`events.jsonl`](events.jsonl). The two
immutable attempt records are in [`attempt-001.json`](attempt-001.json) and
[`attempt-002.json`](attempt-002.json).

[`jira-work-item-metadata.json`](jira-work-item-metadata.json) contains only
the governed planning metadata selected for the Jira work item. It does not
project Attempt 1 or Attempt 2 because trustworthy runtime projection belongs
to the telemetry integration.

## What to inspect

1. Events 1–5 remain inside Attempt 1 even though they include a model request
   and a tool call.
2. Event 6 closes Attempt 1 as failed.
3. Event 7 is the explicit, observable retry boundary.
4. Events 8–11 belong to Attempt 2.
5. The Jira record remains independent of inferred runtime outcomes.
6. A historical query over attempt records counts two attempts and one
   tool-classified failure.

If a host does not expose an explicit retry event, the entire visible
invocation is recorded as one attempt. The system must not infer additional
attempts by parsing model prose or unavailable reasoning.
