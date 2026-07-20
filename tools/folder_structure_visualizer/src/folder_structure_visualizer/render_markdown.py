from __future__ import annotations

from .models import TreeNode
from .render_mermaid import render_mermaid
from .render_tree import render_tree


def render_markdown(root: TreeNode, metadata: dict) -> str:
    name = metadata.get("name", root.name)
    generated_at = metadata["generated_at"]
    root_path = metadata.get("root_path", str(root.path))
    warnings = metadata.get("warnings", [])
    color_by_depth = bool(metadata.get("color_by_depth", False))
    mermaid_direction = metadata.get("mermaid_direction", "LR")

    lines = [
        f"# Folder Structure: {name}",
        "",
        f"Generated: {generated_at}",
        "",
        "Root:",
        str(root_path),
        "",
        "## Tree",
        "",
        "```text",
        render_tree(root).rstrip(),
        "```",
        "",
        "## Mermaid Diagram",
        "",
        "```mermaid",
        render_mermaid(
            root,
            color_by_depth=color_by_depth,
            direction=mermaid_direction,
        ).rstrip(),
        "```",
    ]

    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)

    return "\n".join(lines) + "\n"
