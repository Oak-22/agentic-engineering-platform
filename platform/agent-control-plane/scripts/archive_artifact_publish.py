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
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


DEFAULT_ARCHIVE_DIRNAME = "artifact-archive"


def resolve_archive_root(
    *, project_dir: Path | None, archive_base: Path | None = None
) -> Path:
    """Return the per-project archive directory, outside the repository."""
    base = archive_base or Path(
        os.environ.get("AEP_ARTIFACT_ARCHIVE_DIR", Path.home() / ".claude")
    ).expanduser()
    project_slug = project_dir.name if project_dir else "unknown-project"
    return base / DEFAULT_ARCHIVE_DIRNAME / project_slug


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
