from __future__ import annotations

from .models import TreeNode


def render_tree(root: TreeNode) -> str:
    lines = [_label(root)]
    _append_children(lines, root.children, "")
    return "\n".join(lines) + "\n"


def _append_children(lines: list[str], children: list[TreeNode], prefix: str) -> None:
    for index, child in enumerate(children):
        is_last = index == len(children) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{_label(child)}")
        extension = "    " if is_last else "│   "
        _append_children(lines, child.children, prefix + extension)


def _label(node: TreeNode) -> str:
    if node.description:
        return f"{node.name} — {node.description}"
    return node.name
