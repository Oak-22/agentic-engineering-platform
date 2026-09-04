#!/usr/bin/env python3
"""Normalize one Copilot review and calculate the exact-head check result.

The GitHub workflow owns API calls and check-run publication. This module owns
the provider-neutral interpretation so the same rules run locally and in CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

# Keep direct script execution and the repository's import-by-path tests on the
# same standard-library-only module path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_pull_request_readiness import ReadinessError, normalize_copilot_review


def gate(review: object, *, head_sha: str) -> dict[str, Any]:
    """Return the normalized review and its check conclusion."""
    normalized = normalize_copilot_review(review, current_head=head_sha)
    if normalized["headSha"] != head_sha:
        conclusion = "failure"
    elif normalized["status"] == "pending":
        conclusion = "pending"
    elif normalized["actionableFindings"] or normalized["unrecognizedFindings"]:
        conclusion = "failure"
    elif normalized["status"] == "neutral":
        conclusion = "neutral"
    elif normalized["status"] == "success":
        conclusion = "success"
    else:
        conclusion = "failure"
    return {"conclusion": conclusion, "review": normalized}


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize an exact-head Copilot review")
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("input", nargs="?", type=Path, help="review JSON; omit for stdin")
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    args = parse_args(arguments)
    try:
        raw = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
        result = gate(json.loads(raw), head_sha=args.head_sha)
    except (OSError, json.JSONDecodeError, ReadinessError) as error:
        print(f"Copilot review is not safely normalizable: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["conclusion"] in {"success", "neutral"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
