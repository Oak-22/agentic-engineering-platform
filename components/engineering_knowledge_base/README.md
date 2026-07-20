# Engineering Knowledge Base

Status: **Planned public component contract**

This component will define the portable structure through which
engineering observations become durable, retrievable knowledge. It is
separate from any developer's private knowledge content.

## Intended Responsibilities

- schemas for incidents, decisions, learning notes, and case studies
- provenance from source activity to captured knowledge
- private, team, and public promotion boundaries
- lifecycle rules for reviewing, refining, and retiring knowledge
- interfaces for retrieval systems and agent instruction workflows
- templates that downstream repositories can adopt consistently

## Privacy Boundary

The canonical component will contain only reusable schemas, templates,
documentation, and tooling. Personal notes may be mounted through a
machine-local `engineering_knowledge_base` overlay and must not be
committed automatically.

## Platform Relationships

The component receives validated learning from the Developer Learning
Retrieval Service and supplies provenance and knowledge artifacts to the
Agent Instruction Control Plane.
