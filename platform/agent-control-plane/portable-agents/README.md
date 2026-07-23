# Portable Agent Manifest

The portable agent manifest is the smallest runtime-neutral source needed to
render a specialist agent for a supported coding-agent runtime.

Product repositories own their agent manifests. The platform's agent control
plane owns this contract, validation, and runtime adapters.

## Version 1 contract

A manifest is a TOML file with these required fields:

```toml
schema_version = 1
id = "architecture-steward"
name = "Architecture Steward"
description = "Use for architecture governance."
tools = ["read", "search", "edit"]
instructions = """
You are the product architecture steward.
"""
```

- `schema_version` selects the contract version.
- `id` is a stable lowercase, hyphenated identifier.
- `name` and `description` are human-facing discovery metadata.
- `tools` contains portable capability names. Runtime adapters must reject
  unsupported capabilities instead of silently widening permissions.
- `instructions` is the complete runtime-neutral agent instruction body.

Version 1 deliberately excludes model selection, telemetry, handoffs, skills,
and repository routing. Those fields should be added only after a real
cross-runtime requirement is validated.

## GitHub custom-agent adapter

Render a manifest to GitHub's `.agent.md` format:

```sh
python3 scripts/render_portable_agent.py \
  --manifest /path/to/agent.toml \
  --runtime github \
  --output /path/to/.github/agents/example.agent.md
```

Use `--check` in CI to verify that an installed file matches its manifest:

```sh
python3 scripts/render_portable_agent.py \
  --manifest /path/to/agent.toml \
  --runtime github \
  --output /path/to/.github/agents/example.agent.md \
  --check
```
