#!/usr/bin/env python3
"""Record prompt-scoped instruction evidence and inject its response contract.

Run with `--runtime <claude|codex|copilot>`. The `copilot` leg (AEPI-96) is
unverified: whether GitHub Copilot's hook system exposes a prompt-submit-time
event at all, and whether `.github/hooks/instruction-manifest.json` actually
invokes this script, is unconfirmed — mirrors the same caveat
`agent_permission_gate.py` carries for its Copilot `--runtime` leg.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import importlib.util
from typing import Any, Callable, Iterator, TextIO

CONTRACT_PATH = (
    "platform/agent-control-plane/agent-assets/instructions/"
    "prompt-instruction-manifest.md"
)
INSTRUCTIONS_REGISTRY = (
    "platform/agent-control-plane/agent-assets/instructions/instructions_registry.json"
)
SKILLS_REGISTRY = (
    "platform/agent-control-plane/agent-assets/skills/skills_registry.json"
)
ADAPTER_SURFACES = {
    "claude": (".claude/", "claude-rules-adapter"),
    "codex": (".codex/", "codex-instruction-adapter"),
    "copilot": (".github/", "copilot-instruction-adapter"),
}
RUNTIME_PROVIDERS = {"claude": "anthropic", "codex": "openai", "copilot": "github"}
EVIDENCE_LABELS = {
    "Observed",
    "Runtime baseline",
    "Explicitly invoked",
    "Read during turn",
    "Declared",
}
STORE_INDEX = {
    "schemaVersion": 2,
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
            "pattern": "<runtime>/<session-id>.jsonl",
            "kind": "session-ledger",
            "scope": "session",
            "runtimeSource": "runtime directory and runtime field in each JSONL event",
            "retention": {
                "safeToRotate": True,
                "safeToDelete": True,
                "notes": "Retain until citation, investigation, or reproducibility dependencies end.",
            },
        },
        {
            "pattern": "<runtime>/<session-id>.jsonl.lock",
            "kind": "lock",
            "scope": "session",
            "runtimeSource": "hook append serialization",
            "retention": {
                "safeToRotate": True,
                "safeToDelete": True,
                "notes": "Recreated on demand; contains no instruction evidence.",
            },
        },
    ],
}


def _load_local_store():
    cached = sys.modules.get("local_store")
    if cached is not None:
        return cached
    path = Path(__file__).resolve().parent / "local_store.py"
    spec = importlib.util.spec_from_file_location("local_store", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load local_store at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_local_store = _load_local_store()


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
    return _local_store.repository_identity(root).repository_id


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
    citation_location: dict[str, Any],
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
        "schemaVersion": 2,
        "recordId": record_id,
        "instruction": instruction,
        "evidenceType": evidence_type,
        "reason": reason,
        "citation": {
            "label": label,
            **citation_location,
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
    root = _local_store.store_root(
        "instruction-evidence", project_dir=repository_root(Path.cwd())
    ).parent
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def write_json_atomically(path: Path, value: dict[str, Any]) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def project_storage_root(root: Path) -> Path:
    identity = _local_store.repository_identity(root)
    project_key = identity.identity_hash
    project_root, _ = _local_store.ensure_store(
        "instruction-evidence", project_dir=root, create=True
    )
    index = project_root / "store-index.json"
    expected_index = {
        **STORE_INDEX,
        "repositoryId": repository_id(root),
        "projectKey": project_key,
    }
    try:
        current_index = json.loads(index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        current_index = None
    if current_index != expected_index:
        write_json_atomically(index, expected_index)
    return project_root


def project_view(root: Path, canonical_root: Path) -> Path:
    configured = os.environ.get("AEP_INSTRUCTION_EVIDENCE_VIEW")
    view = Path(configured) if configured else root / ".local-mirrors" / "instruction-evidence"
    view.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not view.exists() and not view.is_symlink():
        try:
            view.symlink_to(canonical_root, target_is_directory=True)
        except FileExistsError:
            pass
    if view.resolve(strict=False) == canonical_root.resolve():
        return view
    return canonical_root


def safe_session_id(session_id: str) -> str:
    if not session_id.strip():
        raise ValueError("session_id is required for instruction evidence")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", session_id)


def ledger_path(root: Path, runtime: str, session_id: str) -> Path:
    runtime_root = project_storage_root(root) / runtime
    runtime_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return runtime_root / f"{safe_session_id(session_id)}.jsonl"


def legacy_ledger_path(root: Path, session_id: str) -> Path:
    return project_storage_root(root) / f"{safe_session_id(session_id)}.jsonl"


@contextmanager
def ledger_lock(path: Path) -> Iterator[None]:
    """Serialize one runtime ledger without adding a hook dependency."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        if os.name == "nt":
            import msvcrt

            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def parse_events(lines: list[str]) -> list[dict[str, Any]]:
    events = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def migrate_legacy_events(
    root: Path, runtime: str, session_id: str, ledger: TextIO
) -> None:
    """Copy only runtime-attributed legacy events into an empty new ledger.

    Events from the former flat layout that lack a runtime remain quarantined in
    place because assigning them to a provider would invent provenance.
    """
    ledger.seek(0, os.SEEK_END)
    if ledger.tell() != 0:
        return
    legacy = legacy_ledger_path(root, session_id)
    if not legacy.is_file():
        return
    migrated = [
        line
        for line in legacy.read_text(encoding="utf-8").splitlines()
        if any(
            event.get("runtime") == runtime
            for event in parse_events([line])
        )
    ]
    if migrated:
        ledger.write("\n".join(migrated) + "\n")
        ledger.flush()


@contextmanager
def open_runtime_ledger(
    root: Path, runtime: str, session_id: str
) -> Iterator[TextIO]:
    path = ledger_path(root, runtime, session_id)
    with ledger_lock(path):
        with path.open("a+", encoding="utf-8") as ledger:
            migrate_legacy_events(root, runtime, session_id, ledger)
            yield ledger


def append_event(
    root: Path, runtime: str, session_id: str, event: dict[str, Any]
) -> int:
    with open_runtime_ledger(root, runtime, session_id) as ledger:
        ledger.seek(0)
        line_number = len(ledger.readlines()) + 1
        ledger.seek(0, os.SEEK_END)
        ledger.write(json.dumps(event, sort_keys=True) + "\n")
        ledger.flush()
        return line_number


def append_manifest(
    root: Path,
    runtime: str,
    session_id: str,
    build_event: Callable[[list[dict[str, Any]], int], dict[str, Any]],
) -> dict[str, Any]:
    with open_runtime_ledger(root, runtime, session_id) as ledger:
        ledger.seek(0)
        lines = ledger.readlines()
        line_number = len(lines) + 1
        event = build_event(parse_events(lines), line_number)
        ledger.seek(0, os.SEEK_END)
        ledger.write(json.dumps(event, sort_keys=True) + "\n")
        ledger.flush()
        return event


def load_registry(root: Path, relative: str) -> dict[str, Any]:
    try:
        return json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def registered_instructions(root: Path) -> list[dict[str, Any]]:
    return load_registry(root, INSTRUCTIONS_REGISTRY).get("instructions", [])


def registered_skills(root: Path) -> dict[str, str]:
    skills = load_registry(root, SKILLS_REGISTRY).get("skills", [])
    return {skill["id"]: skill["skillFile"] for skill in skills if skill.get("skillFile")}


def instruction_sources(root: Path) -> set[str]:
    """Repository-relative paths that count as instruction sources."""
    sources = {
        instruction["canonicalPath"]
        for instruction in registered_instructions(root)
        if instruction.get("canonicalPath")
    }
    sources.update(registered_skills(root).values())
    return sources


def skill_name_from_tool_input(tool_input: Any, known: dict[str, str]) -> str | None:
    if not isinstance(tool_input, dict):
        return None
    for key in ("skill", "skill_name", "name", "command"):
        value = tool_input.get(key)
        if isinstance(value, str) and value in known:
            return value
    for value in tool_input.values():
        if isinstance(value, str) and value in known:
            return value
    return None


def digest_id(prefix: str, seed: dict[str, Any]) -> str:
    payload = json.dumps(seed, sort_keys=True, separators=(",", ":"))
    return f"{prefix}_{hashlib.sha256(payload.encode()).hexdigest()[:24]}"


def runtime_event_metadata(
    runtime: str, payload: dict[str, Any]
) -> dict[str, str]:
    metadata = {
        "runtime": runtime,
        "provider": RUNTIME_PROVIDERS[runtime],
    }
    model = payload.get("model")
    if isinstance(model, str) and model.strip():
        metadata["model"] = model
    return metadata


def events_since_last_manifest(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Events recorded after the previous manifest, i.e. during the last turn.

    Skill invocations and instruction reads are stamped with the prompt that
    was already manifested when they occurred, so selecting them by the current
    prompt identifier would strand them permanently. Position in the ledger,
    not prompt identity, is what places them in the turn that just completed.
    """
    for index in range(len(events) - 1, -1, -1):
        if events[index].get("event") == "prompt_manifest":
            return events[index + 1:]
    return events


def claude_explicitly_invoked(
    root: Path,
    events: list[dict[str, Any]],
    citation_location: dict[str, Any],
) -> list[dict[str, Any]]:
    known = registered_skills(root)
    sources: dict[str, dict[str, Any]] = {}
    for event in events_since_last_manifest(events):
        if event.get("event") != "skill_invoked":
            continue
        instruction = known.get(str(event.get("skill") or ""))
        invocation_id = str(event.get("invocation_id") or "")
        if not instruction or not invocation_id:
            continue
        sources[instruction] = evidence_record(
            root,
            instruction,
            "Explicitly invoked",
            f"Skill {event.get('skill')} invoked via {event.get('path')}",
            {"invocationId": invocation_id, "invocationKind": "skill"},
            {"invocationId": invocation_id},
            citation_location,
        )
    return list(sources.values())


def claude_read_during_turn(
    root: Path,
    events: list[dict[str, Any]],
    citation_location: dict[str, Any],
) -> list[dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for event in events_since_last_manifest(events):
        if event.get("event") != "instruction_read":
            continue
        instruction = event.get("instruction")
        tool_event_id = str(event.get("tool_event_id") or "")
        if not instruction or not tool_event_id:
            continue
        sources[instruction] = evidence_record(
            root,
            instruction,
            "Read during turn",
            "Instruction source opened by the Read tool during this turn",
            {"runtime": "claude", "toolEventId": tool_event_id},
            {"toolEventId": tool_event_id},
            citation_location,
        )
    return list(sources.values())


def declared_adapters(
    root: Path,
    runtime: str,
    covered: set[str],
    citation_location: dict[str, Any],
) -> list[dict[str, Any]]:
    """Instructions a runtime adapter requires but the runtime never announced."""
    surface = ADAPTER_SURFACES.get(runtime)
    if surface is None:
        return []
    prefix, declaration_kind = surface
    records = []
    for instruction in registered_instructions(root):
        canonical = instruction.get("canonicalPath")
        if not canonical or canonical in covered:
            continue
        adapters = [
            adapter
            for adapter in instruction.get("runtimeAdapters", [])
            if adapter.startswith(prefix)
        ]
        if not adapters:
            continue
        adapter_path = adapters[0]
        records.append(
            evidence_record(
                root,
                canonical,
                "Declared",
                f"Required by {adapter_path} without an authoritative load event",
                {"adapterPath": adapter_path, "declarationKind": declaration_kind},
                {"adapterPath": adapter_path},
                citation_location,
            )
        )
    return records


def codex_baselines(
    root: Path, cwd: Path, citation_location: dict[str, Any]
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
                citation_location,
            )
        )
    return records


def copilot_baselines(
    root: Path, citation_location: dict[str, Any]
) -> list[dict[str, Any]]:
    """GitHub Copilot's documented repository-instructions baseline.

    Unlike Codex's per-scope AGENTS.md walk, Copilot's repository custom
    instructions convention is a single fixed root file
    (`.github/copilot-instructions.md`), not a directory-scoped search — so
    there is no scope walk to mirror here. Whether this hook ever actually
    runs for a Copilot session is a separate, unconfirmed question (AEPI-96);
    this function only describes what Copilot's own discovery rules cover
    when the hook does run.
    """
    candidate = root / ".github" / "copilot-instructions.md"
    if not candidate.is_file():
        return []
    instruction = candidate.relative_to(root).as_posix()
    return [
        evidence_record(
            root,
            instruction,
            "Runtime baseline",
            "GitHub Copilot repository custom instructions discovery",
            {
                "runtime": "copilot",
                "discoveryMechanism": "copilot-instructions-root-file",
                "scopePath": ".",
            },
            {"runtime": "copilot"},
            citation_location,
        )
    ]


def claude_observed(
    root: Path,
    events: list[dict[str, Any]],
    prompt_id: str | None,
    citation_location: dict[str, Any],
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
                citation_location,
            )
    return list(sources.values())


def render_citation(runtime: str, source: dict[str, Any]) -> str:
    """Render one source's citation for the given runtime.

    Claude Code and Copilot route a markdown link through an external-program
    handler that requires a URL scheme and rejects a line suffix, so they get
    a bare workspace-relative reference instead. Codex has no such handler and
    renders a markdown link normally, so Codex gets an absolute-path link.
    """
    citation = source["citation"]
    path = citation.get("workspacePath") or citation["absolutePath"]
    line = citation["line"]
    if runtime != "codex":
        return f"`{path}:{line}`"
    target = f"{citation['absolutePath']}:{line}"
    return f"[{citation['label']}](<{target}>)"


def citation_location(
    root: Path, runtime: str, log_path: Path, line_number: int
) -> dict[str, Any]:
    """Return the structured citation location for one ledger line.

    Stores runtime, workspace-relative path, absolute path, and line as data
    rather than a rendered string, so a runtime's presentation choice never
    has to be baked into recorded evidence.
    """
    absolute_path = log_path.absolute()
    try:
        workspace_path: str | None = absolute_path.relative_to(root).as_posix()
    except ValueError:
        workspace_path = None
    return {
        "runtime": runtime,
        "workspacePath": workspace_path,
        "absolutePath": absolute_path.as_posix(),
        "line": line_number,
    }


def additional_context(
    runtime: str, session_id: str, sources: list[dict[str, Any]]
) -> str:
    """Build the context injected back into the prompt.

    Declares runtime and session identity unconditionally. Session identity
    is stated here rather than left to be inferred from the ledger
    citation's filename: that inference worked, but only as a side effect of
    the ledger being named per session, and it disappeared entirely on turns
    with no hook-observed sources, where no citation is emitted. See
    evidence/side-effects/session-identity-via-instruction-ledger.md."""
    rows = "\n".join(
        f"| {source['instruction']} | {source['evidenceType']} | {source['reason']} |"
        for source in sources
    )
    if not rows:
        rows = "| (no hook-observed sources) | Declared | Complete from turn evidence |"
    # Every hook-seeded source in this manifest was appended as one ledger
    # event, so they share one citation. Hoisting it out of a per-row column
    # keeps the table narrow enough that terminals don't word-wrap the path
    # mid-string, which breaks cmd/ctrl-click file resolution.
    citation_line = (
        f"Ledger citation: {render_citation(runtime, sources[0])}\n\n"
        if sources
        else ""
    )
    return (
        "For this prompt, follow the response contract in "
        f"`{CONTRACT_PATH}`. Append its `Instruction References` table to the "
        "final response. The hook seed below is prompt-scoped; supplement it "
        "with explicitly invoked skills and instructions read during this turn. "
        "Do not claim `Observed` without an authoritative runtime event.\n\n"
        f"{citation_line}"
        "| Instruction | Evidence | Reason |\n"
        "| --- | --- | --- |\n"
        f"{rows}\n\n"
        f"Runtime: {runtime}. Session: {session_id}."
    )


def handle(runtime: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    session_value = payload.get("session_id")
    if not isinstance(session_value, str) or not session_value.strip():
        raise ValueError("session_id is required for instruction evidence")
    session_id = session_value
    event_name = str(payload.get("hook_event_name") or "")
    cwd = Path(payload.get("cwd") or os.getcwd())
    root = repository_root(cwd)
    canonical_root = project_storage_root(root)
    view_root = project_view(root, canonical_root)
    canonical_ledger = ledger_path(root, runtime, session_id)
    log_path = view_root / runtime / canonical_ledger.name

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
                runtime,
                session_id,
                {
                    "event": "instruction_loaded",
                    **runtime_event_metadata(runtime, payload),
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

    if runtime == "claude" and event_name == "UserPromptExpansion":
        command_name = str(payload.get("command_name") or "")
        if command_name in registered_skills(root):
            append_event(
                root,
                runtime,
                session_id,
                {
                    "event": "skill_invoked",
                    **runtime_event_metadata(runtime, payload),
                    "skill": command_name,
                    "path": "user-typed-command",
                    "invocation_id": digest_id(
                        "inv",
                        {
                            "session_id": session_id,
                            "prompt_id": payload.get("prompt_id"),
                            "command_name": command_name,
                        },
                    ),
                    "prompt_id": payload.get("prompt_id"),
                },
            )
        return None

    if runtime == "claude" and event_name == "PreToolUse":
        skill = skill_name_from_tool_input(
            payload.get("tool_input"), registered_skills(root)
        )
        tool_use_id = str(payload.get("tool_use_id") or "")
        if skill and tool_use_id:
            append_event(
                root,
                runtime,
                session_id,
                {
                    "event": "skill_invoked",
                    **runtime_event_metadata(runtime, payload),
                    "skill": skill,
                    "path": "skill-tool",
                    "invocation_id": tool_use_id,
                    "prompt_id": payload.get("prompt_id"),
                },
            )
        return None

    if runtime == "claude" and event_name == "PostToolUse":
        tool_input = payload.get("tool_input")
        file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
        tool_use_id = str(payload.get("tool_use_id") or "")
        if file_path and tool_use_id:
            instruction = display_path(str(file_path), root)
            if instruction in instruction_sources(root):
                append_event(
                    root,
                    runtime,
                    session_id,
                    {
                        "event": "instruction_read",
                        **runtime_event_metadata(runtime, payload),
                        "instruction": instruction,
                        "tool_event_id": tool_use_id,
                        "prompt_id": payload.get("prompt_id"),
                    },
                )
        return None

    if event_name and event_name != "UserPromptSubmit":
        return None

    prompt_id = payload.get("prompt_id") or payload.get("turn_id")
    def build_manifest(
        events: list[dict[str, Any]], line_number: int
    ) -> dict[str, Any]:
        # Every record in this manifest lands on the single ledger line the
        # manifest is about to occupy, so a citation opens the log at the
        # record itself.
        location = citation_location(root, runtime, log_path, line_number)
        if runtime == "claude":
            sources = claude_observed(root, events, prompt_id, location)
            sources += claude_explicitly_invoked(root, events, location)
            sources += claude_read_during_turn(root, events, location)
        elif runtime == "codex":
            sources = codex_baselines(root, cwd, location)
        elif runtime == "copilot":
            sources = copilot_baselines(root, location)
        else:
            sources = []
        sources += declared_adapters(
            root,
            runtime,
            {source["instruction"] for source in sources},
            location,
        )
        return {
            "event": "prompt_manifest",
            "prompt_id": prompt_id,
            **runtime_event_metadata(runtime, payload),
            "runtimeSessionId": session_id,
            "sources": sources,
        }

    manifest = append_manifest(root, runtime, session_id, build_manifest)
    sources = manifest["sources"]
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context(runtime, session_id, sources),
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime", choices=("claude", "codex", "copilot"), required=True
    )
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
