# Claude Skill Catalog

This directory exposes the canonical packages under
`platform/agent-control-plane/agent-assets/skills/` to Claude Code through
relative symlinks. The reference catalog below lists every skill published in
Anthropic's official skills repository so developers can study production and
example patterns before creating a repository-specific skill.

Catalog snapshot: 2026-07-30. A catalog entry is a reference and is not
installed in this repository. Check the
[Anthropic skills repository](https://github.com/anthropics/skills) for newer
entries, implementation details, dependencies, and license terms. Anthropic
describes these as examples and reference implementations; behavior can differ
across Claude products.

## Repository skills

- `deliver-governed-change` — Coordinate a traceable change across work tracking, documentation, code, review, and closure.
- `handoff-agent-work` — Preserve intent, evidence, authority, and state when work moves between agents or runtimes.
- `manage-git-workflow` — Govern branches, commits, pushes, pull requests, merges, and cleanup.
- `manage-jira-confluence` — Read and update Jira and Confluence as one traceable Atlassian workflow.
- `shape-repository-change` — Turn repository observations and changes into coherent delivery-unit candidates.
- `shape-readme-entrypoint` — Keep a repository README focused on orientation and a hands-on quick start.

## Anthropic reference skills

- `algorithmic-art` — Create generative art with deterministic randomness and interactive controls.
- `brand-guidelines` — Apply Anthropic's published brand colors and typography to artifacts.
- `canvas-design` — Create polished static visual designs in PNG and PDF formats.
- `claude-api` — Build applications with the Claude API and Anthropic SDKs.
- `doc-coauthoring` — Guide a structured workflow for collaboratively drafting documentation.
- `docx` — Create, read, edit, and visually verify Word documents.
- `frontend-design` — Build distinctive, production-quality web interfaces.
- `internal-comms` — Draft common internal updates, reports, FAQs, and announcements.
- `mcp-builder` — Design and implement high-quality Model Context Protocol servers.
- `pdf` — Read, create, edit, and visually verify PDF files.
- `pptx` — Create, read, edit, and verify PowerPoint presentations.
- `skill-creator` — Create, evaluate, and improve Agent Skills.
- `slack-gif-creator` — Create animated GIFs optimized for Slack.
- `theme-factory` — Apply reusable visual themes to documents, slides, and web artifacts.
- `web-artifacts-builder` — Build complex interactive HTML artifacts with modern frontend tooling.
- `webapp-testing` — Test and debug local web applications with Playwright.
- `xlsx` — Create, read, edit, and verify spreadsheet files.

## Using the catalog

Study the closest official skill before authoring a custom one, then keep the
custom workflow focused on a distinct trigger, input, output, and success
condition. Install a reference skill only when the repository should depend on
its behavior; otherwise use it as a design reference.
