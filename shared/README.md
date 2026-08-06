# Shared Platform Assets

This directory owns stable cross-domain assets. Add an artifact here only when
at least two platform components share its lifecycle or contract. Potential
future reuse is not sufficient reason to move a component-owned artifact here.

- [`schemas/`](schemas/) contains shared data and event schemas.
- [`contracts/`](contracts/) contains cross-component interface contracts.
- [`tooling/`](tooling/) contains repository-wide reusable tooling, including
  the independently packageable folder-structure visualizer.
