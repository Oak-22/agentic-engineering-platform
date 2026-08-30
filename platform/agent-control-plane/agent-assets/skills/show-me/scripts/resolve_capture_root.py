#!/usr/bin/env python3
"""Resolve and write show-me captures into a machine-local viewing cache.

Captures are written once, to a machine-local, per-project directory outside
the repository, so they survive across sessions without ever being tracked.
A repo-local symlink view exposes the same files from inside the repository
for convenience, mirroring instruction_manifest_hook.py's project_view().

This cache is deliberately named and structured to stay distinct from the
Engineering Knowledge Base (EKB, see append_inbox_entry.py) — EKB is a
separate, standalone repository that consumes this cache downstream, not a
destination this module writes to.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path
import shutil
import sys


def _load_local_store():
    """Import local_store.py by path; this skill lives under agent-assets/,
    the store definition under scripts/ — neither is an installed package."""
    cached = sys.modules.get("local_store")
    if cached is not None:
        return cached
    store_path = (
        Path(__file__).resolve().parents[4] / "scripts" / "local_store.py"
    )
    spec = importlib.util.spec_from_file_location("local_store", store_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load local_store at {store_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_local_store = _load_local_store()
DEFAULT_CAPTURE_DIRNAME = _local_store.STORES["show-me-captures"].dirname


def resolve_capture_root(
    *, project_dir: Path | None, capture_base: Path | None = None
) -> Path:
    """Return the per-project capture directory, outside the repository.

    Resolved through local_store.py's single StoreSpec definition, since
    show-me runs under Claude Code, Codex, and Copilot alike — never nest
    this under a single provider's own directory (e.g. `~/.claude/`)."""
    if project_dir is None:
        raise ValueError("project_dir is required for show-me capture placement")
    root, _ = _local_store.ensure_store(
        "show-me-captures", project_dir=project_dir, base=capture_base, create=True
    )
    return root


def capture_filename(*, slug: str, runtime: str, date: dt.date | None = None) -> str:
    """Return '<date>-show-me-<runtime>-<slug>' with no extension.

    The caller appends .md/.html. Date stays first for chronological sorting,
    ``show-me`` identifies the producing workflow, and runtime identifies the
    originating model/runtime without requiring the file to be opened.
    """
    day = (date or dt.date.today()).isoformat()
    return f"{day}-show-me-{runtime}-{slug}"


def _dedupe(capture_root: Path, stem: str, extension: str) -> Path:
    candidate = capture_root / f"{stem}.{extension}"
    counter = 2
    while candidate.exists():
        candidate = capture_root / f"{stem}-{counter}.{extension}"
        counter += 1
    return candidate


def write_capture(
    content: str, *, capture_root: Path, stem: str, extension: str
) -> Path:
    """Write content to capture_root/<stem>.<extension>, de-duplicating on
    name collision by appending -2, -3, ... before the extension. Returns
    the written path."""
    capture_root.mkdir(parents=True, exist_ok=True)
    destination = _dedupe(capture_root, stem, extension)
    destination.write_text(content, encoding="utf-8")
    return destination


def copy_capture(source: Path, *, capture_root: Path, stem: str) -> Path:
    """Copy an already-published file (e.g. an Artifact HTML file) into
    capture_root, reusing stem and source's own extension, de-duplicating
    the same way as write_capture."""
    capture_root.mkdir(parents=True, exist_ok=True)
    extension = source.suffix.lstrip(".")
    destination = _dedupe(capture_root, stem, extension)
    shutil.copy2(source, destination)
    return destination


def write_latest_pointer(destination: Path, *, capture_root: Path) -> Path:
    """Overwrite capture_root/latest.<ext> as a relative symlink to
    destination, so a stable URL (e.g. a bookmarked file:// address in an
    integrated browser) always resolves to the most recent capture of that
    extension without the filename needing to be re-typed or re-copied.

    destination must already live directly inside capture_root."""
    pointer = capture_root / f"latest{destination.suffix}"
    if pointer.is_symlink() or pointer.exists():
        pointer.unlink()
    pointer.symlink_to(destination.name)
    return pointer


def capture_project_view(repo_root: Path, canonical_root: Path) -> Path:
    """Return a repo-local view of canonical_root, creating a symlink at
    <repo_root>/.local-mirrors/show-me-captures if one doesn't exist yet.

    Named after this skill specifically, not the generic
    engineering-knowledge-base destination, because that destination is
    designed to hold multiple future producers (see
    platform/developer-learning-retrieval/docs/design.md) — a mirror scoped to
    the producer stays unambiguous as more of them are added later.

    Falls back to canonical_root if a view already exists at that path and
    points elsewhere. No content is written here — this only exposes a
    second access path to the same files.
    """
    return _local_store.project_view(repo_root, "show-me-captures", canonical_root)
