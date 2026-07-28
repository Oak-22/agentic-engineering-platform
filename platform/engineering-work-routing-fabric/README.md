# Engineering Work Routing Fabric

The Engineering Work Routing Fabric is a contract-first subsystem for turning
undifferentiated human-agent activity into traceable routing decisions without
making the model or router authoritative for destination data.

It answers:

> What work happened, what causal chain produced it, where should evidence or
> coordination be routed, and how can duplicate or circular execution be
> stopped safely?

## Boundary

The routing fabric owns:

- stable work-event identity and causal correlation
- append-only event envelopes
- routing decisions and their rationale
- delivery idempotency keys and receipts
- exact-duplicate and semantic-recurrence signals
- recommendations to continue, return a prior result, replan, stop, or
  intervene

It does not own:

- agent instructions or authority policy, which belong to the Agent Control
  Plane
- model, token, latency, and cost measurements, which belong to the Inference
  Telemetry Observatory
- curated learning, which belongs to the Engineering Knowledge Base
- coordinated work state, which belongs to Jira
- durable shared explanation, which belongs to Confluence
- source history, which belongs to Git

## v0 flow

```text
work-event
    ↓
routing-decision
    ↓
destination delivery
    ↓
delivery-receipt
```

Frontier models may propose semantic classification and routing rationale.
Deterministic infrastructure supplies identity, provenance, write
idempotency, state checks, and approval enforcement.

The fabric operates above deterministic service APIs and is distinct from a
service mesh, which would govern network communication among independently
deployed services. See
[`API, MCP, Routing Fabric, and Service Mesh Layering`](../../docs/architecture/api-mcp-and-service-mesh-layering.md).

## Contents

- [`schemas/`](schemas/) defines work events, routing decisions, and delivery
  receipts.
- [`policies/loop-guard-policy.json`](policies/loop-guard-policy.json) defines
  the first deterministic recurrence controls.
- [`examples/`](examples/) contains fixtures derived from real platform work.
- [`scripts/validate_examples.py`](scripts/validate_examples.py) validates the
  contract fixtures without third-party dependencies.

## Validate

```sh
python3 platform/engineering-work-routing-fabric/scripts/validate_examples.py
```

## Deliberate v0 exclusions

This draft does not provide a queue, database, daemon, model classifier,
destination credentials, or live Jira/Confluence writes. It establishes a
small replayable contract before operational infrastructure is introduced.
