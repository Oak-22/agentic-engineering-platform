# Skills

Place repeatable workflow playbooks here.

Recommended layout:

- `.github/skills/<skill-name>/SKILL.md`
- `.agents/skills/<skill-name>` as a relative symlink when Codex should
  discover the canonical skill.

All checked-in canonical skills currently require a matching Codex adapter.
Run `scripts/check-agent-discovery-layout.sh` to verify the one-to-one mapping.

Available skills:

- `manage-git-workflow/`
  Apply explicit authorization boundaries to branches, commits, pushes, pull
  requests, merges, and cleanup.
- `manage-jira-confluence/`
  Operate linked Jira discovery, Jira delivery, and Confluence knowledge
  workflows with verified cross-product traceability.
- `shape-readme-entrypoint/`
  Keep README files focused on hands-on evaluation while routing product
  thinking, architecture, and migration context into durable docs.
