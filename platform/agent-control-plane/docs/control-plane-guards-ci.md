# Control Plane Guards in CI

## Purpose

The control plane ships drift and integrity guards that a maintainer can run
locally. `.github/workflows/control-plane-guards.yml` makes those same guards
run on every pull request to `main`, so a forgotten local command cannot let a
stale adapter, a schema error, a registry defect, or a misplaced runtime
discovery surface reach the integration branch.

This document explains how that enforcement works, what each GitHub Actions
concept in the workflow does, and how to operate and troubleshoot it.

## Four separate signals

These are frequently conflated. They are different mechanisms with different
authority:

| Signal | Produced by | Authority |
| --- | --- | --- |
| Workflow success | The `control-plane-guards` job finishing green | Evidence that the guards passed on this commit |
| Required-check enforcement | The `main` branch ruleset requiring that check | Blocks merge deterministically |
| Copilot code review | GitHub Copilot, requested automatically | Advisory comments only; approves nothing |
| Human approval | An accountable reviewer | The governed approval for the change |

`main` stays protected by the executable Actions check whether or not Copilot
is available and whether or not it produces findings.

## Workflow anatomy

GitHub Actions nests four things. Reading the file top to bottom:

```text
workflow  .github/workflows/control-plane-guards.yml   "Control Plane Guards"
  event   pull_request / push / workflow_dispatch      what starts a run
  job     control-plane-guards                         one runner, one status check
  step    "Guard - contract schemas"                   one action or one command
```

A **workflow** is the file. An **event** starts a run of it. A **job** is a
unit that gets its own fresh runner and reports its own status check. A
**step** is either a reusable `uses:` action or a `run:` shell command.

### Events

| Event | Purpose |
| --- | --- |
| `pull_request` to `main` | The gate. Every proposed change is verified before merge. |
| `push` to `main` | Backstop for anything reaching `main` outside a gated pull request. |
| `workflow_dispatch` | Manual run from the Actions tab or `gh workflow run`, for diagnostics. |

There is deliberately **no `paths:` filter**. A path filter looks like an
optimization, but a required status check that is skipped never reports a
conclusion at all, so the merge requirement stays pending forever instead of
passing. A required check must run on every pull request. The guards are cheap
enough that this costs little.

### Runner isolation

`runs-on: ubuntu-latest` gives the job a clean, ephemeral virtual machine. It
holds no repository state, no maintainer virtualenv, and nothing from a
previous run. That is why the workflow checks the repository out and installs
its dependencies explicitly instead of assuming
`platform/agent-control-plane/.venv` exists. Anything the job does not install
is not there.

The runner's filesystem does not persist. Only the job's logs, its status, its
step summary, and any cache it writes survive the run.

### Contexts and expressions

`${{ ... }}` is an expression evaluated by the runner before the step runs.
This workflow uses:

| Expression | Meaning |
| --- | --- |
| `github.workflow` | The workflow's name, used to scope the concurrency group. |
| `github.ref` | The ref being built, which separates concurrency per branch or pull request. |
| `github.event_name` | Which event triggered the run; used to cancel only pull-request runs. |
| `job.status` | The job's status so far (`success`, `failure`, `cancelled`), read by the summary step. |
| `steps.<id>.outcome` | One guard step's result, so the summary can name which contract broke. |
| `always()` | A status-check function that makes the summary step run even after a failure. |

Without `always()`, a step inherits an implicit `success()` condition — the
summary would be skipped in exactly the failure case a reader most needs it.

Guard outcomes reach the summary script through `env:` rather than being
interpolated directly into the shell body. Expression values are substituted
into the script text before the shell parses it, so interpolating untrusted or
free-form values inline is a script-injection path. Passing them as
environment variables keeps them data.

### Permissions, secrets, and forks

```yaml
permissions:
  contents: read
```

This sets the `GITHUB_TOKEN`'s scope for the whole workflow. The guards only
read the checked-out tree, so no write scope is needed and none is granted. The
workflow references no secret.

The trigger is `pull_request`, never `pull_request_target`. The distinction
matters because this workflow **checks out and executes pull-request code**,
including code from forks:

- `pull_request` runs the workflow definition from the base branch in a
  restricted context. For a fork, the token is read-only and repository secrets
  are unavailable, so untrusted code cannot exfiltrate anything or write to the
  repository.
- `pull_request_target` runs in the base repository's context with a writable
  token and access to secrets. Combining it with a checkout of the pull
  request's head is a well-known privilege-escalation pattern: anyone who can
  open a pull request could run arbitrary code with the repository's
  credentials.

`pull_request_target` is only appropriate for workflows that do not execute
untrusted code, which this one does.

### Action pinning and maintenance

Third-party actions are pinned to full-length commit SHAs, with the readable
release version kept in a comment above each `uses:` line:

```yaml
# actions/checkout v7.0.1
uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
```

A tag such as `v7` is a moving pointer that its owner can repoint. A commit SHA
is immutable, so the workflow runs the exact code that was reviewed. Pinning
this way trades automatic patch updates for supply-chain integrity, and
`.github/dependabot.yml` already covers the `github-actions` ecosystem at the
repository root, so Dependabot opens a pull request when a pinned action has a
newer release — which lands the bump through the same reviewed, guarded path as
any other change.

### Cache, not artifact

`setup-python`'s `cache: pip` stores the pip download cache between runs, keyed
from a hash of `platform/agent-control-plane/pyproject.toml`. When the
dependency metadata changes, the key changes and the cache misses.

A **cache** is an optimization: `python -m pip install` runs on every run
regardless, so a cold cache changes how long the job takes and never what it
concludes. An **artifact** is a durable output published for download after a
run. This workflow produces no artifact because it builds nothing — it only
answers pass or fail. Uploading one would create a file nobody consumes.

### Concurrency, cancellation, and timeouts

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

The group keys one in-flight run per workflow and ref. Pushing a new commit to
an open pull request cancels the superseded run, because only the newest
commit's verdict matters and the older answer is about code nobody will merge.
A cancelled run reports the `cancelled` conclusion, which does not satisfy a
required check.

Runs on `main` are allowed to finish: the integration branch keeps a complete
record of every commit that landed on it.

`timeout-minutes: 15` bounds the job. Without it a hung step would occupy a
runner until the six-hour default expires.

Every guard is an ordinary process. A nonzero exit code fails its step, and a
failed step fails the job unless it is marked otherwise. That is the entire
pass/fail contract — the guards need no Actions-specific integration.

## Merge enforcement

Enforcement lives in a GitHub **branch ruleset**, not in the workflow. A green
workflow is evidence; the ruleset is what turns that evidence into a merge
requirement.

| Setting | Value |
| --- | --- |
| Ruleset | `Protect main` (repository → Settings → Rules → Rulesets) |
| Target | Branch `~DEFAULT_BRANCH` |
| Enforcement | Active |
| Required status check context | `control-plane-guards` |
| Strict policy | Branch must be up to date with `main` before merging |
| Pull request | Required, with one approving review |

The required status check context is the **job ID**, `control-plane-guards`,
because the job declares no separate `name:`. Renaming that job ID silently
detaches the rule: the ruleset keeps waiting on a context that nothing reports,
and the pull request never becomes mergeable. Treat the job ID as a published
interface.

GitHub normally only offers contexts it has already observed, so the workflow
runs once on a real pull request before the rule can select it.

A failing required check is not an ordinary thing to route around. Bypass is
reserved for a deliberate, recorded exception, not for a delivery path.

## Copilot code review

Copilot code review is configured on the same ruleset:

| Setting | Value |
| --- | --- |
| Rule | Automatically request Copilot code review |
| Review draft pull requests | Enabled |
| Review new pushes | Enabled |

Reviewing drafts surfaces feedback before a human is asked to look. Reviewing
new pushes keeps the review attached to the current commit rather than only the
first version of the change.

### What Copilot sees

Copilot reviews the pull-request diff plus repository context from the base
branch, including `.github/copilot-instructions.md` and the path-scoped files
under `.github/instructions/`. Those instructions on `main` are the review
policy source.

This makes the review **independent of the developer's local agent session**:
it does not inherit the implementation conversation, the reasoning behind a
choice, or any context the author never wrote down. It is not, however, blind
to the implementation — it reads the diff and the repository. Independence here
means a separate vantage point, not ignorance.

### What Copilot cannot do

Under GitHub's current behavior, Copilot code review submits **Comment**
reviews. It cannot approve a pull request, cannot request changes in the
blocking sense, cannot satisfy a required approving review, and cannot block a
merge. It is an advisory reviewer, not the deterministic enforcement mechanism
and not the accountable human approver.

Findings are triaged by the author or a human reviewer. Suggestions are not
applied automatically, and a Copilot comment is not evidence that a change is
correct.

Automatic review requires a Copilot Pro, Pro+, or Max plan on the account that
owns the repository. When it is unavailable, the fallback is to request the
review manually from the pull request's Reviewers menu, and the Actions gate is
unaffected — it never depended on Copilot.

## Local equivalents

Every CI command has a local equivalent. Run them from the repository root
using the maintainer virtualenv described in the
[component README](../README.md):

```bash
P=platform/agent-control-plane/.venv/bin/python

scripts/check-agent-discovery-layout.sh
"$P" -m unittest discover -s platform/agent-control-plane/tests
"$P" platform/agent-control-plane/scripts/validate_asset_registries.py
"$P" platform/agent-control-plane/scripts/validate_contracts.py
"$P" platform/agent-control-plane/scripts/generate_instruction_adapters.py --check
```

CI invokes these as `python`, because `setup-python` has already put the
resolved interpreter first on `PATH`. The layout guard prefers the maintainer
virtualenv when it exists and falls back to `python3`, which is why it works
unchanged in both places.

The layout guard calls the registry validator itself, so the registry step is
partly redundant. It is kept as its own step because a separately named step
makes a registry failure identifiable from the job list without reading a log.

The interpreter version comes from `project.requires-python` in
`platform/agent-control-plane/pyproject.toml` via `python-version-file`, so the
YAML never restates a version that could drift from the package's own contract.
Because that constraint has no upper bound, CI resolves to the newest Python
the runner offers; a future release that breaks the guards surfaces here first.

## Inspecting and troubleshooting runs

In the browser, the pull request's Checks tab and the repository's Actions tab
show each run, its jobs, its steps, and the job summary the workflow writes.

From the terminal:

```bash
gh run list --workflow control-plane-guards.yml     # recent runs
gh run view <run-id>                                # jobs and step outcomes
gh run view <run-id> --log-failed                   # only the failing step's log
gh run watch <run-id>                               # follow a run in progress
gh run rerun <run-id> --failed                      # retry only failed jobs
gh workflow run control-plane-guards.yml --ref main # manual dispatch
```

Read the job summary first. It reports each guard's outcome next to the local
command that reproduces it, so the usual path is: read the summary, run that
one command locally, fix, push.

A stale instruction adapter is the most common failure. The adapter-freshness
guard fails when `.claude/rules/` or `.github/instructions/` frontmatter no
longer matches `instructions_registry.json`. Regenerate and commit:

```bash
platform/agent-control-plane/.venv/bin/python \
  platform/agent-control-plane/scripts/generate_instruction_adapters.py
```

For a run whose failure is not reproducible locally, re-run it with debug
logging enabled — the "Re-run jobs" menu offers "Enable debug logging", which
sets `ACTIONS_RUNNER_DEBUG` and `ACTIONS_STEP_DEBUG` for that run and exposes
each step's internal tracing.

A cancelled run is usually not a defect: pushing again to an open pull request
cancels the superseded run by design. Re-running a cancelled run reproduces a
verdict about a commit that has already been replaced; push or re-run against
the current head instead.

## Deliberately omitted

These GitHub Actions features are not used here. Adding one without a consumer
would cost maintenance and teach a pattern this repository does not need.

| Feature | Why it is absent |
| --- | --- |
| Matrix | All five guards need the same lightweight Python environment. A matrix would multiply setup cost and split one protected check into several. |
| Artifacts | The workflow builds nothing. Its output is a pass/fail conclusion plus a job summary, neither of which is a downloadable file. |
| Deployment environments | Nothing is deployed, so there is no environment to gate, approve, or scope secrets to. |
| Service containers | The guards run in-process against the checked-out tree with no database, queue, or network dependency. |
| Self-hosted runners | The job needs only Python and a checkout, which hosted runners provide with better isolation and no maintenance. |
| Reusable workflows | Reuse needs a second caller. This repository has one workflow; extracting it now would add indirection with no consumer. |
| Composite actions | Same reason: the guard steps are called once, from one place. |
| Path filters | A required check that is skipped never reports, leaving the merge requirement pending forever. |
| Scheduled runs | The guards verify repository content, which only changes when a commit changes it. A cron run would re-verify an unchanged tree. |

Revisit any row when a concrete consumer appears.
