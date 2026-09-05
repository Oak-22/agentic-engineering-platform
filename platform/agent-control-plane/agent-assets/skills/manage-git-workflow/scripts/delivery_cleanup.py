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

    return PullRequest(
        number=returned_number,
        state=required_string("state").upper(),
        merged_at=merged_at,
        merge_oid=merge_oid,
        base_branch=required_string("baseRefName"),
        head_branch=required_string("headRefName"),
        head_oid=required_string("headRefOid"),
        url=required_string("url"),
    )


def load_pull_request(workspace: Path, number: int) -> PullRequest:
    result = run(
        [
            "gh",
            "pr",
            "view",
            str(number),
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
    so loose files in it are never at risk. Deletion is unconditional because
    containment was already proven against `base_ref`; `git branch -d` would
    re-check against `HEAD` instead and call a delivery merged into `main`
    unmerged whenever the checkout sits on the workbench.
    """
    for candidate in report.safe_to_delete:
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
    if workbench_sync_needed:
        at_risk |= paths_written_between(primary, WORKBENCH_BRANCH, remote_base)

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
    )


def sync_workbench_with_base(
    workspace: Path, *, workbench_branch: str, base_branch: str
) -> str:
    """Bring workbench_branch up to date with a freshly fast-forwarded base.

    Tries a fast-forward first, the common case when the workbench holds no
    commits of its own beyond the merged history. Falls back to a real merge
    when it does. Never resolves a conflicting merge automatically: aborts and
    reports instead, matching this repository's "deny rather than silently
    allow" pattern for outcomes that cannot be verified safe.
    """
    if is_ancestor(workspace, base_branch, workbench_branch):
        return "already-up-to-date"
    if git(workspace, "merge", "--ff-only", base_branch, check=False).returncode == 0:
        return "fast-forwarded"
    if git(workspace, "merge", "--no-edit", base_branch, check=False).returncode == 0:
        return "merged"
    git(workspace, "merge", "--abort", check=False)
    return "conflict-manual-resolution-required"


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
    """
    primary = plan.primary_workspace
    pull_request = plan.pull_request
    if plan.head_contained_in_base and not is_ancestor(
        primary, pull_request.head_oid, pull_request.base_branch
    ):
        raise CleanupError(
            f"{pull_request.head_branch} is no longer contained in "
            f"{pull_request.base_branch}; the base moved during cleanup"
        )
    git(primary, "branch", "-D", "--", pull_request.head_branch)


def execute_cleanup(plan: CleanupPlan) -> str | None:
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
    return "\n".join(lines)


def cleanup_plan_as_json(
    plan: CleanupPlan, *, executed: bool, workbench_sync: str | None = None
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
            if args.execute:
                workbench_sync = execute_cleanup(plan)
            if args.format == "json":
                print(
                    cleanup_plan_as_json(
                        plan, executed=args.execute, workbench_sync=workbench_sync
                    )
                )
            else:
                print(render_plan(plan, executed=args.execute, workbench_sync=workbench_sync))
            if workbench_sync == "conflict-manual-resolution-required":
                print(
                    f"Workbench sync blocked: {WORKBENCH_BRANCH} could not be merged "
                    f"with {pull_request.base_branch} without conflicts. Resolve "
                    f"manually with `git merge {pull_request.base_branch}` on "
                    f"{WORKBENCH_BRANCH}.",
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
