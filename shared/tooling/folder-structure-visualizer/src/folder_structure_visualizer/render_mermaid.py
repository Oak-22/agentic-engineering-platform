from __future__ import annotations

import json
from html import escape

from .models import TreeNode


VALID_DIRECTIONS = {"TD", "LR"}


def render_mermaid(root: TreeNode, color_by_depth: bool = False, direction: str = "LR") -> str:
    direction = direction.upper()
    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"Unsupported Mermaid direction: {direction}")

    nodes: list[TreeNode] = []
    edges: list[tuple[int, int]] = []
    _collect(root, nodes, edges)

    lines = [f"graph {direction}"]
    for index, node in enumerate(nodes):
        lines.append(f"    node_{index}[{_escape_label(_node_label(node))}]")
    if edges:
        lines.append("")
    for parent_index, child_index in edges:
        lines.append(f"    node_{parent_index} --> node_{child_index}")

    if color_by_depth:
        lines.append("")
        for index, node in enumerate(nodes):
            lines.append(f"    class node_{index} {_depth_class(node.depth)}")
        lines.extend(
            [
                "",
                "    classDef depth0 fill:#263238,color:#ffffff,stroke:#102027,stroke-width:2px",
                "    classDef depth1 fill:#e3f2fd,color:#0d47a1,stroke:#90caf9",
                "    classDef depth2 fill:#e8f5e9,color:#1b5e20,stroke:#a5d6a7",
                "    classDef depth3 fill:#fff8e1,color:#ff6f00,stroke:#ffe082",
                "    classDef depth4plus fill:#f3e5f5,color:#4a148c,stroke:#ce93d8",
            ]
        )

    return "\n".join(lines) + "\n"


def _collect(root: TreeNode, nodes: list[TreeNode], edges: list[tuple[int, int]]) -> None:
    parent_index = len(nodes)
    nodes.append(root)
    for child in root.children:
        child_index = len(nodes)
        edges.append((parent_index, child_index))
        _collect(child, nodes, edges)


def _escape_label(label: str) -> str:
    return json.dumps(label, ensure_ascii=False)


def _node_label(node: TreeNode) -> str:
    if node.description:
        return f"{escape(node.name)}<br/><small>{escape(node.description)}</small>"
    return node.name


def _depth_class(depth: int) -> str:
    if depth <= 3:
        return f"depth{depth}"
    return "depth4plus"
