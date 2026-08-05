from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .render_image import render_image
from .render_html import render_html_viewer
from .render_markdown import render_markdown
from .render_mermaid import VALID_DIRECTIONS, render_mermaid
from .render_tree import render_tree
from .scanner import scan_directory

ALLOWED_FORMATS = {"tree", "markdown", "mermaid", "svg", "png", "html"}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        formats = parse_formats(args.formats)
        root_path = Path(args.root).expanduser()
        output_dir = Path(args.output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        annotations = load_annotations(args.annotations) if args.annotations else None

        result = scan_directory(
            root_path,
            max_depth=args.max_depth,
            include_files=args.include_files,
            include_hidden=args.include_hidden,
            include_archives=args.include_archives,
            ignore_patterns=args.ignore,
            annotations=annotations,
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        parser.error(str(exc))
        return 2

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    name = args.name or result.root.name
    metadata = {
        "name": name,
        "generated_at": generated_at,
        "root_path": str(result.root.path),
        "warnings": result.warnings,
        "color_by_depth": args.color_by_depth,
        "mermaid_direction": args.mermaid_direction,
    }

    needs_mermaid_source = bool({"mermaid", "svg", "png", "html"} & formats)
    mermaid_file = output_dir / "structure.mmd"
    svg_file = output_dir / "structure.svg"

    if "tree" in formats:
        (output_dir / "structure.txt").write_text(render_tree(result.root), encoding="utf-8")
    if "markdown" in formats:
        (output_dir / "structure.md").write_text(
            render_markdown(result.root, metadata), encoding="utf-8"
        )
    if needs_mermaid_source:
        mermaid_file.write_text(
            render_mermaid(
                result.root,
                color_by_depth=args.color_by_depth,
                direction=args.mermaid_direction,
            ),
            encoding="utf-8",
        )
    rendered_svg = False
    if "svg" in formats:
        rendered_svg = render_image(mermaid_file, svg_file)
    if "png" in formats:
        render_image(mermaid_file, output_dir / "structure.png")
    if "html" in formats:
        if rendered_svg or render_image(mermaid_file, svg_file):
            (output_dir / "structure.html").write_text(
                render_html_viewer(svg_file, f"Folder Structure: {name}"),
                encoding="utf-8",
            )

    for warning in result.warnings:
        print(f"Warning: {warning}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="folder_structure_visualizer",
        description="Generate text, Markdown, Mermaid, and optional image maps of folders.",
    )
    parser.add_argument("--root", required=True, help="Directory to scan.")
    parser.add_argument(
        "--annotations",
        help="JSON file mapping root-relative node paths to concise descriptions.",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory where generated files are written. Defaults to the current directory.",
    )
    parser.add_argument("--name", help="Human-readable project name for the document title.")
    parser.add_argument("--max-depth", type=int, help="Inclusive recursion depth. Root is depth 0.")
    parser.add_argument("--include-files", action="store_true", help="Include files as leaf nodes.")
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include files and folders whose names start with a dot.",
    )
    parser.add_argument(
        "--include-archives",
        action="store_true",
        help="Include archive-like folders that are ignored by default.",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="Case-insensitive substring to ignore. Repeat for multiple patterns.",
    )
    parser.add_argument(
        "--formats",
        default="tree,markdown,mermaid",
        help="Comma-separated output formats: tree,markdown,mermaid,svg,png,html.",
    )
    parser.add_argument(
        "--color-by-depth",
        action="store_true",
        help="Add Mermaid classes and colors based on node depth.",
    )
    parser.add_argument(
        "--mermaid-direction",
        default="LR",
        choices=sorted(VALID_DIRECTIONS),
        help="Mermaid graph direction. LR is narrower for broad folder trees; TD is top-down.",
    )
    return parser


def load_annotations(path: str) -> dict[str, str]:
    annotation_path = Path(path).expanduser()
    try:
        value = json.loads(annotation_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Could not read annotations file: {annotation_path} ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid annotations JSON: {annotation_path} ({exc.msg})") from exc

    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(description, str)
        for key, description in value.items()
    ):
        raise ValueError("--annotations must contain a JSON object of path-to-string entries")

    return {
        key.strip().replace("\\", "/"): description.strip()
        for key, description in value.items()
        if key.strip() and description.strip()
    }


def parse_formats(value: str) -> set[str]:
    formats = {item.strip().casefold() for item in value.split(",") if item.strip()}
    if not formats:
        raise ValueError("--formats must include at least one format")
    unknown = formats - ALLOWED_FORMATS
    if unknown:
        raise ValueError(f"Unsupported format(s): {', '.join(sorted(unknown))}")
    return formats
