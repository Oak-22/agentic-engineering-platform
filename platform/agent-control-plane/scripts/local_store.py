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

Consumers today: `instruction_manifest_hook.py`,
`archive_artifact_publish.py`, `resolve_capture_root.py`,
`render_session_snapshot.py`, and the view-only public-skills store.

`provider-docs` is deliberately absent: it caches under the OS temp directory
rather than this namespace, because it is refetchable scratch rather than
retained state.
"""

from __future__ import annotations

import os
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_NAMESPACE = "aep"
MIRROR_DIRNAME = ".local-mirrors"
IDENTITY_HASH_LENGTH = 24
REPOSITORY_METADATA = "repository.json"
REPOSITORY_METADATA_SCHEMA_VERSION = 1


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
    env_is_store_root: bool = False


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
        env_is_store_root=True,
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


@dataclass(frozen=True)
class RepositoryIdentity:
    """Stable identity plus the readable, non-authoritative display name."""

    readable_name: str
    repository_id: str
    identity_hash: str
    partition_name: str
    normalized_remote: str | None
    workspace_path: str


def _git_output(root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *arguments], cwd=root, check=False, capture_output=True, text=True
        )
    except OSError:
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


DEFAULT_REMOTE_PORTS = {"ssh": "22", "https": "443", "http": "80", "git": "9418"}


def canonical_authority(scheme: str, authority: str) -> str:
    """Lowercase the host, keeping a port only when it identifies the server.

    Two instances on one host behind different ports are different
    repositories, so a non-default port belongs in the identity. It is
    bracketed to keep the SCP-form ':' separator unambiguous and to guarantee
    a ported identity can never collide with a portless one. A default or
    absent port renders exactly as before, so existing partitions keep their
    hashes.
    """
    if authority.startswith("["):
        # IPv6 literal, which carries its own brackets and may be followed
        # by :port. Splitting on the first ':' here would truncate the address.
        literal, _, remainder = authority.partition("]")
        host, port = f"{literal}]", remainder.lstrip(":")
    else:
        host, _, port = authority.partition(":")
    host = host.lower()
    if port and port != DEFAULT_REMOTE_PORTS.get(scheme.lower()):
        return f"[{host}:{port}]"
    return host


def normalize_remote(remote: str) -> str:
    """Return a credential-free repository identity for common Git URL forms."""
    value = remote.strip()
    if not value:
        return ""
    # SCP-like SSH form: user@host:owner/repo.git. The host needs at least two
    # characters: a single letter before ':' is a Windows drive, so `C:/repo`
    # is a local path and must not be read as a host named `c`.
    match = re.match(r"^(?:[^@/]+@)?([^:/]{2,}):(.+)$", value)
    if match and "://" not in value:
        host, path = match.groups()
        clean_path = path.removesuffix(".git").strip("/")
        return f"git@{host.lower()}:{clean_path}.git"
    match = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*)://([^/]+)/(.*)$", value)
    if match:
        scheme, authority, path = match.groups()
        host = canonical_authority(scheme, authority.rsplit("@", 1)[-1])
        clean_path = path.removesuffix(".git").strip("/")
        return f"git@{host}:{clean_path}.git"
    return value.removesuffix(".git").rstrip("/")


def normalize_readable_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return normalized.lower() or "unknown-project"


def repository_identity(project_dir: Path) -> RepositoryIdentity:
    root = project_dir.expanduser().resolve()
    remote = normalize_remote(_git_output(root, "config", "--get", "remote.origin.url"))
    if remote:
        repository_id = remote
        raw_name = remote.rsplit("/", 1)[-1].removesuffix(".git")
    else:
        # A path-derived fallback cannot unify separate no-remote clones, but it
        # is deterministic and, unlike a directory-name slug, does not silently
        # alias unrelated repositories with the same basename.
        repository_id = f"local:{root.as_posix()}"
        raw_name = root.name
    readable = normalize_readable_name(raw_name)
    digest = hashlib.sha256(repository_id.encode("utf-8")).hexdigest()[:IDENTITY_HASH_LENGTH]
    return RepositoryIdentity(
        readable_name=readable,
        repository_id=repository_id,
        identity_hash=digest,
        partition_name=f"{readable}--{digest}",
        normalized_remote=remote or None,
        workspace_path=str(root),
    )


def repository_metadata(identity: RepositoryIdentity, *, now: str | None = None) -> dict[str, Any]:
    observed = now or datetime.now(timezone.utc).isoformat()
    return {
        "schemaVersion": REPOSITORY_METADATA_SCHEMA_VERSION,
        "readableRepositoryName": identity.readable_name,
        "repositoryId": identity.repository_id,
        "repositoryIdentityHash": identity.identity_hash,
        "partitionName": identity.partition_name,
        "normalizedRemote": identity.normalized_remote,
        "lastObservedWorkspacePath": identity.workspace_path,
        "lastObservedAt": observed,
    }


def write_json_atomically(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # A failing os.replace would otherwise strand the temporary beside the
    # store; unlink is a no-op once the replace has consumed it.
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.",
            suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def ensure_repository_metadata(root: Path, identity: RepositoryIdentity) -> Path:
    path = root / REPOSITORY_METADATA
    current: dict[str, Any] = {}
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    value = repository_metadata(identity)
    value["createdAt"] = current.get("createdAt", value["lastObservedAt"])
    write_json_atomically(path, value)
    return path


def validate_repository_metadata(root: Path, identity: RepositoryIdentity) -> list[str]:
    errors: list[str] = []
    if root.name != identity.partition_name:
        errors.append(
            f"partition {root.name!r} does not match canonical {identity.partition_name!r}"
        )
    try:
        value = json.loads((root / REPOSITORY_METADATA).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"repository metadata is unreadable: {error}"]
    expected = {
        "readableRepositoryName": identity.readable_name,
        "repositoryId": identity.repository_id,
        "repositoryIdentityHash": identity.identity_hash,
        "partitionName": identity.partition_name,
        "normalizedRemote": identity.normalized_remote,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            errors.append(f"metadata {key} does not match canonical repository identity")
    return errors


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

    configured = os.environ.get(spec.env_var) if spec.env_var else None
    if base is None and configured and spec.env_is_store_root:
        root = Path(configured).expanduser()
    else:
        root = storage_root(base=base, env_var=spec.env_var) / spec.dirname
    if spec.project_scoped:
        if project_dir is None:
            raise ValueError(f"project_dir is required for project-scoped store {name!r}")
        root = root / repository_identity(project_dir).partition_name
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
        if STORES[name].project_scoped:
            assert project_dir is not None
            ensure_repository_metadata(canonical, repository_identity(project_dir))
    if repo_root is None:
        return canonical, None
    return canonical, project_view(repo_root, name, canonical)
