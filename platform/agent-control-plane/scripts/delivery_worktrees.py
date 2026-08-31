#!/usr/bin/env python3
"""Own one Git worktree per active Jira delivery, so agents stop colliding.

Two agents sharing a checkout cannot work at once: whichever switches branches
last decides what the other one sees, and neither can tell that it happened.
Giving each delivery its own worktree removes the contention, but only if
ownership is recorded somewhere both can read — otherwise the collision moves
from the branch to the directory.

This records task, branch, worktree path, base commit, and owning agent for
every active delivery, refuses a second claim on either the branch or the
path, and surfaces file overlap between concurrent deliveries before they
reach integration. Divergence between active branches is expected; what must
not happen is divergence nobody can attribute.

Branches come from `prepare_delivery_branch.py` rather than a second
implementation of baseline verification: a worktree cut from an unverified
`main` is the same defect in a new directory.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


JIRA_KEY_PATTERN = re.compile(r"^[a-z]+/(?P<key>[A-Z][A-Z0-9_]*-[1-9][0-9]*)-")

REGISTERED_LIVE = "active"
REGISTERED_MISSING = "missing"
UNREGISTERED = "unregistered"

STORE_NAME = "delivery-worktrees"
OWNERSHIP_FILENAME = "worktree-ownership.json"


class WorktreeError(RuntimeError):
    """Raised when delivery worktree ownership cannot be established."""


@dataclass(frozen=True)
class Ownership:
    """One agent's claim on one delivery's branch and directory."""

    branch: str
    jira_key: str
    worktree_path: str
    base_commit: str
    agent: str
    created_at: str


@dataclass(frozen=True)
class Reconciled:
    """An ownership record checked against what Git actually has."""

    status: str
    branch: str | None
    worktree_path: str
    ownership: Ownership | None
    head_oid: str | None
    behind_main: int = 0

    @property
    def needs_attention(self) -> bool:
        return self.status != REGISTERED_LIVE


# --------------------------------------------------------------------------
# Decisions — pure, so ownership rules are testable without a repository
# --------------------------------------------------------------------------


def jira_key_of(branch: str) -> str:
    """The Jira key a delivery branch carries."""
    match = JIRA_KEY_PATTERN.match(branch)
    if match is None:
        raise WorktreeError(
            f"{branch!r} carries no Jira issue key. A delivery worktree is owned "
            "by a work item, so the branch must name one."
        )
    return match.group("key")


def claim_conflict(
    branch: str, worktree_path: str, existing: Sequence[Ownership]
) -> str | None:
    """Why this claim cannot be granted, or None.

    Both halves matter. Two claims on one branch mean two agents publishing
    incompatible histories to the same ref; two claims on one directory mean
    they overwrite each other's files. Either is enough to refuse.
    """
    for owned in existing:
        if owned.branch == branch:
            return (
                f"{branch} is already owned by {owned.agent} at "
                f"{owned.worktree_path} since {owned.created_at}. Release it "
                "before claiming it again."
            )
        if owned.worktree_path == worktree_path:
            return (
                f"{worktree_path} is already the worktree for {owned.branch}, "
                f"owned by {owned.agent}. Choose another path."
            )
    return None


def reconcile(
    records: Sequence[Ownership], worktree_paths: Mapping[str, tuple[str | None, str]]
) -> tuple[Reconciled, ...]:
    """Compare recorded ownership with the worktrees Git actually has.

    A record whose directory is gone is reported rather than deleted. It is
    evidence that a delivery was abandoned or cleaned up outside this tooling,
    and discarding it silently would destroy the only trace.
    """
    reconciled: list[Reconciled] = []
    recorded_paths = {record.worktree_path for record in records}

    for record in records:
        live = worktree_paths.get(record.worktree_path)
        reconciled.append(
            Reconciled(
                status=REGISTERED_LIVE if live else REGISTERED_MISSING,
                branch=record.branch,
                worktree_path=record.worktree_path,
                ownership=record,
                head_oid=live[1] if live else None,
            )
        )

    for path, (branch, head) in sorted(worktree_paths.items()):
        if path in recorded_paths:
            continue
        reconciled.append(
            Reconciled(
                status=UNREGISTERED,
                branch=branch,
                worktree_path=path,
                ownership=None,
                head_oid=head,
            )
        )
    return tuple(reconciled)


def overlaps(
    paths_by_branch: Mapping[str, frozenset[str]],
) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """File overlap between concurrent deliveries, as coordination risk.

    Overlap is not a conflict and is never a blocker — two deliveries may
    legitimately touch one file. It is reported before integration because a
    textual merge succeeding is not evidence the two outcomes are compatible.
    """
    found: list[tuple[str, str, tuple[str, ...]]] = []
    branches = sorted(paths_by_branch)
    for index, first in enumerate(branches):
        for second in branches[index + 1 :]:
            shared = paths_by_branch[first] & paths_by_branch[second]
            if shared:
                found.append((first, second, tuple(sorted(shared))))
    return tuple(found)


REFRESH_CURRENT = "current"
REFRESH_MERGE = "merge"
REFRESH_BLOCKED = "blocked"


def refresh_decision(
    baseline_is_current: bool, dirty_entries: Sequence[str], behind: int
) -> tuple[str, str]:
    """Whether a delivery branch can take `main` in, and why not.

    Order matters. Merging a stale `main` into a delivery branch is worse than
    leaving it behind: it looks like the branch was updated while quietly
    pinning it to an older integration point.
    """
    if not baseline_is_current:
        return (
            REFRESH_BLOCKED,
            "local main is not level with origin/main, so merging it would pin "
            "this delivery to a stale integration point. Prepare the baseline "
            "first.",
        )
    if dirty_entries:
        listed = "\n".join(f"    {entry}" for entry in dirty_entries)
        return (
            REFRESH_BLOCKED,
            "the delivery worktree has uncommitted changes, so a merge would mix "
            "them into the result:\n" + listed,
        )
    if behind == 0:
        return (REFRESH_CURRENT, "already contains every main commit")
    return (REFRESH_MERGE, f"{behind} commit(s) behind main")


def default_worktree_path(root: Path, jira_key: str) -> Path:
    """Where a delivery worktree goes when the caller does not say.

    Beside the repository rather than inside it. A worktree nested in the
    primary checkout shows up in its status as untracked content, which is
    exactly the dirty-tree condition that blocks the next delivery.
    """
    return root.parent / f"{root.name}.worktrees" / jira_key


# --------------------------------------------------------------------------
# Git and storage
# --------------------------------------------------------------------------


def _git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=check, capture_output=True, text=True
    )


def _module(name: str, path: Path):
    import importlib.util

    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - packaging guard
        raise WorktreeError(f"could not load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sibling(name: str):
    return _module(name, Path(__file__).resolve().parent / f"{name}.py")


def _cleanup_module():
    """`delivery_cleanup` owns worktree parsing; this reuses it rather than
    growing a second parser that can disagree with it."""
    root = Path(__file__).resolve().parents[1]
    return _module(
        "delivery_cleanup",
        root
        / "agent-assets"
        / "skills"
        / "manage-git-workflow"
        / "scripts"
        / "delivery_cleanup.py",
    )


def live_worktrees(root: Path) -> dict[str, tuple[str | None, str]]:
    """Worktree path -> (branch, head oid), excluding the primary checkout."""
    cleanup = _cleanup_module()
    found: dict[str, tuple[str | None, str]] = {}
    for worktree in cleanup.inspect_worktrees(root):
        if worktree.path == root.resolve():
            continue
        found[str(worktree.path)] = (worktree.branch, worktree.head_oid)
    return found


def ownership_path(root: Path) -> Path:
    store = _sibling("local_store")
    canonical, _ = store.ensure_store(
        STORE_NAME, repo_root=root, project_dir=root, create=True
    )
    return canonical / OWNERSHIP_FILENAME


def load_ownership(path: Path) -> tuple[Ownership, ...]:
    if not path.exists():
        return ()
    try:
        raw = json.loads(path.read_text())
        entries = raw["worktrees"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise WorktreeError(f"ownership record at {path} is unreadable") from error
    return tuple(
        Ownership(
            branch=str(item["branch"]),
            jira_key=str(item["jiraKey"]),
            worktree_path=str(item["worktreePath"]),
            base_commit=str(item["baseCommit"]),
            agent=str(item["agent"]),
            created_at=str(item["createdAt"]),
        )
        for item in entries
    )


def save_ownership(path: Path, records: Sequence[Ownership]) -> None:
    payload = {
        "schemaVersion": 1,
        "worktrees": [
            {
                "branch": record.branch,
                "jiraKey": record.jira_key,
                "worktreePath": record.worktree_path,
                "baseCommit": record.base_commit,
                "agent": record.agent,
                "createdAt": record.created_at,
            }
            for record in sorted(records, key=lambda item: item.branch)
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(path)


def behind_main(root: Path, branch: str) -> int:
    result = _git(root, "rev-list", "--count", f"{branch}..main", check=False)
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def changed_paths(root: Path, branch: str) -> frozenset[str]:
    result = _git(root, "diff", "--name-only", f"main...{branch}", check=False)
    if result.returncode != 0:
        return frozenset()
    return frozenset(line for line in result.stdout.splitlines() if line)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def create(
    root: Path, branch: str, agent: str, requested_path: Path | None, *, now: str | None = None
) -> Ownership:
    key = jira_key_of(branch)
    target = (requested_path or default_worktree_path(root, key)).resolve()

    record_path = ownership_path(root)
    existing = load_ownership(record_path)
    conflict = claim_conflict(branch, str(target), existing)
    if conflict:
        raise WorktreeError(conflict)

    if target.exists() and any(target.iterdir()):
        raise WorktreeError(
            f"{target} already exists and is not empty. A delivery worktree must "
            "start from a directory this operation created."
        )

    preflight = _sibling("governed_task_preflight")
    branch_is_local = preflight.local_branch_exists(root, branch)
    if not branch_is_local:
        prepare = _sibling("prepare_delivery_branch")
        error = prepare.validate_branch_name(branch)
        if error:
            raise WorktreeError(error)
        decisions = prepare.plan(root, fetch=True)
        blocked = prepare.blocking(decisions)
        if blocked:
            raise WorktreeError(
                "the integration baseline is not ready, so a worktree would start "
                "from an unverified commit:\n"
                + "\n".join(f"  {item.stage}: {item.detail}" for item in blocked)
            )

    target.parent.mkdir(parents=True, exist_ok=True)
    added = _git(
        root,
        "worktree",
        "add",
        *(() if branch_is_local else ("-b", branch)),
        str(target),
        *((branch,) if branch_is_local else ("main",)),
        check=False,
    )
    if added.returncode != 0:
        raise WorktreeError(
            f"could not create the worktree: {added.stderr.strip() or 'unknown failure'}"
        )

    base = _git(target, "rev-parse", "HEAD").stdout.strip()
    record = Ownership(
        branch=branch,
        jira_key=key,
        worktree_path=str(target),
        base_commit=base,
        agent=agent,
        created_at=now or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    save_ownership(record_path, [*existing, record])
    return record


def release(root: Path, branch: str, *, remove: bool) -> Ownership:
    record_path = ownership_path(root)
    existing = load_ownership(record_path)
    matching = [item for item in existing if item.branch == branch]
    if not matching:
        raise WorktreeError(f"{branch} is not a recorded delivery worktree")
    record = matching[0]

    if remove:
        target = Path(record.worktree_path)
        removed = _git(root, "worktree", "remove", str(target), check=False)
        if removed.returncode != 0:
            raise WorktreeError(
                "could not remove the worktree, so ownership was left in place: "
                + (removed.stderr.strip() or "unknown failure")
            )
        parent = target.parent
        if parent.exists() and not any(parent.iterdir()):
            shutil.rmtree(parent, ignore_errors=True)

    save_ownership(record_path, [item for item in existing if item.branch != branch])
    return record


def status(root: Path) -> tuple[Reconciled, ...]:
    reconciled = reconcile(load_ownership(ownership_path(root)), live_worktrees(root))
    return tuple(
        item
        if item.status != REGISTERED_LIVE or item.branch is None
        else Reconciled(
            status=item.status,
            branch=item.branch,
            worktree_path=item.worktree_path,
            ownership=item.ownership,
            head_oid=item.head_oid,
            behind_main=behind_main(root, item.branch),
        )
        for item in reconciled
    )


def refresh(root: Path, branch: str) -> tuple[str, str]:
    """Bring one delivery branch up to current `main`, inside its own worktree.

    Merges rather than rebases: a delivery branch may already be published,
    and rewriting a published ref to tidy its history is not this operation's
    call to make.
    """
    matching = [
        item for item in load_ownership(ownership_path(root)) if item.branch == branch
    ]
    if not matching:
        raise WorktreeError(f"{branch} is not a recorded delivery worktree")
    worktree = Path(matching[0].worktree_path)
    if not worktree.exists():
        raise WorktreeError(
            f"{worktree} is recorded but not present, so there is nothing to update"
        )

    preflight = _sibling("governed_task_preflight")
    prepare = _sibling("prepare_delivery_branch")
    tracked, ahead, behind = preflight.main_divergence(root)
    baseline_is_current = (
        prepare.baseline_decision(tracked, ahead, behind).action == prepare.OK
    )
    dirty = tuple(
        line
        for line in _git(
            worktree, "status", "--porcelain=v1", "--untracked-files=all"
        ).stdout.splitlines()
        if line
    )

    action, detail = refresh_decision(
        baseline_is_current, dirty, behind_main(root, branch)
    )
    if action == REFRESH_BLOCKED:
        raise WorktreeError(detail)
    if action == REFRESH_CURRENT:
        return action, detail

    merged = _git(worktree, "merge", "--no-edit", "main", check=False)
    if merged.returncode != 0:
        _git(worktree, "merge", "--abort", check=False)
        raise WorktreeError(
            f"merging main into {branch} conflicts. The merge was aborted and "
            "nothing was changed. Resolve it deliberately in "
            f"{worktree}, then verify the delivery again."
        )
    return action, detail


def overlap_report(root: Path) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    records = load_ownership(ownership_path(root))
    return overlaps({record.branch: changed_paths(root, record.branch) for record in records})


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def render_status(reconciled: Sequence[Reconciled]) -> str:
    if not reconciled:
        return "No delivery worktrees are registered."
    lines = []
    for item in reconciled:
        if item.status == REGISTERED_LIVE and item.ownership:
            lines.append(
                f"  [active] {item.ownership.jira_key} {item.branch}\n"
                f"    worktree: {item.worktree_path}\n"
                f"    base:     {item.ownership.base_commit}\n"
                f"    owner:    {item.ownership.agent} since {item.ownership.created_at}"
                + (
                    f"\n    behind:   {item.behind_main} commit(s) behind main; "
                    "run refresh before integration"
                    if item.behind_main
                    else ""
                )
            )
        elif item.status == REGISTERED_MISSING and item.ownership:
            lines.append(
                f"  [missing] {item.ownership.jira_key} {item.branch}\n"
                f"    worktree: {item.worktree_path} is recorded but not present.\n"
                f"    The delivery was abandoned or cleaned up outside this tooling. "
                "Release it once you know which."
            )
        else:
            lines.append(
                f"  [unregistered] {item.branch or 'detached'}\n"
                f"    worktree: {item.worktree_path} exists with no ownership record, "
                "so no agent can be held to it."
            )
    return "\n".join(lines)


def render_overlap(found: Sequence[tuple[str, str, tuple[str, ...]]]) -> str:
    if not found:
        return "No file overlap between active deliveries."
    lines = ["File overlap between active deliveries (coordination risk, not a conflict):"]
    for first, second, shared in found:
        lines.append(f"  {first} and {second} both change:")
        lines.extend(f"    {path}" for path in shared)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    creating = commands.add_parser("create", help="claim a worktree for a delivery branch")
    creating.add_argument("branch")
    creating.add_argument("--agent", required=True, help="opaque identity of the owning agent")
    creating.add_argument("--path", type=Path, help="worktree directory; defaults beside the repository")

    commands.add_parser("list", help="show recorded ownership against live worktrees")

    releasing = commands.add_parser("release", help="release a claim")
    releasing.add_argument("branch")
    releasing.add_argument(
        "--remove", action="store_true", help="also remove the worktree directory"
    )

    commands.add_parser("overlap", help="report file overlap between active deliveries")

    refreshing = commands.add_parser(
        "refresh", help="merge current main into one delivery branch"
    )
    refreshing.add_argument("branch")

    for name in ("create", "list", "release", "overlap", "refresh"):
        commands.choices[name].add_argument(
            "--format", choices=("text", "json"), default="text"
        )

    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        root = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        print("not inside a Git working tree", file=sys.stderr)
        return 2

    try:
        if args.command == "create":
            record = create(root, args.branch, args.agent, args.path)
            print(
                json.dumps(record.__dict__, indent=2)
                if args.format == "json"
                else f"Claimed {record.branch} for {record.agent}\n"
                f"  worktree: {record.worktree_path}\n"
                f"  base:     {record.base_commit}"
            )
        elif args.command == "release":
            record = release(root, args.branch, remove=args.remove)
            print(f"Released {record.branch} ({record.worktree_path})")
        elif args.command == "refresh":
            action, detail = refresh(root, args.branch)
            print(
                f"{args.branch}: {detail}"
                if action == REFRESH_CURRENT
                else f"Merged main into {args.branch} ({detail})."
            )
        elif args.command == "overlap":
            found = overlap_report(root)
            print(
                json.dumps(
                    [
                        {"branches": [a, b], "paths": list(paths)}
                        for a, b, paths in found
                    ],
                    indent=2,
                )
                if args.format == "json"
                else render_overlap(found)
            )
        else:
            reconciled = status(root)
            print(
                json.dumps(
                    [
                        {
                            "status": item.status,
                            "branch": item.branch,
                            "worktreePath": item.worktree_path,
                            "baseCommit": item.ownership.base_commit if item.ownership else None,
                            "agent": item.ownership.agent if item.ownership else None,
                        }
                        for item in reconciled
                    ],
                    indent=2,
                )
                if args.format == "json"
                else render_status(reconciled)
            )
            if any(item.needs_attention for item in reconciled):
                return 1
    except WorktreeError as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
