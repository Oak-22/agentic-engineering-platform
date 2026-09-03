#!/usr/bin/env python3
"""Evaluate whether a governed pull request is ready for human acceptance."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class ReadinessError(RuntimeError):
    """Raised when the supplied evidence does not match the readiness contract."""


@dataclass(frozen=True)
class ReadinessResult:
    schemaVersion: int
    ready: bool
    headSha: str
    blockers: tuple[str, ...]
    disputedThreads: tuple[str, ...]


def required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReadinessError(f"{field} must be a non-empty string")
    return value


def evaluate(snapshot: object) -> ReadinessResult:
    if not isinstance(snapshot, dict):
        raise ReadinessError("readiness evidence must be a JSON object")
    if snapshot.get("schemaVersion") != 1:
        raise ReadinessError("schemaVersion must be 1")

    head = required_string(snapshot.get("headSha"), "headSha")
    blockers: list[str] = []
    if snapshot.get("currentWithBase") is not True:
        blockers.append("delivery branch is not current with main")

    checks = snapshot.get("requiredChecks")
    if not isinstance(checks, list) or not checks:
        raise ReadinessError("requiredChecks must contain at least one check")
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise ReadinessError(f"requiredChecks[{index}] must be an object")
        name = required_string(check.get("name"), f"requiredChecks[{index}].name")
        status = required_string(check.get("status"), f"requiredChecks[{index}].status")
        if status != "success":
            blockers.append(f"required check {name} is {status}")

    copilot = snapshot.get("copilotReview")
    if not isinstance(copilot, dict):
        raise ReadinessError("copilotReview must be an object")
    reviewed_head = required_string(copilot.get("headSha"), "copilotReview.headSha")
    actionable = copilot.get("actionableFindings")
    if not isinstance(actionable, int) or isinstance(actionable, bool) or actionable < 0:
        raise ReadinessError("copilotReview.actionableFindings must be a non-negative integer")
    if reviewed_head != head:
        blockers.append("latest Copilot review does not cover the current head")
    if actionable:
        blockers.append(f"Copilot review has {actionable} actionable finding(s)")

    threads = snapshot.get("reviewThreads")
    if not isinstance(threads, list):
        raise ReadinessError("reviewThreads must be an array")
    disputed: list[str] = []
    for index, thread in enumerate(threads):
        if not isinstance(thread, dict):
            raise ReadinessError(f"reviewThreads[{index}] must be an object")
        identifier = required_string(thread.get("id"), f"reviewThreads[{index}].id")
        state = required_string(thread.get("state"), f"reviewThreads[{index}].state")
        if state == "actionable":
            blockers.append(f"review thread {identifier} remains actionable")
        elif state == "disputed":
            disputed.append(identifier)
        elif state != "resolved":
            raise ReadinessError(
                f"reviewThreads[{index}].state must be resolved, actionable, or disputed"
            )

    if snapshot.get("evidenceAligned") is not True:
        blockers.append("Jira and pull-request delivery evidence are not aligned")

    return ReadinessResult(
        schemaVersion=1,
        ready=not blockers,
        headSha=head,
        blockers=tuple(blockers),
        disputedThreads=tuple(disputed),
    )


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate governed pull-request readiness evidence."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="JSON evidence file; omit to read stdin",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    args = parse_args(arguments)
    try:
        raw = args.input.read_text() if args.input else sys.stdin.read()
        result = evaluate(json.loads(raw))
    except (OSError, json.JSONDecodeError, ReadinessError) as error:
        print(f"Pull-request readiness evidence is invalid: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "schemaVersion": result.schemaVersion,
                "ready": result.ready,
                "headSha": result.headSha,
                "blockers": list(result.blockers),
                "disputedThreads": list(result.disputedThreads),
            },
            indent=2,
        )
    )
    return 0 if result.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
