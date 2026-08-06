#!/usr/bin/env python3
"""Record prompt-scoped instruction evidence and inject its response contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
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
STORE_INDEX = {
    "schemaVersion": 1,
    "storeType": "instruction-evidence",
    "generatedBy": {
        "component": "instruction_manifest_hook.py",
        "artifactKind": "runtime-generated",
    },
    "fileClasses": [
        {
            "pattern": "repository.json",
            "kind": "metadata",
            "scope": "project",
            "runtimeSource": "hook storage initialization",
            "retention": {
                "safeToRotate": True,
                "safeToDelete": True,
                "notes": "Recreated from repository identity when the project partition is initialized.",
            },
        },
        {
            "pattern": "store-index.json",
            "kind": "index",
            "scope": "project",
            "runtimeSource": "hook storage initialization",
            "retention": {
                "safeToRotate": True,
                "safeToDelete": True,
                "notes": "Descriptive metadata; regenerated from the hook implementation.",
            },
        },
        {
            "pattern": "<session-id>.jsonl",
            "kind": "session-ledger",
            "scope": "session",
            "runtimeSource": "runtime recorded in each JSONL event",
            "retention": {
                "safeToRotate": True,
                "safeToDelete": True,
                "notes": "Retain until citation, investigation, or reproducibility dependencies end.",
            },
        },
    ],
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


def git_output(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


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


def repository_id(root: Path) -> str:
    remote = git_output(root, "config", "--get", "remote.origin.url")
    return remote or f"git:{root.name}"


def worktree_state(root: Path, relative_path: str) -> str:
    status = git_output(root, "status", "--short", "--", relative_path)
    if status.startswith("??"):
        return "untracked"
    return "modified" if status else "clean"


def evidence_record(
    root: Path,
    instruction: str,
    evidence_type: str,
    reason: str,
    proof: dict[str, Any],
    identity_seed: dict[str, Any],
    log_path: Path,
) -> dict[str, Any]:
    source_path = root / instruction
    content = source_path.read_bytes()
    revision = git_output(root, "rev-parse", "HEAD")
    git_blob = git_output(root, "hash-object", instruction)
    digest = hashlib.sha256(content).hexdigest()
    repository = repository_id(root)
    record_key = json.dumps(
        {
            "repository": repository,
            "revision": revision,
            "instruction": instruction,
            "digest": digest,
            "evidenceType": evidence_type,
            "identity": identity_seed,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    record_id = f"iev_{hashlib.sha256(record_key.encode()).hexdigest()[:24]}"
    label = (
        f"{root.name} · {revision[:8]} · {instruction} · {git_blob[:8]}"
    )
    return {
        "schemaVersion": 1,
        "recordId": record_id,
        "instruction": instruction,
        "evidenceType": evidence_type,
        "reason": reason,
        "citation": {
            "label": label,
            "href": log_path.absolute().as_posix(),
            "activeRepositoryId": repository,
            "repositoryId": repository,
            "baseRevision": revision,
            "path": instruction,
            "sha256": digest,
            "gitBlob": git_blob,
            "worktreeState": worktree_state(root, instruction),
        },
        "proof": proof,
    }


def storage_root() -> Path:
    configured = os.environ.get("AEP_INSTRUCTION_MANIFEST_DIR")
    default_root = (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        / "aep"
        / "instruction-evidence"
    )
    root = Path(configured) if configured else default_root
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def project_storage_root(root: Path) -> Path:
    project_key = hashlib.sha256(repository_id(root).encode()).hexdigest()[:24]
    project_root = storage_root() / project_key
    project_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = project_root / "repository.json"
    if not metadata.exists():
        metadata.write_text(
            json.dumps(
                {
                    "repositoryId": repository_id(root),
                    "projectKey": project_key,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    index = project_root / "store-index.json"
    if not index.exists():
        index.write_text(
            json.dumps(
                {
                    **STORE_INDEX,
                    "repositoryId": repository_id(root),
                    "projectKey": project_key,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return project_root


def project_view(root: Path, canonical_root: Path) -> Path:
    configured = os.environ.get("AEP_INSTRUCTION_EVIDENCE_VIEW")
    view = Path(configured) if configured else root / ".aep" / "instruction-evidence"
    view.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not view.exists() and not view.is_symlink():
        view.symlink_to(canonical_root, target_is_directory=True)
    if view.resolve(strict=False) == canonical_root.resolve():
        return view
    return canonical_root


def ledger_path(root: Path, session_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id) or "unknown-session"
    return project_storage_root(root) / f"{safe_id}.jsonl"


def append_event(root: Path, session_id: str, event: dict[str, Any]) -> None:
    with ledger_path(root, session_id).open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps(event, sort_keys=True) + "\n")


def read_events(root: Path, session_id: str) -> list[dict[str, Any]]:
    path = ledger_path(root, session_id)
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def codex_baselines(
    root: Path, cwd: Path, log_path: Path
) -> list[dict[str, Any]]:
    try:
        relative = cwd.resolve().relative_to(root)
    except ValueError:
        relative = Path()
    candidates = [root / "AGENTS.md"]
    current = root
    for part in relative.parts:
        current /= part
        candidates.append(current / "AGENTS.md")
    records = []
    for candidate in candidates:
        if not candidate.is_file():
            continue
        instruction = candidate.relative_to(root).as_posix()
        records.append(
            evidence_record(
                root,
                instruction,
                "Runtime baseline",
                "Codex repository guidance for the active working scope",
                {
                    "runtime": "codex",
                    "discoveryMechanism": "agents-md-scope-discovery",
                    "scopePath": candidate.parent.relative_to(root).as_posix() or ".",
                },
                {
                    "runtime": "codex",
                    "scope": (
                        cwd.resolve().relative_to(root).as_posix()
                        if cwd.resolve().is_relative_to(root)
                        else "."
                    ),
                },
                log_path,
            )
        )
    return records


def claude_observed(
    root: Path,
    events: list[dict[str, Any]],
    prompt_id: str | None,
    log_path: Path,
) -> list[dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("event") != "instruction_loaded":
            continue
        observed_prompt = event.get("prompt_id")
        if observed_prompt is not None and observed_prompt != prompt_id:
            continue
        instruction = event.get("instruction")
        if instruction:
            observation_id = str(event.get("observation_id") or "")
            sources[instruction] = evidence_record(
                root,
                instruction,
                "Observed",
                "Claude Code emitted InstructionsLoaded",
                {
                    "runtime": "claude",
                    "eventName": "InstructionsLoaded",
                    "observationId": observation_id,
                    "loadReason": event.get("load_reason"),
                },
                {"observationId": observation_id},
                log_path,
            )
    return list(sources.values())


def additional_context(runtime: str, sources: list[dict[str, Any]]) -> str:
    rows = "\n".join(
        (
            f"| {source['instruction']} | {source['evidenceType']} | "
            f"[{source['citation']['label']}](<{source['citation']['href']}>) | "
            f"{source['reason']} |"
        )
        for source in sources
    )
    if not rows:
        rows = (
            "| (no hook-observed sources) | Declared | "
            "No structured citation | Complete from turn evidence |"
        )
    return (
        "For this prompt, follow the response contract in "
        f"`{CONTRACT_PATH}`. Append its `Instruction References` table to the "
        "final response. The hook seed below is prompt-scoped; supplement it "
        "with explicitly invoked skills and instructions read during this turn. "
        "Do not claim `Observed` without an authoritative runtime event.\n\n"
        "| Instruction | Evidence | Citation | Reason |\n"
        "| --- | --- | --- | --- |\n"
        f"{rows}\n\n"
        f"Runtime: {runtime}."
    )


def handle(runtime: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    session_id = str(payload.get("session_id") or "unknown-session")
    event_name = str(payload.get("hook_event_name") or "")
    cwd = Path(payload.get("cwd") or os.getcwd())
    root = repository_root(cwd)
    canonical_root = project_storage_root(root)
    view_root = project_view(root, canonical_root)
    canonical_ledger = ledger_path(root, session_id)
    log_path = view_root / canonical_ledger.name

    if runtime == "claude" and event_name == "InstructionsLoaded":
        file_path = payload.get("file_path")
        if file_path:
            observation_seed = json.dumps(
                {
                    "session_id": session_id,
                    "prompt_id": payload.get("prompt_id"),
                    "file_path": str(file_path),
                    "load_reason": payload.get("load_reason"),
                    "memory_type": payload.get("memory_type"),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            append_event(
                root,
                session_id,
                {
                    "event": "instruction_loaded",
                    "runtime": "claude",
                    "observation_id": (
                        "obs_"
                        + hashlib.sha256(observation_seed.encode()).hexdigest()[:24]
                    ),
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
        claude_observed(
            root, read_events(root, session_id), prompt_id, log_path
        )
        if runtime == "claude"
        else codex_baselines(root, cwd, log_path)
    )
    append_event(
        root,
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
