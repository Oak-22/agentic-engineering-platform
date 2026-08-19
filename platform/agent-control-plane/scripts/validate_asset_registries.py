#!/usr/bin/env python3
"""Validate canonical asset registries against runtime projections."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / "platform" / "agent-control-plane" / "agent-assets"


def load(relative: str) -> dict:
    path = ROOT / relative
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot load {relative}: {error}") from error


def require_file(relative: str, label: str) -> None:
    if not (ROOT / relative).is_file():
        raise ValueError(f"{label} does not resolve: {relative}")


def validate_hooks() -> int:
    registry = load("platform/agent-control-plane/agent-assets/hooks/hooks_registry.json")
    count = 0
    for hook in registry["hooks"]:
        for field in ("implementation", "documentation"):
            require_file(hook[field], f"hook {hook['id']} {field}")
        registrations = hook.get("runtimes", [])
        if "registration" in hook:
            registrations = [hook]
        for registration in registrations:
            require_file(registration["registration"], f"hook {hook['id']} registration")
        count += 1
    return count


def validate_skills() -> int:
    registry = load("platform/agent-control-plane/agent-assets/skills/skills_registry.json")
    entries = {skill["id"]: skill for skill in registry["skills"]}
    canonical_dirs = {
        path.name
        for path in (ASSETS / "skills").iterdir()
        if path.is_dir()
    }
    if canonical_dirs != set(entries):
        raise ValueError(
            f"skill registry drift: canonical={sorted(canonical_dirs)} "
            f"registered={sorted(entries)}"
        )
    for skill in entries.values():
        require_file(skill["skillFile"], f"skill {skill['id']} SKILL.md")
        for binding in skill["runtimeBindings"]:
            path = ROOT / binding
            if not path.is_symlink():
                raise ValueError(f"skill {skill['id']} binding is not a symlink: {binding}")
            if not path.exists():
                raise ValueError(f"skill {skill['id']} binding does not resolve: {binding}")
    return len(entries)


def validate_instructions() -> int:
    registry = load("platform/agent-control-plane/agent-assets/instructions/instructions_registry.json")
    entries = {instruction["id"]: instruction for instruction in registry["instructions"]}
    canonical_files = {
        path.stem
        for path in (ASSETS / "instructions").glob("*.md")
        if path.name != "README.md"
    }
    if canonical_files != set(entries):
        raise ValueError(
            f"instruction registry drift: canonical={sorted(canonical_files)} "
            f"registered={sorted(entries)}"
        )
    for instruction in entries.values():
        require_file(instruction["canonicalPath"], f"instruction {instruction['id']}")
        for adapter in instruction["runtimeAdapters"]:
            require_file(adapter, f"instruction {instruction['id']} adapter")
            adapter_path = ROOT / adapter
            imports = [line[1:] for line in adapter_path.read_text(encoding="utf-8").splitlines() if line.startswith("@")]
            if not imports:
                raise ValueError(f"instruction adapter has no canonical import: {adapter}")
            if not (adapter_path.parent / imports[0]).is_file():
                raise ValueError(f"instruction adapter import does not resolve: {adapter}")
    return len(entries)


def validate_contract_surface() -> int:
    """Every contract compiles, and every evidence type has a producer."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import validate_contracts

    try:
        names = validate_contracts.schema_names()
        for name in names:
            validate_contracts.validator_for(name)
    except validate_contracts.ContractUnavailableError as error:
        raise ValueError(str(error)) from error

    import instruction_manifest_hook

    index = {
        **instruction_manifest_hook.STORE_INDEX,
        "repositoryId": "git:validation",
        "projectKey": "0" * 24,
    }
    errors = validate_contracts.validate_store_index(index)
    if errors:
        raise ValueError(f"store index does not conform: {'; '.join(errors)}")

    hook_source = Path(instruction_manifest_hook.__file__).read_text(encoding="utf-8")
    unproduced = [
        evidence_type
        for evidence_type in validate_contracts.evidence_types()
        if f'"{evidence_type}"' not in hook_source
    ]
    if unproduced:
        raise ValueError(
            f"evidence types declared in the contract without a producer: {unproduced}"
        )
    return len(names)


def main() -> int:
    try:
        hooks = validate_hooks()
        skills = validate_skills()
        instructions = validate_instructions()
        contracts = validate_contract_surface()
    except ValueError as error:
        print(f"asset registry validation failed: {error}", file=sys.stderr)
        return 1
    print(
        f"asset registries valid: {hooks} hooks, {skills} skills, "
        f"{instructions} instructions, {contracts} contracts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
