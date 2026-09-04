#!/usr/bin/env python3
"""Evaluate whether a governed pull request is ready for human acceptance."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


class ReadinessError(RuntimeError):
    """Raised when the supplied evidence does not match the readiness contract."""


@dataclass(frozen=True)
class ReadinessResult:
    schemaVersion: int
    ready: bool
    headSha: str
    blockers: tuple[str, ...]
    disputedThreads: tuple[str, ...]
    disputedFindings: tuple[str, ...]


COPILOT_STATUSES = frozenset({"pending", "success", "failure", "neutral"})
REQUIRED_CHECK_NAMES = frozenset({"control-plane-guards", "aep-copilot-review"})


def required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReadinessError(f"{field} must be a non-empty string")
    return value


def _review_id(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ReadinessError("copilotReview.reviewId must be a string or integer")
    if isinstance(value, int) and value < 1:
        raise ReadinessError("copilotReview.reviewId integer must be positive")
    rendered = str(value).strip()
    if not rendered:
        raise ReadinessError("copilotReview.reviewId must be non-empty")
    return rendered


def _identifier(value: object, field: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ReadinessError(f"{field} must be a string or integer")
    if isinstance(value, int) and value < 1:
        raise ReadinessError(f"{field} integer must be positive")
    rendered = str(value).strip()
    if not rendered:
        raise ReadinessError(f"{field} must be non-empty")
    return rendered


def _head_sha(value: object) -> str:
    rendered = required_string(value, "copilotReview.headSha").strip()
    if len(rendered) < 7:
        raise ReadinessError("copilotReview.headSha must be at least 7 characters")
    return rendered


def _finding(value: object, index: int, *, source: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReadinessError(f"{source}[{index}] must be an object")
    finding_id = _identifier(value.get("id"), f"{source}[{index}].id")
    actionable = value.get("actionable")
    if not isinstance(actionable, bool):
        raise ReadinessError(f"{source}[{index}].actionable must be boolean")
    disposition = value.get("disposition", "open")
    if disposition not in {"open", "disputed", "suppressed"}:
        raise ReadinessError(
            f"{source}[{index}].disposition must be open, disputed, or suppressed"
        )
    finding_source = value.get("source", "unknown")
    if finding_source not in {"line", "summary", "suppressed", "unknown"}:
        raise ReadinessError(f"{source}[{index}].source has unknown format")
    return {
        "id": finding_id,
        "source": finding_source,
        "actionable": actionable,
        "disposition": disposition,
    }


def normalize_copilot_review(review: object, *, current_head: str | None = None) -> dict[str, Any]:
    """Normalize provider review payloads into the readiness contract.

    A provider may call the review ``COMMENTED`` even when it contains no
    actionable finding. That state is deliberately not treated as clean: each
    finding must be classified, or the review remains a failure/unknown result.
    """
    if not isinstance(review, dict):
        raise ReadinessError("Copilot review must be an object")
    head = _head_sha(review.get("headSha"))
    review_id = _review_id(review.get("reviewId"))
    submitted_at = required_string(review.get("submittedAt"), "copilotReview.submittedAt")

    raw_findings = review.get("normalizedFindings")
    if raw_findings is None:
        raw_findings = []
        for key, source in (("lineComments", "line"), ("summaryFindings", "summary"), ("suppressedFindings", "suppressed")):
            entries = review.get(key, [])
            if not isinstance(entries, list):
                raise ReadinessError(f"copilotReview.{key} must be an array")
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ReadinessError(f"copilotReview.{key} entries must be objects")
                copied = dict(entry)
                copied.setdefault("source", source)
                if source == "suppressed":
                    copied.setdefault("actionable", False)
                    copied.setdefault("disposition", "suppressed")
                raw_findings.append(copied)
    if not isinstance(raw_findings, list):
        raise ReadinessError("copilotReview.normalizedFindings must be an array")

    # One id may arrive more than once. Keeping the first would let a benign
    # copy hide a later actionable or unrecognized one, so duplicates merge
    # toward the more severe reading; position follows the first occurrence.
    normalized: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(raw_findings):
        finding = _finding(entry, index, source="copilotReview.normalizedFindings")
        existing = by_id.get(finding["id"])
        if existing is None:
            by_id[finding["id"]] = finding
            normalized.append(finding)
            continue
        existing["actionable"] = existing["actionable"] or finding["actionable"]
        if finding["source"] == "unknown":
            existing["source"] = "unknown"
        if finding["disposition"] == "open":
            existing["disposition"] = "open"

    disputed_raw = review.get("disputedFindings", [])
    if not isinstance(disputed_raw, list):
        raise ReadinessError("copilotReview.disputedFindings must be an array")
    disputed = []
    for index, entry in enumerate(disputed_raw):
        if isinstance(entry, (str, int)) and not isinstance(entry, bool):
            disputed.append(_identifier(entry, f"copilotReview.disputedFindings[{index}]"))
        elif isinstance(entry, dict):
            disputed.append(
                _identifier(entry.get("id"), f"copilotReview.disputedFindings[{index}].id")
            )
        else:
            raise ReadinessError(f"copilotReview.disputedFindings[{index}] is not identifiable")
    disputed = list(dict.fromkeys(disputed))

    status = review.get("status")
    if status is None:
        state = review.get("state")
        if state in {"PENDING", "IN_PROGRESS"}:
            status = "pending"
        elif state in {"COMMENTED", "CHANGES_REQUESTED"}:
            status = "failure"
        elif state == "APPROVED":
            status = "success"
        else:
            raise ReadinessError("copilotReview.status has unknown format")
    if status not in COPILOT_STATUSES:
        raise ReadinessError("copilotReview.status has unknown format")

    # A COMMENTED review without classified findings is never evidence of a
    # clean review. Keep it visible as an unrecognized finding.
    if review.get("state") == "COMMENTED" and not normalized and not disputed:
        normalized.append({
            "id": f"review:{review_id}:unclassified",
            "source": "summary",
            "actionable": True,
            "disposition": "open",
        })
        status = "failure"

    if current_head is not None and head != current_head:
        status = "failure"
    actionable = sum(
        1 for item in normalized if item["actionable"] and item["disposition"] == "open"
    )
    unknown = sum(1 for item in normalized if item["source"] == "unknown")
    return {
        "status": status,
        "reviewId": review_id,
        "headSha": head,
        "submittedAt": submitted_at,
        "normalizedFindings": normalized,
        "disputedFindings": disputed,
        "actionableFindings": actionable,
        "unrecognizedFindings": unknown,
    }


def evaluate(snapshot: object) -> ReadinessResult:
    if not isinstance(snapshot, dict):
        raise ReadinessError("readiness evidence must be a JSON object")
    if snapshot.get("schemaVersion") != 2:
        raise ReadinessError("schemaVersion must be 2")

    head = required_string(snapshot.get("headSha"), "headSha")
    blockers: list[str] = []
    if snapshot.get("currentWithBase") is not True:
        blockers.append("delivery branch is not current with main")

    checks = snapshot.get("requiredChecks")
    if not isinstance(checks, list) or not checks:
        raise ReadinessError("requiredChecks must contain at least one check")
    check_names: set[str] = set()
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise ReadinessError(f"requiredChecks[{index}] must be an object")
        name = required_string(check.get("name"), f"requiredChecks[{index}].name")
        status = required_string(check.get("status"), f"requiredChecks[{index}].status")
        if name in check_names:
            raise ReadinessError(f"requiredChecks contains duplicate check {name}")
        check_names.add(name)
        if status != "success":
            blockers.append(f"required check {name} is {status}")

    missing_checks = REQUIRED_CHECK_NAMES - check_names
    if missing_checks:
        blockers.append("missing required check(s): " + ", ".join(sorted(missing_checks)))

    copilot = normalize_copilot_review(snapshot.get("copilotReview"), current_head=head)
    if copilot["headSha"] != head:
        blockers.append("latest Copilot review does not cover the current head")
    if copilot["status"] != "success":
        blockers.append(f"Copilot review status is {copilot['status']}")
    if copilot["actionableFindings"]:
        blockers.append(f"Copilot review has {copilot['actionableFindings']} actionable finding(s)")
    if copilot["unrecognizedFindings"]:
        blockers.append("Copilot review has unrecognized finding(s)")

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
        schemaVersion=2,
        ready=not blockers,
        headSha=head,
        blockers=tuple(blockers),
        disputedThreads=tuple(disputed),
        disputedFindings=tuple(copilot["disputedFindings"]),
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
                "disputedFindings": list(result.disputedFindings),
            },
            indent=2,
        )
    )
    return 0 if result.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
