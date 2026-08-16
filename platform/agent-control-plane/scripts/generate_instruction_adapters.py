#!/usr/bin/env python3
"""Render Claude and Copilot instruction adapter files from the canonical instruction registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = (
    ROOT
    / "platform"
    / "agent-control-plane"
    / "agent-assets"
    / "instructions"
    / "instructions_registry.json"
)


def repository_root() -> Path:
    return ROOT


def load_registry(root: Path) -> dict:
    path = (
        root
        / "platform"
        / "agent-control-plane"
        / "agent-assets"
        / "instructions"
        / "instructions_registry.json"
    )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot load {path}: {error}") from error


def canonical_import_line(instruction_id: str) -> str:
    return f"@../../platform/agent-control-plane/agent-assets/instructions/{instruction_id}.md\n"


def render_claude_adapter(scope_globs: list[str], import_line: str) -> str:
    lines = ["---", "paths:"]
    lines.extend(f'  - "{glob}"' for glob in scope_globs)
    lines.append("---")
    lines.append("")
    return "\n".join(lines) + "\n" + import_line


def render_copilot_adapter(description: str, scope_globs: list[str], import_line: str) -> str:
    apply_to = ",".join(scope_globs)
    lines = [
        "---",
        f'description: "{description}"',
        f'applyTo: "{apply_to}"',
        "---",
        "",
    ]
    return "\n".join(lines) + "\n" + import_line


def adapter_paths_for(root: Path, instruction: dict) -> tuple[Path, Path] | None:
    adapters = instruction.get("runtimeAdapters", [])
    if not adapters:
        return None
    claude_path = None
    copilot_path = None
    for adapter in adapters:
        if adapter.endswith(".instructions.md"):
            copilot_path = root / adapter
        elif adapter.endswith(".md"):
            claude_path = root / adapter
    if claude_path is None or copilot_path is None:
        raise ValueError(
            f"instruction {instruction['id']} runtimeAdapters missing a Claude or Copilot entry: {adapters}"
        )
    return claude_path, copilot_path


def render_all(root: Path, registry: dict) -> dict[Path, str]:
    rendered: dict[Path, str] = {}
    for instruction in registry["instructions"]:
        paths = adapter_paths_for(root, instruction)
        if paths is None:
            continue
        claude_path, copilot_path = paths
        scope_globs = instruction["scopeGlobs"]
        description = instruction["copilotDescription"]
        import_line = canonical_import_line(instruction["id"])
        rendered[claude_path] = render_claude_adapter(scope_globs, import_line)
        rendered[copilot_path] = render_copilot_adapter(description, scope_globs, import_line)
    return rendered


def write_if_changed(path: Path, content: str) -> bool:
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report stale adapter files without writing; exit nonzero if any are stale",
    )
    args = parser.parse_args(argv)

    root = repository_root()
    try:
        registry = load_registry(root)
        rendered = render_all(root, registry)
    except (ValueError, KeyError) as error:
        print(f"generate_instruction_adapters failed: {error}", file=sys.stderr)
        return 1

    if args.check:
        stale = [
            path
            for path, content in rendered.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != content
        ]
        if stale:
            for path in stale:
                print(f"stale: {path.relative_to(root)}", file=sys.stderr)
            return 1
        print(f"{len(rendered)} instruction adapter files up to date")
        return 0

    changed = sum(1 for path, content in rendered.items() if write_if_changed(path, content))
    print(f"generated {len(rendered)} instruction adapter files ({changed} changed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
