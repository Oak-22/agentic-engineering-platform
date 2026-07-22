from pathlib import Path

import pytest

from folder_structure_visualizer.scanner import scan_directory


def test_scans_simple_nested_folder_structure(tmp_path: Path) -> None:
    (tmp_path / "01 Branding" / "Logo Design").mkdir(parents=True)
    (tmp_path / "00 Inbox").mkdir()

    result = scan_directory(tmp_path)

    assert [child.name for child in result.root.children] == ["00 Inbox", "01 Branding"]
    assert result.root.children[1].children[0].name == "Logo Design"


def test_respects_max_depth_with_root_at_depth_zero(tmp_path: Path) -> None:
    (tmp_path / "level1" / "level2" / "level3").mkdir(parents=True)

    result = scan_directory(tmp_path, max_depth=1)

    assert result.root.depth == 0
    assert result.root.children[0].depth == 1
    assert result.root.children[0].children == []


def test_ignores_hidden_by_default_and_can_include_hidden(tmp_path: Path) -> None:
    (tmp_path / ".private").mkdir()
    (tmp_path / "public").mkdir()

    default_result = scan_directory(tmp_path)
    included_result = scan_directory(tmp_path, include_hidden=True)

    assert [child.name for child in default_result.root.children] == ["public"]
    assert [child.name for child in included_result.root.children] == [".private", "public"]


def test_ignores_archive_folders_by_default_and_can_include_archives(tmp_path: Path) -> None:
    (tmp_path / "01 Branding").mkdir()
    (tmp_path / "zz Archive").mkdir()

    default_result = scan_directory(tmp_path)
    included_result = scan_directory(tmp_path, include_archives=True)

    assert [child.name for child in default_result.root.children] == ["01 Branding"]
    assert [child.name for child in included_result.root.children] == ["01 Branding", "zz Archive"]


def test_includes_files_only_when_requested(tmp_path: Path) -> None:
    (tmp_path / "section").mkdir()
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")

    default_result = scan_directory(tmp_path)
    included_result = scan_directory(tmp_path, include_files=True)

    assert [child.name for child in default_result.root.children] == ["section"]
    assert [child.name for child in included_result.root.children] == ["section", "notes.txt"]
    assert included_result.root.children[1].is_dir is False


def test_custom_ignore_uses_case_insensitive_substrings(tmp_path: Path) -> None:
    (tmp_path / "Client Deliverables").mkdir()
    (tmp_path / "node exports").mkdir()

    result = scan_directory(tmp_path, ignore_patterns=["deliver"])

    assert [child.name for child in result.root.children] == ["node exports"]


def test_attaches_annotations_by_root_relative_path(tmp_path: Path) -> None:
    (tmp_path / "src" / "package").mkdir(parents=True)

    result = scan_directory(
        tmp_path,
        annotations={
            ".": "Project root and top-level configuration.",
            "src": "Application source code.",
            "src/package": "Importable Python package.",
        },
    )

    assert result.root.description == "Project root and top-level configuration."
    assert result.root.children[0].description == "Application source code."
    assert result.root.children[0].children[0].description == "Importable Python package."
    assert result.warnings == []


def test_reports_every_rendered_node_missing_an_annotation(tmp_path: Path) -> None:
    (tmp_path / "src" / "package").mkdir(parents=True)

    result = scan_directory(tmp_path, annotations={".": "Project root."})

    assert result.warnings == [
        "Missing semantic annotation: src",
        "Missing semantic annotation: src/package",
    ]


def test_rejects_missing_or_non_directory_roots(tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        scan_directory(tmp_path / "missing")
    with pytest.raises(NotADirectoryError):
        scan_directory(file_path)
