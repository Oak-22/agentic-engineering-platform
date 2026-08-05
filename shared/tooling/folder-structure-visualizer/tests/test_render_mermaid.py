from pathlib import Path

from folder_structure_visualizer.render_mermaid import render_mermaid
from folder_structure_visualizer.scanner import scan_directory


def test_mermaid_output_contains_stable_node_ids_and_edges(tmp_path: Path) -> None:
    (tmp_path / "00 Inbox").mkdir()
    (tmp_path / "01 Branding" / "Logo Design").mkdir(parents=True)

    mermaid = render_mermaid(scan_directory(tmp_path).root)

    assert "graph LR" in mermaid
    assert f'node_0["{tmp_path.name}"]' in mermaid
    assert 'node_1["00 Inbox"]' in mermaid
    assert "node_0 --> node_1" in mermaid
    assert "node_2 --> node_3" in mermaid


def test_mermaid_can_render_top_down_direction(tmp_path: Path) -> None:
    (tmp_path / "00 Inbox").mkdir()

    mermaid = render_mermaid(scan_directory(tmp_path).root, direction="TD")

    assert "graph TD" in mermaid


def test_mermaid_escapes_special_characters_and_unicode(tmp_path: Path) -> None:
    (tmp_path / 'Client "A" & Brand-Logo (v2) 🚀').mkdir()

    mermaid = render_mermaid(scan_directory(tmp_path).root)

    assert 'Client \\"A\\" & Brand-Logo (v2) 🚀' in mermaid
    assert 'node_1["Client \\"A\\" & Brand-Logo (v2) 🚀"]' in mermaid


def test_mermaid_color_by_depth_adds_classes_and_definitions(tmp_path: Path) -> None:
    (tmp_path / "a" / "b" / "c" / "d").mkdir(parents=True)

    mermaid = render_mermaid(scan_directory(tmp_path).root, color_by_depth=True)

    assert "class node_0 depth0" in mermaid
    assert "class node_4 depth4plus" in mermaid
    assert "classDef depth0" in mermaid
    assert "classDef depth4plus" in mermaid


def test_mermaid_includes_files_as_leaf_nodes_when_scanned(tmp_path: Path) -> None:
    (tmp_path / "section").mkdir()
    (tmp_path / "section" / "brief.md").write_text("# Brief", encoding="utf-8")

    mermaid = render_mermaid(scan_directory(tmp_path, include_files=True).root)

    assert '["brief.md"]' in mermaid


def test_mermaid_adds_descriptions_to_node_labels(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    root = scan_directory(
        tmp_path,
        annotations={".": "Project root.", "src": "Application <source>."},
    ).root

    mermaid = render_mermaid(root)

    assert f'{tmp_path.name}<br/><small>Project root.</small>' in mermaid
    assert 'src<br/><small>Application &lt;source&gt;.</small>' in mermaid
