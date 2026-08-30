#!/usr/bin/env python3
"""Mirror a just-published Claude Artifact file to a durable local archive.

Session scratchpad directories are ephemeral. This hook runs after the
Claude Code Artifact tool publishes or republishes a file and copies it to a
local, untracked archive path so it survives session end without ever writing
into this repository. It is intentionally Claude-specific: Codex has no
equivalent Artifact event registration.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
from typing import Any


def _load_local_store():
    """Import local_store.py by path; scripts/ is not an installed package."""
    cached = sys.modules.get("local_store")
    if cached is not None:
        return cached
    store_path = Path(__file__).resolve().parent / "local_store.py"
    spec = importlib.util.spec_from_file_location("local_store", store_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load local_store at {store_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_local_store = _load_local_store()
DEFAULT_ARCHIVE_DIRNAME = _local_store.STORES["artifact-archive"].dirname


def resolve_archive_root(
    *, project_dir: Path | None, archive_base: Path | None = None
) -> Path:
    """Return the per-project archive directory, outside the repository.

    Resolved through local_store.py's single StoreSpec definition — see that
    module for why the namespace stays provider-neutral rather than nested
    under `~/.claude/`, even though this feature is Claude-specific today."""
    if project_dir is None:
        raise ValueError("project_dir is required for artifact archive placement")
    root, _ = _local_store.ensure_store(
        "artifact-archive", project_dir=project_dir, base=archive_base, create=True
    )
    return root


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def superseded_name(current: Path) -> str:
    """Name for the version being displaced, stamped with when it was archived.

    The existing file's own mtime is the right stamp: it records when that
    version was the published one, which is what a reader wants to know. The
    wall clock at the moment it is displaced would say only when a newer
    version arrived.
    """
    stamped = datetime.fromtimestamp(current.stat().st_mtime, timezone.utc)
    return f"{current.stem}.{stamped.strftime('%Y%m%dT%H%M%SZ')}{current.suffix}"


def preserve_existing(destination: Path) -> Path | None:
    """Move the archived version aside so a republish cannot destroy it.

    Returns the path it was preserved at, or None when there was nothing to
    preserve. A second-level timestamp can repeat, so a repeated name is
    accepted only when it already holds identical bytes; otherwise a counter
    disambiguates rather than one version overwriting another.
    """
    if not destination.exists():
        return None
    archived = destination.parent / superseded_name(destination)
    if archived.exists():
        if file_digest(archived) == file_digest(destination):
            return archived
        stem, suffix = archived.stem, archived.suffix
        counter = 2
        while (candidate := archived.parent / f"{stem}-{counter}{suffix}").exists():
            counter += 1
        archived = candidate
    shutil.move(destination, archived)
    return archived


def archive_file(source: Path, archive_root: Path) -> tuple[Path, Path | None]:
    """Copy source into archive_root under its own filename.

    The published name always holds the current version, so existing archive
    paths stay resolvable. Any version it displaces is preserved alongside it
    rather than overwritten: republishing from one local path is how an
    artifact keeps its URL, so that path is reused routinely and the archive
    would otherwise retain only the most recent publish.

    Returns (current, superseded_or_None). Republishing identical content
    supersedes nothing.
    """
    archive_root.mkdir(parents=True, exist_ok=True)
    destination = archive_root / source.name
    if destination.exists() and file_digest(destination) == file_digest(source):
        return destination, None
    superseded = preserve_existing(destination)
    shutil.copy2(source, destination)
    return destination, superseded


def handle(payload: dict[str, Any], *, project_dir: Path | None) -> dict[str, Any] | None:
    event_name = str(payload.get("hook_event_name") or "")
    if event_name and event_name != "PostToolUse":
        return None
    if str(payload.get("tool_name") or "") != "Artifact":
        return None

    file_path = str((payload.get("tool_input") or {}).get("file_path") or "")
    if not file_path:
        return None
    source = Path(file_path)
    if not source.is_file():
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"Artifact archive skipped: {source} no longer exists."
                ),
            }
        }

    archive_root = resolve_archive_root(project_dir=project_dir)
    try:
        destination, superseded = archive_file(source, archive_root)
    except OSError as error:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"Artifact archive failed for {source} "
                    f"({type(error).__name__}: {error})."
                ),
            }
        }

    context = f"Artifact mirrored to local archive: {destination}"
    if superseded is not None:
        context += f" (previous version kept as {superseded.name})"
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    project_dir_env = os.environ.get("CLAUDE_PROJECT_DIR")
    project_dir = Path(project_dir_env) if project_dir_env else None
    try:
        payload = json.load(sys.stdin)
        output = handle(payload, project_dir=project_dir)
        if output is not None:
            print(json.dumps(output))
    except (json.JSONDecodeError, OSError, TypeError, ValueError) as error:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": (
                            f"Artifact archive hook failed to run ({type(error).__name__})."
                        ),
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
