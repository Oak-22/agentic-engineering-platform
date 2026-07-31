#!/usr/bin/env python3
"""Block new governed task isolation when the prior delivery is unfinished."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    head_ref_name: str
    url: str


@dataclass(frozen=True)
class RepositoryState:
    dirty_entries: tuple[str, ...]
    open_governed_pull_requests: tuple[PullRequest, ...]
    current_branch: str
    current_pull_request_state: str | None
    current_remote_branch_exists: bool


class InspectionError(RuntimeError):
    """Raised when the preflight cannot establish repository delivery state."""


def run(
    command: Sequence[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def repository_root(cwd: Path) -> Path:
    try:
        result = run(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    except (OSError, subprocess.CalledProcessError) as error:
        raise InspectionError("not inside a Git working tree") from error
    return Path(result.stdout.strip())


def inspect_repository(root: Path) -> RepositoryState:
    try:
        status = run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=root)
        branch = run(["git", "branch", "--show-current"], cwd=root).stdout.strip()
        open_prs_result = run(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "open",
                "--limit",
                "100",
                "--json",
                "number,title,headRefName,url",
            ],
            cwd=root,
        )
    except FileNotFoundError as error:
        raise InspectionError(f"required executable is unavailable: {error.filename}") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip() or str(error)
        raise InspectionError(f"repository inspection failed: {detail}") from error

    try:
        open_pr_data = json.loads(open_prs_result.stdout)
    except json.JSONDecodeError as error:
        raise InspectionError("GitHub returned invalid pull-request data") from error

    open_governed_pull_requests = tuple(
        PullRequest(
            number=int(item["number"]),
            title=str(item["title"]),
            head_ref_name=str(item["headRefName"]),
            url=str(item["url"]),
        )
        for item in open_pr_data
        if str(item.get("headRefName", "")).startswith("agent/")
    )

    current_pull_request_state: str | None = None
    current_remote_branch_exists = False
    if branch.startswith("agent/"):
        pr_result = run(
            [
                "gh",
                "pr",
                "list",
                "--head",
                branch,
                "--state",
                "all",
                "--limit",
                "1",
                "--json",
                "state",
            ],
            cwd=root,
        )
        try:
            current_pr_data = json.loads(pr_result.stdout)
        except json.JSONDecodeError as error:
            raise InspectionError("GitHub returned invalid current-branch data") from error
        if current_pr_data:
            current_pull_request_state = str(current_pr_data[0]["state"]).upper()

        remote_result = run(
            ["git", "ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{branch}"],
            cwd=root,
            check=False,
        )
        if remote_result.returncode not in (0, 2):
            detail = remote_result.stderr.strip() or "unknown remote inspection failure"
            raise InspectionError(f"could not inspect the current remote branch: {detail}")
        current_remote_branch_exists = remote_result.returncode == 0

    return RepositoryState(
        dirty_entries=tuple(line for line in status.stdout.splitlines() if line),
        open_governed_pull_requests=open_governed_pull_requests,
        current_branch=branch,
        current_pull_request_state=current_pull_request_state,
        current_remote_branch_exists=current_remote_branch_exists,
    )


def blockers_for(state: RepositoryState) -> list[str]:
    blockers: list[str] = []

    if state.dirty_entries:
        blockers.append(
            "Can't implement the next task: the working tree has uncommitted changes. "
            "Commit the current delivery, or intentionally stash or resolve its changes, "
            "before creating another branch or worktree.\n"
            + "\n".join(f"  {entry}" for entry in state.dirty_entries)
        )

    if state.open_governed_pull_requests:
        blockers.append(
            "Can't implement the next task. Review and merge the outstanding pull "
            "request, then complete branch cleanup.\n"
            + "\n".join(
                f"  #{pull_request.number} {pull_request.title} "
                f"({pull_request.head_ref_name}) {pull_request.url}"
                for pull_request in state.open_governed_pull_requests
            )
        )

    if (
        state.current_branch.startswith("agent/")
        and state.current_pull_request_state == "MERGED"
        and state.current_remote_branch_exists
    ):
        blockers.append(
            "Can't implement the next task: the current pull request is merged, but "
            f"remote branch origin/{state.current_branch} still exists. Complete the "
            "authorized remote branch cleanup first."
        )

    if (
        state.current_branch.startswith("agent/")
        and state.current_pull_request_state is None
        and state.current_remote_branch_exists
    ):
        blockers.append(
            "Can't implement the next task: the current published feature branch has "
            "no pull request. Publish or intentionally resolve the current delivery "
            "before creating another branch or worktree."
        )

    return blockers


def main() -> int:
    try:
        root = repository_root(Path.cwd())
        state = inspect_repository(root)
    except InspectionError as error:
        print(f"Can't verify whether the next governed task is safe: {error}", file=sys.stderr)
        return 2

    blockers = blockers_for(state)
    if blockers:
        print("\n\n".join(blockers), file=sys.stderr)
        return 1

    print(
        "Governed task preflight passed: the working tree is clean and no "
        "outstanding agent pull request blocks task isolation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
