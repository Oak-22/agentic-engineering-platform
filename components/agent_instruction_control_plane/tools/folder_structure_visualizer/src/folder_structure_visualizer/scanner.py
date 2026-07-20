from __future__ import annotations

import re
from pathlib import Path

from .models import ScanResult, TreeNode

DEFAULT_ARCHIVE_TERMS = (
    "archive",
    "archives",
    "archived",
    "old",
    "backup",
    "backups",
    "deprecated",
    "zz archive",
    "99 archive",
)

DEFAULT_SYSTEM_IGNORES = (
    ".DS_Store",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
)


def scan_directory(
    root: Path | str,
    *,
    max_depth: int | None = None,
    include_files: bool = False,
    include_hidden: bool = False,
    include_archives: bool = False,
    ignore_patterns: list[str] | None = None,
    annotations: dict[str, str] | None = None,
) -> ScanResult:
    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Root path does not exist: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Root path is not a directory: {root_path}")
    if max_depth is not None and max_depth < 0:
        raise ValueError("--max-depth must be 0 or greater")

    warnings: list[str] = []
    custom_patterns = tuple(pattern.casefold() for pattern in (ignore_patterns or []) if pattern)
    system_patterns = tuple(pattern.casefold() for pattern in DEFAULT_SYSTEM_IGNORES)
    archive_patterns = tuple(pattern.casefold() for pattern in DEFAULT_ARCHIVE_TERMS)
    node_annotations = annotations or {}

    def should_ignore(path: Path) -> bool:
        name = path.name
        normalized = name.casefold()
        if not include_hidden and name.startswith("."):
            return True
        if any(pattern in normalized for pattern in system_patterns):
            return True
        if not include_archives and _matches_archive_term(normalized, archive_patterns):
            return True
        return any(pattern in normalized for pattern in custom_patterns)

    def build_node(path: Path, depth: int) -> TreeNode:
        relative_path = "." if path == root_path else path.relative_to(root_path).as_posix()
        node = TreeNode(
            name=path.name,
            path=path,
            is_dir=path.is_dir(),
            depth=depth,
            description=node_annotations.get(relative_path),
        )
        if not node.is_dir or (max_depth is not None and depth >= max_depth):
            return node

        try:
            children = list(path.iterdir())
        except PermissionError:
            warnings.append(f"Skipped inaccessible folder: {path}")
            return node
        except OSError as exc:
            warnings.append(f"Skipped unreadable folder: {path} ({exc})")
            return node

        visible_children = [child for child in children if not should_ignore(child)]
        dirs: list[Path] = []
        files: list[Path] = []
        for child in visible_children:
            try:
                if child.is_dir():
                    dirs.append(child)
                elif include_files and child.is_file():
                    files.append(child)
            except PermissionError:
                warnings.append(f"Skipped inaccessible path: {child}")
            except OSError as exc:
                warnings.append(f"Skipped unreadable path: {child} ({exc})")

        sorted_children = sorted(dirs, key=_sort_key) + sorted(files, key=_sort_key)
        node.children = [build_node(child, depth + 1) for child in sorted_children]
        return node

    root_node = build_node(root_path, 0)
    if annotations is not None:
        for node in _walk(root_node):
            if node.description is None:
                relative_path = "." if node.path == root_path else node.path.relative_to(root_path).as_posix()
                warnings.append(f"Missing semantic annotation: {relative_path}")

    return ScanResult(root=root_node, warnings=warnings)


def _sort_key(path: Path) -> str:
    return path.name.casefold()


def _walk(node: TreeNode):
    yield node
    for child in node.children:
        yield from _walk(child)


def _matches_archive_term(normalized_name: str, archive_patterns: tuple[str, ...]) -> bool:
    for pattern in archive_patterns:
        if pattern == "old":
            if re.search(r"(^|[^a-z0-9])old([^a-z0-9]|$)", normalized_name):
                return True
            continue
        if pattern in normalized_name:
            return True
    return False
