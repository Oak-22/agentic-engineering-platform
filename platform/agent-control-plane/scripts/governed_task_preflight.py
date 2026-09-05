#!/usr/bin/env python3
"""Block new governed task isolation when the prior delivery is unfinished.

Run with no arguments for the human-facing CLI check `scripts/README.md`
documents (exit 0 pass, 1 blocked, 2 undeterminable). Run with `--hook` to
answer one PreToolUse event from stdin as a Claude Code or Codex hook,
denying `git checkout -b` / `git switch -c` when this module's own blockers
apply and staying silent otherwise.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


JIRA_ISSUE_KEY_PATTERN = r"[A-Z][A-Z0-9_]*-[1-9][0-9]*"
DELIVERY_BRANCH_PATTERN = re.compile(
    rf"^(?:feature|fix|bugfix|hotfix|refactor|chore|docs|release)/"
    rf"{JIRA_ISSUE_KEY_PATTERN}(?:-|$)"
)
LEGACY_AGENT_BRANCH_PATTERN = re.compile(
    rf"^agent/{JIRA_ISSUE_KEY_PATTERN}(?:-|$)"
)


def is_governed_delivery_branch(branch: str) -> bool:
    """Recognize current delivery branches and historical agent-prefixed refs."""
    return bool(
        DELIVERY_BRANCH_PATTERN.match(branch)
        or LEGACY_AGENT_BRANCH_PATTERN.match(branch)
    )


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
    stale_local_delivery_branches: tuple[str, ...]
    workbench_exists: bool
    workbench_commits_behind_main: int
    remote_main_tracked: bool
    main_ahead_of_remote: int
    main_behind_remote: int
    #: Paths the pending operation would write. Empty when nothing is known
    #: about where it is headed, which is also the case where an untracked
    #: file cannot be in its way.
    at_risk_paths: tuple[str, ...] = ()


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


def local_branch_exists(root: Path, branch: str) -> bool:
    result = run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=root,
        check=False,
    )
    return result.returncode == 0


def workbench_commits_behind_main(root: Path) -> int:
    """How far the private capture branch has drifted behind main, or 0.

    Any nonzero count blocks. A workbench missing even one main commit cannot
    be reconciled against main honestly: evidence that looks workbench-only
    may simply be main content the workbench has not seen yet. Counting
    commits is not a proxy for that judgment, which is why there is no
    tolerance threshold here.
    """
    if not local_branch_exists(root, "workbench/local") or not local_branch_exists(
        root, "main"
    ):
        return 0
    result = run(
        ["git", "rev-list", "--count", "workbench/local..main"],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def main_divergence(root: Path) -> tuple[bool, int, int]:
    """Compare local main with origin/main: (tracked, ahead, behind).

    Reads the remote-tracking ref as it stands rather than fetching. This
    check is read-only by contract, so a result is only as current as the
    last fetch; the governed preparation operation fetches before it trusts
    this comparison.
    """
    if not local_branch_exists(root, "main"):
        return (False, 0, 0)
    remote = run(
        ["git", "show-ref", "--verify", "--quiet", "refs/remotes/origin/main"],
        cwd=root,
        check=False,
    )
    if remote.returncode != 0:
        return (False, 0, 0)
    result = run(
        ["git", "rev-list", "--left-right", "--count", "main...origin/main"],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        return (False, 0, 0)
    try:
        ahead_text, behind_text = result.stdout.split()
        return (True, int(ahead_text), int(behind_text))
    except ValueError:
        return (False, 0, 0)


UNTRACKED_STATUS = "??"


def status_entries(root: Path) -> tuple[str, ...]:
    """Every uncommitted entry as ``"XY path"``, parsed from ``-z`` output.

    The human-readable status form quotes and escapes unusual paths, so a
    gate built on it can name a file that does not exist. The NUL-separated
    form keeps each path exactly as Git holds it, which is what the at-risk
    comparison below comes down to.
    """
    result = run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "unknown Git failure"
        raise InspectionError(f"could not inspect the working tree: {detail}")
    fields = result.stdout.split("\0")
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


def entry_status(entry: str) -> str:
    return entry[:2]


def entry_path(entry: str) -> str:
    return entry[3:]


def paths_written_between(root: Path, left: str, right: str) -> frozenset[str]:
    """Working-tree paths that moving from `left` to `right` would write.

    This is the set Git itself protects: a switch or a merge rewrites only
    the paths that differ, leaves every other file alone, and refuses when an
    incoming tracked file would land on an untracked one.
    """
    result = run(
        ["git", "diff", "--name-only", "-z", left, right], cwd=root, check=False
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "unknown Git failure"
        raise InspectionError(f"could not compare {left} with {right}: {detail}")
    return frozenset(path for path in result.stdout.split("\0") if path)


def branch_creation_start_point(command: str) -> str | None:
    """The revision a branch-creation command would start from, if it names one.

    Creating a branch without a start point branches from `HEAD` and writes
    nothing to the working tree. A start point is what makes the command able
    to overwrite a file, so it is what decides which files are at risk.
    """
    match = BRANCH_CREATION_START_POINT_PATTERN.search(command)
    if match is None:
        return None
    start = match.group("start")
    return start if start and not start.startswith("-") else None


def blocking_entries(
    dirty_entries: Sequence[str], at_risk_paths: Sequence[str]
) -> tuple[str, ...]:
    """The uncommitted entries that actually stand in the way.

    A tracked modification is unfinished delivery work and always blocks:
    carrying it across a branch is how one delivery's evidence ends up in
    another's. An untracked file is not delivery work. The workbench pattern
    expects loose capture notes in the primary checkout as its steady state,
    and Git preserves an untracked file across a switch or a merge unless an
    incoming tracked file would land on its exact path. Refusing on every
    loose file blocks far more than the hazard it guards.
    """
    at_risk = frozenset(at_risk_paths)
    return tuple(
        entry
        for entry in dirty_entries
        if entry_status(entry) != UNTRACKED_STATUS or entry_path(entry) in at_risk
    )


def inspect_repository(
    root: Path, *, at_risk_paths: Sequence[str] = ()
) -> RepositoryState:
    try:
        status_lines = status_entries(root)
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
        reconciliation_result = run(
            [
                sys.executable,
                str(
                    root
                    / ".agents"
                    / "skills"
                    / "manage-git-workflow"
                    / "scripts"
                    / "delivery_cleanup.py"
                ),
                "stale",
                "--primary-workspace",
                str(root),
                "--no-fetch",
                "--format",
                "json",
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
    try:
        reconciliation_data = json.loads(reconciliation_result.stdout)
        reconciliation_candidates = reconciliation_data["candidates"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise InspectionError("local cleanup audit returned invalid data") from error

    open_governed_pull_requests = tuple(
        PullRequest(
            number=int(item["number"]),
            title=str(item["title"]),
            head_ref_name=str(item["headRefName"]),
            url=str(item["url"]),
        )
        for item in open_pr_data
        if is_governed_delivery_branch(str(item.get("headRefName", "")))
    )

    current_pull_request_state: str | None = None
    current_remote_branch_exists = False
    if is_governed_delivery_branch(branch):
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

    remote_main_tracked, main_ahead, main_behind = main_divergence(root)

    return RepositoryState(
        dirty_entries=status_lines,
        at_risk_paths=tuple(at_risk_paths),
        open_governed_pull_requests=open_governed_pull_requests,
        current_branch=branch,
        current_pull_request_state=current_pull_request_state,
        current_remote_branch_exists=current_remote_branch_exists,
        stale_local_delivery_branches=tuple(
            str(candidate["branch"])
            for candidate in reconciliation_candidates
            if candidate.get("classification") == "safe-to-delete"
        ),
        workbench_exists=local_branch_exists(root, "workbench/local"),
        workbench_commits_behind_main=workbench_commits_behind_main(root),
        remote_main_tracked=remote_main_tracked,
        main_ahead_of_remote=main_ahead,
        main_behind_remote=main_behind,
    )


def blockers_for(state: RepositoryState) -> list[str]:
    blockers: list[str] = []

    if state.remote_main_tracked:
        ahead = state.main_ahead_of_remote
        behind = state.main_behind_remote
        if ahead and behind:
            blockers.append(
                f"Can't implement the next task: local main has diverged from "
                f"origin/main ({ahead} unique local commit(s), {behind} unique "
                "remote commit(s)). A delivery branch cut from this main would "
                "carry commits that were never reviewed. Reconcile the two "
                "deliberately; this check will not rewrite history for you."
            )
        elif ahead:
            blockers.append(
                f"Can't implement the next task: local main is {ahead} commit(s) "
                "ahead of origin/main. Those commits reached main without a "
                "reviewed pull request. Deliver or remove them deliberately "
                "before carving another branch from this main."
            )
        elif behind:
            blockers.append(
                f"Can't implement the next task: local main is {behind} commit(s) "
                "behind origin/main, so a branch cut from it would start from a "
                "stale integration baseline. Fast-forward first with "
                "`git switch main && git merge --ff-only origin/main`."
            )

    if state.workbench_exists and state.workbench_commits_behind_main > 0:
        blockers.append(
            f"Can't implement the next task: workbench/local is "
            f"{state.workbench_commits_behind_main} commit(s) behind main, so its "
            "remaining changes cannot be told apart from main content it has not "
            "seen yet. Sync it with `git switch workbench/local && git merge main` "
            "before reconciling workbench evidence."
        )

    obstructing = blocking_entries(state.dirty_entries, state.at_risk_paths)
    if obstructing:
        blockers.append(
            "Can't implement the next task: the working tree holds changes this "
            "operation would carry across or overwrite. Commit the current "
            "delivery, or intentionally stash or resolve these entries, before "
            "creating another branch or worktree.\n"
            + "\n".join(f"  {entry}" for entry in obstructing)
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
        is_governed_delivery_branch(state.current_branch)
        and state.current_pull_request_state == "MERGED"
        and state.current_remote_branch_exists
    ):
        blockers.append(
            "Can't implement the next task: the current pull request is merged, but "
            f"remote branch origin/{state.current_branch} still exists. Complete the "
            "authorized remote branch cleanup first."
        )

    if (
        is_governed_delivery_branch(state.current_branch)
        and state.current_pull_request_state is None
        and state.current_remote_branch_exists
    ):
        blockers.append(
            "Can't implement the next task: the current published feature branch has "
            "no pull request. Publish or intentionally resolve the current delivery "
            "before creating another branch or worktree."
        )

    return blockers


def warnings_for(state: RepositoryState) -> list[str]:
    warnings: list[str] = []

    preserved = tuple(
        entry
        for entry in state.dirty_entries
        if entry not in blocking_entries(state.dirty_entries, state.at_risk_paths)
    )
    if preserved:
        warnings.append(
            "Untracked files are present and will be preserved. They are not on "
            "the list of paths this operation writes, so they do not block it:\n"
            + "\n".join(f"  {entry}" for entry in preserved)
        )

    if state.stale_local_delivery_branches:
        warnings.append(
            "Local cleanup debt detected. These merged Jira-keyed branches are safe "
            "reconciliation candidates; preflight will not delete them:\n"
            + "\n".join(
                f"  {branch}" for branch in state.stale_local_delivery_branches
            )
            + "\nRun delivery_cleanup.py stale in verification mode, then with "
            "--execute after cleanup is authorized."
        )

    return warnings


CANONICAL_PREPARATION = (
    "Create the branch through the governed preparation operation instead, "
    "which verifies the baseline and cuts the branch from the exact commit it "
    "verified:\n"
    "  python3 platform/agent-control-plane/scripts/prepare_delivery_branch.py "
    "<category>/<JIRA-ISSUE-KEY>-<slug>"
)

BRANCH_CREATION_COMMAND_PATTERN = re.compile(r"\bgit\s+(?:checkout\s+-b\b|switch\s+-c\b)")
BRANCH_CREATION_START_POINT_PATTERN = re.compile(
    r"\bgit\s+(?:checkout\s+-b|switch\s+-c)\s+(?P<branch>\S+)(?:\s+(?P<start>\S+))?"
)


def targets_branch_creation(command: str) -> bool:
    """Whether a shell command creates and switches to a new branch.

    Matches literal ``git checkout -b`` / ``git switch -c`` invocations only.
    A command that reaches the same effect through a wrapper, alias, or
    subshell is not recognized here — hardening this matcher against
    deliberate evasion is a separate, later change, not this one.
    """
    return bool(BRANCH_CREATION_COMMAND_PATTERN.search(command))


def deny_decision(reason: str) -> dict[str, dict[str, str]]:
    """The PreToolUse JSON shape both Claude Code and Codex accept for deny."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def hook_response(tool_input: dict[str, Any], root: Path) -> dict[str, dict[str, str]] | None:
    """Return a deny decision for an unsafe branch-creation command.

    Returns None — no opinion — for every other command, and for a safe
    branch-creation command. An inspection failure denies rather than
    silently allowing: an unverifiable repository state is not evidence the
    action is safe.
    """
    command = str(tool_input.get("command", ""))
    if not targets_branch_creation(command):
        return None
    try:
        start_point = branch_creation_start_point(command)
        at_risk = (
            paths_written_between(root, "HEAD", start_point)
            if start_point
            else frozenset()
        )
        state = inspect_repository(root, at_risk_paths=sorted(at_risk))
    except InspectionError as error:
        return deny_decision(f"Can't verify whether the next governed task is safe: {error}")
    blockers = blockers_for(state)
    if not blockers:
        return None
    return deny_decision("\n\n".join([*blockers, CANONICAL_PREPARATION]))


def run_as_hook(stdin_payload: str, cwd: Path) -> int:
    """Read one PreToolUse event from stdin and print a decision, if any.

    Silent (prints nothing, exits 0) for malformed input, a non-Bash tool
    call, a command outside a Git worktree, or any command this preflight has
    no opinion on. The JSON on stdout decides the outcome for a matched,
    blocked command; exit code carries no meaning in this mode.
    """
    try:
        event = json.loads(stdin_payload)
    except json.JSONDecodeError:
        return 0

    tool_name = event.get("tool_name")
    if tool_name is not None and tool_name != "Bash":
        return 0

    try:
        root = repository_root(cwd)
    except InspectionError:
        return 0

    decision = hook_response(event.get("tool_input") or {}, root)
    if decision is not None:
        print(json.dumps(decision))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--hook" in args:
        return run_as_hook(sys.stdin.read(), Path.cwd())

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

    warnings = warnings_for(state)
    if warnings:
        print("\n\n".join(warnings), file=sys.stderr)

    print(
        "Governed task preflight passed: nothing uncommitted stands in the way "
        "and no outstanding governed pull request blocks task isolation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
