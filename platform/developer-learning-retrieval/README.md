# Developer Learning Retrieval Service

Status: **Planned — design only**

This service will turn real AI-assisted engineering activity into short,
targeted retrieval-practice sessions. Its primary interaction is a daily
five-to-ten-minute developer quiz conducted through Codex or another
compatible agent surface.

## Intended Responsibilities

- consume learning signals from commits, debugging sessions, agent runs,
  and telemetry
- select concepts that merit reinforcement
- generate questions grounded in the developer's actual work
- schedule questions using spaced-repetition intervals
- require an unaided recall attempt before revealing explanations
- record confidence, misconceptions, and later retrieval outcomes
- promote durable insights into reviewed shared scope

## Platform Relationships

```mermaid
flowchart TB
  Activity["`**AI-assisted engineering activity**
  *commits · debugging · agent runs · notes*`"]
  Observatory["`**Telemetry observatory**
  *normalize · correlate · attach provenance*`"]
  Signals[("`**Learning-signal store**`")]
  Retrieval["`**Retrieval service**
  *select concepts · generate grounded prompts*
  *spaced-repetition scheduling*`"]
  Session["`**Daily 5–10 minute recall session**
  *attempt from memory first*
  *explanation unlocked after*`"]
  Personal["`**Personal learning notes**
  *author-only · machine-local · not committed*`"]
  Promotion["`**Promotion ladder**
  *personal → repo → domain → global*
  *gated by reuse, review, and signoff*`"]
  Artifacts["`**Artifact-typed control plane**
  *instructions · skills · hooks*`"]
  Enterprise["`**Enterprise knowledge systems**
  *planned contract · optional integration*`"]

  Activity --> Observatory --> Signals --> Retrieval --> Session
  Session -->|"confidence · misconceptions · outcomes"| Personal
  Personal --> Promotion
  Promotion --> Artifacts
  Promotion <-.->|"canonical export"| Enterprise
  Artifacts -.->|"durable concepts for reinforcement"| Retrieval

  subgraph Legend[" Status "]
    direction LR
    L1["`in repository`"]
    L2["`planned`"]
    L3["`author-only`"]
  end

  classDef built fill:#eef4ff,stroke:#3f5c8f,stroke-width:1.6px,color:#182234;
  classDef ingest fill:#fff4df,stroke:#a86f18,stroke-width:1.6px,color:#2b2112;
  classDef store fill:#f3efff,stroke:#7355a8,stroke-width:1.6px,color:#241b38;
  classDef knowledge fill:#f7eff7,stroke:#875b87,stroke-width:1.6px,color:#2f1f2f;
  classDef planned fill:#eaf7ee,stroke:#438459,stroke-width:1.6px,color:#14281b,stroke-dasharray: 7 4;
  classDef personal fill:#f2f2f0,stroke:#7a7a72,stroke-width:1.6px,color:#33332e,stroke-dasharray: 1 4;

  class Activity built;
  class Observatory ingest;
  class Signals store;
  class Retrieval,Session,Enterprise planned;
  class Promotion,Artifacts knowledge;
  class Personal,L3 personal;
  class L1 built;
  class L2 planned;
  style Legend fill:#ffffff,stroke:#c8c8c8,color:#555555;
```

*Summary view; border style carries status, per the diagram's own legend.
Bold names the component, italics its responsibilities. Personal learning
notes stay with their author and are never committed. No scheduler, quiz
engine, or persistence layer is implemented; see Implementation Boundary.
The block above is the canonical source; regenerate
[`developer-learning-retrieval-in-context.svg`](docs/diagrams/developer-learning-retrieval-in-context.svg)
from it after any edit.*

The service design is documented in [`design.md`](docs/design.md).

Deferred feature concepts:

- [Shared Shell Assistance Gradient](features/shared-shell-assistance-gradient.md)
  explores three assistance interfaces over one continuous shell session as a
  source of learning and retention signals.

## Implementation Boundary

No scheduler, quiz engine, Codex automation, or user interface has been
implemented yet, and no learning signals are consumed from commits,
debugging sessions, or telemetry. Nothing in this directory runs. It
establishes the planned service boundary without overstating its maturity.
