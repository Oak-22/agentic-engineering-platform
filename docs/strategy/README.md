# Strategy Notes

This folder holds strategic rationale for the AI Agent Instruction
Control Plane.

These notes explain why the control-plane pattern exists, what kinds of
problems it is meant to govern, and how the pattern can travel across
domains. They are not part of the minimum install surface for adopting
the template.

## Current Notes

- [`invisible-systems-thesis.md`](invisible-systems-thesis.md)
  Defines the broad thesis behind the control plane: invisible surfaces
  such as authority, evidence, provenance, uncertainty, review, and
  human consequences should be made explicit enough to govern.

## Placement Rule

- Domain-agnostic control-plane philosophy belongs here.
- Applied validation notes that test the template through a specific
  project belong in `docs/` near the relevant validation document.
- Domain-specific governance theses belong in the downstream domain
  repository that owns that application or research surface.

For the current biohealth direction, keep the general thesis in this
repository and keep the clinical/bioscience governance thesis in the
biohealth control-plane repository.
