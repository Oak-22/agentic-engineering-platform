# Architecture

Durable platform architecture, ownership boundaries, and design contracts
belong here.

- [`adr/`](adr/) records repository-wide and component-scoped architecture
  decisions using one central register.
- [`authority-and-discovery-layering.md`](authority-and-discovery-layering.md)
  states the repository-wide rule that every layered asset type keeps one
  canonical, deepest-applicable source, with shallower layers linking inward
  instead of copying mechanics outward.
- [`control-artifact-assurance-spectrum.md`](control-artifact-assurance-spectrum.md)
  places every behavior-constraining artifact on a spectrum from interpretive
  to mechanically enforced, and states how strong an assurance a given control
  should carry.
- [`engineering-knowledge-base.md`](engineering-knowledge-base.md) defines the
  planned portable contract for durable engineering knowledge.
