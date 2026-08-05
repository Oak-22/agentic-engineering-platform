# Canonical Execution Policies

This directory owns provider-neutral bounded-execution policy instances. A
policy defines the resource boundary, approval and escalation strategy, bypass
rules, and intended enforcement tier without embedding provider configuration
syntax.

JSON Schemas that validate these portable policies belong in
[`../../contracts/`](../../contracts/). Provider capability mappings,
supported versions, and renderers belong in
[`../../adapters/runtimes/`](../../adapters/runtimes/).

Generated provider configuration must preserve the canonical security intent.
An adapter must reject or explicitly report unsupported requirements instead
of silently weakening them.
