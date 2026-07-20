from pathlib import Path

from folder_structure_visualizer.render_markdown import render_markdown
from folder_structure_visualizer.scanner import scan_directory


def test_markdown_includes_title_root_tree_mermaid_and_warnings(tmp_path: Path) -> None:
    (tmp_path / "00 Inbox").mkdir()
    result = scan_directory(tmp_path)
    markdown = render_markdown(
        result.root,
        {
            "name": "Demo",
            "generated_at": "2026-06-16 15:30",
            "root_path": str(tmp_path.resolve()),
            "warnings": ["Skipped inaccessible folder: /private/demo"],
        },
    )

    assert "# Folder Structure: Demo" in markdown
    assert "Generated: 2026-06-16 15:30" in markdown
    assert str(tmp_path.resolve()) in markdown
    assert "```text" in markdown
    assert "├── 00 Inbox" in markdown or "└── 00 Inbox" in markdown
    assert "```mermaid" in markdown
    assert "graph LR" in markdown
    assert "## Warnings" in markdown
    assert "- Skipped inaccessible folder: /private/demo" in markdown
