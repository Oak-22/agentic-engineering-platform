#!/usr/bin/env python3
"""Render evidence/assertion-to-evidence/ledger.md from ledger.json.

The JSON is the source of truth; the Markdown is a derived projection whose
tallies are computed rather than hand-maintained. ``--check`` reports a stale
render without writing, so CI can refuse a ledger whose counts disagree with
its rows. Enum fields are validated here with the standard library so the
render never depends on ``jsonschema``; the contract under ``contracts/``
remains the authoritative schema.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
LEDGER_DIR = ROOT / "evidence" / "assertion-to-evidence"
SOURCE_PATH = LEDGER_DIR / "ledger.json"
RENDER_PATH = LEDGER_DIR / "ledger.md"

CONFIRMED = ("unlabelled", "green", "yellow", "red")
DIRECTION = ("never", "expired", "undetermined")
CAUGHT = ("yes", "no")
NONE = "none"

GENERATED_MARKER = (
    "<!-- generated from ledger.json by "
    "platform/agent-control-plane/scripts/render_assertion_ledger.py; "
    "edit the JSON, then re-run the script -->"
)

COLUMN_KEY = [
    ("Confirmed",
     "A human's label on the finding's quality: **green** — holds as stated; "
     "**yellow** — holds with a caveat noted in the row; **red** — does not hold. "
     "A row enters as **unlabelled** and stays so until a human reads it."),
    ("Found by",
     "Who judged the assertion unsupported: **human**, or `<runtime>:<session>` "
     "(the same session ID the commit trailer carries). **unrecorded** — the "
     "judging session was not captured."),
    ("Direction",
     "**never** — the evidence was never produced. **expired** — it existed and "
     "stopped being true. **undetermined** — not yet established which."),
    ("Countermeasure that should have caught it",
     "The mechanism that, if operating, would have surfaced the instance before "
     "a human did. **none** — no such mechanism exists; the instance is a current gap."),
    ("Caught?",
     "**yes** — the countermeasure surfaced it. **no** — a human found it first; "
     "the row says how."),
    ("Fixed", "What was done, or **open** with a pointer to where it is tracked."),
]

INSTANCE_COLUMNS = [
    "#", "Confirmed", "Found", "Found by", "Where", "Asserted", "Actual",
    "Direction", "Countermeasure that should have caught it", "Caught?", "Fixed",
]


def load_source(path: Path = SOURCE_PATH) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot load {path}: {error}") from error


def validate(source: dict) -> None:
    """Enum and referential checks that the render depends on. Actionable on failure."""
    known = set(source.get("countermeasures", []))
    seen_ids: set[int] = set()
    for row in source.get("instances", []):
        rid = row.get("id")
        if rid in seen_ids:
            raise ValueError(f"instance id {rid} appears twice")
        seen_ids.add(rid)
        for field, allowed in (("confirmed", CONFIRMED), ("direction", DIRECTION), ("caught", CAUGHT)):
            if row.get(field) not in allowed:
                raise ValueError(f"instance {rid}: {field}={row.get(field)!r} not in {allowed}")
        cm = row.get("countermeasure")
        if cm != NONE and cm not in known:
            raise ValueError(
                f"instance {rid}: countermeasure {cm!r} is not listed under countermeasures; "
                f"add it there or use {NONE!r}"
            )
        if row["confirmed"] in ("yellow", "red") and not row.get("confirmedNote"):
            raise ValueError(f"instance {rid}: confirmed={row['confirmed']} requires confirmedNote")


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _with_note(value: str, note: str | None) -> str:
    return f"{value} — {note}" if note else value


def _found(row: dict) -> str:
    found = row["found"]
    recorded = row.get("recorded")
    return f"{found} (recorded {recorded})" if recorded and recorded != found else found


def render_instance_row(row: dict) -> str:
    cells = [
        str(row["id"]),
        _with_note(row["confirmed"], row.get("confirmedNote")),
        _found(row),
        row["foundBy"],
        row["where"],
        row["asserted"],
        row["actual"],
        row["direction"],
        _with_note(row["countermeasure"], row.get("countermeasureNote")),
        _with_note(row["caught"], row.get("caughtNote")),
        row["fixed"],
    ]
    return "| " + " | ".join(_cell(c) for c in cells) + " |"


def tallies(source: dict) -> list[tuple[str, str, str, str]]:
    """Per-countermeasure rows: (name, should-have-caught, caught, missed)."""
    should = Counter()
    caught = Counter()
    for row in source["instances"]:
        cm = row["countermeasure"]
        should[cm] += 1
        if row["caught"] == "yes":
            caught[cm] += 1
    out = []
    for cm in source["countermeasures"]:
        n = should[cm]
        if n == 0:
            out.append((cm, "0", "n/a", "n/a"))
        else:
            out.append((cm, str(n), str(caught[cm]), str(n - caught[cm])))
    if should[NONE]:
        out.append(("no countermeasure exists", str(should[NONE]), "n/a", "n/a"))
    return out


def direction_line(source: dict) -> str:
    counts = Counter(row["direction"] for row in source["instances"])
    parts = [f"{d} {counts[d]}" for d in DIRECTION if counts[d]]
    return "By direction: " + ", ".join(parts) + "."


def render(source: dict) -> str:
    lines = [
        "# Assertion-to-Evidence Ledger",
        "",
        GENERATED_MARKER,
        "",
        "## Column key",
        "",
        "| Column | Values |",
        "| --- | --- |",
    ]
    lines.extend(f"| {name} | {desc} |" for name, desc in COLUMN_KEY)
    lines += [
        "",
        "## Instances",
        "",
        "| " + " | ".join(INSTANCE_COLUMNS) + " |",
        "| " + " | ".join("---" for _ in INSTANCE_COLUMNS) + " |",
    ]
    lines.extend(render_instance_row(row) for row in sorted(source["instances"], key=lambda r: r["id"]))
    lines += [
        "",
        "## Tallies",
        "",
        "Computed from the instances above by the renderer.",
        "",
        "| Countermeasure | Instances it should have caught | Caught | Missed |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(f"| {a} | {b} | {c} | {d} |" for a, b, c, d in tallies(source))
    lines += ["", direction_line(source), "", "## Reading the tallies", ""]
    for note in source["readingNotes"]:
        lines += [note, ""]
    return "\n".join(lines).rstrip("\n") + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report a stale ledger.md without writing; exit nonzero if stale",
    )
    args = parser.parse_args(argv)
    try:
        source = load_source()
        validate(source)
        content = render(source)
    except (ValueError, KeyError) as error:
        print(f"render_assertion_ledger failed: {error}", file=sys.stderr)
        return 1

    current = RENDER_PATH.read_text(encoding="utf-8") if RENDER_PATH.is_file() else None
    if args.check:
        if current != content:
            print(f"stale: {RENDER_PATH.relative_to(ROOT)}", file=sys.stderr)
            return 1
        print(f"{RENDER_PATH.relative_to(ROOT)} up to date ({len(source['instances'])} instances)")
        return 0

    if current == content:
        print(f"{RENDER_PATH.relative_to(ROOT)} unchanged")
    else:
        RENDER_PATH.write_text(content, encoding="utf-8")
        print(f"rendered {RENDER_PATH.relative_to(ROOT)} ({len(source['instances'])} instances)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
