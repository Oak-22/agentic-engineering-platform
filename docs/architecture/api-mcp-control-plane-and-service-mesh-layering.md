# API, MCP, Control Plane, and Service Mesh Layering

The Agentic Engineering Platform should treat deterministic service APIs as
the durable execution boundary beneath agent-facing protocols. MCP can expose
selected capabilities to agents, but it does not replace the APIs used by
services, command-line tools, user interfaces, automation, or other clients.

## Layering Model

```text
agent or model workflow
    ↓
MCP tools and resources
    ↓
Agent Control Plane orchestration and authorization
    ↓
shared contracts and deterministic service APIs
    ↓
application services
    ↓
optional service mesh
    ↓
network and infrastructure
```

Each layer has a distinct responsibility:

- **Service APIs** define stable, deterministic capabilities and validation
  boundaries.
- **MCP** describes and presents selected capabilities in a form that agents
  can discover and invoke.
- **Agent Control Plane** applies task authority, selects governed actions,
  checks destination state, and stops, replans, or escalates unsafe repeated
  execution.
- **Shared contracts and schemas** define only the cross-pillar interfaces
  needed by concrete producers and consumers.
- **Service mesh** governs how independently deployed services communicate
  over protocols such as HTTP, gRPC, and TCP.

A useful execution principle is:

```text
model proposes
    → MCP adapts
    → API validates
    → policy authorizes
    → service executes
    → native audit evidence proves
```

## Biological Mental Model

In a biological analogy:

- a microservice is a cell;
- its API is the membrane and set of receptors through which it accepts
  defined signals;
- its implementation is the intracellular machinery that interprets those
  signals;
- a service mesh resembles the extracellular signaling and transport
  environment shared by many cells;
- a coordinated collection of services resembles tissue or an organ.

The mesh externalizes communication concerns that would otherwise be repeated
inside every service, including service identity, mutual TLS, traffic policy,
retries, timeouts, load balancing, and network observability. It governs how
and whether signals travel; it does not define their domain meaning.

## Boundary with the Agent Control Plane

The Agent Control Plane and a service mesh operate at different semantic
levels.

| Agent Control Plane | Service mesh |
| --- | --- |
| Governs engineering actions and evidence | Routes network requests |
| Operates on authority, current destination state, and task intent | Operates on HTTP, gRPC, or TCP traffic |
| Suppresses duplicates and escalates recurrence | Supplies transport security, resilience, and observability |
| Expresses why an action is allowed | Governs how service traffic moves |

Control-plane capabilities may eventually use independently deployed services
with stable APIs. A service mesh could govern communication among those
services, but it would not own task authority, destination semantics, or
delivery evidence.

Destination systems remain authoritative for their own state. Governed
workflows should read that state before mutation, avoid repeating an
already-satisfied action, and retain Jira keys, run and attempt identifiers,
and native audit records as evidence. The platform does not need a generalized
work-event or delivery-receipt schema until a concrete cross-pillar interface
requires one.

## Adoption Rule

A service mesh is optional infrastructure, not an inherent requirement of
microservices. Introduce one only when the number, independence, language
diversity, security requirements, or traffic-policy needs of deployed services
make duplicated in-service networking logic harder to operate than the mesh
itself.

Until that threshold is reached, ordinary APIs, authentication, telemetry,
timeouts, retries, and queues provide a simpler deterministic baseline.
