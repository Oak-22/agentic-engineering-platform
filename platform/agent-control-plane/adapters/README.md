# Agent Control Plane Adapters

Adapters project portable Agent Control Plane contracts and assets across two
distinct boundaries: destination systems and agent runtimes.

- [`jira/`](jira/) maps governed work-item metadata into a Jira deployment.
- [`runtimes/`](runtimes/) owns provider runtime capability declarations,
  supported-version ranges, configuration renderers, and mapping tests.

Keep destination adapters beside `runtimes/` while Jira is the only concrete
destination. Introduce a `destinations/` namespace when a second destination
adapter makes that grouping useful; do not classify Jira as an agent runtime.

Portable intent remains in `contracts/` and `agent-assets/`. Adapters may
translate that intent but must not become an alternate canonical source.
