# Diagrams

Repository-level diagrams. The directory is flat: one canonical file per
diagram, with any derived exports beside it under the same stem.

| Diagram | Canonical | Derived |
| --- | --- | --- |
| Agentic Engineering Platform | [`agentic-engineering-platform-diagram.svg`](agentic-engineering-platform-diagram.svg) — hand-authored SVG | `.png`, `.pdf` |
| Mechanistic guarantee comparison | [`mechanistic-guarantee-compare.html`](mechanistic-guarantee-compare.html) — self-contained | — |
| Mechanistic guarantee footprint | [`mechanistic-guarantee-footprint.html`](mechanistic-guarantee-footprint.html) — self-contained | — |

Edit the canonical file and regenerate the derived exports from it; never
edit an export directly.

## Placement and promotion

Files arrive here two ways.

- **Authored in place.** A hand-written SVG or an Excalidraw source lives
  here from the start, with its exports generated alongside.
- **Promoted.** A rapid visualization produced during a session — an
  `.html` page viewable in the integrated browser — is copied here by a
  human once it proves worth keeping. Promotion is a deliberate one-off
  judgment, never automated, and drops any record of which runtime
  produced the file.

A promoted `.html` is durable by placement: it needs no inbound link from
prose to belong here, because it opens on its own as a complete visual
object. Runtimes without native artifact tooling reach the same outcome
with Mermaid; a Mermaid capture may be promoted here as a file, or its
diagram source pasted inline into the doc that discusses the mechanism,
whichever leaves the reader with something that reads completely.

Full policy:
[`platform/agent-control-plane/docs/local-doc-mirrors.md`](../../platform/agent-control-plane/docs/local-doc-mirrors.md).
Component-scoped diagrams live under their component, for example
[`platform/agent-control-plane/docs/diagrams/`](../../platform/agent-control-plane/docs/diagrams/).
