#!/usr/bin/env python3
"""Classify what `workbench/local` still holds that integration does not.

The workbench is a capture stream, so most of what it carries has already
reached `main` by some route: cherry-picked, reshaped at hunk level, squashed,
or rewritten during review. Commit identity does not survive any of those, so
asking "is this SHA on main" answers the wrong question and reports work as
missing when its outcome is already delivered.

This module asks about content instead. A workbench commit whose paths no
longer differ between `main` and `workbench/local` has had its outcome
delivered, however it travelled. That test is cheap and settles most of the
stream.

It cannot settle the rest, because it is not commit-scoped. When a later
capture commit changes a file an earlier one also touched, the path differs
on account of the later change, and every earlier commit sharing it would be
reported as blocking. So whatever survives the cheap test is replayed onto
`main`: a cherry-pick that leaves the tree unchanged proves the outcome is
already there, whatever route it took and however the surrounding lines have
since moved. That replay is reserved for the small residual set, since
replaying the whole stream would cost far more than the question is worth.

What remains after both is small enough for a person to judge, and each
remaining item is placed in one of the reconciliation states below.

Run with no arguments for a human-readable audit, or `--format json` for the
machine-readable shape the governed preparation flow consumes.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


REPRESENTED = "represented"
IN_DELIVERY = "in-delivery"
PARKED = "parked"
SUPERSEDED = "superseded"
UNRESOLVED = "unresolved"

#: Only `unresolved` blocks. The other four are deliberate dispositions.
BLOCKING_STATES = frozenset({UNRESOLVED})
DISPOSITION_STATES = frozenset({PARKED, SUPERSEDED})

WORKBENCH_BRANCH = "workbench/local"
INTEGRATION_BRANCH = "main"


class EvidenceError(RuntimeError):
    """Raised when workbench evidence cannot be established."""


def _sibling_module(name: str):
    """Load a sibling script as a module.

    Registers it in `sys.modules` before executing it: from Python 3.14,
    `dataclasses` resolves a class's defining module through that table, and
    a decorated dataclass in an unregistered module raises instead.
    """
    import importlib.util

    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py"
    )
    if spec is None or spec.loader is None:  # pragma: no cover - packaging guard
        raise EvidenceError(f"could not load the {name} module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class WorkbenchCommit:
    """One non-merge commit present on the workbench but not on `main`."""

    sha: str
    subject: str
    paths: tuple[str, ...]
    patch_id: str | None

    @property
    def evidence_id(self) -> str:
        """Stable identity for recording a disposition against this outcome.

        Prefers the patch identity, which survives the workbench being
        rebased or re-merged from `main`; falls back to the commit SHA when
        Git cannot produce one (an empty or binary-only change).
        """
        return self.patch_id or self.sha

    @property
    def current_workbench_sha(self) -> str:
        """The current observed locator for this workbench evidence."""
        return self.sha


@dataclass(frozen=True)
class Disposition:
    """A recorded human decision to park or supersede one outcome."""

    state: str
    reason: str
    recorded_at: str

    def __post_init__(self) -> None:
        if self.state not in DISPOSITION_STATES:
            raise ValueError(
                f"disposition state must be one of {sorted(DISPOSITION_STATES)}, "
                f"got {self.state!r}"
            )
        if not self.reason.strip():
            raise ValueError("a disposition must carry a readable reason")


@dataclass(frozen=True)
class ClassifiedCommit:
    commit: WorkbenchCommit
    state: str
    rationale: str

    @property
    def blocks(self) -> bool:
        return self.state in BLOCKING_STATES


def classify_commit(
    commit: WorkbenchCommit,
    *,
    residual_paths: frozenset[str],
    delivery_patch_ids: Mapping[str, str],
    delivery_paths: Mapping[str, frozenset[str]],
    dispositions: Mapping[str, Disposition],
) -> ClassifiedCommit:
    """Place one workbench commit in a reconciliation state.

    Precedence is deliberate: observed facts outrank recorded intent. Work
    that is demonstrably delivered is `represented` even if someone once
    parked it, because the recording is then simply out of date. A recorded
    disposition only decides outcomes that are still genuinely absent.
    """
    still_differing = tuple(path for path in commit.paths if path in residual_paths)

    if commit.paths and not still_differing:
        return ClassifiedCommit(
            commit,
            REPRESENTED,
            "every path this commit touched is identical between "
            f"{INTEGRATION_BRANCH} and {WORKBENCH_BRANCH}",
        )

    if commit.patch_id and commit.patch_id in delivery_patch_ids:
        branch = delivery_patch_ids[commit.patch_id]
        return ClassifiedCommit(
            commit,
            IN_DELIVERY,
            f"an identical change is on the live delivery branch {branch}",
        )

    covering = _covering_delivery_branch(frozenset(still_differing), delivery_paths)
    if covering is not None:
        return ClassifiedCommit(
            commit,
            IN_DELIVERY,
            f"the delivery branch {covering} already changes every remaining path",
        )

    recorded = dispositions.get(commit.evidence_id)
    if recorded is not None:
        return ClassifiedCommit(
            commit, recorded.state, f"recorded {recorded.state}: {recorded.reason}"
        )

    return ClassifiedCommit(
        commit,
        UNRESOLVED,
        "absent from integration and from every live delivery branch, with no "
        "recorded disposition. Deliver, park, or supersede it: "
        + ", ".join(still_differing or commit.paths),
    )


def _covering_delivery_branch(
    remaining: frozenset[str],
    delivery_paths: Mapping[str, frozenset[str]],
) -> str | None:
    """The first live delivery branch that touches every remaining path.

    Path coverage is a weaker signal than patch identity — a branch touching
    the same file is not proof it carries the same change — so it only ever
    routes an outcome to review on that branch. It never marks one delivered.
    """
    if not remaining:
        return None
    for branch, paths in sorted(delivery_paths.items()):
        if remaining <= paths:
            return branch
    return None


def classify_all(
    commits: Iterable[WorkbenchCommit],
    *,
    residual_paths: frozenset[str],
    delivery_patch_ids: Mapping[str, str],
    delivery_paths: Mapping[str, frozenset[str]],
    dispositions: Mapping[str, Disposition],
) -> tuple[ClassifiedCommit, ...]:
    return tuple(
        classify_commit(
            commit,
            residual_paths=residual_paths,
            delivery_patch_ids=delivery_patch_ids,
            delivery_paths=delivery_paths,
            dispositions=dispositions,
        )
        for commit in commits
    )


def unresolved(classified: Iterable[ClassifiedCommit]) -> tuple[ClassifiedCommit, ...]:
    return tuple(item for item in classified if item.blocks)


# --------------------------------------------------------------------------
# Git inspection
# --------------------------------------------------------------------------


def _git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=check,
        capture_output=True,
        text=True,
    )


def branch_exists(root: Path, branch: str) -> bool:
    return _git(root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0


def residual_paths(root: Path) -> frozenset[str]:
    """Paths whose content still differs between `main` and the workbench."""
    result = _git(
        root, "diff", "--name-only", INTEGRATION_BRANCH, WORKBENCH_BRANCH, check=False
    )
    if result.returncode != 0:
        raise EvidenceError("could not diff the workbench against the integration branch")
    return frozenset(line for line in result.stdout.splitlines() if line)


def patch_id(root: Path, sha: str) -> str | None:
    """Content identity for one commit, independent of its SHA and metadata."""
    show = _git(root, "show", "--patch", "--no-color", sha, check=False)
    if show.returncode != 0 or not show.stdout.strip():
        return None
    computed = subprocess.run(
        ["git", "patch-id", "--stable"],
        cwd=root,
        input=show.stdout,
        capture_output=True,
        text=True,
        check=False,
    )
    fields = computed.stdout.split()
    return fields[0] if fields else None


def workbench_commits(root: Path) -> tuple[WorkbenchCommit, ...]:
    """Non-merge commits on the workbench that `main` does not have.

    Merges are excluded deliberately: a merge of `main` into the workbench
    introduces no workbench-authored outcome, and counting them is what made
    the raw commit count so misleading.
    """
    listed = _git(
        root,
        "rev-list",
        "--no-merges",
        "--reverse",
        f"{INTEGRATION_BRANCH}..{WORKBENCH_BRANCH}",
        check=False,
    )
    if listed.returncode != 0:
        raise EvidenceError("could not list workbench commits")

    commits: list[WorkbenchCommit] = []
    for sha in (line.strip() for line in listed.stdout.splitlines()):
        if not sha:
            continue
        subject = _git(root, "log", "-1", "--format=%s", sha, check=False).stdout.strip()
        names = _git(
            root, "show", "--name-only", "--format=", "--no-color", sha, check=False
        )
        paths = tuple(line for line in names.stdout.splitlines() if line)
        commits.append(
            WorkbenchCommit(
                sha=sha, subject=subject, paths=paths, patch_id=patch_id(root, sha)
            )
        )
    return tuple(commits)


def live_delivery_branches(root: Path, recognizer) -> tuple[str, ...]:
    """Local and remote Jira-keyed branches, excluding the workbench and main."""
    result = _git(
        root, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes/origin",
        check=False,
    )
    if result.returncode != 0:
        return ()
    seen: list[str] = []
    for raw in result.stdout.splitlines():
        name = raw.strip()
        short = name[len("origin/") :] if name.startswith("origin/") else name
        if short in {INTEGRATION_BRANCH, WORKBENCH_BRANCH} or not recognizer(short):
            continue
        if short not in seen:
            seen.append(short)
    return tuple(seen)


def delivery_evidence(
    root: Path, branches: Sequence[str]
) -> tuple[dict[str, str], dict[str, frozenset[str]]]:
    """Patch identities and changed paths for each live delivery branch."""
    patch_ids: dict[str, str] = {}
    paths: dict[str, frozenset[str]] = {}
    for branch in branches:
        listed = _git(
            root, "rev-list", "--no-merges", f"{INTEGRATION_BRANCH}..{branch}", check=False
        )
        if listed.returncode != 0:
            continue
        for sha in (line.strip() for line in listed.stdout.splitlines()):
            if not sha:
                continue
            identity = patch_id(root, sha)
            if identity and identity not in patch_ids:
                patch_ids[identity] = branch
        changed = _git(
            root, "diff", "--name-only", INTEGRATION_BRANCH, branch, check=False
        )
        if changed.returncode == 0:
            paths[branch] = frozenset(
                line for line in changed.stdout.splitlines() if line
            )
    return patch_ids, paths


# --------------------------------------------------------------------------
# Machine-local dispositions
# --------------------------------------------------------------------------


DISPOSITION_FILENAME = "workbench-dispositions.json"


def disposition_path(root: Path) -> Path:
    """Where parked and superseded decisions live for this repository.

    Machine-local by contract. A disposition is one developer's judgment
    about their own capture stream, not a repository fact, so recording it in
    version-controlled content would publish machine-specific state and make
    every other checkout inherit a decision it never made.
    """
    module = _sibling_module("local_store")
    canonical, _ = module.ensure_store(
        "workbench-dispositions", repo_root=root, project_dir=root, create=True
    )
    return canonical / DISPOSITION_FILENAME


def load_dispositions(path: Path) -> dict[str, Disposition]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
        entries = raw["dispositions"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise EvidenceError(f"disposition record at {path} is unreadable") from error
    loaded: dict[str, Disposition] = {}
    for evidence_id, item in entries.items():
        loaded[str(evidence_id)] = Disposition(
            state=str(item["state"]),
            reason=str(item["reason"]),
            recorded_at=str(item["recordedAt"]),
        )
    return loaded


def save_dispositions(path: Path, dispositions: Mapping[str, Disposition]) -> None:
    payload = {
        "schemaVersion": 1,
        "dispositions": {
            evidence_id: {
                "state": item.state,
                "reason": item.reason,
                "recordedAt": item.recorded_at,
            }
            for evidence_id, item in sorted(dispositions.items())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(path)


class UnknownEvidence(EvidenceError):
    """An evidence identity that matches no current workbench outcome."""


def resolve_evidence_id(candidate: str, known: Sequence[str]) -> str:
    """Expand an unambiguous prefix to a full evidence identity.

    Reports are readable because they abbreviate, so an abbreviation is what
    a person copies. Accepting only the full identity would record a
    disposition that silently matches nothing, which looks like success and
    behaves like a no-op.
    """
    if candidate in known:
        return candidate
    matches = [identity for identity in known if identity.startswith(candidate)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise UnknownEvidence(
            f"{candidate!r} matches no workbench-only outcome. Run this command "
            "with no arguments to list the current evidence identities."
        )
    raise UnknownEvidence(
        f"{candidate!r} is ambiguous between: " + ", ".join(sorted(matches))
    )


def record_disposition(
    path: Path, evidence_id: str, state: str, reason: str, *, now: str | None = None
) -> Disposition:
    recorded = Disposition(
        state=state,
        reason=reason,
        recorded_at=now or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    dispositions = load_dispositions(path)
    dispositions[evidence_id] = recorded
    save_dispositions(path, dispositions)
    return recorded


# --------------------------------------------------------------------------
# Delivery probe
# --------------------------------------------------------------------------


def probe_delivered(root: Path, shas: Sequence[str]) -> frozenset[str]:
    """Which of `shas` are already contained in `main`, by empty cherry-pick.

    The cheap classification asks whether paths differ, which cannot separate
    a commit's own outcome from later work on the same file. Replaying the
    commit onto integration answers directly: a cherry-pick that leaves the
    tree unchanged proves the content is already there, whatever route it
    took and however the surrounding lines have since moved.

    This is the only part of the audit that writes anything. It provisions a
    detached scratch worktree, never touches the caller's checkout, and
    always removes what it created. It is deliberately reserved for the small
    residual set, because replaying every workbench commit would cost far
    more than the question is worth.
    """
    if not shas:
        return frozenset()

    scratch = Path(tempfile.mkdtemp(prefix="aep-evidence-probe-"))
    added = _git(
        root, "worktree", "add", "--detach", str(scratch), INTEGRATION_BRANCH, check=False
    )
    if added.returncode != 0:
        raise EvidenceError(
            "could not provision a scratch worktree to probe delivery; "
            f"git said: {added.stderr.strip()}"
        )

    delivered: set[str] = set()
    try:
        for sha in shas:
            replay = _git(scratch, "cherry-pick", "--no-commit", sha, check=False)
            if replay.returncode == 0:
                staged = _git(scratch, "diff", "--cached", "--quiet", check=False)
                if staged.returncode == 0:
                    delivered.add(sha)
            _git(scratch, "cherry-pick", "--abort", check=False)
            _git(scratch, "reset", "--hard", check=False)
            _git(scratch, "clean", "-fdq", check=False)
    finally:
        _git(root, "worktree", "remove", "--force", str(scratch), check=False)
        shutil.rmtree(scratch, ignore_errors=True)
    return frozenset(delivered)


def apply_probe(
    classified: Sequence[ClassifiedCommit], delivered: frozenset[str]
) -> tuple[ClassifiedCommit, ...]:
    """Promote probed commits to `represented`, leaving every other verdict."""
    promoted = []
    for item in classified:
        if item.commit.sha in delivered:
            promoted.append(
                ClassifiedCommit(
                    item.commit,
                    REPRESENTED,
                    f"replaying this commit onto {INTEGRATION_BRANCH} changes "
                    "nothing, so its outcome is already there; the paths that "
                    "still differ carry later work",
                )
            )
        else:
            promoted.append(item)
    return tuple(promoted)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def audit(root: Path, recognizer, *, probe: bool = True) -> tuple[ClassifiedCommit, ...]:
    if not branch_exists(root, WORKBENCH_BRANCH):
        return ()
    branches = live_delivery_branches(root, recognizer)
    patch_ids, paths = delivery_evidence(root, branches)
    classified = classify_all(
        workbench_commits(root),
        residual_paths=residual_paths(root),
        delivery_patch_ids=patch_ids,
        delivery_paths=paths,
        dispositions=load_dispositions(disposition_path(root)),
    )
    if not probe:
        return classified
    residual = tuple(item.commit.sha for item in unresolved(classified))
    return apply_probe(classified, probe_delivered(root, residual))


def as_json(classified: Sequence[ClassifiedCommit]) -> str:
    return json.dumps(
        {
            "schemaVersion": 1,
            "evidence": [
                {
                    "currentWorkbenchSha": item.commit.current_workbench_sha,
                    "stablePatchId": item.commit.patch_id,
                    "evidenceId": item.commit.evidence_id,
                    "subject": item.commit.subject,
                    "paths": list(item.commit.paths),
                    "state": item.state,
                    "rationale": item.rationale,
                }
                for item in classified
            ],
            "unresolvedCount": len(unresolved(classified)),
        },
        indent=2,
    )


def as_text(classified: Sequence[ClassifiedCommit]) -> str:
    if not classified:
        return "No workbench-only commits to reconcile."
    blocking = unresolved(classified)
    counts: dict[str, int] = {}
    for item in classified:
        counts[item.state] = counts.get(item.state, 0) + 1
    lines = [
        f"{len(classified)} workbench-only commit(s): "
        + ", ".join(f"{count} {state}" for state, count in sorted(counts.items())),
    ]
    if blocking:
        lines.append("\nUnreconciled workbench evidence:")
    else:
        lines.append("\nReconciled workbench evidence:")
    for item in classified:
        lines.append(f"  {item.commit.sha[:7]} {item.commit.subject}")
        lines.append(f"  Stable patch ID: {item.commit.patch_id or '(none; SHA fallback)'}")
        lines.append(f"  Current workbench SHA: {item.commit.current_workbench_sha}")
        lines.append(f"  Evidence: {item.commit.evidence_id}")
        lines.append(f"  State: {item.state}")
        lines.append(f"  Rationale: {item.rationale}")
        if item.blocks:
            lines.append(f"  Paths: {', '.join(item.commit.paths)}")
            lines.append("  Required disposition: deliver, park, or supersede")
        lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--park",
        metavar="EVIDENCE_ID",
        help="record an evidence identity as intentionally parked",
    )
    parser.add_argument(
        "--supersede",
        metavar="EVIDENCE_ID",
        help="record an evidence identity as superseded by later work",
    )
    parser.add_argument("--reason", help="required readable reason for a disposition")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        root = Path(
            _git(Path.cwd(), "rev-parse", "--show-toplevel").stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        print("not inside a Git working tree", file=sys.stderr)
        return 2

    if args.park or args.supersede:
        if not args.reason:
            print("--park and --supersede require --reason", file=sys.stderr)
            return 2
        state = PARKED if args.park else SUPERSEDED
        preflight = _sibling_module("governed_task_preflight")
        try:
            known = [
                item.commit.evidence_id
                for item in audit(root, preflight.is_governed_delivery_branch)
            ]
            evidence_id = resolve_evidence_id(args.park or args.supersede, known)
            record_disposition(disposition_path(root), evidence_id, state, args.reason)
        except (EvidenceError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 2
        print(f"recorded {state} for {evidence_id}")
        return 0

    preflight = _sibling_module("governed_task_preflight")

    try:
        classified = audit(root, preflight.is_governed_delivery_branch)
    except EvidenceError as error:
        print(str(error), file=sys.stderr)
        return 2

    print(as_json(classified) if args.format == "json" else as_text(classified))
    return 1 if unresolved(classified) else 0


if __name__ == "__main__":
    raise SystemExit(main())
