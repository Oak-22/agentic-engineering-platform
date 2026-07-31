# Codex Skill Catalog

This directory exposes the repository's installed, shared skills to Codex.
The reference catalogs below show the standard skills published by OpenAI so
developers can study proven workflow boundaries before creating a
repository-specific skill.

Catalog snapshot: 2026-07-30. A catalog entry is a reference and is not
installed in this repository. OpenAI's current examples live in the
[OpenAI plugins catalog](https://github.com/openai/plugins), where skills can
be packaged with hooks, commands, agents, MCP configuration, and supporting
assets. The older [`openai/skills`](https://github.com/openai/skills)
repository is deprecated.

## Repository skills

- `deliver-governed-change` — Coordinate a traceable change across work tracking, documentation, code, review, and closure.
- `handoff-agent-work` — Preserve intent, evidence, authority, and state when work moves between agents or runtimes.
- `manage-git-workflow` — Govern branches, commits, pushes, pull requests, merges, and cleanup.
- `manage-jira-confluence` — Read and update Jira and Confluence as one traceable Atlassian workflow.
- `shape-readme-entrypoint` — Keep a repository README focused on orientation and a hands-on quick start.

## OpenAI system skills

These skills are bundled with current Codex distributions.

- `imagegen` — Generate or edit raster images.
- `openai-docs` — Answer OpenAI product and API questions from current official documentation.
- `plugin-creator` — Scaffold and update installable Codex plugins and marketplace entries.
- `skill-creator` — Create or improve reusable Agent Skills.
- `skill-installer` — List and install skills from OpenAI's catalog or another GitHub repository.

## High-value OpenAI plugin examples

These current, non-deprecated examples show how OpenAI packages focused skills
with the runtime surfaces needed to deliver a complete workflow.

- [`github`](https://github.com/openai/plugins/tree/main/plugins/github) — Inspect repositories, triage pull requests and issues, debug CI, and publish changes.
- [`figma`](https://github.com/openai/plugins/tree/main/plugins/figma) — Implement designs, generate Code Connect templates, and derive design-system rules.
- [`notion`](https://github.com/openai/plugins/tree/main/plugins/notion) — Plan implementation, synthesize research, prepare meetings, and capture knowledge.
- [`build-web-apps`](https://github.com/openai/plugins/tree/main/plugins/build-web-apps) — Combine frontend design, browser testing, UI components, payments, and database guidance.
- [`codex-security`](https://github.com/openai/plugins/tree/main/plugins/codex-security) — Run security scans, analyze findings, and guide investigations.
- [`openai-developers`](https://github.com/openai/plugins/tree/main/plugins/openai-developers) — Build with OpenAI APIs, the Agents SDK, and ChatGPT Apps.
- [`sentry`](https://github.com/openai/plugins/tree/main/plugins/sentry) — Inspect and summarize recent production issues and events.
- [`stripe`](https://github.com/openai/plugins/tree/main/plugins/stripe) — Integrate payment and business workflows.
- [`vercel`](https://github.com/openai/plugins/tree/main/plugins/vercel) — Build and deploy web applications and agents.
- [`slack`](https://github.com/openai/plugins/tree/main/plugins/slack) — Package collaboration workflows around a connected Slack workspace.

## Using the catalog

Study the closest official plugin and its nested skills before authoring a
custom skill. Keep the custom workflow focused on a distinct trigger, input,
output, and success condition. Treat catalog entries as design references
until the repository explicitly adopts their runtime dependencies.
