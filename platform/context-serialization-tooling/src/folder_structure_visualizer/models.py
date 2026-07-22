from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TreeNode:
    name: str
    path: Path
    is_dir: bool
    depth: int
    description: str | None = None
    children: list["TreeNode"] = field(default_factory=list)


@dataclass
class ScanResult:
    root: TreeNode
    warnings: list[str] = field(default_factory=list)
