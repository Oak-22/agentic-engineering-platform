#!/usr/bin/env python3
"""Verify hook registrations against the canonical hooks registry.

Skills propagate by symlink and instructions by rendered adapter, so neither
can silently disagree with its canonical source. Hook registrations are
different: each runtime requires its own native JSON (or shell) schema and
there is no adapter file to render, so every registration is hand-written.
This module makes that hand-written surface checkable in both directions --
a registry leg whose registration does not exist, and a live registration the
registry never declared.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Iterable, NamedTuple


ROOT = Path(__file__).resolve().parents[3]
REGISTRY = "platform/agent-control-plane/agent-assets/hooks/hooks_registry.json"

# Every control-plane hook implementation is invoked by its repository-relative
# path, however the surrounding command spells the repository root.
IMPLEMENTATION_PATTERN = re.compile(
    r"platform/agent-control-plane/scripts/[A-Za-z0-9_./-]+\.py"
)


class Registration(NamedTuple):
    """One event-to-implementation binding read out of a runtime's own config.

    `event` is normalized for comparison; `spelling` keeps the file's own
    casing so a report quotes what a reader will actually find in the file.
    """

    event: str
    implementation: str
    spelling: str = ""

    def key(self) -> tuple[str, str]:
        return (self.event, self.implementation)


class Leg(NamedTuple):
    """One runtime's declared registration of one hook."""

    hook_id: str
    runtime: str
    registration: str
    events: tuple[str, ...]
    implementation: str
    verified: bool


class Finding(NamedTuple):
    severity: str  # "error" or "unconfirmed"
    message: str


def normalize_event(event: str) -> str:
    """Runtimes disagree on event casing; the binding is the same either way."""
    return event.lower()


def read_json_command_registrations(path: Path) -> list[Registration]:
    """Read Codex, Claude, and Copilot hook configs.

    All three nest an event map under a top-level `hooks` key. They differ in
    how deep the command sits and in whether the command field is `command` or
    `bash`, so the walk collects every string under an event rather than
    encoding three shapes.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    events = document.get("hooks")
    if not isinstance(events, dict):
        raise ValueError(f"{path_label(path)} has no top-level 'hooks' object")

    registrations: list[Registration] = []
    for event, entries in events.items():
        for command in collect_commands(entries):
            for match in IMPLEMENTATION_PATTERN.findall(command):
                registrations.append(
                    Registration(normalize_event(event), match, event)
                )
    return registrations


def collect_commands(node: object) -> Iterable[str]:
    """Yield every `command`/`bash` string reachable beneath one event entry."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("command", "bash") and isinstance(value, str):
                yield value
            else:
                yield from collect_commands(value)
    elif isinstance(node, list):
        for item in node:
            yield from collect_commands(item)


def read_shell_registrations(path: Path, events: tuple[str, ...]) -> list[Registration]:
    """Read a git hook, whose file name is its event and whose body is shell."""
    text = path.read_text(encoding="utf-8")
    return [
        Registration(normalize_event(event), match, event)
        for event in events
        for match in IMPLEMENTATION_PATTERN.findall(text)
    ]


def path_label(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def legs(registry: dict) -> list[Leg]:
    """Flatten both registry shapes into one list of runtime legs.

    A `centralized` hook carries a `runtimes` array; a `runtime-owned` hook is
    flat, with its single runtime and registration at the top level.
    """
    flattened: list[Leg] = []
    for hook in registry["hooks"]:
        implementation = hook["implementation"]
        entries = hook.get("runtimes")
        if entries is None:
            entries = [hook]
        for entry in entries:
            flattened.append(
                Leg(
                    hook_id=hook["id"],
                    runtime=entry["runtime"],
                    registration=entry["registration"],
                    events=tuple(entry["events"]),
                    implementation=implementation,
                    verified=entry.get("verified", True),
                )
            )
    return flattened


def read_registrations(leg: Leg) -> list[Registration]:
    """Parse one registration file in whichever format its runtime requires."""
    path = ROOT / leg.registration
    if path.suffix == ".json":
        return read_json_command_registrations(path)
    return read_shell_registrations(path, leg.events)


def verify(registry: dict) -> list[Finding]:
    findings: list[Finding] = []
    parsed: dict[str, list[Registration]] = {}
    unreadable: set[str] = set()
    declared: set[tuple[str, str, str]] = set()

    for leg in legs(registry):
        path = ROOT / leg.registration
        location = f"hook '{leg.hook_id}' runtime '{leg.runtime}'"

        if not path.is_file():
            findings.append(
                Finding(
                    "error",
                    f"{location}: declared registration file does not exist: "
                    f"{leg.registration}",
                )
            )
            continue

        if leg.registration not in parsed and leg.registration not in unreadable:
            try:
                parsed[leg.registration] = read_registrations(leg)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                unreadable.add(leg.registration)
                findings.append(
                    Finding(
                        "error",
                        f"{location}: registration file cannot be read: "
                        f"{leg.registration}: {error}",
                    )
                )
        if leg.registration in unreadable:
            continue

        present = {entry.key() for entry in parsed[leg.registration]}
        for event in leg.events:
            key = normalize_event(event)
            declared.add((leg.registration, key, leg.implementation))
            found = (key, leg.implementation) in present
            if found and leg.verified:
                continue
            if not leg.verified:
                # `verified: false` is a deliberate honesty marker: the
                # registration is declared but nobody has confirmed the runtime
                # actually fires it. That stays true when the file matches, so
                # the leg is reported either way and never fails the check.
                state = "present but unconfirmed" if found else "absent"
                findings.append(
                    Finding(
                        "unconfirmed",
                        f"{location}: '{event}' -> {leg.implementation} in "
                        f"{leg.registration} is {state} (declared "
                        f"verified: false)",
                    )
                )
                continue
            findings.append(
                Finding(
                    "error",
                    f"{location}: {leg.registration} has no '{event}' entry "
                    f"invoking {leg.implementation}",
                )
            )

    # The reverse direction: a live registration the registry never declared.
    for registration, entries in parsed.items():
        for entry in sorted(set(entries)):
            if (registration, entry.event, entry.implementation) in declared:
                continue
            findings.append(
                Finding(
                    "error",
                    f"{registration}: '{entry.spelling or entry.event}' invokes "
                    f"{entry.implementation}, which the registry does not "
                    f"declare for this file and event",
                )
            )

    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--registry",
        default=REGISTRY,
        help="repository-relative path to the hooks registry",
    )
    arguments = parser.parse_args(argv)

    try:
        registry = json.loads((ROOT / arguments.registry).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"cannot load {arguments.registry}: {error}", file=sys.stderr)
        return 1

    findings = verify(registry)
    errors = [finding for finding in findings if finding.severity == "error"]
    unconfirmed = [finding for finding in findings if finding.severity == "unconfirmed"]

    for finding in unconfirmed:
        print(f"unconfirmed: {finding.message}")
    for finding in errors:
        print(f"hook registration mismatch: {finding.message}", file=sys.stderr)

    checked = len(legs(registry))
    if errors:
        print(
            f"hook registration verification failed: {len(errors)} mismatch(es) "
            f"across {checked} declared runtime leg(s)",
            file=sys.stderr,
        )
        return 1
    print(
        f"hook registrations verified: {checked} runtime leg(s) match their "
        f"registration files, {len(unconfirmed)} unconfirmed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
