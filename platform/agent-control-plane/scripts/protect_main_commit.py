#!/usr/bin/env python3
"""Reject ordinary local commits while the integration branch is checked out."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


INTEGRATION_BRANCH = "main"
BYPASS_VARIABLE = "AEP_ALLOW_MAIN_COMMIT"


class InspectionError(RuntimeError):
    """Raised when the current branch cannot be established safely."""


def current_branch(cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise InspectionError("Git is unavailable") from error

    if result.returncode == 0:
        return result.stdout.strip()
    if result.returncode == 1:
        return None

    detail = result.stderr.strip() or "unknown Git inspection failure"
    raise InspectionError(detail)


def should_block(branch: str | None, bypass_value: str | None) -> bool:
    return branch == INTEGRATION_BRANCH and bypass_value != "1"


def main() -> int:
    try:
        branch = current_branch(Path.cwd())
    except InspectionError as error:
        print(f"Can't verify the current branch: {error}", file=sys.stderr)
        return 2

    if not should_block(branch, os.environ.get(BYPASS_VARIABLE)):
        return 0

    print(
        "Commit blocked: main is the clean integration base. Capture exploratory "
        "work on a private workbench or commit governed work on its Jira-keyed "
        "delivery branch.\n\n"
        "For an explicitly authorized exceptional commit to main, rerun the commit "
        f"with {BYPASS_VARIABLE}=1.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
