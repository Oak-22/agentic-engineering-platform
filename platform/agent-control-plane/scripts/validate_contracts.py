#!/usr/bin/env python3
"""Compile the portable contract schemas and validate instances against them.

The schema files under ``contracts/`` are the single source of truth for the
shapes defined here. This module resolves and compiles them; it does not
restate any rule they contain.

``jsonschema`` is imported here and nowhere in the hook implementations. Hooks
run under the runtime's bare ``python3`` with no virtual environment, so a
third-party import on that path would couple every prompt to an unmanaged
dependency. Validation runs from tests and from the registry validator, which
are invoked deliberately and can fail loudly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"

INSTRUCTION_EVIDENCE_RECORD = "instruction-evidence-record.schema.json"
INSTRUCTION_EVIDENCE_STORE = "instruction-evidence-store.schema.json"
AGENT_RUN_ATTEMPT = "agent-run-attempt.schema.json"
JIRA_WORK_ITEM_METADATA = "jira-work-item-metadata.schema.json"


class ContractUnavailableError(RuntimeError):
    """Raised when the validation dependency or a schema file is missing."""


def _require_jsonschema():
    try:
        import jsonschema
    except ModuleNotFoundError as error:  # pragma: no cover - environment guard
        raise ContractUnavailableError(
            "jsonschema is required for contract validation. The system "
            "interpreter is externally managed, so install into a virtual "
            "environment:\n"
            "  cd platform/agent-control-plane\n"
            "  python3 -m venv .venv\n"
            '  .venv/bin/python -m pip install -e ".[validation]"\n'
            "then run this check with .venv/bin/python."
        ) from error
    return jsonschema


def load_schema(name: str) -> dict[str, Any]:
    path = CONTRACTS / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractUnavailableError(f"cannot load contract {name}: {error}") from error


def schema_names() -> list[str]:
    return sorted(path.name for path in CONTRACTS.glob("*.schema.json"))


def validator_for(name: str):
    """Return a compiled validator, raising if the schema itself is invalid."""
    jsonschema = _require_jsonschema()
    schema = load_schema(name)
    validator_class = jsonschema.validators.validator_for(schema)
    validator_class.check_schema(schema)
    return validator_class(schema)


def _errors(name: str, instance: Any) -> list[str]:
    validator = validator_for(name)
    messages = []
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path)):
        location = "/".join(str(part) for part in error.path) or "<root>"
        messages.append(f"{location}: {error.message}")
    return messages


def validate_record(record: Any) -> list[str]:
    """Return human-readable errors for one instruction-evidence record."""
    return _errors(INSTRUCTION_EVIDENCE_RECORD, record)


def validate_store_index(index: Any) -> list[str]:
    """Return human-readable errors for a generated store index."""
    return _errors(INSTRUCTION_EVIDENCE_STORE, index)


def validate_attempt(attempt: Any) -> list[str]:
    """Return human-readable errors for one agent-run attempt record."""
    return _errors(AGENT_RUN_ATTEMPT, attempt)


def validate_work_item_metadata(metadata: Any) -> list[str]:
    """Return human-readable errors for governed Jira work-item metadata."""
    return _errors(JIRA_WORK_ITEM_METADATA, metadata)


def evidence_types() -> list[str]:
    """Return the evidence types the record contract admits."""
    schema = load_schema(INSTRUCTION_EVIDENCE_RECORD)
    return list(schema["$defs"]["common"]["properties"]["evidenceType"]["enum"])
