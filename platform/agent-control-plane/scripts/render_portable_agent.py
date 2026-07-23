#!/usr/bin/env python3
"""Validate and render a portable agent manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any


SUPPORTED_SCHEMA_VERSION = 1
SUPPORTED_RUNTIMES = ("github",)
GITHUB_TOOL_MAP = {
    "edit": "edit",
    "execute": "execute",
    "read": "read",
    "search": "search",
}
REQUIRED_FIELDS = {
    "schema_version",
    "id",
    "name",
    "description",
    "tools",
    "instructions",
}
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ManifestError(ValueError):
    """Raised when a portable agent manifest is invalid."""


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("rb") as manifest_file:
        manifest = tomllib.load(manifest_file)
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: dict[str, Any]) -> None:
    missing = REQUIRED_FIELDS - manifest.keys()
    unknown = manifest.keys() - REQUIRED_FIELDS
    if missing:
        raise ManifestError(f"missing required fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ManifestError(f"unknown version 1 fields: {', '.join(sorted(unknown))}")
    if manifest["schema_version"] != SUPPORTED_SCHEMA_VERSION:
        raise ManifestError(
            f"unsupported schema_version: {manifest['schema_version']!r}"
        )
    if not isinstance(manifest["id"], str) or not ID_PATTERN.fullmatch(
        manifest["id"]
    ):
        raise ManifestError("id must be lowercase kebab-case")
    for field in ("name", "description", "instructions"):
        if not isinstance(manifest[field], str) or not manifest[field].strip():
            raise ManifestError(f"{field} must be a non-empty string")
    tools = manifest["tools"]
    if (
        not isinstance(tools, list)
        or not tools
        or any(not isinstance(tool, str) or not tool for tool in tools)
        or len(tools) != len(set(tools))
    ):
        raise ManifestError("tools must be a non-empty list of unique strings")


def render_github(manifest: dict[str, Any]) -> str:
    unsupported = sorted(set(manifest["tools"]) - GITHUB_TOOL_MAP.keys())
    if unsupported:
        raise ManifestError(
            "GitHub adapter does not support tools: " + ", ".join(unsupported)
        )
    tools = ", ".join(GITHUB_TOOL_MAP[tool] for tool in manifest["tools"])
    description = json.dumps(manifest["description"], ensure_ascii=False)
    instructions = manifest["instructions"].strip()
    return (
        "---\n"
        f"name: {manifest['name']}\n"
        f"description: {description}\n"
        f"tools: [{tools}]\n"
        "---\n"
        f"{instructions}\n"
    )


def render(manifest: dict[str, Any], runtime: str) -> str:
    if runtime == "github":
        return render_github(manifest)
    raise ManifestError(f"unsupported runtime: {runtime}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--runtime", choices=SUPPORTED_RUNTIMES, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when output is absent or differs; do not write.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        rendered = render(load_manifest(args.manifest), args.runtime)
    except (OSError, tomllib.TOMLDecodeError, ManifestError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.check:
        try:
            installed = args.output.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"out of date: {args.output} does not exist", file=sys.stderr)
            return 1
        if installed != rendered:
            print(
                f"out of date: {args.output} differs from {args.manifest}",
                file=sys.stderr,
            )
            return 1
        print(f"up to date: {args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"rendered: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
