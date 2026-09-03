#!/usr/bin/env python3
"""Safely publish the checked-out Jira-keyed delivery branch.

The command is read-only apart from refreshing remote-tracking refs unless
``--execute`` is supplied. Execution may integrate the branch's existing
remote tip and current ``origin/main`` with non-rewriting merges, then pushes
the checked-out branch to the same remote branch. It never accepts a refspec,
force-pushes, deletes a ref, rebases, or updates ``main``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


REMOTE = "origin"
BASE_BRANCH = "main"
EXPECTED_REPOSITORY = "Oak-22/agentic-engineering-platform"
DELIVERY_BRANCH = re.compile(
    r"^(?:feature|fix|refactor|chore|docs)/"
    r"[A-Z][A-Z0-9_]*-[1-9][0-9]*-[a-z0-9][a-z0-9-]*$"
)
REMOTE_URL = re.compile(
    r"^(?:git@github\.com:|ssh://git@github\.com/|https://github\.com/)"
    r"(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)


class PublicationError(RuntimeError):
    """Raised when publication cannot be proven safe."""


@dataclass(frozen=True)
class PublicationPlan:
    repository: str
    branch: str
    head: str
    base_head: str
    remote_head: str | None
    remote_sync: str
    base_sync: str


@dataclass(frozen=True)
class PublicationResult:
    schemaVersion: int
    outcome: str
    repository: str
    branch: str
    headBefore: str
    headAfter: str | None
    remoteHeadBefore: str | None
    remoteHeadAfter: str | None
    remoteSync: str
    baseSync: str
    executed: bool


def git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown git failure"
        raise PublicationError(f"git {' '.join(arguments)} failed: {detail}")
    return result


def resolve_root(path: Path) -> Path:
    candidate = path.resolve()
    result = git(candidate, "rev-parse", "--show-toplevel")
    root = Path(result.stdout.strip()).resolve()
    if root != candidate:
        raise PublicationError(f"workspace must name the repository root: {candidate} != {root}")
    return root


def resolve(root: Path, revision: str) -> str:
    result = git(root, "rev-parse", "--verify", revision, check=False)
    if result.returncode != 0:
        raise PublicationError(f"required revision is unavailable: {revision}")
    return result.stdout.strip()


def is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    result = git(root, "merge-base", "--is-ancestor", ancestor, descendant, check=False)
    if result.returncode not in (0, 1):
        raise PublicationError(f"could not compare ancestry: {ancestor} -> {descendant}")
    return result.returncode == 0


def repository_from_remote(url: str) -> str:
    match = REMOTE_URL.match(url.strip())
    if match is None:
        raise PublicationError(f"{REMOTE} is not a supported GitHub remote: {url!r}")
    repository = match.group("repository")
    if repository.casefold() != EXPECTED_REPOSITORY.casefold():
        raise PublicationError(
            f"{REMOTE} addresses {repository}, expected {EXPECTED_REPOSITORY}"
        )
    return repository


def require_clean(root: Path) -> None:
    status = git(root, "status", "--porcelain=v1", "--untracked-files=all").stdout
    if status.strip():
        raise PublicationError("working tree is not clean:\n" + status.rstrip())


def remote_tracking_head(root: Path, branch: str) -> str | None:
    result = git(root, "rev-parse", "--verify", f"refs/remotes/{REMOTE}/{branch}", check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def synchronization(root: Path, local_head: str, other_head: str) -> str:
    if local_head == other_head or is_ancestor(root, other_head, local_head):
        return "none"
    if is_ancestor(root, local_head, other_head):
        return "fast-forward"
    return "merge"


def build_plan(root: Path, *, fetch: bool = True) -> PublicationPlan:
    root = resolve_root(root)
    require_clean(root)
    branch = git(root, "branch", "--show-current").stdout.strip()
    if not branch or not DELIVERY_BRANCH.match(branch):
        raise PublicationError(
            "publication requires the checked-out Jira-keyed delivery branch: "
            "<feature|fix|refactor|chore|docs>/<JIRA-KEY>-<slug>"
        )

    remote_url = git(root, "remote", "get-url", REMOTE).stdout.strip()
    repository = repository_from_remote(remote_url)
    if fetch:
        git(root, "fetch", "--prune", REMOTE)

    head = resolve(root, "HEAD")
    base_head = resolve(root, f"refs/remotes/{REMOTE}/{BASE_BRANCH}")
    remote_head = remote_tracking_head(root, branch)
    remote_sync = (
        synchronization(root, head, remote_head) if remote_head is not None else "none"
    )

    projected_head = remote_head if remote_sync == "fast-forward" else head
    if projected_head == base_head:
        raise PublicationError(
            f"{branch} has no delivery commit outside current {REMOTE}/{BASE_BRANCH}; "
            "nothing can be published"
        )
    base_sync = synchronization(root, projected_head, base_head)
    if base_sync == "fast-forward":
        raise PublicationError(
            f"{branch} has no delivery commit outside current {REMOTE}/{BASE_BRANCH}; "
            "nothing can be published"
        )

    return PublicationPlan(
        repository=repository,
        branch=branch,
        head=head,
        base_head=base_head,
        remote_head=remote_head,
        remote_sync=remote_sync,
        base_sync=base_sync,
    )


def merge_ref(root: Path, revision: str, mode: str) -> None:
    if mode == "none":
        return
    arguments = ("merge", "--ff-only", revision) if mode == "fast-forward" else (
        "merge",
        "--no-edit",
        revision,
    )
    result = git(root, *arguments, check=False)
    if result.returncode != 0:
        git(root, "merge", "--abort", check=False)
        detail = result.stderr.strip() or result.stdout.strip() or "unknown merge failure"
        raise PublicationError(
            f"could not integrate {revision} without rewriting history; "
            f"the merge was aborted: {detail}"
        )


def execute(root: Path, plan: PublicationPlan) -> PublicationResult:
    root = resolve_root(root)
    require_clean(root)
    if git(root, "branch", "--show-current").stdout.strip() != plan.branch:
        raise PublicationError("the checked-out branch changed after publication planning")
    if resolve(root, "HEAD") != plan.head:
        raise PublicationError("the delivery branch changed after publication planning")

    if plan.remote_head is not None:
        merge_ref(root, f"refs/remotes/{REMOTE}/{plan.branch}", plan.remote_sync)
    merge_ref(root, f"refs/remotes/{REMOTE}/{BASE_BRANCH}", plan.base_sync)
    require_clean(root)

    head_after = resolve(root, "HEAD")
    push = git(
        root,
        "push",
        "--set-upstream",
        REMOTE,
        f"refs/heads/{plan.branch}:refs/heads/{plan.branch}",
        check=False,
    )
    if push.returncode != 0:
        detail = push.stderr.strip() or push.stdout.strip() or "unknown push failure"
        raise PublicationError(f"same-branch publication was rejected: {detail}")

    observed = git(root, "ls-remote", "--heads", REMOTE, f"refs/heads/{plan.branch}").stdout
    fields = observed.strip().split()
    remote_after = fields[0] if len(fields) == 2 else None
    if remote_after != head_after:
        raise PublicationError(
            f"publication verification failed: local {head_after}, remote {remote_after}"
        )
    return PublicationResult(
        schemaVersion=1,
        outcome="published",
        repository=plan.repository,
        branch=plan.branch,
        headBefore=plan.head,
        headAfter=head_after,
        remoteHeadBefore=plan.remote_head,
        remoteHeadAfter=remote_after,
        remoteSync=plan.remote_sync,
        baseSync=plan.base_sync,
        executed=True,
    )


def result_for_plan(plan: PublicationPlan) -> PublicationResult:
    return PublicationResult(
        schemaVersion=1,
        outcome="planned",
        repository=plan.repository,
        branch=plan.branch,
        headBefore=plan.head,
        headAfter=None,
        remoteHeadBefore=plan.remote_head,
        remoteHeadAfter=None,
        remoteSync=plan.remote_sync,
        baseSync=plan.base_sync,
        executed=False,
    )


def render_text(result: PublicationResult) -> str:
    mode = "published" if result.executed else "verified dry run"
    lines = [
        f"Delivery branch publication {mode} for {result.branch}.",
        f"  Repository: {result.repository}",
        f"  Remote branch sync: {result.remoteSync}",
        f"  Current main sync: {result.baseSync}",
        f"  Head before: {result.headBefore}",
    ]
    if result.headAfter:
        lines.append(f"  Verified remote head: {result.headAfter}")
    else:
        lines.append("  Re-run with --execute to integrate and publish this same branch.")
    return "\n".join(lines)


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify and safely publish the checked-out Jira-keyed delivery branch."
    )
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--no-fetch", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    args = parse_args(arguments)
    try:
        plan = build_plan(args.workspace, fetch=not args.no_fetch)
        result = execute(args.workspace, plan) if args.execute else result_for_plan(plan)
        print(json.dumps(asdict(result), indent=2) if args.format == "json" else render_text(result))
        return 0
    except PublicationError as error:
        print(f"Delivery branch publication blocked: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
