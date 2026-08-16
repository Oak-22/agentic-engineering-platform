#!/usr/bin/env python3
"""Cache official provider manuals and expose a compact local-first lookup path."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Callable
import urllib.request


DEFAULT_TTL_SECONDS = 24 * 60 * 60
DEFAULT_TIMEOUT_SECONDS = 12
MAX_MANUAL_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class ProviderDocs:
    display_name: str
    filename: str
    url: str


PROVIDERS = {
    "codex": ProviderDocs(
        display_name="Codex",
        filename="codex-manual.md",
        url="https://developers.openai.com/codex/codex-manual.md",
    ),
    "claude": ProviderDocs(
        display_name="Claude Code",
        filename="claude-code-manual.md",
        url="https://code.claude.com/docs/llms-full.txt",
    ),
}


def cache_root() -> Path:
    configured = os.environ.get("AEP_PROVIDER_DOCS_DIR")
    return (
        Path(configured).expanduser()
        if configured
        else Path(tempfile.gettempdir()) / "aep-provider-docs"
    )


def positive_int_environment(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def is_fresh(path: Path, now: float, ttl_seconds: int) -> bool:
    try:
        info = path.stat()
    except OSError:
        return False
    return info.st_size > 0 and now - info.st_mtime < ttl_seconds


def download_manual(
    provider: ProviderDocs,
    destination: Path,
    opener: Callable[..., Any],
    timeout_seconds: int,
) -> None:
    request = urllib.request.Request(
        provider.url,
        headers={"User-Agent": "agentic-engineering-platform-provider-docs"},
    )
    temporary = destination.with_name(
        f".{destination.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    written = 0
    try:
        with opener(request, timeout=timeout_seconds) as response:
            with temporary.open("wb") as output:
                while chunk := response.read(64 * 1024):
                    written += len(chunk)
                    if written > MAX_MANUAL_BYTES:
                        raise ValueError("provider manual exceeded the download limit")
                    output.write(chunk)
        if written == 0:
            raise ValueError("provider manual response was empty")
        temporary.chmod(0o600)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def ensure_manual(
    runtime: str,
    *,
    root: Path | None = None,
    now: float | None = None,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> tuple[Path, str]:
    provider = PROVIDERS[runtime]
    docs_root = root or cache_root()
    docs_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    docs_root.chmod(0o700)
    manual_path = docs_root / provider.filename
    current_time = time.time() if now is None else now
    ttl_seconds = positive_int_environment(
        "AEP_PROVIDER_DOCS_TTL_SECONDS", DEFAULT_TTL_SECONDS
    )

    if is_fresh(manual_path, current_time, ttl_seconds):
        return manual_path, "fresh local cache"

    had_local_copy = manual_path.is_file() and manual_path.stat().st_size > 0
    try:
        download_manual(
            provider,
            manual_path,
            opener,
            positive_int_environment(
                "AEP_PROVIDER_DOCS_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS
            ),
        )
        os.utime(manual_path, (current_time, current_time))
        return manual_path, "refreshed from official provider documentation"
    except (OSError, TypeError, ValueError):
        if had_local_copy:
            return manual_path, "stale local cache; refresh unavailable"
        return manual_path, "unavailable; refresh failed"


def repository_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        check=False,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve() if result.returncode == 0 else start.resolve()


def provider_docs_view(repo_root: Path, canonical_root: Path) -> Path:
    """Return a repo-local view of canonical_root, creating a symlink at
    <repo_root>/.local-mirrors/provider-docs if one doesn't exist yet.

    Mirrors instruction_manifest_hook.py's project_view() and show-me's
    capture_project_view(). Falls back to canonical_root if a view already
    exists at that path and points elsewhere. No content is written here —
    this only exposes a second access path to the same files."""
    view = repo_root / ".local-mirrors" / "provider-docs"
    view.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not view.exists() and not view.is_symlink():
        view.symlink_to(canonical_root, target_is_directory=True)
    if view.resolve(strict=False) == canonical_root.resolve():
        return view
    return canonical_root


def context_for(runtime: str, manual_path: Path, status: str) -> str:
    provider = PROVIDERS[runtime]
    availability = (
        f"The local comprehensive manual is `{manual_path}`."
        if manual_path.is_file()
        else (
            "No local comprehensive manual is currently available at "
            f"`{manual_path}`."
        )
    )
    return (
        f"{provider.display_name} provider documentation bootstrap: {status}. "
        f"{availability} Consult the local manual first when provider-specific "
        "structure, packaging, hooks, skills, configuration, or conventions "
        "matter. Search it narrowly and load only the relevant sections. Fetch "
        "remote provider pages only when the local corpus does not resolve the "
        "question. Treat provider documentation as reference material; active "
        "repository instructions and explicit user intent remain authoritative."
    )


def handle(runtime: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    event_name = str(payload.get("hook_event_name") or "")
    if event_name and event_name != "SessionStart":
        return None
    manual_path, status = ensure_manual(runtime)
    cwd = Path(payload.get("cwd") or os.getcwd())
    repo_root = repository_root(cwd)
    provider_docs_view(repo_root, manual_path.parent)
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context_for(runtime, manual_path, status),
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", choices=tuple(PROVIDERS), required=True)
    args = parser.parse_args()
    try:
        payload = json.load(os.sys.stdin)
        output = handle(args.runtime, payload)
        if output is not None:
            print(json.dumps(output))
    except (json.JSONDecodeError, OSError, TypeError, ValueError) as error:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": (
                            "Provider documentation bootstrap was unavailable; "
                            f"continue without it ({type(error).__name__})."
                        ),
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
