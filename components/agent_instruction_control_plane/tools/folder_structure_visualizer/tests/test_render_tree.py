from pathlib import Path

from folder_structure_visualizer.render_tree import render_tree
from folder_structure_visualizer.scanner import scan_directory


def test_render_tree_uses_standard_tree_characters(tmp_path: Path) -> None:
    (tmp_path / "00 Inbox").mkdir()
    (tmp_path / "01 Branding" / "Brand Assets").mkdir(parents=True)
    (tmp_path / "01 Branding" / "Logo Design").mkdir()

    tree = render_tree(scan_directory(tmp_path).root)

    assert f"{tmp_path.name}\n" in tree
    assert "├── 00 Inbox" in tree
    assert "└── 01 Branding" in tree
    assert "    ├── Brand Assets" in tree
    assert "    └── Logo Design" in tree


def test_render_tree_places_one_description_beside_each_annotated_node(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    root = scan_directory(
        tmp_path,
        annotations={".": "Project root.", "src": "Application source."},
    ).root

    tree = render_tree(root)

    assert f"{tmp_path.name} — Project root." in tree
    assert "└── src — Application source." in tree
