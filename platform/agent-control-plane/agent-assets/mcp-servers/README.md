# Canonical MCP Servers

This directory owns provider-neutral Model Context Protocol (MCP) server
definitions — the external tool and resource connectors an agent may use. A
definition describes the server's identity and purpose, transport, required
scopes or credential references, and the skill(s) that depend on it, without
embedding provider configuration syntax.

Provider configuration formats (`.mcp.json` for Claude Code, the
`[mcp_servers.*]` table in Codex's `config.toml`, VS Code's `mcp.json` for
GitHub Copilot), supported transports and versions, and renderers belong in
[`../../adapters/runtimes/`](../../adapters/runtimes/). JSON Schemas that
validate these portable definitions belong in
[`../../contracts/`](../../contracts/).

Add a server definition only when a concrete integration exists or is
actively being wired up.

## What belongs in a definition

- Server identity: name, upstream service, and a one-line purpose.
- Transport: stdio, SSE, or streamable HTTP, and which is authoritative if a
  target provider only supports a subset.
- Required scopes and the name of the credential or environment variable that
  supplies them — never the credential value itself.
- The skill(s) or role charter(s) that depend on this server, so removing or
  changing it surfaces what else breaks.
- Any elicitation, resource, or prompt capabilities a consuming agent should
  expect, if the server exposes more than tools.

## What does not belong here

- Provider-specific configuration keys, file formats, or install scopes.
- Secrets, tokens, or environment-specific endpoints. Credential resolution
  stays in each runtime's native secret store.
- Speculative servers with no owning skill and no concrete integration plan.

## Folder structure

```text
mcp-servers/
  README.md
  <server-name>/
    server.md        # canonical definition: identity, transport, scopes, dependents
    references/       # optional — deeper integration notes, upstream API caveats
```

Name each server directory for the upstream service it connects to (for
example `jira-confluence/`, `github/`), not for the runtime that will consume
it. A server used by more than one runtime still gets exactly one definition
here; per-runtime rendering is an adapter's job, not a reason to fork the
canonical directory.
