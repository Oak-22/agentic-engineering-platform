#!/usr/bin/env python3
"""Record prompt-scoped instruction evidence and inject its response contract."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

CONTRACT_PATH = (
    "platform/agent-control-plane/agent-assets/instructions/"
    "prompt-instruction-manifest.md"
)
EVIDENCE_LABELS = {
    "Observed",
    "Runtime baseline",
    "Explicitly invoked",
    "Read during turn",
    "Declared",
}


def repository_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        check=False,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve() if result.returncode == 0 else start.resolve()


def display_path(path_value: str, root: Path) -> str:
    path = Path(path_value).expanduser()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        pass
    try:
        return "~/" + path.resolve().relative_to(Path.home().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def storage_root() -> Path:
    configured = os.environ.get("AEP_INSTRUCTION_MANIFEST_DIR")
    root = Path(configured) if configured else Path(tempfile.gettempdir()) / "aep-instruction-manifests"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def ledger_path(session_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id) or "unknown-session"
    return storage_root() / f"{safe_id}.jsonl"


def append_event(session_id: str, event: dict[str, Any]) -> None:
    with ledger_path(session_id).open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps(event, sort_keys=True) + "\n")


def read_events(session_id: str) -> list[dict[str, Any]]:
    path = ledger_path(session_id)
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def codex_baselines(root: Path, cwd: Path) -> list[dict[str, str]]:
    try:
        relative = cwd.resolve().relative_to(root)
    except ValueError:
        relative = Path()
    candidates = [root / "AGENTS.md"]
    current = root
    for part in relative.parts:
        current /= part
        candidates.append(current / "AGENTS.md")
    return [
        {
            "instruction": candidate.relative_to(root).as_posix(),
            "evidence": "Runtime baseline",
            "reason": "Codex repository guidance for the active working scope",
        }
        for candidate in candidates
        if candidate.is_file()
    ]


def claude_observed(
    events: list[dict[str, Any]], prompt_id: str | None
) -> list[dict[str, str]]:
    sources: dict[str, dict[str, str]] = {}
    for event in events:
        if event.get("event") != "instruction_loaded":
            continue
        observed_prompt = event.get("prompt_id")
        if observed_prompt is not None and observed_prompt != prompt_id:
            continue
        instruction = event.get("instruction")
        if instruction:
            sources[instruction] = {
                "instruction": instruction,
                "evidence": "Observed",
                "reason": "Claude Code emitted InstructionsLoaded",
            }
    return list(sources.values())


def additional_context(runtime: str, sources: list[dict[str, str]]) -> str:
    rows = "\n".join(
        f"| {source['instruction']} | {source['evidence']} | {source['reason']} |"
        for source in sources
    )
    if not rows:
        rows = "| (no hook-observed sources) | Declared | Complete from turn evidence |"
    return (
        "For this prompt, follow the response contract in "
        f"`{CONTRACT_PATH}`. Append its `Instruction References` table to the "
        "final response. The hook seed below is prompt-scoped; supplement it "
        "with explicitly invoked skills and instructions read during this turn. "
        "Do not claim `Observed` without an authoritative runtime event.\n\n"
        "| Instruction | Evidence | Reason |\n"
        "| --- | --- | --- |\n"
        f"{rows}\n\n"
        f"Runtime: {runtime}."
    )


def handle(runtime: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    session_id = str(payload.get("session_id") or "unknown-session")
    event_name = str(payload.get("hook_event_name") or "")
    cwd = Path(payload.get("cwd") or os.getcwd())
    root = repository_root(cwd)

    if runtime == "claude" and event_name == "InstructionsLoaded":
        file_path = payload.get("file_path")
        if file_path:
            append_event(
                session_id,
                {
                    "event": "instruction_loaded",
                    "instruction": display_path(str(file_path), root),
                    "load_reason": payload.get("load_reason"),
                    "memory_type": payload.get("memory_type"),
                    "prompt_id": payload.get("prompt_id"),
                },
            )
        return None

    if event_name and event_name != "UserPromptSubmit":
        return None

    prompt_id = payload.get("prompt_id") or payload.get("turn_id")
    sources = (
        claude_observed(read_events(session_id), prompt_id)
        if runtime == "claude"
        else codex_baselines(root, cwd)
    )
    append_event(
        session_id,
        {
            "event": "prompt_manifest",
            "prompt_id": prompt_id,
            "runtime": runtime,
            "sources": sources,
        },
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context(runtime, sources),
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", choices=("claude", "codex"), required=True)
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
        output = handle(args.runtime, payload)
        if output is not None:
            print(json.dumps(output))
    except (json.JSONDecodeError, OSError, TypeError, ValueError) as error:
        print(f"instruction manifest hook: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
