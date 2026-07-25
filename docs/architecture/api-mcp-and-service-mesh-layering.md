# API, MCP, Routing Fabric, and Service Mesh Layering

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
application orchestration and engineering-work routing
    ↓
deterministic service APIs and event contracts
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
- **Engineering Work Routing Fabric** records what work happened, determines
  where evidence or coordination should be routed, and prevents duplicate or
  circular execution.
- **Service mesh** governs how independently deployed services communicate
  over protocols such as HTTP, gRPC, and TCP.

A useful execution principle is:

```text
model proposes
    → MCP adapts
    → API validates
    → policy authorizes
    → service executes
    → receipt proves
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

## Boundary with the Routing Fabric

The Engineering Work Routing Fabric and a service mesh operate at different
semantic levels.

| Engineering Work Routing Fabric | Service mesh |
| --- | --- |
| Routes engineering work and evidence | Routes network requests |
| Operates on work events, causal chains, and decisions | Operates on HTTP, gRPC, or TCP traffic |
| Supplies idempotency and recurrence controls | Supplies transport security, resilience, and observability |
| Expresses why work should move | Governs how service traffic moves |

The routing fabric may eventually be implemented by independently deployed
services with stable APIs. A service mesh could then govern communication
among those services, but the routing fabric would not itself become the
service mesh.

## Adoption Rule

A service mesh is optional infrastructure, not an inherent requirement of
microservices. Introduce one only when the number, independence, language
diversity, security requirements, or traffic-policy needs of deployed services
make duplicated in-service networking logic harder to operate than the mesh
itself.

Until that threshold is reached, ordinary APIs, authentication, telemetry,
timeouts, retries, and queues provide a simpler deterministic baseline.
