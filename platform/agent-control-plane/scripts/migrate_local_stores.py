#!/usr/bin/env python3
"""Plan and execute the AEPI-80 machine-local store partition migration."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
import sys

import local_store


PROJECT_STORES = tuple(
    name for name, spec in local_store.STORES.items() if spec.project_scoped
)


RUN_MANIFEST = "run.json"

# experiment-runs is the only store whose pre-registration layout nests content
# directly under the store root, as <experiment>/<run-id>/, with no partition
# segment for the hash-only and slug-only probes to find. Its runs record the
# repository they ran against, so they are attributed from that record.
EVIDENCE_ATTRIBUTED_STORES = frozenset({"experiment-runs"})


@dataclass(frozen=True)
class MigrationEntry:
    store: str
    source: str
    target: str
    sourceKind: str
    fileCount: int
    collisions: tuple[str, ...]
    action: str
    reason: str = ""


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_under(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def starts_with(target: Path, prefix: Path, chunk_size: int = 1 << 20) -> bool:
    """Report whether `target` begins with the whole content of `prefix`.

    Append-only ledgers grow without bound, so both files are streamed rather
    than read whole: a long-lived session ledger should not have to fit in
    memory to be recognized as an already-migrated copy of a shorter one.
    """
    if prefix.stat().st_size > target.stat().st_size:
        return False
    with prefix.open("rb") as expected, target.open("rb") as actual:
        while block := expected.read(chunk_size):
            if actual.read(len(block)) != block:
                return False
    return True


def compatible_file(relative: str, source: Path, target: Path) -> bool:
    if relative == local_store.REPOSITORY_METADATA:
        # Generated identity metadata is intentionally regenerated for the new
        # partition and therefore supersedes legacy metadata after validation.
        return True
    if file_digest(source) == file_digest(target):
        return True
    if relative.endswith(".jsonl"):
        return starts_with(target, source)
    return False


def claimed_partition(entry: Path) -> str | None:
    """Partition the runs beneath `entry` claim, from their own manifests.

    Returns None when no run records a readable repository, or when runs
    disagree. Attribution has to come from the run's own record: treating
    unpartitioned content as belonging to whichever repository happens to be
    migrating is the silent misattribution this partitioning exists to
    prevent, and it is unrecoverable once two repositories' runs are merged.
    """
    claimed = set()
    for manifest in sorted(entry.rglob(RUN_MANIFEST)):
        try:
            recorded = json.loads(manifest.read_text(encoding="utf-8")).get("repo")
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
        if recorded:
            claimed.add(local_store.repository_identity(Path(recorded)).partition_name)
    return claimed.pop() if len(claimed) == 1 else None


def unpartitioned_entries(store_parent: Path, target: Path) -> list[Path]:
    """Directories sitting directly under the store root, outside any partition.

    A partition name always carries the `--` separator, so anything without one
    predates registration. The target itself is excluded.
    """
    if not store_parent.is_dir():
        return []
    return sorted(
        path
        for path in store_parent.iterdir()
        if path.is_dir()
        and not path.is_symlink()
        and path != target
        and "--" not in path.name
    )


def plan(repo_root: Path, namespace: Path | None = None) -> dict:
    identity = local_store.repository_identity(repo_root)
    entries: list[MigrationEntry] = []
    for name in PROJECT_STORES:
        spec = local_store.STORES[name]
        store_parent = local_store.storage_root(base=namespace, env_var=spec.env_var) / spec.dirname
        if spec.env_is_store_root and namespace is None and os.environ.get(spec.env_var or ""):
            store_parent = Path(os.environ[spec.env_var]).expanduser()
        target = store_parent / identity.partition_name
        candidates = (
            (store_parent / identity.identity_hash, "hash-only"),
            (store_parent / repo_root.name, "slug-only"),
        )
        target_files = files_under(target)
        for source, source_kind in candidates:
            if source == target or not source.exists() or source.is_symlink():
                continue
            source_files = files_under(source)
            collisions = tuple(
                relative
                for relative, path in source_files.items()
                if relative in target_files
                and not compatible_file(relative, path, target_files[relative])
            )
            already_copied = bool(source_files) and all(
                relative in target_files
                and compatible_file(relative, path, target_files[relative])
                for relative, path in source_files.items()
            )
            entries.append(
                MigrationEntry(
                    store=name,
                    source=str(source),
                    target=str(target),
                    sourceKind=source_kind,
                    fileCount=len(source_files),
                    collisions=collisions,
                    action=(
                        "blocked"
                        if collisions
                        else "already-migrated"
                        if already_copied
                        else "merge"
                    ),
                )
            )
        if name in EVIDENCE_ATTRIBUTED_STORES:
            entries.extend(
                unpartitioned_entry(name, source, target, identity)
                for source in unpartitioned_entries(store_parent, target)
            )
    return {
        "schemaVersion": 1,
        "repository": asdict(identity),
        "entries": [asdict(entry) for entry in entries],
        "blocked": any(entry.action == "blocked" for entry in entries),
    }


def unpartitioned_entry(
    store: str, source: Path, target: Path, identity
) -> MigrationEntry:
    """Classify one pre-registration directory against this repository."""
    claimed = claimed_partition(source)
    if claimed is None:
        reason = (
            f"no run manifest under {source.name} records a repository, or its "
            "runs disagree; attribute it by hand rather than by assumption"
        )
    elif claimed != identity.partition_name:
        reason = (
            f"{source.name} records repository {claimed}, not "
            f"{identity.partition_name}"
        )
    else:
        reason = ""

    destination = target / source.name
    source_files, target_files = files_under(source), files_under(destination)
    already_copied = bool(source_files) and all(
        relative in target_files
        and compatible_file(relative, path, target_files[relative])
        for relative, path in source_files.items()
    )
    return MigrationEntry(
        store=store,
        source=str(source),
        target=str(destination),
        sourceKind="unpartitioned",
        fileCount=len(source_files),
        collisions=(),
        action=(
            "blocked" if reason else "already-migrated" if already_copied else "merge"
        ),
        reason=reason,
    )


def execute(plan_value: dict) -> None:
    if plan_value["blocked"]:
        raise RuntimeError("migration plan contains content collisions")
    for entry in plan_value["entries"]:
        source, target = Path(entry["source"]), Path(entry["target"])
        target.mkdir(mode=0o700, parents=True, exist_ok=True)
        for relative, source_file in files_under(source).items():
            destination = target / relative
            if destination.exists():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination)
        source_files, target_files = files_under(source), files_under(target)
        for relative, source_file in source_files.items():
            if relative not in target_files or not compatible_file(
                relative, source_file, target_files[relative]
            ):
                raise RuntimeError(f"verification failed for {source / relative}")


def repoint_views(repo_root: Path, namespace: Path | None = None) -> None:
    """Repoint `.local-mirrors/` at the partitions this run actually migrated.

    The namespace must match the one `plan` and `execute` used. Resolving it
    from the ambient default instead would leave every view of a non-default
    namespace pointing at the pre-migration target.
    """
    identity = local_store.repository_identity(repo_root)
    for name in PROJECT_STORES:
        target = local_store.store_root(name, project_dir=repo_root, base=namespace)
        if not target.exists():
            continue
        local_store.ensure_repository_metadata(target, identity)
        view = repo_root / local_store.MIRROR_DIRNAME / name
        if view.is_symlink() and view.resolve(strict=False) != target.resolve():
            view.unlink()
        local_store.project_view(repo_root, name, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--namespace", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--format", choices=("json",), default="json")
    arguments = parser.parse_args()
    repo_root = arguments.repo_root.resolve()
    value = plan(repo_root, arguments.namespace)
    print(json.dumps(value, indent=2, sort_keys=True))
    if not arguments.execute:
        return 2 if value["blocked"] else 0
    try:
        execute(value)
        repoint_views(repo_root, arguments.namespace)
    except (OSError, RuntimeError) as error:
        print(f"migration failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
