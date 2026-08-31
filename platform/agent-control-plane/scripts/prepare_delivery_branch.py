#!/usr/bin/env python3
"""Create a Jira-keyed delivery branch from a verified integration baseline.

Branch creation used to be a shell command run after a separate check, so the
state the check verified and the state the branch was cut from could differ.
This makes them one operation: every precondition is proven, the exact `main`
commit is re-read immediately before the branch is created, and the branch is
cut from that commit rather than from whatever happens to be checked out.

Read-only by default — it prints the plan and changes nothing. `--execute`
authorizes the two mutations it will ever make: fast-forwarding local `main`
when that is safe, and merging `main` into a clean `workbench/local`. It never
commits, stashes, discards, rebases, force-updates, or resolves a conflict.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


INTEGRATION_BRANCH = "main"
WORKBENCH_BRANCH = "workbench/local"
REMOTE = "origin"

#: The categories a new delivery branch may use, derived from the work item's
#: governed Class field. Cleanup tooling still recognizes the retired three.
AUTHORING_CATEGORIES = ("feature", "fix", "refactor", "chore", "docs")
RETIRED_CATEGORIES = {
    "bugfix": "`bugfix` duplicated `fix`; use `fix`",
    "hotfix": "`hotfix` was `fix` plus urgency; use `fix` and set the work item's priority",
    "release": "`release` described a process step rather than a change; it is not a delivery class",
}

BRANCH_NAME_PATTERN = re.compile(
    r"^(?P<category>[a-z]+)/(?P<key>[A-Z][A-Z0-9_]*-[1-9][0-9]*)-(?P<slug>[a-z0-9][a-z0-9-]*)$"
)

OK = "ok"
FAST_FORWARD = "fast-forward"
SYNC = "sync"
BLOCKED = "blocked"


class PreparationError(RuntimeError):
    """Raised when preparation cannot proceed or cannot be verified."""


@dataclass(frozen=True)
class Decision:
    """What one preparation stage concluded, and why."""

    stage: str
    action: str
    detail: str

    @property
    def blocks(self) -> bool:
        return self.action == BLOCKED

    @property
    def mutates(self) -> bool:
        return self.action in {FAST_FORWARD, SYNC}


# --------------------------------------------------------------------------
# Decisions — pure, so every safety boundary is testable without a repository
# --------------------------------------------------------------------------


def validate_branch_name(name: str) -> str | None:
    """Return an error for a branch name that breaks the contract, else None."""
    match = BRANCH_NAME_PATTERN.match(name)
    if match is None:
        return (
            f"{name!r} is not a delivery branch name. Use "
            "<category>/<JIRA-ISSUE-KEY>-<outcome-slug>, for example "
            "refactor/PROJ-12-telemetry-layout."
        )
    category = match.group("category")
    if category in RETIRED_CATEGORIES:
        return (
            f"the category {category!r} is retired for new work: "
            f"{RETIRED_CATEGORIES[category]}."
        )
    if category not in AUTHORING_CATEGORIES:
        return (
            f"{category!r} is not a change class. Derive the category from the "
            "work item's Class field: " + ", ".join(AUTHORING_CATEGORIES) + "."
        )
    return None


def baseline_decision(tracked: bool, ahead: int, behind: int) -> Decision:
    """Whether local `main` can carry a new delivery branch."""
    if not tracked:
        return Decision(
            "integration baseline",
            OK,
            f"no {REMOTE}/{INTEGRATION_BRANCH} to compare against; "
            f"using local {INTEGRATION_BRANCH} as the baseline",
        )
    if ahead and behind:
        return Decision(
            "integration baseline",
            BLOCKED,
            f"local {INTEGRATION_BRANCH} has diverged from {REMOTE}/{INTEGRATION_BRANCH} "
            f"({ahead} unique local commit(s), {behind} unique remote commit(s)). "
            "Reconcile the two deliberately; this operation will not rewrite history.",
        )
    if ahead:
        return Decision(
            "integration baseline",
            BLOCKED,
            f"local {INTEGRATION_BRANCH} is {ahead} commit(s) ahead of "
            f"{REMOTE}/{INTEGRATION_BRANCH}. Those commits reached the integration "
            "branch without a reviewed pull request. Deliver or remove them first.",
        )
    if behind:
        return Decision(
            "integration baseline",
            FAST_FORWARD,
            f"local {INTEGRATION_BRANCH} is {behind} commit(s) behind "
            f"{REMOTE}/{INTEGRATION_BRANCH} and fast-forwards cleanly",
        )
    return Decision(
        "integration baseline",
        OK,
        f"local {INTEGRATION_BRANCH} matches {REMOTE}/{INTEGRATION_BRANCH}",
    )


def workbench_decision(exists: bool, behind: int) -> Decision:
    """Whether the capture stream is current enough to reconcile against."""
    if not exists:
        return Decision(
            "workbench baseline",
            OK,
            f"no {WORKBENCH_BRANCH}; this repository uses the direct-delivery "
            "entry path and is not held to the workbench contract",
        )
    if behind:
        return Decision(
            "workbench baseline",
            SYNC,
            f"{WORKBENCH_BRANCH} is {behind} commit(s) behind {INTEGRATION_BRANCH} "
            "and needs it merged in before its remaining changes mean anything",
        )
    return Decision(
        "workbench baseline",
        OK,
        f"{WORKBENCH_BRANCH} contains every {INTEGRATION_BRANCH} commit",
    )


def worktree_decision(dirty_entries: Sequence[str]) -> Decision:
    if dirty_entries:
        listed = "\n".join(f"    {entry}" for entry in dirty_entries)
        return Decision(
            "working tree",
            BLOCKED,
            "the working tree has uncommitted changes, so branches cannot be "
            "switched safely. Commit or deliberately resolve them first:\n" + listed,
        )
    return Decision("working tree", OK, "clean")


def evidence_decision(unresolved_count: int, summary: str) -> Decision:
    if unresolved_count:
        return Decision(
            "workbench evidence",
            BLOCKED,
            f"{unresolved_count} workbench-only outcome(s) have no disposition. "
            "Deliver, park, or supersede each one before starting new work:\n"
            + summary,
        )
    return Decision("workbench evidence", OK, "every workbench-only outcome is accounted for")


def blocking(decisions: Sequence[Decision]) -> tuple[Decision, ...]:
    return tuple(decision for decision in decisions if decision.blocks)


# --------------------------------------------------------------------------
# Git orchestration
# --------------------------------------------------------------------------


def _git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=check, capture_output=True, text=True
    )


def _sibling(name: str):
    import importlib.util

    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py"
    )
    if spec is None or spec.loader is None:  # pragma: no cover - packaging guard
        raise PreparationError(f"could not load the {name} module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def current_branch(root: Path) -> str:
    return _git(root, "branch", "--show-current").stdout.strip()


def resolve(root: Path, revision: str) -> str:
    result = _git(root, "rev-parse", revision, check=False)
    if result.returncode != 0:
        raise PreparationError(f"could not resolve {revision}")
    return result.stdout.strip()


def plan(root: Path, *, fetch: bool) -> tuple[Decision, ...]:
    """Inspect the repository and decide every stage without mutating it."""
    preflight = _sibling("governed_task_preflight")
    evidence = _sibling("workbench_evidence")

    if fetch:
        fetched = _git(root, "fetch", REMOTE, check=False)
        if fetched.returncode != 0:
            detail = fetched.stderr.strip() or "unknown fetch failure"
            return (
                Decision(
                    "remote",
                    BLOCKED,
                    f"could not fetch {REMOTE}: {detail}. Preparation will not trust "
                    "a stale remote-tracking ref.",
                ),
            )

    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    decisions = [
        worktree_decision(tuple(line for line in status.stdout.splitlines() if line))
    ]

    tracked, ahead, behind = preflight.main_divergence(root)
    decisions.append(baseline_decision(tracked, ahead, behind))

    workbench_exists = preflight.local_branch_exists(root, WORKBENCH_BRANCH)
    decisions.append(
        workbench_decision(
            workbench_exists, preflight.workbench_commits_behind_main(root)
        )
    )

    # Evidence is only meaningful once the workbench holds all of main, and
    # only costs anything when there is a workbench at all.
    if workbench_exists and not any(item.blocks for item in decisions):
        classified = evidence.audit(root, preflight.is_governed_delivery_branch)
        outstanding = evidence.unresolved(classified)
        decisions.append(
            evidence_decision(
                len(outstanding),
                "\n".join(
                    f"    {item.commit.sha[:7]} {item.commit.subject} "
                    f"[{item.commit.evidence_id[:12]}]"
                    for item in outstanding
                ),
            )
        )

    return tuple(decisions)


def execute(root: Path, branch: str, decisions: Sequence[Decision]) -> tuple[str, str]:
    """Apply the authorized mutations and create the branch. Returns (branch, base).

    Restores the original checkout on any failure, so a stopped preparation
    leaves the repository where it started rather than parked mid-operation.
    """
    started_on = current_branch(root)
    try:
        for decision in decisions:
            if decision.action == FAST_FORWARD:
                _git(root, "switch", INTEGRATION_BRANCH)
                merged = _git(
                    root, "merge", "--ff-only", f"{REMOTE}/{INTEGRATION_BRANCH}", check=False
                )
                if merged.returncode != 0:
                    raise PreparationError(
                        f"fast-forwarding {INTEGRATION_BRANCH} failed: "
                        + (merged.stderr.strip() or "unknown failure")
                    )
            elif decision.action == SYNC:
                _git(root, "switch", WORKBENCH_BRANCH)
                merged = _git(
                    root, "merge", "--no-edit", INTEGRATION_BRANCH, check=False
                )
                if merged.returncode != 0:
                    _git(root, "merge", "--abort", check=False)
                    raise PreparationError(
                        f"merging {INTEGRATION_BRANCH} into {WORKBENCH_BRANCH} "
                        "conflicts. The merge was aborted and nothing was changed. "
                        "Resolve it deliberately, then run this again."
                    )

        # Re-read the baseline immediately before use. Anything learned earlier
        # in this run is now old enough to be wrong.
        tracked, ahead, behind = _sibling("governed_task_preflight").main_divergence(root)
        revalidated = baseline_decision(tracked, ahead, behind)
        if revalidated.action != OK:
            raise PreparationError(
                f"the integration baseline changed during preparation: {revalidated.detail}"
            )

        base = resolve(root, INTEGRATION_BRANCH)
        created = _git(root, "switch", "-c", branch, base, check=False)
        if created.returncode != 0:
            raise PreparationError(
                f"could not create {branch}: "
                + (created.stderr.strip() or "unknown failure")
            )
        return branch, base
    except PreparationError:
        if started_on and current_branch(root) != started_on:
            _git(root, "switch", started_on, check=False)
        raise


def render_text(
    branch: str, decisions: Sequence[Decision], *, executed: bool, base: str | None
) -> str:
    lines = [f"Delivery branch preparation for {branch}", ""]
    for decision in decisions:
        marker = {OK: "ok", BLOCKED: "BLOCKED", FAST_FORWARD: "would fast-forward", SYNC: "would sync"}[
            decision.action
        ]
        if executed and decision.mutates:
            marker = "fast-forwarded" if decision.action == FAST_FORWARD else "synced"
        lines.append(f"  [{marker}] {decision.stage}: {decision.detail}")
    if blocking(decisions):
        lines.append("\nPreparation stopped. Nothing was changed.")
    elif executed:
        lines.append(f"\nCreated {branch} from verified {INTEGRATION_BRANCH} at {base}.")
    else:
        pending = [decision for decision in decisions if decision.mutates]
        lines.append(
            "\nRe-run with --execute to "
            + (
                "apply the changes above and create the branch."
                if pending
                else "create the branch."
            )
        )
    return "\n".join(lines)


def render_json(
    branch: str, decisions: Sequence[Decision], *, executed: bool, base: str | None
) -> str:
    return json.dumps(
        {
            "schemaVersion": 1,
            "branch": branch,
            "executed": executed,
            "base": base,
            "blocked": bool(blocking(decisions)),
            "stages": [
                {"stage": item.stage, "action": item.action, "detail": item.detail}
                for item in decisions
            ],
        },
        indent=2,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branch", help="<category>/<JIRA-ISSUE-KEY>-<outcome-slug>")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="authorize fast-forwarding main, syncing the workbench, and creating the branch",
    )
    parser.add_argument("--no-fetch", action="store_true", help="skip fetching the remote")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(list(argv) if argv is not None else None)

    error = validate_branch_name(args.branch)
    if error:
        print(error, file=sys.stderr)
        return 2

    try:
        root = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        print("not inside a Git working tree", file=sys.stderr)
        return 2

    if _sibling("governed_task_preflight").local_branch_exists(root, args.branch):
        print(f"{args.branch} already exists; reuse is not preparation", file=sys.stderr)
        return 2

    try:
        decisions = plan(root, fetch=not args.no_fetch)
    except PreparationError as error:  # noqa: F841 - reported below
        print(str(error), file=sys.stderr)
        return 2

    base: str | None = None
    executed = False
    if args.execute and not blocking(decisions):
        try:
            _, base = execute(root, args.branch, decisions)
            executed = True
        except PreparationError as failure:
            print(str(failure), file=sys.stderr)
            return 1

    render = render_json if args.format == "json" else render_text
    output = render(args.branch, decisions, executed=executed, base=base)
    if blocking(decisions):
        print(output, file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
