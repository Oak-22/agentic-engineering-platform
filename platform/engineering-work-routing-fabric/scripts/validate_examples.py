#!/usr/bin/env python3
"""Validate Engineering Work Routing Fabric v0 schemas and fixtures."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


COMPONENT_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = COMPONENT_ROOT / "schemas"
EXAMPLES = COMPONENT_ROOT / "examples"
POLICY_PATH = COMPONENT_ROOT / "policies" / "loop-guard-policy.json"

EVENT_ID = re.compile(r"^evt-[a-z0-9][a-z0-9-]*$")
DECISION_ID = re.compile(r"^decision-[a-z0-9][a-z0-9-]*$")
RECEIPT_ID = re.compile(r"^receipt-[a-z0-9][a-z0-9-]*$")
EVENT_TYPE = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+$")

DESTINATIONS = {"telemetry", "knowledge-base", "jira", "confluence", "git"}
WRITE_ACTIONS = {"create", "append", "update", "publish"}
ROUTE_ACTIONS = WRITE_ACTIONS | {"suppress", "defer", "no-op"}
RECOMMENDATIONS = {"continue", "return-prior", "replan", "stop", "intervene"}
NO_CHANGE_OUTCOMES = {
    "already-applied",
    "already-satisfied",
    "suppressed",
    "deferred",
    "rejected",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise AssertionError(f"{path}: expected a JSON object")
    return value


def require_keys(value: dict[str, Any], keys: set[str], label: str) -> None:
    missing = sorted(keys - value.keys())
    if missing:
        raise AssertionError(f"{label}: missing keys {missing}")


def validate_event(event: dict[str, Any], label: str) -> None:
    require_keys(
        event,
        {
            "schemaVersion",
            "eventId",
            "occurredAt",
            "eventType",
            "summary",
            "executionMode",
            "source",
            "correlationId",
            "hopCount",
            "artifacts",
        },
        label,
    )
    assert event["schemaVersion"] == 1, label
    assert EVENT_ID.fullmatch(event["eventId"]), label
    assert EVENT_TYPE.fullmatch(event["eventType"]), label
    assert event["executionMode"] in {"human", "agent", "hybrid"}, label
    assert isinstance(event["summary"], str) and event["summary"], label
    assert isinstance(event["hopCount"], int) and event["hopCount"] >= 0, label
    assert isinstance(event["artifacts"], list), label
    require_keys(event["source"], {"surface", "repository"}, f"{label}.source")
    if "parentEventId" in event:
        assert EVENT_ID.fullmatch(event["parentEventId"]), label
    if "proposedAction" in event:
        action = event["proposedAction"]
        require_keys(
            action,
            {"actionType", "destination", "target", "intent"},
            f"{label}.proposedAction",
        )
        assert action["actionType"] in WRITE_ACTIONS, label
        assert action["destination"] in DESTINATIONS, label


def validate_decision(decision: dict[str, Any], label: str) -> None:
    require_keys(
        decision,
        {
            "schemaVersion",
            "decisionId",
            "eventId",
            "decidedAt",
            "policyVersion",
            "loopAssessment",
            "routes",
        },
        label,
    )
    assert decision["schemaVersion"] == 1, label
    assert DECISION_ID.fullmatch(decision["decisionId"]), label
    assert EVENT_ID.fullmatch(decision["eventId"]), label
    assessment = decision["loopAssessment"]
    require_keys(
        assessment,
        {"classification", "recurrenceCount", "recommendation"},
        f"{label}.loopAssessment",
    )
    assert assessment["recommendation"] in RECOMMENDATIONS, label
    assert assessment["recurrenceCount"] >= 0, label
    assert isinstance(decision["routes"], list) and decision["routes"], label
    for index, route in enumerate(decision["routes"]):
        route_label = f"{label}.routes[{index}]"
        require_keys(
            route,
            {"destination", "action", "reasonCode", "rationale", "approval"},
            route_label,
        )
        assert route["destination"] in DESTINATIONS, route_label
        assert route["action"] in ROUTE_ACTIONS, route_label
        approval = route["approval"]
        require_keys(approval, {"required", "status"}, f"{route_label}.approval")
        if approval["required"]:
            assert approval["status"] in {"pending", "approved", "rejected"}, route_label
        else:
            assert approval["status"] == "not-required", route_label
        if route["action"] in WRITE_ACTIONS:
            require_keys(
                route,
                {"target", "idempotencyKey", "actionFingerprint"},
                route_label,
            )


def validate_receipt(receipt: dict[str, Any], label: str) -> None:
    require_keys(
        receipt,
        {
            "schemaVersion",
            "receiptId",
            "decisionId",
            "eventId",
            "destination",
            "idempotencyKey",
            "outcome",
            "stateChanged",
            "observedAt",
        },
        label,
    )
    assert receipt["schemaVersion"] == 1, label
    assert RECEIPT_ID.fullmatch(receipt["receiptId"]), label
    assert DECISION_ID.fullmatch(receipt["decisionId"]), label
    assert EVENT_ID.fullmatch(receipt["eventId"]), label
    assert receipt["destination"] in DESTINATIONS, label
    if receipt["outcome"] in NO_CHANGE_OUTCOMES:
        assert receipt["stateChanged"] is False, label
    if receipt["outcome"] == "already-applied":
        assert RECEIPT_ID.fullmatch(receipt["originalReceiptId"]), label


def validate_schema_documents() -> None:
    for name in (
        "work-event.schema.json",
        "routing-decision.schema.json",
        "delivery-receipt.schema.json",
    ):
        schema = load_json(SCHEMAS / name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["type"] == "object"


def load_fixture_directory(
    directory: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        value = load_json(path)
        label = str(path.relative_to(COMPONENT_ROOT))
        if "eventId" in value and "eventType" in value:
            validate_event(value, label)
            events.append(value)
        elif "decisionId" in value and "routes" in value:
            validate_decision(value, label)
            decisions.append(value)
        elif "receiptId" in value and "outcome" in value:
            validate_receipt(value, label)
            receipts.append(value)
        else:
            raise AssertionError(f"{label}: unrecognized fixture type")

    event_ids = {event["eventId"] for event in events}
    decision_by_id = {decision["decisionId"]: decision for decision in decisions}
    assert len(event_ids) == len(events), f"{directory.name}: duplicate event IDs"
    assert len(decision_by_id) == len(decisions), f"{directory.name}: duplicate decisions"
    for decision in decisions:
        assert decision["eventId"] in event_ids, (
            f"{directory.name}: decision references unknown event"
        )
    for receipt in receipts:
        decision = decision_by_id.get(receipt["decisionId"])
        assert decision is not None, f"{directory.name}: receipt references unknown decision"
        assert receipt["eventId"] == decision["eventId"], (
            f"{directory.name}: receipt event does not match decision"
        )
    return events, decisions, receipts


def validate_append_example() -> tuple[int, int, int]:
    directory = EXAMPLES / "append-to-existing-implementation-record"
    events, decisions, receipts = load_fixture_directory(directory)
    assert len(events) == len(decisions) == len(receipts) == 1
    routes = {route["destination"]: route for route in decisions[0]["routes"]}
    assert routes["knowledge-base"]["action"] == "append"
    assert routes["knowledge-base"]["reasonCode"] == "same-outcome-boundary"
    assert routes["jira"]["action"] == "suppress"
    assert routes["confluence"]["action"] == "suppress"
    assert receipts[0]["outcome"] == "applied"
    return len(events), len(decisions), len(receipts)


def validate_exact_duplicate_example() -> tuple[int, int, int]:
    directory = EXAMPLES / "exact-duplicate-suppression"
    events, decisions, receipts = load_fixture_directory(directory)
    assert len(events) == len(decisions) == 1
    assert len(receipts) == 2
    first = next(receipt for receipt in receipts if receipt["outcome"] == "applied")
    duplicate = next(
        receipt for receipt in receipts if receipt["outcome"] == "already-applied"
    )
    assert first["idempotencyKey"] == duplicate["idempotencyKey"]
    assert duplicate["originalReceiptId"] == first["receiptId"]
    assert duplicate["stateChanged"] is False
    return len(events), len(decisions), len(receipts)


def validate_semantic_loop_example() -> tuple[int, int, int]:
    directory = EXAMPLES / "semantic-loop-suppression"
    events, decisions, receipts = load_fixture_directory(directory)
    assert len(events) == len(decisions) == len(receipts) == 2
    assert len({event["eventId"] for event in events}) == 2
    assert len({event["correlationId"] for event in events}) == 1
    first_decision = next(
        decision
        for decision in decisions
        if decision["loopAssessment"]["classification"] == "none"
    )
    repeated_decision = next(
        decision
        for decision in decisions
        if decision["loopAssessment"]["classification"] == "semantic-recurrence"
    )
    assert repeated_decision["loopAssessment"]["recommendation"] == "replan"
    assert repeated_decision["loopAssessment"]["matchedEventId"] == first_decision["eventId"]
    first_route = first_decision["routes"][0]
    repeated_route = repeated_decision["routes"][0]
    assert first_route["actionFingerprint"] == repeated_route["actionFingerprint"]
    assert first_route["idempotencyKey"] != repeated_route["idempotencyKey"]
    assert repeated_route["action"] == "suppress"
    suppressed = next(receipt for receipt in receipts if receipt["outcome"] == "suppressed")
    assert suppressed["stateChanged"] is False
    return len(events), len(decisions), len(receipts)


def validate_all() -> dict[str, int]:
    validate_schema_documents()
    policy = load_json(POLICY_PATH)
    assert policy["policyId"] == "loop-guard-v0.1"
    assert policy["exactDuplicate"]["action"] == "return-prior"
    assert policy["semanticRecurrence"]["firstRecurrence"] == "replan"
    assert policy["hopLimit"]["maximum"] == 8

    totals = {"events": 0, "decisions": 0, "receipts": 0}
    for result in (
        validate_append_example(),
        validate_exact_duplicate_example(),
        validate_semantic_loop_example(),
    ):
        totals["events"] += result[0]
        totals["decisions"] += result[1]
        totals["receipts"] += result[2]
    return totals


def main() -> None:
    totals = validate_all()
    print("Engineering Work Routing Fabric fixtures valid")
    print(
        f"validated {totals['events']} events, "
        f"{totals['decisions']} decisions, "
        f"and {totals['receipts']} receipts"
    )


if __name__ == "__main__":
    main()
