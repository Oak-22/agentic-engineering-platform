from pathlib import Path

from folder_structure_visualizer.cli import main


def test_cli_writes_expected_files_and_overwrites_outputs(tmp_path: Path) -> None:
    root = tmp_path / "root"
    output = tmp_path / "out"
    (root / "00 Inbox").mkdir(parents=True)
    output.mkdir()
    stale_file = output / "structure.txt"
    stale_file.write_text("stale", encoding="utf-8")

    exit_code = main(
        [
            "--root",
            str(root),
            "--output-dir",
            str(output),
            "--formats",
            "tree,markdown,mermaid",
        ]
    )

    assert exit_code == 0
    assert (output / "structure.txt").read_text(encoding="utf-8") != "stale"
    assert (output / "structure.md").exists()
    assert (output / "structure.mmd").exists()
    assert "00 Inbox" in (output / "structure.txt").read_text(encoding="utf-8")


def test_cli_loads_annotations_into_generated_outputs(tmp_path: Path) -> None:
    root = tmp_path / "root"
    output = tmp_path / "out"
    (root / "src").mkdir(parents=True)
    annotations = tmp_path / "annotations.json"
    annotations.write_text(
        '{".": "Project root.", "src": "Application source."}',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--root",
            str(root),
            "--output-dir",
            str(output),
            "--annotations",
            str(annotations),
            "--formats",
            "tree,mermaid",
        ]
    )

    assert exit_code == 0
    assert "root — Project root." in (output / "structure.txt").read_text(encoding="utf-8")
    assert "src — Application source." in (output / "structure.txt").read_text(
        encoding="utf-8"
    )
    assert "Application source." in (output / "structure.mmd").read_text(encoding="utf-8")


def test_cli_generates_mermaid_source_for_svg_request_without_renderer(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    monkeypatch.setattr("folder_structure_visualizer.render_image.shutil.which", lambda _: None)
    root = tmp_path / "root"
    output = tmp_path / "out"
    (root / "01 Branding").mkdir(parents=True)

    exit_code = main(
        [
            "--root",
            str(root),
            "--output-dir",
            str(output),
            "--formats",
            "svg",
        ]
    )

    assert exit_code == 0
    assert (output / "structure.mmd").exists()
    captured = capsys.readouterr()
    assert "Mermaid CLI not found" in captured.out


def test_cli_writes_interactive_html_viewer(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "root"
    output = tmp_path / "out"
    (root / "01 Branding").mkdir(parents=True)

    def fake_render_image(mermaid_file: Path, output_file: Path) -> bool:
        output_file.write_text(
            '<svg viewBox="0 0 100 100"><text>01 Branding</text></svg>',
            encoding="utf-8",
        )
        return True

    monkeypatch.setattr("folder_structure_visualizer.cli.render_image", fake_render_image)

    exit_code = main(
        [
            "--root",
            str(root),
            "--output-dir",
            str(output),
            "--formats",
            "html",
        ]
    )

    html = (output / "structure.html").read_text(encoding="utf-8")
    assert exit_code == 0
    assert (output / "structure.mmd").exists()
    assert (output / "structure.svg").exists()
    assert "data-action=\"zoom-in\"" in html
    assert "viewBox.baseVal" in html
    assert "lockSvgSize" in html
    assert "fitToScreen" in html
    assert "01 Branding" in html
