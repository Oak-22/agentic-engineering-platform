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
import importlib.util
import json
import os
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
    return _local_store.store_root(
        "artifact-archive", project_dir=project_dir, base=archive_base
    )


def archive_file(source: Path, archive_root: Path) -> Path:
    """Copy source into archive_root, preserving its filename. Returns the copy's path."""
    archive_root.mkdir(parents=True, exist_ok=True)
    destination = archive_root / source.name
    shutil.copy2(source, destination)
    return destination


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
        destination = archive_file(source, archive_root)
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

    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"Artifact mirrored to local archive: {destination}",
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
