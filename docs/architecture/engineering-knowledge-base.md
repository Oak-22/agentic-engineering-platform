# Engineering Knowledge Base

Status: **Planned public component contract**

This design surface defines the portable structure through which engineering
observations become durable, retrievable knowledge. It is separate from any
developer's private knowledge content.

## Intended Responsibilities

- schemas for incidents, decisions, learning notes, and case studies
- provenance from source activity to captured knowledge
- private, team, and public promotion boundaries
- lifecycle rules for reviewing, refining, and retiring knowledge
- interfaces for retrieval systems and agent instruction workflows
- templates that downstream repositories can adopt consistently

## Privacy Boundary

The public contract will contain only reusable schemas, templates,
documentation, and tooling. Personal notes may be mounted through a
machine-local `engineering-knowledge-base` overlay and must not be committed
automatically.

## Platform Relationships

The contract receives validated learning from Developer Learning Retrieval and
supplies provenance and knowledge artifacts to Agent Instruction Control Plane.
