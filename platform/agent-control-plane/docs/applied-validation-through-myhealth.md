# Applied Validation Through myHealth

myHealth is a downstream proving ground for the portable agent contract. It
owns its health-domain and product-specific agent definitions; the Agent
Instruction Control Plane owns the manifest contract and runtime adapters.

## Artifact classification

The initial inventory uses three ownership classes:

| Artifact | Classification | Reason |
| --- | --- | --- |
| Portable manifest contract and renderer | Platform-generic | Every downstream repository can use them. |
| Architecture Steward identity and rules | myHealth-product | They cite myHealth ADRs and architecture boundaries. |
| Code Reviewer core review priorities | Platform-generic candidate | Risk-first review is reusable, but PHI checks are an overlay. |
| Compliance agent | Health-domain | Its behavior depends on clinical governance and PHI policy. |
| Data Engineer agent | myHealth-product | It depends on myHealth ingestion contracts and MCP tools. |
| Documentation Curator | Platform-generic candidate | Its general role is reusable; its sources and vocabulary are product-owned. |
| Security Expert | Platform-generic candidate | Least privilege is reusable; sensitive-data rules are a health overlay. |
| Tester | Platform-generic candidate | Test discipline is reusable; ingestion and pseudonymization rules are product-owned. |
| `.github/instructions/myhealth-context.instructions.md` | myHealth-product | It supplies repository identity and local architecture context. |
| Privacy and compliance instructions and skills | Health-domain | They encode regulated-domain boundaries. |
| Ingestion instructions, prompts, and skills | myHealth-product | They encode application contracts and workflows. |
| Hook JSON and shell implementations | Mixed | Hook lifecycle is generic; the enforced policies remain downstream-owned. |
| `.github/local/overlays/` | Personal/local | These are intentionally machine-local and are not portable assets. |

Candidate status does not authorize moving an artifact. Promotion should occur
only after another repository demonstrates the same stable behavior.

## Architecture Steward pilot

The pilot establishes:

1. The original GitHub custom agent is the behavioral baseline.
2. myHealth stores a runtime-neutral TOML manifest under
   `agent-pack/agents/architecture-steward/`.
3. The platform GitHub adapter renders the existing
   `.github/agents/architecture-steward.agent.md`.
4. Exact output equality verifies that adopting the manifest did not alter the
   agent's discovery metadata, tools, or instructions.
5. A `--check` invocation detects future source/generated-output drift.

This validates packaging and provenance before adding model routing, telemetry,
handoffs, or additional runtimes to the contract.
