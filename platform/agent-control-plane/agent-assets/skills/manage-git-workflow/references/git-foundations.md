# Git Foundations

Use this prompt when you want explanations grounded in practical Git first principles.

## Instructions

- Explain concepts using the mental flow: inspect -> stage -> commit -> sync.
- Distinguish local Git objects from GitHub platform metadata.
- Clarify branch vs remote terms precisely:
  - `main` is a branch name.
  - `origin` is a local alias for a remote URL.
  - `origin/main` is a remote-tracking reference.
- Prefer concise examples with `git status`, `git add`, `git commit`, `git fetch`, and `git push`.
- When discussing authentication, separate SSH transport identity from GitHub API token authority.
- Correct misunderstandings directly, then restate the accurate mental model in one sentence.

## Tool and Transport Boundaries

Keep the local Git model, Git transport, and GitHub platform distinct:

```text
git       = local Git model and history
SSH/HTTPS = transport for Git objects and refs
gh        = GitHub platform API/CLI
```

`git` manages the local repository and history, including status, diffs,
commits, branches, merges, and logs. These operations can be performed
offline. `git fetch`, `git pull`, and `git push` communicate with a remote;
that transport may use SSH or HTTPS. SSH is common, but it is not inherently
required.

`gh` manages GitHub-level context and metadata that Git itself does not own,
such as pull requests, issues, reviews, Actions, releases, labels, projects,
and repository settings. The two interfaces overlap because both can call
GitHub operations, but `gh` does not replace local `git`.

## Output Style

- Keep explanations beginner-friendly but technically exact.
- Use short, concrete examples over abstract definitions.
- End with a one-line recap of "what changed locally" vs "what changed on remote".
