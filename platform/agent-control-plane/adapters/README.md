# Agent Control Plane Adapters

Adapters project portable Agent Control Plane contracts and assets across two
distinct boundaries: destination systems and agent runtimes. Destination
surfaces are intentionally flat so the adapter name is also the boundary an
agent sees:

- [`github/`](github/) maps governed delivery operations to GitHub platform
  APIs, primarily through the shared GitHub MCP server.
- [`jira/`](jira/) maps governed work-item metadata and delivery operations to
  the configured Atlassian/Jira surfaces.
- [`runtimes/`](runtimes/) owns provider runtime capability declarations,
  supported-version ranges, configuration renderers, and mapping tests.

Do not add a `destinations/` namespace for these adapters. Jira and GitHub are
the primary destination boundaries, and future destination adapters should be
added as siblings unless there is a concrete, reviewed reason to introduce a
different grouping.

Portable intent remains in `contracts/` and `agent-assets/`. Adapters may
translate that intent but must not become an alternate canonical source.
