#!/usr/bin/env python3
"""Canonical resolution for this platform's machine-local stores.

Every store this platform writes outside the repository lives under one
provider-neutral namespace (`$XDG_DATA_HOME/aep`, default
`~/.local/share/aep`) and is exposed back into the repository as a symlink
under the gitignored `.local-mirrors/`. Both halves of that convention are
defined here, once.

This is the same port discipline
`docs/strategy/native-provider-state-ports.md` names and
`docs/strategy/session-transcript-reader.md` applies to session transcripts:
one shared definition per concern, with purpose-built consumers layered on
top, rather than each consumer re-deriving the namespace independently.

Consumers today: the public-skills store. The four stores declared below that
predate this module still compute the namespace inline; they are registered
here so the inventory is centrally true, and migrating them is a separate,
deliberate change — not something to fold into an unrelated edit.

`provider-docs` is deliberately absent: it caches under the OS temp directory
rather than this namespace, because it is refetchable scratch rather than
retained state.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_NAMESPACE = "aep"
MIRROR_DIRNAME = ".local-mirrors"


@dataclass(frozen=True)
class StoreSpec:
    """How one machine-local store resolves.

    dirname:        directory under the `aep` namespace.
    env_var:        override for the namespace base, honored before XDG.
    project_scoped: whether a per-project subdirectory is appended. Stores
                    holding per-project output are scoped; stores holding
                    content that travels across projects are not.
    summary:        one line, for the mirror README and docs.
    """

    dirname: str
    env_var: str | None
    project_scoped: bool
    summary: str


STORES: dict[str, StoreSpec] = {
    "public-skills": StoreSpec(
        dirname="skills",
        env_var="AEP_SKILLS_DIR",
        project_scoped=False,
        summary="Skills that travel across projects, not owned by any one repository.",
    ),
    "instruction-evidence": StoreSpec(
        dirname="instruction-evidence",
        env_var="AEP_INSTRUCTION_MANIFEST_DIR",
        project_scoped=True,
        summary="Per-prompt instruction-load evidence ledgers, keyed by runtime and session.",
    ),
    "show-me-captures": StoreSpec(
        dirname="show-me-captures",
        env_var="AEP_SHOW_ME_CAPTURE_DIR",
        project_scoped=True,
        summary="Rendered explanations and diagrams captured by the show-me skill.",
    ),
    "session-snapshots": StoreSpec(
        dirname="session-snapshots",
        env_var="AEP_SESSION_SNAPSHOT_DIR",
        project_scoped=True,
        summary="Reviewable text and tool-call transcripts of agent sessions.",
    ),
    "artifact-archive": StoreSpec(
        dirname="artifact-archive",
        env_var="AEP_ARTIFACT_ARCHIVE_DIR",
        project_scoped=True,
        summary="Every file published through the Artifact tool, mirrored on publish.",
    ),
}


class UnknownStore(KeyError):
    """A store name that is not in the registry."""

    def __init__(self, name: str) -> None:
        known = ", ".join(sorted(STORES))
        super().__init__(f"unknown store {name!r}; registered stores: {known}")


def storage_root(*, base: Path | None = None, env_var: str | None = None) -> Path:
    """Return the provider-neutral namespace root.

    Never nest this under a single runtime's own directory (`~/.claude/`,
    `~/.codex/`): these stores are written and read by whichever runtime is
    active, so their location cannot depend on one vendor's layout.

    `base` overrides everything and exists for testability, mirroring the
    `capture_base` / `snapshot_base` precedent already used elsewhere.
    """
    if base is not None:
        return base
    if env_var:
        configured = os.environ.get(env_var)
        if configured:
            return Path(configured).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(xdg).expanduser() / DEFAULT_NAMESPACE


def project_slug(project_dir: Path | None) -> str:
    """Directory name used to scope a per-project store."""
    return project_dir.name if project_dir else "unknown-project"


def store_root(
    name: str, *, project_dir: Path | None = None, base: Path | None = None
) -> Path:
    """Resolve one registered store's canonical directory.

    Raises UnknownStore rather than silently inventing a path, so a typo
    surfaces at the call site instead of creating an orphan directory.
    """
    try:
        spec = STORES[name]
    except KeyError:
        raise UnknownStore(name) from None

    root = storage_root(base=base, env_var=spec.env_var) / spec.dirname
    if spec.project_scoped:
        root = root / project_slug(project_dir)
    return root


def project_view(repo_root: Path, name: str, canonical_root: Path) -> Path:
    """Expose canonical_root inside the repository at `.local-mirrors/<name>`.

    Returns the view path when it resolves to canonical_root, otherwise
    canonical_root itself — so a pre-existing link pointing elsewhere is
    reported rather than silently replaced.

    `.local-mirrors/` is gitignored: this creates a second access path to the
    same files for humans and agents working inside the repository. It does
    not make the content tracked, shared, or discoverable by any runtime's
    native skill or instruction loading.
    """
    if name not in STORES:
        raise UnknownStore(name)

    view = repo_root / MIRROR_DIRNAME / name
    view.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not view.exists() and not view.is_symlink():
        view.symlink_to(canonical_root, target_is_directory=True)
    if view.resolve(strict=False) == canonical_root.resolve():
        return view
    return canonical_root


def ensure_store(
    name: str,
    *,
    repo_root: Path | None = None,
    project_dir: Path | None = None,
    base: Path | None = None,
    create: bool = False,
) -> tuple[Path, Path | None]:
    """Resolve a store and, when repo_root is given, its repo-local view.

    Returns (canonical_root, view_or_None). `create` makes the canonical
    directory; the view is only linked when the directory it points at can be
    resolved, so a store that has never been written stays unlinked rather
    than leaving a dangling symlink behind.
    """
    canonical = store_root(name, project_dir=project_dir, base=base)
    if create:
        canonical.mkdir(parents=True, exist_ok=True)
    if repo_root is None:
        return canonical, None
    return canonical, project_view(repo_root, name, canonical)
