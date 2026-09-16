#!/usr/bin/env python3
"""Verify and clean targeted or stale local Git delivery state."""

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


WORKBENCH_BRANCH = "workbench/local"
JIRA_ISSUE_KEY_PATTERN = r"[A-Z][A-Z0-9_]*-[1-9][0-9]*"
BRANCH_PATTERN = re.compile(
    rf"^(?:(?:feature|fix|bugfix|hotfix|refactor|chore|docs|release)/"
    rf"{JIRA_ISSUE_KEY_PATTERN}|agent/{JIRA_ISSUE_KEY_PATTERN}|"
    rf"{JIRA_ISSUE_KEY_PATTERN})(?:-|$)"
)
LOCAL_COMMAND_TIMEOUT_SECONDS = 30.0
NETWORK_COMMAND_TIMEOUT_SECONDS = 120.0


class CleanupError(RuntimeError):
    """Raised when cleanup cannot be proven safe."""


@dataclass(frozen=True)
class PullRequest:
    number: int
    state: str
    merged_at: str | None
    merge_oid: str | None
    base_branch: str
    head_branch: str
    head_oid: str
    url: str
    # Paths the pull request changed, as GitHub reports them; None when the
    # data did not carry them (hermetic tests, older callers).
    changed_files: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Worktree:
    path: Path
    head_oid: str
    branch: str | None


BASE_ALREADY_CURRENT = "already-current"
BASE_REF_UPDATE = "ref-update"
BASE_FAST_FORWARD_IN_PLACE = "fast-forward-in-place"


@dataclass(frozen=True)
class CleanupPlan:
    primary_workspace: Path
    pull_request: PullRequest
    target_worktree: Worktree | None
    initial_primary_branch: str
    return_branch: str
    head_contained_in_base: bool
    remote_branch_exists: bool
    workbench_sync_needed: bool
    base_advance: str
    base_oid_at_plan: str
    switch_required: bool
    primary_conflicts: tuple[str, ...]
    # Paths the merged pull request changed: the proof that main is authoritative
    # for them when the workbench sync conflicts.
    delivered_paths: frozenset[str] = frozenset()
    # The PR's own commits plus its fork point; the versions of a delivered
    # path that the workbench may hold and still be safely superseded.
    pull_request_commits: tuple[str, ...] = ()
    # Predicted workbench-sync conflicts, split by whether the cleanup may resolve
    # them (delivered) or must stop (undelivered workbench work).
    resolvable_conflicts: tuple[str, ...] = ()
    blocking_conflicts: tuple[str, ...] = ()


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
        raise CleanupError(f"required executable is unavailable: {error.filename}") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip() or str(error)
        raise CleanupError(f"command failed: {' '.join(command)}\n{detail}") from error
    except subprocess.TimeoutExpired as error:
        raise CleanupError(
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
    result = git(candidate, "rev-parse", "--show-toplevel")
    root = Path(result.stdout.strip()).resolve()
    if root != candidate:
        raise CleanupError(
            f"primary workspace must name the repository root: {candidate} != {root}"
        )
    return root


def pull_request_from_data(
    data: object,
    *,
    expected_number: int | None = None,
) -> PullRequest:
    if not isinstance(data, dict):
        raise CleanupError("GitHub returned a non-object pull-request response")

    def required_string(field: str) -> str:
        value = data.get(field)
        if not isinstance(value, str) or not value:
            raise CleanupError(
                f"GitHub pull-request data has invalid or missing {field}"
            )
        return value

    returned_number = data.get("number")
    if not isinstance(returned_number, int) or isinstance(returned_number, bool):
        raise CleanupError("GitHub pull-request data has invalid or missing number")
    if expected_number is not None and returned_number != expected_number:
        raise CleanupError(
            f"GitHub returned pull request #{returned_number} for requested "
            f"#{expected_number}"
        )

    merged_at = data.get("mergedAt")
    if merged_at is not None and not isinstance(merged_at, str):
        raise CleanupError("GitHub pull-request data has invalid mergedAt")

    merge_commit = data.get("mergeCommit")
    if merge_commit is None:
        merge_oid = None
    elif isinstance(merge_commit, dict):
        merge_oid_value = merge_commit.get("oid")
        if not isinstance(merge_oid_value, str) or not merge_oid_value:
            raise CleanupError("GitHub pull-request data has invalid mergeCommit.oid")
        merge_oid = merge_oid_value
    else:
        raise CleanupError("GitHub pull-request data has invalid mergeCommit")

    files = data.get("files")
    changed_files: tuple[str, ...] | None
    if files is None:
        changed_files = None
    elif isinstance(files, list) and all(
        isinstance(item, dict) and isinstance(item.get("path"), str) and item["path"]
        for item in files
    ):
        changed_files = tuple(item["path"] for item in files)
    else:
        raise CleanupError("GitHub pull-request data has invalid files")

    return PullRequest(
        number=returned_number,
        state=required_string("state").upper(),
        merged_at=merged_at,
        merge_oid=merge_oid,
        base_branch=required_string("baseRefName"),
        head_branch=required_string("headRefName"),
        head_oid=required_string("headRefOid"),
        url=required_string("url"),
        changed_files=changed_files,
    )


def load_pull_request(workspace: Path, number: int) -> PullRequest:
    result = run(
        [
            "gh",
            "pr",
            "view",
            str(number),
            "--json",
            "number,state,mergedAt,mergeCommit,baseRefName,headRefName,headRefOid,url,files",
        ],
        cwd=workspace,
        timeout=NETWORK_COMMAND_TIMEOUT_SECONDS,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise CleanupError("GitHub returned invalid pull-request data") from error
    return pull_request_from_data(data, expected_number=number)


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
            "number,state,mergedAt,mergeCommit,baseRefName,headRefName,headRefOid,url",
        ],
        cwd=workspace,
        timeout=NETWORK_COMMAND_TIMEOUT_SECONDS,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise CleanupError("GitHub returned invalid pull-request data") from error
    if not isinstance(data, list):
        raise CleanupError("GitHub returned non-list pull-request data")
    return tuple(pull_request_from_data(item) for item in data)


def parse_worktrees(output: str) -> tuple[Worktree, ...]:
    records: list[Worktree] = []
    fields: dict[str, str] = {}

    def append_record() -> None:
        if not fields:
            return
        branch_ref = fields.get("branch")
        branch = None
        if branch_ref:
            prefix = "refs/heads/"
            if not branch_ref.startswith(prefix):
                raise CleanupError(f"unexpected worktree branch ref: {branch_ref}")
            branch = branch_ref.removeprefix(prefix)
        records.append(
            Worktree(
                path=Path(fields["worktree"]).resolve(),
                head_oid=fields["HEAD"],
                branch=branch,
            )
        )

    for line in output.splitlines():
        if not line:
            append_record()
            fields = {}
            continue
        key, _, value = line.partition(" ")
        if key in {"worktree", "HEAD", "branch"}:
            fields[key] = value
    append_record()
    return tuple(records)


def inspect_worktrees(workspace: Path) -> tuple[Worktree, ...]:
    return parse_worktrees(git(workspace, "worktree", "list", "--porcelain").stdout)


def branch_exists(workspace: Path, branch: str) -> bool:
    result = git(
        workspace,
        "show-ref",
        "--verify",
        "--quiet",
        f"refs/heads/{branch}",
        check=False,
    )
    if result.returncode not in (0, 1):
        raise CleanupError(f"could not inspect local branch {branch}")
    return result.returncode == 0


def current_branch(workspace: Path) -> str:
    branch = git(workspace, "branch", "--show-current").stdout.strip()
    if not branch:
        raise CleanupError(f"detached HEAD is not supported in {workspace}")
    return branch


def status_entries(workspace: Path) -> tuple[str, ...]:
    """Every uncommitted entry as ``"XY path"``, parsed from ``-z`` output.

    The human-readable status form quotes and escapes unusual paths, so a
    gate built on it can name a file that does not exist. The NUL-separated
    form keeps each path exactly as Git holds it.
    """
    fields = git(
        workspace,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    ).stdout.split("\0")
    entries: list[str] = []
    index = 0
    while index < len(fields):
        field = fields[index]
        index += 1
        if not field:
            continue
        code, path = field[:2], field[3:]
        # A rename or copy carries its origin path in the following field.
        if "R" in code or "C" in code:
            index += 1
        entries.append(f"{code} {path}")
    return tuple(entries)


def entry_path(entry: str) -> str:
    return entry[3:]


def paths_written_between(workspace: Path, left: str, right: str) -> frozenset[str]:
    """Working-tree paths that moving from `left` to `right` would write."""
    result = git(workspace, "diff", "--name-only", "-z", left, right, check=False)
    if result.returncode != 0:
        raise CleanupError(f"could not compare {left} with {right} in {workspace}")
    return frozenset(path for path in result.stdout.split("\0") if path)


def obstructing_entries(
    workspace: Path, at_risk_paths: frozenset[str]
) -> tuple[str, ...]:
    """Uncommitted entries sitting on a path this cleanup would write.

    Git rewrites only the paths that differ across a switch or a merge; it
    preserves every other file and refuses only when an incoming tracked file
    would land on an untracked one. Refusing on the presence of any loose
    file blocks far more than that hazard, and the workbench pattern expects
    loose capture notes in the primary checkout as its steady state.
    """
    return tuple(
        entry
        for entry in status_entries(workspace)
        if entry_path(entry) in at_risk_paths
    )


def require_clean(workspace: Path, role: str) -> None:
    """Refuse any uncommitted content at all.

    Reserved for a checkout about to be removed, where the whole directory
    goes and an untracked file in it would be destroyed rather than
    preserved. Every other gate here is scoped to the paths at risk.
    """
    status = git(
        workspace,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    ).stdout
    if status.strip():
        raise CleanupError(f"{role} is dirty and must be preserved:\n{status.rstrip()}")


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
        raise CleanupError(
            f"could not compare ancestry: {ancestor} -> {descendant}"
        )
    return result.returncode == 0


def refresh_remote(workspace: Path) -> None:
    git(
        workspace,
        "fetch",
        "--prune",
        "origin",
        timeout=NETWORK_COMMAND_TIMEOUT_SECONDS,
    )


def local_delivery_branches(workspace: Path) -> dict[str, str]:
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


def live_remote_branches(workspace: Path) -> set[str]:
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


def classify_branch(
    workspace: Path,
    *,
    branch: str,
    head_oid: str,
    base_ref: str,
    worktree_branches: set[str],
    remote_branches: set[str],
    pull_requests: Sequence[PullRequest],
) -> Candidate:
    if branch in worktree_branches:
        return Candidate(branch, head_oid, "preserve", "branch is checked out")
    if branch in remote_branches:
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
        f"merged PR #{pull_request.number}; remote absent; tip reachable from "
        f"{base_ref}",
        pull_request.number,
    )


def build_reconciliation_report(
    workspace: Path,
    *,
    base_ref: str = "origin/main",
    remote_branches: set[str] | None = None,
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
        raise CleanupError(f"could not inspect integration base {base_ref}")
    if base_check.returncode == 1:
        raise CleanupError(f"integration base is unavailable: {base_ref}")

    remotes = (
        live_remote_branches(workspace)
        if remote_branches is None
        else remote_branches
    )
    prs = load_pull_requests(workspace) if pull_requests is None else pull_requests
    worktree_branches = {
        worktree.branch
        for worktree in inspect_worktrees(workspace)
        if worktree.branch is not None
    }
    candidates = tuple(
        classify_branch(
            workspace,
            branch=branch,
            head_oid=head_oid,
            base_ref=base_ref,
            worktree_branches=worktree_branches,
            remote_branches=remotes,
            pull_requests=prs,
        )
        for branch, head_oid in sorted(local_delivery_branches(workspace).items())
    )
    return ReconciliationReport(base_ref=base_ref, candidates=candidates)


def execute_reconciliation(
    workspace: Path,
    report: ReconciliationReport,
) -> None:
    """Delete the verified safe candidates and prune stale worktree metadata.

    There is no working-tree gate here because there is no working-tree
    write: deleting a ref and pruning metadata touch no file in the checkout,
    so loose files in it are never at risk.

    `git branch -d` is not usable: it re-checks containment against `HEAD` and
    would call a delivery merged into `main` unmerged whenever the checkout
    sits on the workbench. Forcing the delete therefore gives up Git's own
    safety net, so every candidate is re-verified here — tip unchanged since
    it was classified, and still contained in the base — before any branch is
    deleted. Verifying the whole set first keeps a moved ref from leaving a
    half-finished reconciliation behind.
    """
    deletable = report.safe_to_delete
    for candidate in deletable:
        tip = git(
            workspace, "rev-parse", "--verify", f"refs/heads/{candidate.branch}"
        ).stdout.strip()
        if tip != candidate.head_oid:
            raise CleanupError(
                f"{candidate.branch} moved since it was classified "
                f"({candidate.head_oid} to {tip}); nothing was deleted"
            )
        if not is_ancestor(workspace, tip, report.base_ref):
            raise CleanupError(
                f"{candidate.branch} is no longer contained in {report.base_ref}; "
                "nothing was deleted"
            )
    for candidate in deletable:
        git(workspace, "branch", "-D", "--", candidate.branch)
    git(workspace, "worktree", "prune")
    remaining = local_delivery_branches(workspace)
    undeleted = tuple(
        candidate.branch
        for candidate in report.safe_to_delete
        if candidate.branch in remaining
    )
    if undeleted:
        raise CleanupError(
            "cleanup verification failed; local branches remain: "
            + ", ".join(undeleted)
        )


def reconciliation_as_json(
    report: ReconciliationReport,
    *,
    executed: bool,
) -> str:
    return json.dumps(
        {
            "baseRef": report.base_ref,
            "executed": executed,
            "candidates": [asdict(candidate) for candidate in report.candidates],
        },
        indent=2,
        sort_keys=True,
    )


def render_reconciliation(
    report: ReconciliationReport,
    *,
    executed: bool,
) -> str:
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


def build_cleanup_plan(
    primary_workspace: Path,
    pull_request: PullRequest,
    *,
    remote_branches: set[str] | None = None,
) -> CleanupPlan:
    primary = resolve_primary_workspace(primary_workspace)
    if pull_request.state != "MERGED" or not pull_request.merged_at:
        raise CleanupError(f"pull request #{pull_request.number} is not merged")
    if not pull_request.merge_oid:
        raise CleanupError(f"pull request #{pull_request.number} has no merge result")

    for role, branch in (
        ("base", pull_request.base_branch),
        ("head", pull_request.head_branch),
    ):
        valid_ref = git(
            primary,
            "check-ref-format",
            f"refs/heads/{branch}",
            check=False,
        )
        if valid_ref.returncode != 0:
            raise CleanupError(f"pull request has invalid {role} branch: {branch}")

    remote_base = f"refs/remotes/origin/{pull_request.base_branch}"
    remote_base_result = git(
        primary,
        "show-ref",
        "--verify",
        "--quiet",
        remote_base,
        check=False,
    )
    if remote_base_result.returncode not in (0, 1):
        raise CleanupError(
            f"could not inspect remote base origin/{pull_request.base_branch}"
        )
    if remote_base_result.returncode == 1:
        raise CleanupError(f"remote base is unavailable: origin/{pull_request.base_branch}")
    if not branch_exists(primary, pull_request.base_branch):
        raise CleanupError(f"local base is unavailable: {pull_request.base_branch}")
    if not is_ancestor(primary, pull_request.merge_oid, remote_base):
        raise CleanupError(
            f"merge result {pull_request.merge_oid} is not reachable from "
            f"origin/{pull_request.base_branch}"
        )

    if not branch_exists(primary, pull_request.head_branch):
        raise CleanupError(
            f"local branch is already absent: {pull_request.head_branch}"
        )
    local_head = git(
        primary,
        "rev-parse",
        "--verify",
        f"refs/heads/{pull_request.head_branch}",
    ).stdout.strip()
    if local_head != pull_request.head_oid:
        raise CleanupError(
            f"local branch tip {local_head} does not match published head "
            f"{pull_request.head_oid}"
        )

    worktrees = inspect_worktrees(primary)
    primary_records = tuple(item for item in worktrees if item.path == primary)
    if len(primary_records) != 1:
        raise CleanupError(f"primary workspace is not uniquely registered: {primary}")
    target_records = tuple(
        item for item in worktrees if item.branch == pull_request.head_branch
    )
    if len(target_records) > 1:
        raise CleanupError(
            f"feature branch has multiple worktrees: {pull_request.head_branch}"
        )
    target_worktree = target_records[0] if target_records else None
    if target_worktree:
        if target_worktree.head_oid != pull_request.head_oid:
            raise CleanupError(
                f"target worktree HEAD {target_worktree.head_oid} does not match "
                f"published head {pull_request.head_oid}"
            )
        require_clean(target_worktree.path, "delivery checkout")

    initial_primary_branch = current_branch(primary)
    allowed_primary_branches = {
        pull_request.base_branch,
        pull_request.head_branch,
        WORKBENCH_BRANCH,
    }
    if initial_primary_branch not in allowed_primary_branches:
        raise CleanupError(
            f"primary workspace is on unrelated branch {initial_primary_branch}"
        )

    base_records = tuple(
        item for item in worktrees if item.branch == pull_request.base_branch
    )
    if base_records and base_records[0].path != primary:
        raise CleanupError(
            f"base branch {pull_request.base_branch} is checked out outside the "
            f"primary workspace: {base_records[0].path}"
        )

    return_branch = pull_request.base_branch
    if branch_exists(primary, WORKBENCH_BRANCH):
        workbench_records = tuple(
            item for item in worktrees if item.branch == WORKBENCH_BRANCH
        )
        if not workbench_records or workbench_records[0].path == primary:
            return_branch = WORKBENCH_BRANCH

    workbench_sync_needed = (
        return_branch == WORKBENCH_BRANCH
        and return_branch != pull_request.base_branch
        and not is_ancestor(primary, remote_base, WORKBENCH_BRANCH)
    )

    head_contained_in_base = is_ancestor(primary, pull_request.head_oid, remote_base)

    local_base_oid = git(
        primary, "rev-parse", "--verify", f"refs/heads/{pull_request.base_branch}"
    ).stdout.strip()
    remote_base_oid = git(primary, "rev-parse", remote_base).stdout.strip()
    if local_base_oid == remote_base_oid:
        base_advance = BASE_ALREADY_CURRENT
    elif not is_ancestor(primary, local_base_oid, remote_base):
        raise CleanupError(
            f"local {pull_request.base_branch} is not an ancestor of "
            f"origin/{pull_request.base_branch}, so it cannot be advanced without "
            "rewriting history. Reconcile the two deliberately."
        )
    elif initial_primary_branch == pull_request.base_branch:
        base_advance = BASE_FAST_FORWARD_IN_PLACE
    else:
        base_advance = BASE_REF_UPDATE

    # The primary keeps its visible branch unless the cleanup genuinely needs
    # it moved: off a branch that is about to be deleted, or onto the
    # workbench so its sync merge has somewhere to happen.
    switch_required = initial_primary_branch == pull_request.head_branch or (
        workbench_sync_needed and initial_primary_branch != return_branch
    )

    at_risk: frozenset[str] = frozenset()
    if base_advance == BASE_FAST_FORWARD_IN_PLACE:
        at_risk |= paths_written_between(
            primary, pull_request.base_branch, remote_base
        )
    if switch_required:
        landing = (
            remote_base if return_branch == pull_request.base_branch else return_branch
        )
        at_risk |= paths_written_between(primary, "HEAD", landing)
    delivered: frozenset[str] = frozenset()
    commits: tuple[str, ...] = ()
    resolvable: tuple[str, ...] = ()
    blocking: tuple[str, ...] = ()
    if workbench_sync_needed:
        at_risk |= paths_written_between(primary, WORKBENCH_BRANCH, remote_base)
        delivered = delivered_paths(primary, pull_request)
        commits = pull_request_commits(primary, pull_request.merge_oid)
        predicted = predict_sync_conflicts(
            primary, workbench_branch=WORKBENCH_BRANCH, base_branch=remote_base
        )
        candidates = [path for path in predicted if path in delivered]
        carried = carried_entries_by_path(primary, commits, candidates)
        workbench_entries = entries_at(primary, WORKBENCH_BRANCH, candidates)
        resolvable = tuple(
            path
            for path in candidates
            if workbench_version_was_delivered(
                carried=carried[path], workbench_entry=workbench_entries.get(path)
            )
        )
        blocking = tuple(path for path in predicted if path not in resolvable)

    remotes = (
        live_remote_branches(primary)
        if remote_branches is None
        else remote_branches
    )
    return CleanupPlan(
        primary_workspace=primary,
        pull_request=pull_request,
        target_worktree=target_worktree,
        initial_primary_branch=initial_primary_branch,
        return_branch=return_branch,
        head_contained_in_base=head_contained_in_base,
        remote_branch_exists=pull_request.head_branch in remotes,
        workbench_sync_needed=workbench_sync_needed,
        base_advance=base_advance,
        base_oid_at_plan=local_base_oid,
        switch_required=switch_required,
        primary_conflicts=obstructing_entries(primary, at_risk),
        delivered_paths=delivered,
        pull_request_commits=commits,
        resolvable_conflicts=resolvable,
        blocking_conflicts=blocking,
    )


SYNC_CONFLICT = "conflict-manual-resolution-required"
SYNC_MERGED_RESOLVED = "merged-with-delivered-paths-from-base"
SYNC_MERGE_FAILED = "merge-failed-manual-resolution-required"
SYNC_INDEX_DIRTY = "workbench-index-not-clean"


def _nul_separated(output: str) -> tuple[str, ...]:
    return tuple(item for item in output.split("\0") if item)


def _literal(path: str) -> str:
    """A pathspec that names exactly this file.

    Git treats a bare path as a pattern: ``*``, ``?``, ``[`` and a leading
    ``:`` all have meaning, so a conflict proved for one file could otherwise
    be resolved on several. The literal magic disables all of that.
    """
    return f":(literal){path}"


def merge_commit_paths(workspace: Path, merge_oid: str | None) -> frozenset[str]:
    """First-parent diff of a two-parent merge commit, both sides of renames.

    Complete only for a true merge commit: a rebase-and-merge replays several
    commits and the tip's parent is the previous replayed commit, not the
    base, so anything with one parent yields nothing. ``--no-renames`` lists a
    rename's source and destination separately, which is what a merge
    conflict reports.
    """
    if merge_oid is None:
        return frozenset()
    parents = git(workspace, "rev-list", "--parents", "-n", "1", merge_oid, check=False)
    if parents.returncode != 0 or len(parents.stdout.split()) != 3:
        return frozenset()
    result = git(
        workspace,
        "diff",
        "--name-only",
        "--no-renames",
        "-z",
        f"{merge_oid}^1",
        merge_oid,
        check=False,
    )
    if result.returncode != 0:
        return frozenset()
    return frozenset(_nul_separated(result.stdout))


def pull_request_commits(workspace: Path, merge_oid: str | None) -> tuple[str, ...]:
    """Commits the pull request carried, plus its fork point from the base.

    Only a two-parent merge keeps them reachable; a squash or rebase merge
    yields nothing, so provenance cannot be established and every delivered
    path fails closed.
    """
    if merge_oid is None:
        return ()
    parents = git(workspace, "rev-list", "--parents", "-n", "1", merge_oid, check=False)
    if parents.returncode != 0 or len(parents.stdout.split()) != 3:
        return ()
    first, second = f"{merge_oid}^1", f"{merge_oid}^2"
    listed = git(workspace, "rev-list", second, f"^{first}", check=False)
    # --all: a criss-cross history has several merge bases, and the version
    # of a path at any of them is one the branch legitimately started from.
    forks = git(workspace, "merge-base", "--all", first, second, check=False)
    if listed.returncode != 0 or forks.returncode != 0:
        return ()
    return tuple(listed.stdout.split()) + tuple(forks.stdout.split())


# A tree entry is identified by mode and object id together: the same blob
# under a different mode (chmod, regular file <-> symlink) is a different
# version, and Git reports a conflict for that change too.
TreeEntry = tuple[str, str]
TREE_MODE = "040000"
OBJECT_ID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def entry_at(workspace: Path, revision: str, path: str) -> TreeEntry | None:
    """(mode, oid) of path at revision, or None when the tree lacks it.

    ``ls-tree`` distinguishes the two outcomes this code depends on: exit 0
    with an entry means present, exit 0 with no output means absent, and any
    other exit is a lookup failure that must not be mistaken for absence.
    """
    result = git(workspace, "ls-tree", "-z", revision, "--", _literal(path), check=False)
    if result.returncode != 0:
        raise CleanupError(
            f"cannot read {path} at {revision}: "
            + (result.stderr.strip() or f"git ls-tree exited {result.returncode}")
        )
    entries = _nul_separated(result.stdout)
    if not entries:
        return None
    mode, _type, oid = entries[0].split("\t", 1)[0].split(" ", 2)
    return (mode, oid)


def stage_entry(workspace: Path, stage: int, path: str) -> TreeEntry | None:
    """(mode, oid) of path at the given index stage during a merge, or None."""
    result = git(workspace, "ls-files", "--stage", "-z", "--", _literal(path))
    for record in _nul_separated(result.stdout):
        mode, oid, found_stage = record.split("\t", 1)[0].split(" ", 2)
        if int(found_stage) == stage:
            return (mode, oid)
    return None


def entries_at(
    workspace: Path, revision: str, paths: Sequence[str]
) -> dict[str, TreeEntry]:
    """(mode, oid) for each of paths present at revision, in one lookup.

    Same exit-status contract as ``entry_at``; a path the tree lacks is simply
    absent from the result.
    """
    if not paths:
        return {}
    result = git(
        workspace,
        "ls-tree",
        "-z",
        revision,
        "--",
        *(_literal(path) for path in paths),
        check=False,
    )
    if result.returncode != 0:
        raise CleanupError(
            f"cannot read {len(paths)} path(s) at {revision}: "
            + (result.stderr.strip() or f"git ls-tree exited {result.returncode}")
        )
    found: dict[str, TreeEntry] = {}
    for record in _nul_separated(result.stdout):
        meta, _tab, path = record.partition("\t")
        mode, _type, oid = meta.split(" ", 2)
        found[path] = (mode, oid)
    return found


def carried_entries_by_path(
    workspace: Path, commits: Sequence[str], paths: Sequence[str]
) -> dict[str, frozenset[TreeEntry]]:
    """Every version of each path the pull request had at any of its commits.

    One ``ls-tree`` per commit covers every path, so the cost is the number
    of commits rather than commits times conflicts.
    """
    carried: dict[str, set[TreeEntry]] = {path: set() for path in paths}
    for commit in commits:
        for path, entry in entries_at(workspace, commit, paths).items():
            carried[path].add(entry)
    return {path: frozenset(entries) for path, entries in carried.items()}


def workbench_version_was_delivered(
    *, carried: frozenset[TreeEntry], workbench_entry: TreeEntry | None
) -> bool:
    """True only when the workbench's version of a path is one the PR carried.

    That is the provenance the resolution rests on: the workbench holds the
    draft that was transferred (or the fork-point version), so the base's
    reviewed copy supersedes it. Content or mode the PR never saw is later
    workbench work, and a workbench-side deletion is undelivered intent; all
    are False.
    """
    if workbench_entry is None:
        return False
    return workbench_entry in carried


def delivered_paths(workspace: Path, pull_request: PullRequest) -> frozenset[str]:
    """Paths the merged pull request changed.

    The union of two sources, each covering what the other cannot. GitHub's
    file list covers every merge method but names only a rename's
    destination; the merge commit's first-parent diff names both sides of a
    rename but is complete only for a two-parent merge. With neither — a
    squash or rebase merge whose data carried no file list — the set is empty
    and every conflict blocks, rather than risk resolving an undelivered path.
    """
    delivered: set[str] = set()
    if pull_request.changed_files is not None:
        delivered.update(pull_request.changed_files)
    delivered.update(merge_commit_paths(workspace, pull_request.merge_oid))
    return frozenset(delivered)


def predict_sync_conflicts(
    workspace: Path, *, workbench_branch: str, base_branch: str
) -> tuple[str, ...]:
    """Paths that merging base_branch into workbench_branch would conflict on.

    Uses ``git merge-tree --write-tree`` so the plan can say what the sync
    would do without touching the working tree. Exit 0 is a clean merge.
    Exit 1 is a conflicted one — but also what a bad ref returns — so a
    conflict prediction is accepted only when it begins with the written
    tree's id. Anything else means no prediction was made (a Git older than
    2.38, a bad ref) and is raised rather than reported as clean.
    """
    result = git(
        workspace,
        "merge-tree",
        "--write-tree",
        "--name-only",
        "--no-messages",
        "-z",
        workbench_branch,
        base_branch,
        check=False,
    )
    if result.returncode == 0:
        return ()
    # Output is the tree id, then one conflicted path per NUL-terminated entry.
    entries = _nul_separated(result.stdout)
    if result.returncode != 1 or not entries or not OBJECT_ID.fullmatch(entries[0]):
        raise CleanupError(
            f"cannot predict the {workbench_branch} sync: git merge-tree exited "
            f"{result.returncode} without a prediction (Git 2.38 or newer is "
            "required): " + result.stderr.strip()
        )
    return entries[1:]


def conflicted_paths(workspace: Path) -> tuple[str, ...]:
    result = git(workspace, "diff", "--name-only", "--diff-filter=U", "-z")
    return _nul_separated(result.stdout)


def resolve_delivered_conflicts(
    workspace: Path,
    *,
    base_branch: str,
    delivered: frozenset[str],
    commits: Sequence[str] = (),
) -> tuple[str, ...]:
    """Take base_branch's version of every conflicted path the PR delivered.

    A path qualifies only when it is in the delivered set *and* the
    workbench's side of the conflict (index stage 2) is a version the PR
    carried. Returns the conflicted paths it did not touch. A path that
    base_branch deleted is removed; any other is checked out from
    base_branch. Both are staged so the merge can be committed once nothing
    else conflicts.
    """
    remaining = []
    conflicted = conflicted_paths(workspace)
    candidates = [path for path in conflicted if path in delivered]
    carried = carried_entries_by_path(workspace, commits, candidates)
    for path in conflicted:
        if path not in delivered:
            remaining.append(path)
            continue
        if not workbench_version_was_delivered(
            carried=carried[path], workbench_entry=stage_entry(workspace, 2, path)
        ):
            remaining.append(path)
            continue
        # entry_at raises on a lookup failure rather than reporting absence,
        # so a broken object store cannot masquerade as a deletion on the base.
        base_entry = entry_at(workspace, base_branch, path)
        if base_entry is not None and base_entry[0] == TREE_MODE:
            # A file on the workbench where the base now has a directory is
            # not a version to supersede; leave it for a human.
            remaining.append(path)
            continue
        if base_entry is not None:
            git(workspace, "checkout", base_branch, "--", _literal(path))
            git(workspace, "add", "--", _literal(path))
        else:
            git(workspace, "rm", "--quiet", "--", _literal(path))
    return tuple(remaining)


def sync_workbench_with_base(
    workspace: Path,
    *,
    workbench_branch: str,
    base_branch: str,
    delivered: frozenset[str] = frozenset(),
    commits: Sequence[str] = (),
    blocking_out: list[str] | None = None,
) -> str:
    """Bring workbench_branch up to date with a freshly fast-forwarded base.

    Tries a fast-forward first, the common case when the workbench holds no
    commits of its own beyond the merged history. Falls back to a real merge
    when it does.

    A conflict is resolved only on a path the merged pull request changed,
    only when the workbench's version of it is one the pull request carried,
    and only in favour of the base: the workbench then holds the draft that
    was transferred and the base holds its reviewed, merged form. A conflict
    anywhere else — an undelivered path, or a delivered path the workbench
    edited again after transfer — is workbench work, so the merge is aborted
    and reported rather than resolved, matching this repository's "deny
    rather than silently allow" pattern for outcomes that cannot be verified
    safe.
    """
    if is_ancestor(workspace, base_branch, workbench_branch):
        return "already-up-to-date"
    if git(workspace, "merge", "--ff-only", base_branch, check=False).returncode == 0:
        return "fast-forwarded"
    # A real merge ends in a commit of the whole index, so anything already
    # staged would be folded into it. Git refuses such a merge today; this
    # check keeps that guarantee ours rather than Git's. ``--quiet`` exits 1
    # for staged changes and 0 for none; anything else is a probe failure.
    staged = git(workspace, "diff", "--cached", "--quiet", check=False)
    if staged.returncode == 1:
        return SYNC_INDEX_DIRTY
    if staged.returncode != 0:
        raise CleanupError(
            f"cannot read the {workbench_branch} index: git diff --cached exited "
            f"{staged.returncode}: " + staged.stderr.strip()
        )
    # From the merge invocation onward everything runs under one guard: the
    # merge itself can time out after writing MERGE_HEAD, and a probe, a
    # checkout, or the final commit can each raise (index state, a hook,
    # signing). Nothing here may leave MERGE_HEAD behind.
    try:
        if git(workspace, "merge", "--no-edit", base_branch, check=False).returncode == 0:
            return "merged"
        # A nonzero merge is a conflict only when it left unmerged entries.
        # Any other refusal must not be turned into a commit, so it is
        # aborted and reported as its own outcome.
        if not conflicted_paths(workspace):
            git(workspace, "merge", "--abort", check=False)
            return SYNC_MERGE_FAILED
        remaining = resolve_delivered_conflicts(
            workspace, base_branch=base_branch, delivered=delivered, commits=commits
        )
        remaining = tuple(dict.fromkeys(remaining + conflicted_paths(workspace)))
        if remaining:
            if blocking_out is not None:
                blocking_out.extend(remaining)
            git(workspace, "merge", "--abort", check=False)
            return SYNC_CONFLICT
        git(workspace, "commit", "--no-edit")
    except CleanupError:
        git(workspace, "merge", "--abort", check=False)
        raise
    return SYNC_MERGED_RESOLVED


def advance_base(plan: CleanupPlan) -> str:
    """Bring local base level with its remote, writing no file if it can.

    Advancing a branch nobody has checked out is a ref update; it needs no
    working tree and touches none. The script used to reach the same result
    by checking the base out in the primary, which rewrote that checkout's
    files underneath whatever was running in it — the exact interference
    separate worktrees exist to prevent.
    """
    primary = plan.primary_workspace
    base = plan.pull_request.base_branch
    if plan.base_advance == BASE_ALREADY_CURRENT:
        return BASE_ALREADY_CURRENT
    remote_oid = git(primary, "rev-parse", f"origin/{base}").stdout.strip()
    if plan.base_advance == BASE_FAST_FORWARD_IN_PLACE:
        git(primary, "merge", "--ff-only", f"origin/{base}")
        return BASE_FAST_FORWARD_IN_PLACE
    # Compare-and-swap against the value the plan verified, so a base that
    # moved since planning fails the update instead of being overwritten by it.
    result = git(
        primary,
        "update-ref",
        f"refs/heads/{base}",
        remote_oid,
        plan.base_oid_at_plan,
        check=False,
    )
    if result.returncode != 0:
        raise CleanupError(
            f"local {base} moved since this cleanup was planned, so it was not "
            "advanced: " + (result.stderr.strip() or "ref update refused")
        )
    return BASE_REF_UPDATE


def delete_delivery_branch(plan: CleanupPlan) -> None:
    """Delete the merged local delivery ref after proving it is contained.

    `git branch -d` decides "fully merged" against `HEAD`, and this cleanup no
    longer stands on the base branch — from the workbench it would call a
    delivery that is merged into `main` unmerged. Containment is therefore
    checked here against the base itself. When it does not hold, the merge was
    a squash or a rebase, and the plan has already verified from pull-request
    evidence that the result reached the base.

    Because the delete is forced either way, the ref is re-read first: a tip
    that moved since planning no longer carries the history the plan proved
    merged, and forcing it away would discard commits nothing has reviewed.
    """
    primary = plan.primary_workspace
    pull_request = plan.pull_request
    tip = git(
        primary, "rev-parse", "--verify", f"refs/heads/{pull_request.head_branch}"
    ).stdout.strip()
    if tip != pull_request.head_oid:
        raise CleanupError(
            f"{pull_request.head_branch} moved since this cleanup was planned "
            f"({pull_request.head_oid} to {tip}); it was not deleted"
        )
    if plan.head_contained_in_base and not is_ancestor(
        primary, pull_request.head_oid, pull_request.base_branch
    ):
        raise CleanupError(
            f"{pull_request.head_branch} is no longer contained in "
            f"{pull_request.base_branch}; the base moved during cleanup"
        )
    git(primary, "branch", "-D", "--", pull_request.head_branch)


def canonical_worktree_container(primary: Path) -> Path:
    return primary.parent / f"{primary.name}.worktrees"


def remove_empty_canonical_container(
    primary: Path, target_worktree: Worktree | None
) -> None:
    """Remove only the canonical container after its verified child is gone."""
    if target_worktree is None:
        return

    target = target_worktree.path.resolve()
    container = canonical_worktree_container(primary).resolve()
    if target.parent != container:
        return

    remaining_paths = {item.path.resolve() for item in inspect_worktrees(primary)}
    if target in remaining_paths:
        raise CleanupError(
            f"cleanup verification failed: worktree remains {target}"
        )

    if not container.exists() or any(container.iterdir()):
        return

    try:
        container.rmdir()
    except OSError as error:
        raise CleanupError(
            f"could not remove empty canonical worktree container {container}: {error}"
        ) from error


def execute_cleanup(
    plan: CleanupPlan, *, blocking_out: list[str] | None = None
) -> str | None:
    primary = plan.primary_workspace
    pull_request = plan.pull_request

    if plan.primary_conflicts:
        raise CleanupError(
            "primary workspace holds changes on paths this cleanup would "
            "write:\n" + "\n".join(plan.primary_conflicts)
        )

    advance_base(plan)

    if plan.target_worktree and plan.target_worktree.path != primary:
        git(primary, "worktree", "remove", str(plan.target_worktree.path))

    if plan.switch_required and current_branch(primary) != plan.return_branch:
        git(primary, "switch", "--", plan.return_branch)

    delete_delivery_branch(plan)
    git(primary, "worktree", "prune")

    workbench_sync: str | None = None
    if plan.workbench_sync_needed and plan.return_branch == WORKBENCH_BRANCH:
        workbench_sync = sync_workbench_with_base(
            primary,
            workbench_branch=WORKBENCH_BRANCH,
            base_branch=pull_request.base_branch,
            delivered=plan.delivered_paths,
            commits=plan.pull_request_commits,
            blocking_out=blocking_out,
        )

    if branch_exists(primary, pull_request.head_branch):
        raise CleanupError(
            f"cleanup verification failed: local branch remains "
            f"{pull_request.head_branch}"
        )
    if plan.target_worktree and plan.target_worktree.path != primary:
        remaining_paths = {item.path for item in inspect_worktrees(primary)}
        if plan.target_worktree.path in remaining_paths:
            raise CleanupError(
                f"cleanup verification failed: worktree remains "
                f"{plan.target_worktree.path}"
            )
    remove_empty_canonical_container(primary, plan.target_worktree)
    local_base = git(
        primary,
        "rev-parse",
        "--verify",
        f"refs/heads/{pull_request.base_branch}",
    ).stdout.strip()
    remote_base = git(
        primary, "rev-parse", f"origin/{pull_request.base_branch}"
    ).stdout.strip()
    if local_base != remote_base:
        raise CleanupError(
            f"cleanup verification failed: local {pull_request.base_branch} "
            f"does not match origin/{pull_request.base_branch}"
        )

    return workbench_sync


def render_plan(
    plan: CleanupPlan, *, executed: bool, workbench_sync: str | None = None
) -> str:
    target = "not checked out"
    if plan.target_worktree:
        role = (
            "primary checkout"
            if plan.target_worktree.path == plan.primary_workspace
            else "secondary worktree"
        )
        target = f"{role} at {plan.target_worktree.path}"
    remote_state = "still exists" if plan.remote_branch_exists else "already absent"
    mode = "executed" if executed else "verified dry run"
    containment = (
        f"contained in origin/{plan.pull_request.base_branch}"
        if plan.head_contained_in_base
        else "not contained; squash or rebase merge, authorized by merged-PR evidence"
    )
    lines = [
        f"Local cleanup {mode} for PR #{plan.pull_request.number}.",
        f"  PR: {plan.pull_request.url}",
        f"  Branch: {plan.pull_request.head_branch}",
        f"  Checkout: {target}",
        f"  Local deletion: {containment}",
        f"  Base advance: {plan.base_advance}",
        f"  Primary checkout: "
        + (
            f"switches to {plan.return_branch}"
            if plan.switch_required
            else f"stays on {plan.initial_primary_branch}"
        ),
        f"  Remote branch: {remote_state}; this script never deletes it",
    ]
    if plan.primary_conflicts:
        lines.append("  BLOCKED, uncommitted changes on paths this cleanup writes:")
        lines.extend(f"    {entry}" for entry in plan.primary_conflicts)
    if plan.workbench_sync_needed or (
        plan.return_branch == WORKBENCH_BRANCH
        and plan.return_branch != plan.pull_request.base_branch
    ):
        if executed:
            lines.append(f"  Workbench sync: {workbench_sync}")
        else:
            state = "behind" if plan.workbench_sync_needed else "already up to date"
            lines.append(
                f"  Workbench sync: {WORKBENCH_BRANCH} is {state} with "
                f"{plan.pull_request.base_branch}; execute will sync it automatically"
            )
            if plan.resolvable_conflicts:
                lines.append(
                    "    conflicts on delivered paths, resolved from "
                    f"{plan.pull_request.base_branch}:"
                )
                lines.extend(f"      {path}" for path in plan.resolvable_conflicts)
            if plan.blocking_conflicts:
                lines.append(
                    "    BLOCKING conflicts that cannot be proven safe to resolve; "
                    "the sync will abort:"
                )
                lines.extend(f"      {path}" for path in plan.blocking_conflicts)
    return "\n".join(lines)


def cleanup_plan_as_json(
    plan: CleanupPlan,
    *,
    executed: bool,
    workbench_sync: str | None = None,
    blocked_paths: Sequence[str] | None = None,
) -> str:
    """Emit lifecycle evidence consumable by the governed-delivery coordinator."""
    return json.dumps(
        {
            "schemaVersion": 1,
            "outcome": "cleaned" if executed else "verified",
            "executed": executed,
            "pullRequest": plan.pull_request.number,
            "pullRequestUrl": plan.pull_request.url,
            "branch": plan.pull_request.head_branch,
            "mergeOid": plan.pull_request.merge_oid,
            "baseAdvance": plan.base_advance,
            "primarySwitched": plan.switch_required,
            "localCleanup": "completed" if executed else "planned",
            "cleanupDebt": None,
            "remoteBranch": "present" if plan.remote_branch_exists else "absent",
            "remoteDeletionAttempted": False,
            "workbenchSync": workbench_sync,
            # Dry-run predictions, made before anything ran.
            "workbenchPredictedResolvable": list(plan.resolvable_conflicts),
            "workbenchPredictedBlocking": list(plan.blocking_conflicts),
            # What the executed sync actually blocked on; null unless executed.
            "workbenchBlockedPaths": list(blocked_paths or ()) if executed else None,
        },
        indent=2,
        sort_keys=True,
    )


def cleanup_debt_as_json(error: Exception, *, executed: bool) -> str:
    return json.dumps(
        {
            "schemaVersion": 1,
            "outcome": "cleanup-debt",
            "executed": executed,
            "localCleanup": "blocked",
            "cleanupDebt": str(error),
            "remoteDeletionAttempted": False,
        },
        indent=2,
        sort_keys=True,
    )


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify and clean targeted or stale local delivery state."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    pr_parser = subparsers.add_parser(
        "pr",
        help="Verify and clean one merged pull request",
    )
    pr_parser.add_argument(
        "--pr",
        type=int,
        required=True,
        help="Merged pull request number",
    )
    pr_parser.add_argument(
        "--primary-workspace",
        type=Path,
        required=True,
        help="Developer-visible repository root",
    )
    pr_parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the verified local cleanup; otherwise print a dry-run plan",
    )
    pr_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )

    stale_parser = subparsers.add_parser(
        "stale",
        help="Audit and optionally remove stale Jira-keyed local branches",
    )
    stale_parser.add_argument(
        "--primary-workspace",
        type=Path,
        required=True,
        help="Developer-visible repository root",
    )
    stale_parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Updated integration ref used for reachability checks",
    )
    stale_parser.add_argument(
        "--execute",
        action="store_true",
        help="Delete the verified safe candidates; otherwise report only",
    )
    stale_parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Do not fetch or prune (reserved for read-only preflight use)",
    )
    stale_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    args = parse_args(arguments)
    try:
        primary = resolve_primary_workspace(args.primary_workspace)
        if args.mode == "pr":
            refresh_remote(primary)
            remotes = live_remote_branches(primary)
            pull_request = load_pull_request(primary, args.pr)
            plan = build_cleanup_plan(
                primary,
                pull_request,
                remote_branches=remotes,
            )
            workbench_sync = None
            blocking: list[str] = []
            if args.execute:
                workbench_sync = execute_cleanup(plan, blocking_out=blocking)
            if args.format == "json":
                print(
                    cleanup_plan_as_json(
                        plan,
                        executed=args.execute,
                        workbench_sync=workbench_sync,
                        blocked_paths=blocking,
                    )
                )
            else:
                print(render_plan(plan, executed=args.execute, workbench_sync=workbench_sync))
            if workbench_sync == SYNC_CONFLICT:
                # The paths the sync actually hit, not the dry-run prediction,
                # which may be empty or stale by execution time.
                named = ", ".join(blocking) or "unnamed paths"
                print(
                    f"Workbench sync blocked: {WORKBENCH_BRANCH} conflicts with "
                    f"{pull_request.base_branch} on paths that cannot be proven safe "
                    f"to resolve ({named}). Resolve manually with "
                    f"`git merge {pull_request.base_branch}` on {WORKBENCH_BRANCH}.",
                    file=sys.stderr,
                )
            elif workbench_sync == SYNC_INDEX_DIRTY:
                print(
                    f"Workbench sync skipped: {WORKBENCH_BRANCH} has staged changes, "
                    "which a merge commit would fold in. Commit or unstage them, then "
                    f"run `git merge {pull_request.base_branch}` on {WORKBENCH_BRANCH}.",
                    file=sys.stderr,
                )
            elif workbench_sync == SYNC_MERGE_FAILED:
                print(
                    f"Workbench sync blocked: `git merge {pull_request.base_branch}` on "
                    f"{WORKBENCH_BRANCH} was refused without leaving conflicts. The "
                    "merge was aborted; run it manually to see Git's reason.",
                    file=sys.stderr,
                )
            if not args.execute and args.format == "text":
                print(
                    "Run again with --execute only after local cleanup is "
                    "authorized."
                )
            return 0

        if not args.no_fetch:
            refresh_remote(primary)
        remotes = live_remote_branches(primary)
        report = build_reconciliation_report(
            primary,
            base_ref=args.base_ref,
            remote_branches=remotes,
        )
        if args.execute:
            execute_reconciliation(primary, report)
        if args.format == "json":
            print(reconciliation_as_json(report, executed=args.execute))
        else:
            print(render_reconciliation(report, executed=args.execute))
            if not args.execute and report.safe_to_delete:
                print(
                    "Run again with --execute only after global cleanup is "
                    "authorized."
                )
        return 0
    except CleanupError as error:
        if getattr(args, "mode", None) == "pr" and getattr(args, "format", "text") == "json":
            print(cleanup_debt_as_json(error, executed=bool(args.execute)))
        else:
            print(f"Local delivery cleanup blocked: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
