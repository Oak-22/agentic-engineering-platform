# Agent Control Plane Adapters

Adapters project portable Agent Control Plane contracts and assets into native
destination or runtime representations.

- [`jira/`](jira/) maps governed work-item metadata into a Jira deployment.
- [`runtimes/`](runtimes/) owns provider runtime capability declarations,
  supported-version ranges, configuration renderers, and mapping tests.

Portable intent remains in `contracts/` and `agent-assets/`. Adapters may
translate that intent but must not become an alternate canonical source.
