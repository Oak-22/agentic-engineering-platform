# AI Inference Telemetry Dashboard

Reports what agent-assisted engineering work costs, per governed engineering
outcome, across the coding runtimes that did the work.

## Overview

Cost per completed engineering outcome is the question this component owns.
Runtimes record token usage per model call in their own local session files;
delivery branches carry the work item key. Joining those two gives cost per
governed outcome without adding a collector, a daemon, or a database.

[ADR-0003](../../docs/architecture/adr/0003-adopt-langgraph-and-langsmith-as-orchestration-and-telemetry-backends.md)
sets the boundary this component works within. Traces, nested runs, datasets,
experiments, and evaluators belong to LangSmith; durable workflow state
belongs to LangGraph. What stays here is cost and quality per governed
engineering outcome, and cross-runtime comparison — the part that depends on
this platform's own delivery semantics, which no general observability
product models.

The root [Platform Model](../../README.md#platform-model) owns the cross-pillar
producer and analytics boundary.

---

## What it answers

Answered by a report today:

- What did each governed work item cost in inference?
- Which runtime, and which model, did that spend go through?
- How much of the input was served from cache rather than paid for in full?
- How much spend is attributable to a work item at all?

The reserved scope that is not answered yet — quality per outcome, and cost
per *completed* outcome rather than per outcome worked on — needs a signal
this component does not have: whether the work the tokens bought actually
landed. Delivery state lives in Jira and GitHub, so closing that half is a
join against the control plane's delivery records, not more telemetry.

Questions about traces, datasets, experiments, and evaluators are not in
scope here at all; ADR-0003 assigns them to LangSmith.

---

## How it works

```text
~/.claude/projects/**.jsonl        ~/.codex/sessions/**/rollout-*.jsonl
        │                                   │
        └───────────────┬───────────────────┘
                        ▼
        session_transcript_reader.read_usage
        (read-only port, agent-control-plane)
                        ▼
              usage_model.build_report
        (branch → work item, tokens → list-price cost)
                        ▼
                 render_html
                        ▼
     .local-mirrors/telemetry-reports/latest.html
```

Every stage is stdlib-only and read-only toward provider state. The reader is
the control plane's shared port, not a copy: per-runtime path patterns and
payload shapes have one owner, and this component consumes normalized output.

### Running it

```bash
dashboard-report                      # every session that ran in this repo
dashboard-report --since 2026-08-01   # only sessions touched since a date
dashboard-report --runtime claude     # one runtime
dashboard-report --out /tmp/report.html
```

Output goes to the machine-local `telemetry-reports` store, reachable in the
repository at `.local-mirrors/telemetry-reports/latest.html`. Nothing is
written into the repository or into provider state.

### What a report can and cannot prove

The page states its own limits, and they are load-bearing rather than
decorative:

- Cost is list rate times observed tokens. It is not billing data, and it
  reflects neither negotiated rates nor plans that bundle usage.
- Work sits mostly on long-lived branches that name no work item. That spend
  is reported as `unattributed`, and it is usually the largest bucket.
- Codex records token counts without a model identifier, so its usage is
  measured but not priced.
- Quality is absent. This is the cost half of the reserved capability.

---

## Telemetry field families

The vocabulary this component reports against. Only the fields a runtime
actually writes to its session file are observable today — request and model
metrics largely are, cache metrics partly are, and the quality family is not
observable from a transcript at all. The list is kept whole because it names
what a field *would* mean once a producer emits it, and the rollups are built
from its first three families.


### Request Metadata

- Request ID
- User ID
- Session ID
- Agent ID
- Workflow ID
- Timestamp

### Model Metrics

- Model
- Provider
- Prompt Tokens
- Completion Tokens
- Total Tokens
- Estimated Cost
- Latency
- Time To First Token

### Context Metrics

- Prompt Cache Hit
- Cached Tokens
- Cache Savings
- Context Size
- Context Compression Ratio
- Retrieval Token Count

### Agent Metrics

- Tool Calls
- Tool Latency
- Tool Failures
- Retry Count
- Memory Reads
- Memory Writes

### Quality Metrics

- Human Evaluation
- Automated Evaluation Score
- Task Completion
- Error Rate

---

## Layout

| Path | What it is |
| --- | --- |
| `src/dashboard/pricing.py` | Published list rates and the cache-TTL multipliers, with the date they were transcribed |
| `src/dashboard/usage_model.py` | Pure aggregation: branch to work item, samples to rollups |
| `src/dashboard/render_html.py` | One self-contained HTML page, no CDN and no chart library |
| `src/dashboard/report_cli.py` | The only module that touches the filesystem |
| `src/dashboard/{adapter,telemetry,cli,mock_server}.py` | Contract fixture and local testing adapter, per ADR-0003 — a CLI-to-model adapter with a best-effort emitter, exercised against a mock endpoint |
| `examples/single-prompt-turn.json` | One hand-assembled turn record, recording what a host does not expose |
| `docs/service-extension-physical-telemetry.md` | Specification for correlating hardware metrics with agent spans; not implemented |

Verify with:

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

---

## What the report shows

One page, four groupings, each ordered by estimated cost:

| Grouping | Reads |
| --- | --- |
| Work item | Cost per governed outcome, with `unattributed` shown alongside rather than hidden |
| Runtime | Cross-runtime comparison — sound on token volume, partial on cost |
| Model | Which model tier the spend went through |
| Day | Spend over the captured window |

Each row carries estimated cost, total tokens, cache-read share, call count,
session count, and the runtimes involved. A cost that could only be partly
priced is marked, so a total is never silently a floor.

---

## Dependencies

The Python standard library, and nothing else. No streaming platform, no
warehouse, no charting library, and no service to run — deliberately, because
the data this component reports on is already written to local disk by the
runtimes that produced it.
