#!/usr/bin/env python3
"""Audit and optionally remove stale Jira-keyed local delivery branches."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


BRANCH_PATTERN = re.compile(r"^(?:agent/)?AEPI-\d+(?:-|$)")
LOCAL_COMMAND_TIMEOUT_SECONDS = 30.0
NETWORK_COMMAND_TIMEOUT_SECONDS = 120.0


class ReconciliationError(RuntimeError):
    """Raised when local delivery state cannot be reconciled safely."""


@dataclass(frozen=True)
class PullRequest:
    number: int
    state: str
    merged_at: str | None
    head_branch: str
    head_oid: str
    url: str


@dataclass(frozen=True)
class Candidate:
    branch: str
    head_oid: str
    classification: str
    reason: str
    pull_request: int | None = None


@dataclass(frozen=True)
class ReconciliationReport:
    base_ref: str
    candidates: tuple[Candidate, ...]

    @property
    def safe_to_delete(self) -> tuple[Candidate, ...]:
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.classification == "safe-to-delete"
        )


def run(
    command: Sequence[str],
    *,
    cwd: Path,
    check: bool = True,
    timeout: float = LOCAL_COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "GCM_INTERACTIVE": "Never",
            "GH_PROMPT_DISABLED": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=environment,
        )
    except FileNotFoundError as error:
        raise ReconciliationError(
            f"required executable is unavailable: {error.filename}"
        ) from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip() or str(error)
        raise ReconciliationError(
            f"command failed: {' '.join(command)}\n{detail}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise ReconciliationError(
            f"command timed out after {timeout:g} seconds: {' '.join(command)}"
        ) from error


def git(
    workspace: Path,
    *arguments: str,
    check: bool = True,
    timeout: float = LOCAL_COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    return run(
        ["git", *arguments],
        cwd=workspace,
        check=check,
        timeout=timeout,
    )


def resolve_primary_workspace(path: Path) -> Path:
    candidate = path.resolve()
    root = Path(
        git(candidate, "rev-parse", "--show-toplevel").stdout.strip()
    ).resolve()
    if root != candidate:
        raise ReconciliationError(
            f"primary workspace must name the repository root: {candidate} != {root}"
        )
    return root


def require_clean(workspace: Path) -> None:
    status = git(
        workspace,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    ).stdout
    if status.strip():
        raise ReconciliationError(
            "primary workspace is dirty and must be preserved:\n" + status.rstrip()
        )


def local_branches(workspace: Path) -> dict[str, str]:
    output = git(
        workspace,
        "for-each-ref",
        "--format=%(refname:short)%00%(objectname)",
        "refs/heads",
    ).stdout
    branches: dict[str, str] = {}
    for line in output.splitlines():
        branch, separator, oid = line.partition("\0")
        if separator and BRANCH_PATTERN.match(branch):
            branches[branch] = oid
    return branches


def checked_out_branches(workspace: Path) -> set[str]:
    output = git(workspace, "worktree", "list", "--porcelain").stdout
    prefix = "branch refs/heads/"
    return {
        line.removeprefix(prefix)
        for line in output.splitlines()
        if line.startswith(prefix)
    }


def remote_branches(workspace: Path) -> set[str]:
    result = git(
        workspace,
        "ls-remote",
        "--heads",
        "origin",
        timeout=NETWORK_COMMAND_TIMEOUT_SECONDS,
    )
    prefix = "refs/heads/"
    branches: set[str] = set()
    for line in result.stdout.splitlines():
        _, _, ref = line.partition("\t")
        if ref.startswith(prefix):
            branches.add(ref.removeprefix(prefix))
    return branches


def load_pull_requests(workspace: Path) -> tuple[PullRequest, ...]:
    result = run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "all",
            "--limit",
            "1000",
            "--json",
            "number,state,mergedAt,headRefName,headRefOid,url",
        ],
        cwd=workspace,
        timeout=NETWORK_COMMAND_TIMEOUT_SECONDS,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ReconciliationError(
            "GitHub returned invalid pull-request data"
        ) from error
    if not isinstance(data, list):
        raise ReconciliationError("GitHub returned non-list pull-request data")
    return tuple(
        PullRequest(
            number=int(item["number"]),
            state=str(item["state"]).upper(),
            merged_at=(
                str(item["mergedAt"]) if item.get("mergedAt") is not None else None
            ),
            head_branch=str(item["headRefName"]),
            head_oid=str(item["headRefOid"]),
            url=str(item["url"]),
        )
        for item in data
    )


def is_ancestor(workspace: Path, ancestor: str, descendant: str) -> bool:
    result = git(
        workspace,
        "merge-base",
        "--is-ancestor",
        ancestor,
        descendant,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise ReconciliationError(
            f"could not compare ancestry: {ancestor} -> {descendant}"
        )
    return result.returncode == 0


def classify_branch(
    workspace: Path,
    *,
    branch: str,
    head_oid: str,
    base_ref: str,
    worktree_branches: set[str],
    live_remote_branches: set[str],
    pull_requests: Sequence[PullRequest],
) -> Candidate:
    if branch in worktree_branches:
        return Candidate(branch, head_oid, "preserve", "branch is checked out")
    if branch in live_remote_branches:
        return Candidate(branch, head_oid, "preserve", "remote branch still exists")
    if not is_ancestor(workspace, head_oid, base_ref):
        return Candidate(
            branch,
            head_oid,
            "preserve",
            f"branch contains commits not reachable from {base_ref}",
        )

    matches = tuple(
        pull_request
        for pull_request in pull_requests
        if pull_request.head_branch == branch
    )
    if not matches:
        return Candidate(
            branch,
            head_oid,
            "manual-review",
            "no associated pull request was found",
        )

    exact_matches = tuple(
        pull_request
        for pull_request in matches
        if pull_request.head_oid == head_oid
    )
    if not exact_matches:
        return Candidate(
            branch,
            head_oid,
            "manual-review",
            "local branch tip does not match an associated pull request",
        )

    merged = tuple(
        pull_request
        for pull_request in exact_matches
        if pull_request.state == "MERGED" and pull_request.merged_at
    )
    if not merged:
        pull_request = exact_matches[0]
        return Candidate(
            branch,
            head_oid,
            "preserve",
            f"pull request #{pull_request.number} is not merged",
            pull_request.number,
        )

    pull_request = max(merged, key=lambda item: item.number)
    return Candidate(
        branch,
        head_oid,
        "safe-to-delete",
        f"merged PR #{pull_request.number}; remote absent; tip reachable from {base_ref}",
        pull_request.number,
    )


def build_report(
    workspace: Path,
    *,
    base_ref: str = "origin/main",
    live_remote_branches: set[str] | None = None,
    pull_requests: Sequence[PullRequest] | None = None,
) -> ReconciliationReport:
    base_check = git(
        workspace,
        "show-ref",
        "--verify",
        "--quiet",
        f"refs/remotes/{base_ref}",
        check=False,
    )
    if base_check.returncode not in (0, 1):
        raise ReconciliationError(f"could not inspect integration base {base_ref}")
    if base_check.returncode == 1:
        raise ReconciliationError(f"integration base is unavailable: {base_ref}")

    remotes = (
        remote_branches(workspace)
        if live_remote_branches is None
        else live_remote_branches
    )
    prs = load_pull_requests(workspace) if pull_requests is None else pull_requests
    worktrees = checked_out_branches(workspace)
    candidates = tuple(
        classify_branch(
            workspace,
            branch=branch,
            head_oid=head_oid,
            base_ref=base_ref,
            worktree_branches=worktrees,
            live_remote_branches=remotes,
            pull_requests=prs,
        )
        for branch, head_oid in sorted(local_branches(workspace).items())
    )
    return ReconciliationReport(base_ref=base_ref, candidates=candidates)


def execute_reconciliation(
    workspace: Path,
    report: ReconciliationReport,
) -> None:
    require_clean(workspace)
    for candidate in report.safe_to_delete:
        git(workspace, "branch", "-d", "--", candidate.branch)
    git(workspace, "worktree", "prune")
    remaining = local_branches(workspace)
    undeleted = tuple(
        candidate.branch
        for candidate in report.safe_to_delete
        if candidate.branch in remaining
    )
    if undeleted:
        raise ReconciliationError(
            "cleanup verification failed; local branches remain: "
            + ", ".join(undeleted)
        )


def report_as_json(report: ReconciliationReport, *, executed: bool) -> str:
    return json.dumps(
        {
            "baseRef": report.base_ref,
            "executed": executed,
            "candidates": [asdict(candidate) for candidate in report.candidates],
        },
        indent=2,
        sort_keys=True,
    )


def render_report(report: ReconciliationReport, *, executed: bool) -> str:
    mode = "executed" if executed else "verified dry run"
    lines = [f"Local delivery reconciliation {mode} against {report.base_ref}."]
    if not report.candidates:
        lines.append("  No Jira-keyed local branches found.")
    for classification in ("safe-to-delete", "manual-review", "preserve"):
        matching = tuple(
            candidate
            for candidate in report.candidates
            if candidate.classification == classification
        )
        if not matching:
            continue
        lines.append(f"  {classification}:")
        lines.extend(
            f"    {candidate.branch}: {candidate.reason}" for candidate in matching
        )
    return "\n".join(lines)


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit and optionally remove stale Jira-keyed local branches."
    )
    parser.add_argument(
        "--primary-workspace",
        type=Path,
        required=True,
        help="Developer-visible repository root",
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Updated integration ref used for reachability checks",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Delete the verified safe candidates; otherwise report only",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Do not fetch or prune before inspection (for read-only preflight use)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    args = parse_args(arguments)
    try:
        workspace = resolve_primary_workspace(args.primary_workspace)
        if not args.no_fetch:
            git(
                workspace,
                "fetch",
                "--prune",
                "origin",
                timeout=NETWORK_COMMAND_TIMEOUT_SECONDS,
            )
        report = build_report(workspace, base_ref=args.base_ref)
        if args.execute:
            execute_reconciliation(workspace, report)
        if args.format == "json":
            print(report_as_json(report, executed=args.execute))
        else:
            print(render_report(report, executed=args.execute))
            if not args.execute and report.safe_to_delete:
                print("Run again with --execute only after global cleanup is authorized.")
        return 0
    except ReconciliationError as error:
        print(f"Local delivery reconciliation blocked: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
