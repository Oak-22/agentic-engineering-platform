# Git Foundations

Use this prompt when you want explanations grounded in practical Git first principles.

## Source Note

Primary source material lives in:
../../../engineering-knowledge-base/personal_learning_notes/foundations/git-foundations.md

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

## Output Style

- Keep explanations beginner-friendly but technically exact.
- Use short, concrete examples over abstract definitions.
- End with a one-line recap of "what changed locally" vs "what changed on remote".
