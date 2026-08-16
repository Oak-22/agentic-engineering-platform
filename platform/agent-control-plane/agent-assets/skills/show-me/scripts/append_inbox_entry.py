#!/usr/bin/env python3
"""Append show-me captures as new cells in the Engineering Knowledge Base inbox notebook.

The canonical Engineering Knowledge Base (EKB) is a separate, standalone
repository, adopted per-project via an ignored symlink named
`engineering-knowledge-base` at the project root. This module resolves that
symlink and appends new learning entries to its inbox notebook, EKB's own
documented canonical intake point — distinct from resolve_capture_root.py's
machine-local, per-runtime-neutral viewing cache.
"""

from __future__ import annotations

import json
from pathlib import Path


EKB_SYMLINK_NAME = "engineering-knowledge-base"
INBOX_NOTEBOOK_RELATIVE_PATH = Path("inbox") / "engineering-learning-dump.ipynb"


def resolve_ekb_root(*, repo_root: Path) -> Path | None:
    """Return the real EKB repo path via <repo_root>/engineering-knowledge-base,
    or None if this project hasn't adopted EKB (missing symlink, broken
    symlink, or a target that doesn't structurally look like EKB). Not every
    project adopts EKB, so this is an expected outcome, not an error."""
    link = repo_root / EKB_SYMLINK_NAME
    if not link.is_symlink() and not link.is_dir():
        return None
    try:
        resolved = link.resolve(strict=True)
    except OSError:
        return None
    if not (resolved / INBOX_NOTEBOOK_RELATIVE_PATH).is_file():
        return None
    return resolved


def _cell_source_lines(body: str) -> list[str]:
    """Split body into nbformat's per-line source list: every line but the
    last keeps its trailing newline, matching the notebook's existing cells."""
    lines = body.splitlines(keepends=True)
    return lines if lines else [""]


def build_entry_cell(*, slug: str, title: str, body_markdown: str) -> dict:
    """Return a new nbformat markdown cell dict for one show-me capture.

    `id` uses the show-me topic slug, matching the notebook's dominant
    hand-authored convention (human-readable kebab-case ids on most cells,
    rather than the random-hex ids on a few others). The heading is folded
    into the source as '## <title>' followed by body_markdown, matching the
    dominant H2-per-entry convention."""
    header = f"## {title}\n\n"
    return {
        "cell_type": "markdown",
        "id": slug,
        "metadata": {},
        "source": _cell_source_lines(header + body_markdown.rstrip("\n")),
    }


def append_inbox_entry(
    *, ekb_root: Path, slug: str, title: str, body_markdown: str
) -> Path:
    """Insert a new markdown cell at index 1 of the EKB inbox notebook
    (immediately after the fixed title cell), preserving all other notebook
    structure exactly. Returns the notebook path written.

    No dedup: every invocation appends exactly one new cell. The inbox is an
    append-only scratchpad by its own design — running this twice for the
    same topic is expected to produce two cells, not one."""
    notebook_path = ekb_root / INBOX_NOTEBOOK_RELATIVE_PATH
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    notebook["cells"].insert(1, build_entry_cell(slug=slug, title=title, body_markdown=body_markdown))
    notebook_path.write_text(
        json.dumps(notebook, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return notebook_path
