#!/usr/bin/env python3
"""Resolve the developer's own cross-project skills, with no platform involved.

These skills are authored by the developer and travel between projects. This
platform mirrors them; it did not produce them and does not own them. That
distinction has a practical consequence: they must resolve in a checkout where
this platform is not installed at all, so this module depends on nothing but
the standard library and must never import from the rest of the control plane.

The rule is deliberately small enough to reimplement in a shell:

    echo "${AGENT_SKILLS_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/agent-skills}"

Resolution only. Creating, editing, or deleting a skill stays an explicit act
by whoever owns the content — nothing here writes, so no agent can acquire a
write path merely by asking where the skills live.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


#: Provider-neutral, and deliberately not this platform's namespace. Nesting
#: developer content under `aep/` is what made the platform look like its
#: owner; nesting it under a runtime's directory would be worse still.
NAMESPACE = "agent-skills"
ENV_VAR = "AGENT_SKILLS_DIR"

SHELL_EQUIVALENT = (
    '"${AGENT_SKILLS_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/agent-skills}"'
)


def skills_root(*, base: Path | None = None) -> Path:
    """Where the developer's cross-project skills live.

    Precedence is the explicit override, then XDG, then the XDG default. No
    repository is consulted: these skills belong to the developer, not to
    whichever checkout happens to be open.
    """
    if base is not None:
        return base
    configured = os.environ.get(ENV_VAR)
    if configured:
        return Path(configured).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(xdg).expanduser() / NAMESPACE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--shell",
        action="store_true",
        help="print the equivalent shell expansion instead of the resolved path",
    )
    parser.add_argument(
        "--exists",
        action="store_true",
        help="exit 1 when the resolved directory does not exist",
    )
    args = parser.parse_args(argv)

    if args.shell:
        print(SHELL_EQUIVALENT)
        return 0

    root = skills_root()
    print(root)
    return 1 if args.exists and not root.is_dir() else 0


if __name__ == "__main__":
    sys.exit(main())
