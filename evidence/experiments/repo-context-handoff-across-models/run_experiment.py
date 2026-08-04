#!/usr/bin/env python3
"""Codex-to-Claude governed context handoff experiment harness.

Three roles stay separated by construction:

* source corpus   -- historical Codex sessions, frozen at a cutoff
* handoff builder -- ephemeral Codex, run outside the tested repository
* target subjects -- two fresh Claude sessions over one clean snapshot

Each phase is a subcommand so an interrupted run resumes without redoing work
and without any phase silently depending on live state. See README.md for the
run path and experiment-design.md for rationale.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
from typing import Any, Callable, Iterable, Sequence


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

EXPERIMENT_DIR = Path(__file__).resolve().parent
PROMPT_DIR = EXPERIMENT_DIR / "prompts"
DEFAULT_PROMPT = PROMPT_DIR / "project-understanding.txt"
MAP_INSTRUCTION = PROMPT_DIR / "handoff-map.txt"
REDUCE_INSTRUCTION = PROMPT_DIR / "handoff-reduce.txt"

DEFAULT_DATA_ROOT = (
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    / "aep"
    / "experiments"
    / "repo-context-handoff-across-models"
)

SNAPSHOT_COMMIT = "5edc12ccf9660cb38a612a7bdf8825475dac20a0"
SOURCE_PROVIDER = "codex"

# `evidence/experiments/` itself is tracked at the snapshot commit and holds
# unrelated experiments, so only this experiment's own directory is scaffold.
EXPERIMENT_SCAFFOLD = "evidence/experiments/repo-context-handoff-across-models"
FORBIDDEN_IN_SUBJECT = (EXPERIMENT_SCAFFOLD, "product-demo", ".aep")
# `.aep/` is created by the instruction-manifest hook during a subject run and
# is the one addition permitted afterwards.
FORBIDDEN_AFTER_RUN = (EXPERIMENT_SCAFFOLD, "product-demo")

BUILDER_MODEL = "gpt-5.6-sol"
BUILDER_EFFORT = "high"
TARGET_MODEL = "opus"
TARGET_EFFORT = "high"
TARGET_TOOLS = "Read,Glob,Grep"
TARGET_PERMISSION_MODE = "plan"

# MEMORY.md startup read limits enforced by Claude Code.
MEMORY_MAX_LINES = 200
MEMORY_MAX_BYTES = 25_000
# Margin below the hard limits; exceeding these warns but does not fail.
MEMORY_WARN_LINES = 180
MEMORY_WARN_BYTES = 22_500

COMMAND_TIMEOUT_SECONDS = 1800

RUN_STATUS_VALID = "VALID"
RUN_STATUS_DEGRADED = "DEGRADED"
RUN_STATUS_INDETERMINATE = "INDETERMINATE"
RUN_STATUS_INVALID = "INVALID"

RUNTIME_WRAPPERS = (
    re.compile(r"<recommended_plugins>.*?</recommended_plugins>", re.DOTALL),
    re.compile(r"<environment_context>.*?</environment_context>", re.DOTALL),
    re.compile(
        r"# AGENTS\.md instructions for .*?<INSTRUCTIONS>.*?</INSTRUCTIONS>",
        re.DOTALL,
    ),
)

SECRET_PATTERNS = (
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
    re.compile(
        r"\b(?:gh[opusr]_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{16,})\b"
    ),
    re.compile(
        r"(?i)\b(?:authorization\s*:\s*bearer|api[_-]?key|password|secret|token)"
        r"\s*[:=]\s*[^\s,;]+"
    ),
)

INSTRUCTION_MANIFEST = re.compile(
    r"\n*Instruction References\n\| Instruction \|.*\Z", re.DOTALL
)

REQUIRED_SECTIONS = (
    "## Scope and authority",
    "## Repository purpose",
    "## Components and ownership boundaries",
    "## Agent customization and runtime model",
    "## Engineering workflows and operating constraints",
    "## Historical decisions and current concerns",
    "## Open questions and stale or conflicting claims",
    "## Source coverage",
)

# Concrete repository markers proving the handoff carries real content rather
# than generic prose. Verified present in the snapshot commit.
SUBSTANCE_MARKERS = (
    "platform/agent-control-plane",
    "AGENTS.md",
    "CLAUDE.md",
    ".agents/skills",
    ".github/instructions",
    "contracts/",
    "evidence/",
    "shared/",
)
SUBSTANCE_MARKER_MINIMUM = 6
SECTION_BODY_MINIMUM_CHARS = 200

# Aimed at the model narrating instead of producing. Bare "TODO" and
# "placeholder" are deliberately absent: both are ordinary vocabulary for
# describing repository content.
META_NARRATION_PATTERNS = (
    re.compile(r"^\s*(?:I'?ll|I will|Let me|Here'?s (?:the|my)|First,? I)\b", re.M),
    re.compile(r"(?i)\b(?:plan\.md|the plan file|as requested|as instructed|"
               r"per your instructions)\b"),
    re.compile(r"(?i)[\[<]\s*(?:placeholder|tbd)\s*[\]>]"),
)

# Narrow on purpose: `evidence/experiments/` is real tracked repository content
# at the snapshot commit, so the bare word "experiment" must stay allowed.
SELF_REFERENCE_PATTERNS = (
    re.compile(r"(?i)repo-context-handoff"),
    re.compile(r"(?i)run_experiment"),
    re.compile(r"(?i)\bhandoff experiment\b"),
    re.compile(r"(?i)\bthis experiment\b"),
    re.compile(r"(?i)\bA/B\b"),
    re.compile(r"(?i)\b(?:baseline|treatment)\s+(?:answer|response|session|arm)\b"),
    re.compile(r"(?i)\bauto[- ]memory experiment\b"),
)

TRANSCRIPT_REFERENCE_PATTERNS = (
    re.compile(r"\.codex/(?:archived_)?sessions"),
    re.compile(r"\.claude/projects"),
    re.compile(r"rollout-\d{4}-\d{2}-\d{2}T"),
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
               r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
)

PRIVACY_PATTERNS = (
    re.compile(r"/Users/[A-Za-z0-9._-]+"),
    re.compile(r"/home/[A-Za-z0-9._-]+"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)

FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
BLOCK_COMMENT = re.compile(r"^[ \t]*<!--.*?-->[ \t]*\n?", re.DOTALL | re.M)

PRIVACY_REVIEW_FIELDS = (
    "reviewed_by",
    "reviewed_at",
    "no_credentials",
    "no_personal_data",
    "no_third_party_names",
    "no_client_or_employer_detail",
    "no_absolute_personal_paths",
    "no_raw_session_identifiers",
)

PUBLISHABLE_ARTIFACTS = (
    "baseline.md",
    "treatment.md",
    "handoff.md",
    "comparison.md",
    "answer.diff",
    "run.json",
    "session-inventory.json",
    "handoff-validation.json",
    "verification.json",
)

SCORING_CRITERIA = (
    "Repository purpose",
    "Component and ownership-boundary accuracy",
    "Runtime-customization model accuracy",
    "Workflow and governance accuracy",
    "Evidence/history usefulness",
    "Uncertainty calibration",
    "Canonical-versus-derived source discipline",
    "Unsupported-claim penalty (5 = none)",
)


class ExperimentError(RuntimeError):
    """A run-stopping condition with an operator-actionable message."""


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Message:
    role: str
    text: str


@dataclass
class SourceSession:
    source_key: str
    provider: str
    path: Path
    source: str
    thread_id: str
    root_session_id: str | None
    is_subagent: bool
    cwd: str | None
    started_at: str | None
    ended_at: str | None
    raw_sha256: str
    raw_bytes: int
    messages: list[Message] = field(default_factory=list)

    @property
    def character_count(self) -> int:
        return sum(len(message.text) for message in self.messages)

    def inventory_record(self, corpus_sha256: str) -> dict[str, Any]:
        return {
            "source_key": self.source_key,
            "provider": self.provider,
            "source": self.source,
            "thread_id": self.thread_id,
            "root_session_id": self.root_session_id,
            "is_subagent": self.is_subagent,
            "cwd": self.cwd,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "raw_sha256": self.raw_sha256,
            "raw_bytes": self.raw_bytes,
            "messages": len(self.messages),
            "characters": self.character_count,
            "corpus_sha256": corpus_sha256,
        }


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------


def sanitize_text(value: str) -> str:
    text = value.replace("\x00", "")
    for pattern in RUNTIME_WRAPPERS:
        text = pattern.sub("[runtime wrapper omitted]", text)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return re.sub(r"\n{4,}", "\n\n\n", text).strip()


def content_text(content: Any, allowed_types: set[str]) -> str:
    if isinstance(content, str):
        return sanitize_text(content)
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") not in allowed_types:
            continue
        value = block.get("text")
        if isinstance(value, str):
            parts.append(value)
    return sanitize_text("\n".join(parts))


def parse_timestamp(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def source_key_for(provider: str, path: Path) -> str:
    payload = f"{provider}\0{os.path.realpath(path)}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def path_within(path_value: str | None, repo: Path) -> bool:
    if not path_value:
        return False
    try:
        path = Path(path_value).expanduser().resolve()
    except OSError:
        return False
    return path == repo or repo in path.parents


def home_relative(path: Path) -> str:
    try:
        return f"~/{path.relative_to(Path.home())}"
    except ValueError:
        return path.name


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def loadable_content(text: str) -> str:
    """Content Claude Code actually loads from MEMORY.md.

    Frontmatter and block-level HTML comments are stripped before the index is
    measured against its read limits, so they must be stripped here too.
    """
    stripped = FRONTMATTER.sub("", text)
    return BLOCK_COMMENT.sub("", stripped)


def normalized_answer(text: str) -> str:
    return INSTRUCTION_MANIFEST.sub("", text).strip()


def dedupe_messages(
    sessions: Sequence[SourceSession],
) -> tuple[list[SourceSession], int]:
    """Drop exact duplicate message texts, keeping the earliest occurrence.

    Codex subagent rollouts replay their parent's turns, so the same text can
    appear in several source files.
    """
    seen: set[str] = set()
    dropped = 0
    for session in sessions:
        kept: list[Message] = []
        for message in session.messages:
            digest = sha256_text(message.text)
            if digest in seen:
                dropped += 1
                continue
            seen.add(digest)
            kept.append(message)
        session.messages = kept
    return [session for session in sessions if session.messages], dropped


def session_segments(
    session: SourceSession, segment_chars: int = 12_000
) -> Iterable[str]:
    header = (
        f"SESSION provider={session.provider} key={session.source_key} "
        f"started={session.started_at or 'unknown'} "
        f"ended={session.ended_at or 'unknown'}"
    )
    for index, message in enumerate(session.messages, start=1):
        prefix = (
            f"{header}\nMESSAGE {index}/{len(session.messages)} role={message.role}"
        )
        text = message.text
        for offset in range(0, len(text), segment_chars):
            part = text[offset : offset + segment_chars]
            continuation = " continuation" if offset else ""
            yield f"{prefix}{continuation}\n{part}\n"


def chunks_for(sessions: Sequence[SourceSession], chunk_chars: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for session in sessions:
        for segment in session_segments(session):
            if current and size + len(segment) > chunk_chars:
                chunks.append("\n".join(current))
                current = []
                size = 0
            current.append(segment)
            size += len(segment)
    if current:
        chunks.append("\n".join(current))
    return chunks


def section_bodies(text: str) -> dict[str, str]:
    bodies: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                bodies[current] = "\n".join(buffer).strip()
            current = line.strip()
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        bodies[current] = "\n".join(buffer).strip()
    return bodies


def validate_handoff(text: str) -> dict[str, Any]:
    """Structural, substantive, and privacy validation of the handoff document.

    Returns a per-rule record. Rules V1-V9 must all pass before the handoff may
    reach a memory directory.
    """
    rules: list[dict[str, Any]] = []

    def record(rule: str, description: str, ok: bool, detail: str = "") -> None:
        rules.append(
            {"rule": rule, "description": description, "passed": ok, "detail": detail}
        )

    stripped = text.strip()
    record(
        "V1",
        "starts with the handoff heading",
        stripped.startswith("# Repository context handoff"),
        "" if stripped.startswith("# Repository context handoff")
        else f"first line: {stripped.splitlines()[0][:80] if stripped else '<empty>'}",
    )

    positions = [(name, stripped.find(name)) for name in REQUIRED_SECTIONS]
    missing = [name for name, index in positions if index < 0]
    ordered = [index for _, index in positions if index >= 0]
    record(
        "V2",
        "all required sections present, in order, non-empty",
        not missing and ordered == sorted(ordered),
        f"missing: {missing}" if missing else "",
    )

    bodies = section_bodies(stripped)
    thin = sorted(
        name
        for name in REQUIRED_SECTIONS
        if len(bodies.get(name, "")) < SECTION_BODY_MINIMUM_CHARS
    )

    authority = bodies.get("## Scope and authority", "")
    has_derived = re.search(r"(?i)derived|non-authoritative", authority) is not None
    has_precedence = (
        re.search(r"(?i)repository files|canonical|prevail|authoritative", authority)
        is not None
    )
    record(
        "V3",
        "scope section declares derived, non-authoritative status",
        has_derived and has_precedence,
        "" if has_derived and has_precedence else "missing derived/precedence claim",
    )

    markers = sorted({m for m in SUBSTANCE_MARKERS if m in stripped})
    substantive = len(markers) >= SUBSTANCE_MARKER_MINIMUM and not thin
    record(
        "V4",
        f"substantive: >={SUBSTANCE_MARKER_MINIMUM} repository markers, "
        f"every section >={SECTION_BODY_MINIMUM_CHARS} chars",
        substantive,
        f"markers={markers} thin_sections={thin}" if not substantive else "",
    )

    narration = sorted(
        {m.group(0).strip() for p in META_NARRATION_PATTERNS for m in p.finditer(stripped)}
    )
    record("V5", "no meta-narration", not narration, f"matches: {narration[:5]}")

    self_refs = sorted(
        {m.group(0) for p in SELF_REFERENCE_PATTERNS for m in p.finditer(stripped)}
    )
    record(
        "V6",
        "no references to the comparison harness",
        not self_refs,
        f"matches: {self_refs[:5]}",
    )

    transcript_refs = sorted(
        {m.group(0) for p in TRANSCRIPT_REFERENCE_PATTERNS for m in p.finditer(stripped)}
    )
    record(
        "V7",
        "no transcript paths or raw session identifiers",
        not transcript_refs,
        f"matches: {transcript_refs[:5]}",
    )

    privacy = sorted(
        {m.group(0) for p in (*SECRET_PATTERNS, *PRIVACY_PATTERNS) for m in p.finditer(stripped)}
    )
    record(
        "V8",
        "no secrets, machine-specific paths, or email addresses",
        not privacy,
        f"matches: {privacy[:5]}",
    )

    loadable = loadable_content(stripped)
    lines = len(loadable.splitlines())
    size = len(loadable.encode())
    record(
        "V9",
        f"loadable within {MEMORY_MAX_LINES} lines and {MEMORY_MAX_BYTES} bytes",
        lines <= MEMORY_MAX_LINES and size <= MEMORY_MAX_BYTES,
        f"lines={lines} bytes={size}",
    )

    warnings = []
    if lines > MEMORY_WARN_LINES or size > MEMORY_WARN_BYTES:
        warnings.append(
            f"within hard limits but above margin: lines={lines} bytes={size}"
        )

    return {
        "passed": all(rule["passed"] for rule in rules),
        "rules": rules,
        "warnings": warnings,
        "loadable_lines": lines,
        "loadable_bytes": size,
        "substance_markers": markers,
    }


def comparison_report(baseline: str, treatment: str) -> tuple[str, str]:
    left = normalized_answer(baseline)
    right = normalized_answer(treatment)
    ratio = difflib.SequenceMatcher(None, left, right).ratio()
    left_headings = [line for line in left.splitlines() if line.startswith("#")]
    right_headings = [line for line in right.splitlines() if line.startswith("#")]
    diff = "\n".join(
        difflib.unified_diff(
            left.splitlines(),
            right.splitlines(),
            fromfile="baseline.md",
            tofile="treatment.md",
            lineterm="",
        )
    )
    rubric = "\n".join(
        f"| {criterion} |  |  |  |" for criterion in SCORING_CRITERIA
    )
    report = f"""# Repository Context Handoff Comparison

One pilot A/B pair. This is a demonstration, not a causal estimate, and it says
nothing about whether the same handoff would help a provider other than Claude.

## Mechanical measures

| Measure | Baseline | Treatment |
| --- | ---: | ---: |
| Words | {len(left.split())} | {len(right.split())} |
| Characters | {len(left)} | {len(right)} |
| Headings | {len(left_headings)} | {len(right_headings)} |

Normalized character-sequence similarity: `{ratio:.3f}`.

Instruction References blocks are retained in the raw answers but removed from
the mechanical comparison because per-session evidence identifiers differ by
design. Neither greater length nor lower similarity is improvement by itself.

## Blinded human scoring

Score `blind/A.md` and `blind/B.md` from 1 (weak) to 5 (strong) before opening
`blind/key.json`.

| Criterion | A | B | Evidence/notes |
| --- | ---: | ---: | --- |
{rubric}

## Decision rule

Call the handoff promising only if the treated answer adds relevant historical
knowledge, preserves or improves verified structural accuracy, keeps derived
claims subordinate to canonical files, and exposes no private transcript
detail. Repeat with counterbalanced ordering and several fresh pairs before
promoting the pattern to a practice.
"""
    return report, diff + "\n"


# --------------------------------------------------------------------------
# Process and filesystem I/O
# --------------------------------------------------------------------------


def run_command(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=COMMAND_TIMEOUT_SECONDS,
        env=env,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ExperimentError(f"command failed ({result.returncode}): {args[0]}: {detail}")
    return result.stdout


def git_value(repo: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def git_require(repo: Path, *args: str) -> str:
    value = git_value(repo, *args)
    if value is None:
        raise ExperimentError(f"git {' '.join(args)} failed in {repo}")
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    os.replace(temp, path)


def read_json(path: Path) -> Any:
    if not path.is_file():
        raise ExperimentError(f"missing required artifact: {path}")
    return json.loads(path.read_text())


def hash_tree(root: Path) -> list[str]:
    """Sorted `<sha256>  <relative path>` lines for every file under root."""
    if not root.exists():
        return []
    entries = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            entries.append(f"{sha256_file(path)}  {path.relative_to(root)}")
    return sorted(entries)


def tracked_file_hashes(repo: Path) -> list[str]:
    listing = git_require(repo, "ls-files", "-z").split("\0")
    entries = []
    for name in listing:
        if not name:
            continue
        path = repo / name
        if path.is_file() and not path.is_symlink():
            entries.append(f"{sha256_file(path)}  {name}")
    return sorted(entries)


def claude_sessions_in(repo: Path) -> list[dict[str, Any]]:
    """Live `claude` processes whose working directory is inside the repo."""
    listing = subprocess.run(
        ["pgrep", "-f", "claude"], text=True, capture_output=True, check=False
    )
    if listing.returncode != 0:
        return []
    found = []
    for pid in listing.stdout.split():
        probe = subprocess.run(
            ["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"],
            text=True,
            capture_output=True,
            check=False,
        )
        cwd = next(
            (
                line[1:]
                for line in probe.stdout.splitlines()
                if line.startswith("n")
            ),
            None,
        )
        if cwd and path_within(cwd, repo):
            found.append({"pid": pid, "cwd": cwd})
    return found


def codex_exec(
    instruction: str,
    stdin_text: str,
    *,
    cwd: Path,
    model: str,
    effort: str,
    output_path: Path,
    log_path: Path,
) -> dict[str, Any]:
    """Run one ephemeral, tool-free, config-isolated Codex builder call.

    `--ignore-user-config` drops the user's MCP servers and model defaults so
    the requested model and effort are the only ones that can apply. Codex does
    not report a resolved model id through `--json`, so provenance is the pinned
    request plus the CLI version.
    """
    args = [
        "codex",
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--ignore-rules",
        "--ignore-user-config",
        "-C",
        str(cwd),
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{effort}"',
        "--json",
        "-o",
        str(output_path),
        instruction,
    ]
    started = datetime.now(timezone.utc)
    result = subprocess.run(
        args,
        input=stdin_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )
    ended = datetime.now(timezone.utc)
    log_path.write_text(result.stdout)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ExperimentError(f"codex exec failed ({result.returncode}): {detail}")
    if not output_path.is_file() or not output_path.read_text().strip():
        raise ExperimentError(f"codex exec produced no output: {output_path}")

    thread_id = None
    usage: dict[str, Any] = {}
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started":
            thread_id = event.get("thread_id")
        elif event.get("type") == "turn.completed" and isinstance(
            event.get("usage"), dict
        ):
            usage = event["usage"]
    return {
        "argv": args[:-1] + ["<instruction>"],
        "thread_id": thread_id,
        "usage": usage,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "elapsed_seconds": round((ended - started).total_seconds(), 3),
        "stderr": result.stderr.strip()[:2000],
    }


def claude_target(
    prompt: str,
    *,
    cwd: Path,
    model: str,
    effort: str,
    tools: str,
    permission_mode: str,
    memory: str,
    memory_dir: Path,
) -> dict[str, Any]:
    """Run one non-persistent Claude subject session.

    `memory` is "on" or "off". Auto memory is always redirected to an isolated
    directory so no code path can reach the real project memory, and "off" is
    enforced by both the setting and the environment variable.
    """
    if memory not in {"on", "off"}:
        raise ExperimentError(f"invalid memory mode: {memory}")
    settings = {
        "autoMemoryEnabled": memory == "on",
        "autoMemoryDirectory": str(memory_dir),
    }
    args = [
        "claude",
        "-p",
        "--no-session-persistence",
        "--model",
        model,
        "--effort",
        effort,
        "--permission-mode",
        permission_mode,
        "--tools",
        tools,
        "--settings",
        json.dumps(settings),
        "--output-format",
        "json",
    ]
    environment = os.environ.copy()
    environment["CLAUDE_CODE_SKIP_PROMPT_HISTORY"] = "1"
    if memory == "off":
        environment["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    else:
        # An inherited CLAUDE_CODE_DISABLE_AUTO_MEMORY=0 or =1 would silently
        # override the setting in either direction.
        environment.pop("CLAUDE_CODE_DISABLE_AUTO_MEMORY", None)

    started = datetime.now(timezone.utc)
    result = subprocess.run(
        args,
        cwd=str(cwd),
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
        timeout=COMMAND_TIMEOUT_SECONDS,
        env=environment,
    )
    ended = datetime.now(timezone.utc)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ExperimentError(f"Claude Code failed ({result.returncode}): {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ExperimentError("Claude Code did not return valid JSON") from error
    payload["_invocation"] = {
        "argv": args,
        "cwd": str(cwd),
        "memory_mode": memory,
        "memory_dir": str(memory_dir),
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "elapsed_seconds": round((ended - started).total_seconds(), 3),
    }
    return payload


def resolved_models(payload: dict[str, Any]) -> list[str]:
    usage = payload.get("modelUsage")
    return sorted(usage) if isinstance(usage, dict) else []


# --------------------------------------------------------------------------
# Source collection
# --------------------------------------------------------------------------


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


def extract_codex_session(path: Path) -> SourceSession | str:
    """Parse one Codex rollout file.

    Identity comes from the first `session_meta` record only. Subagent-spawn
    rollouts replay their parent's `session_meta`, so taking the last record
    makes distinct files claim the same identity. Returns a reason string when
    the file is unusable.
    """
    first_meta: dict[str, Any] | None = None
    timestamps: list[str] = []
    messages: list[Message] = []
    saw_any_record = False

    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError as error:
        return f"unreadable: {error}"

    with handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            saw_any_record = True
            if isinstance(record.get("timestamp"), str):
                timestamps.append(record["timestamp"])
            payload = record.get("payload")
            if not isinstance(payload, dict):
                continue
            if record.get("type") == "session_meta":
                if first_meta is None:
                    first_meta = payload
                continue
            if (
                record.get("type") != "response_item"
                or payload.get("type") != "message"
                or payload.get("role") not in {"user", "assistant"}
            ):
                continue
            text = content_text(payload.get("content"), {"input_text", "output_text"})
            if text:
                messages.append(Message(str(payload["role"]), text))

    if not saw_any_record:
        return "empty file"
    if first_meta is None:
        return "no session_meta record"
    if not messages:
        return "no user or assistant messages"

    thread_id = str(first_meta.get("id") or first_meta.get("session_id") or path.stem)
    root = first_meta.get("session_id")
    return SourceSession(
        source_key=source_key_for(SOURCE_PROVIDER, path),
        provider=SOURCE_PROVIDER,
        path=path,
        source=home_relative(path),
        thread_id=thread_id,
        root_session_id=str(root) if isinstance(root, str) else None,
        is_subagent=isinstance(first_meta.get("source"), dict),
        cwd=first_meta.get("cwd") if isinstance(first_meta.get("cwd"), str) else None,
        started_at=timestamps[0] if timestamps else None,
        ended_at=timestamps[-1] if timestamps else None,
        raw_sha256=sha256_file(path),
        raw_bytes=path.stat().st_size,
        messages=messages,
    )


def collect_codex_sessions(
    repo: Path, cutoff: datetime, excluded: set[str]
) -> tuple[list[SourceSession], dict[str, list[dict[str, Any]]]]:
    """Eligible sessions plus a diagnostic record of what was left out.

    A file's working directory is only knowable after parsing, so unparseable
    files cannot be attributed to a repository. They are reported separately
    from sessions that were attributed and then excluded on the merits.
    """
    home = codex_home()
    candidates: list[Path] = []
    for folder in (home / "sessions", home / "archived_sessions"):
        if folder.exists():
            candidates.extend(folder.rglob("*.jsonl"))

    eligible: list[SourceSession] = []
    excluded_sources: list[dict[str, Any]] = []
    unparseable: list[dict[str, Any]] = []
    for path in sorted(candidates):
        parsed = extract_codex_session(path)
        if isinstance(parsed, str):
            unparseable.append({"source": home_relative(path), "reason": parsed})
            continue
        if not path_within(parsed.cwd, repo):
            continue
        if parsed.source_key in excluded or parsed.thread_id in excluded:
            excluded_sources.append(
                {"source": parsed.source, "reason": "explicitly excluded"}
            )
            continue
        ended = parse_timestamp(parsed.ended_at)
        if ended is None:
            excluded_sources.append(
                {"source": parsed.source, "reason": "no usable timestamp"}
            )
            continue
        if ended > cutoff:
            excluded_sources.append(
                {"source": parsed.source, "reason": f"after cutoff ({parsed.ended_at})"}
            )
            continue
        eligible.append(parsed)

    eligible.sort(key=lambda item: (item.started_at or "", item.source_key))
    return eligible, {"excluded_repo_sources": excluded_sources, "unparseable_files": unparseable}


# --------------------------------------------------------------------------
# Run state
# --------------------------------------------------------------------------


def run_json_path(run_dir: Path) -> Path:
    return run_dir / "run.json"


def load_state(run_dir: Path) -> dict[str, Any]:
    return read_json(run_json_path(run_dir))


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(run_json_path(run_dir), state)


def require_phase(state: dict[str, Any], phase: str) -> None:
    if phase not in state.get("phases_completed", []):
        raise ExperimentError(f"phase '{phase}' has not completed for this run")


def mark_phase(state: dict[str, Any], phase: str) -> None:
    phases = state.setdefault("phases_completed", [])
    if phase not in phases:
        phases.append(phase)


def resolve_cutoff(repo: Path, value: str, commit: str) -> str:
    if value == "commit":
        epoch = git_require(repo, "show", "-s", "--format=%ct", commit)
        stamp = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
        return stamp.isoformat().replace("+00:00", "Z")
    if parse_timestamp(value) is None:
        raise ExperimentError(f"--cutoff must be ISO 8601 or 'commit', got: {value}")
    return value


# --------------------------------------------------------------------------
# Phases
# --------------------------------------------------------------------------


def cmd_preflight(args: argparse.Namespace) -> int:
    repo = args.repo.expanduser().resolve()
    if not (repo / ".git").exists():
        raise ExperimentError(f"not a Git repository root: {repo}")

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = (args.data_root.expanduser().resolve() / run_id)
    if run_json_path(run_dir).exists():
        raise ExperimentError(f"run already initialized: {run_dir}")
    for name in ("corpus", "chunks", "partials", "builder-logs", "probe", "blind"):
        (run_dir / name).mkdir(parents=True, exist_ok=True)
    run_dir.chmod(0o700)

    # A stale backup means an earlier run of the superseded harness died while
    # it still mutated the real memory directory.
    stale = sorted(args.data_root.expanduser().resolve().glob("*/quarantine/original-memory*"))
    if stale and not args.allow_stale_backup:
        raise ExperimentError(
            "stale memory backups from the superseded harness are present; "
            f"restore or remove them first: {[str(p) for p in stale]}"
        )

    concurrent = claude_sessions_in(repo)
    if concurrent and not args.allow_concurrent_claude:
        raise ExperimentError(
            "live Claude sessions have this repository as their working "
            f"directory: {concurrent}. Close them, or pass "
            "--allow-concurrent-claude to continue with a DEGRADED run."
        )
    write_json(run_dir / "concurrent-sessions.json", concurrent)

    real_memory = args.real_memory.expanduser().resolve()
    (run_dir / "real-memory.before.sha256").write_text(
        "\n".join(hash_tree(real_memory)) + "\n"
    )

    docs_hook = repo / "platform/agent-control-plane/scripts/provider_docs_session_start.py"
    docs_warm: dict[str, Any] = {"ran": False}
    if docs_hook.is_file():
        try:
            docs_warm = {
                "ran": True,
                "output": run_command([sys.executable, str(docs_hook), "--runtime", "claude"])[:4000],
            }
        except ExperimentError as error:
            docs_warm = {"ran": True, "error": str(error)[:500]}
    write_json(run_dir / "provider-docs-warm.json", docs_warm)
    docs_root = Path(os.environ.get("TMPDIR", "/tmp")) / "aep-provider-docs"
    (run_dir / "provider-docs.sha256").write_text("\n".join(hash_tree(docs_root)) + "\n")

    prompt_path = args.prompt.expanduser().resolve()
    prompt = prompt_path.read_text()

    state = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "repo": str(repo),
        "snapshot_commit": args.snapshot_commit,
        "prompt_path": str(prompt_path.relative_to(repo)),
        "prompt_sha256": sha256_text(prompt),
        "map_instruction_sha256": sha256_text(MAP_INSTRUCTION.read_text()),
        "reduce_instruction_sha256": sha256_text(REDUCE_INSTRUCTION.read_text()),
        "source_provider": SOURCE_PROVIDER,
        "target_model": args.target_model,
        "target_effort": args.target_effort,
        "target_tools": TARGET_TOOLS,
        "target_permission_mode": TARGET_PERMISSION_MODE,
        "builder_provider": SOURCE_PROVIDER,
        "builder_model_requested": args.builder_model,
        "builder_effort": args.builder_effort,
        "builder_model_resolved": None,
        "builder_model_resolution": (
            "pinned via `codex exec -m` with --ignore-user-config; "
            "codex exec --json exposes no resolved model id"
        ),
        "claude_version": run_command(["claude", "--version"]).strip(),
        "codex_version": run_command(["codex", "--version"]).strip(),
        "git_version": run_command(["git", "--version"]).strip(),
        "real_memory_dir": str(real_memory),
        "concurrent_claude_sessions": concurrent,
        "allowed_concurrent_claude": bool(concurrent) and args.allow_concurrent_claude,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "phases_completed": [],
        "run_status": None,
    }
    mark_phase(state, "preflight")
    save_state(run_dir, state)
    print(json.dumps({"run_dir": str(run_dir), "run_id": run_id}, indent=2))
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.expanduser().resolve()
    state = load_state(run_dir)
    require_phase(state, "preflight")
    repo = Path(state["repo"])
    commit = state["snapshot_commit"]

    subject = (
        args.subject.expanduser().resolve()
        if args.subject
        else Path(os.environ.get("TMPDIR", "/tmp")).resolve()
        / f"aep-{state['run_id']}"
        / repo.name
    )
    if subject.exists():
        raise ExperimentError(f"subject path already exists: {subject}")
    if subject == repo or repo in subject.parents or subject in repo.parents:
        raise ExperimentError("subject clone must not overlap the source repository")
    if run_dir in subject.parents or subject in run_dir.parents:
        raise ExperimentError("subject clone must not overlap the run directory")

    subject.parent.mkdir(parents=True, exist_ok=True)
    run_command(["git", "clone", "--no-hardlinks", str(repo), str(subject)])
    try:
        # A branch named `main` at the snapshot commit reproduces ordinary
        # conditions; a detached HEAD is itself a signal something is unusual.
        run_command(["git", "-C", str(subject), "checkout", "-B", "main", commit])
        run_command(["git", "-C", str(subject), "remote", "remove", "origin"])

        head = git_require(subject, "rev-parse", "HEAD")
        if head != commit:
            raise ExperimentError(f"subject HEAD {head} != snapshot commit {commit}")
        status = git_require(subject, "status", "--porcelain")
        if status:
            raise ExperimentError(f"subject clone is not clean:\n{status}")
        for forbidden in FORBIDDEN_IN_SUBJECT:
            if (subject / forbidden).exists():
                raise ExperimentError(
                    f"experiment scaffold present in subject: {forbidden}"
                )
    except (ExperimentError, OSError):
        # Leave no partial clone behind; a rejected snapshot must be retryable.
        shutil.rmtree(subject, ignore_errors=True)
        raise

    ignored = git_require(subject, "status", "--porcelain", "--ignored=matching")
    (run_dir / "subject-status-ignored.before.txt").write_text(ignored + "\n")
    (run_dir / "subject-files.before.sha256").write_text(
        "\n".join(tracked_file_hashes(subject)) + "\n"
    )

    state["subject_path"] = str(subject)
    state["subject_head"] = head
    mark_phase(state, "snapshot")
    save_state(run_dir, state)
    print(json.dumps({"subject": str(subject), "head": head}, indent=2))
    return 0


def cmd_trust_probe(args: argparse.Namespace) -> int:
    """Accept workspace trust for the subject clone before any measured run."""
    run_dir = args.run_dir.expanduser().resolve()
    state = load_state(run_dir)
    require_phase(state, "snapshot")
    subject = Path(state["subject_path"])
    probe_memory = run_dir / "probe" / "trust-memory"
    probe_memory.mkdir(parents=True, exist_ok=True)
    payload = claude_target(
        "Reply with the single word: ready",
        cwd=subject,
        model=state["target_model"],
        effort="low",
        tools="",
        permission_mode=TARGET_PERMISSION_MODE,
        memory="off",
        memory_dir=probe_memory,
    )
    write_json(run_dir / "probe" / "trust-probe.json", payload)
    result = str(payload.get("result") or "").strip()
    if not result:
        raise ExperimentError("trust probe returned no result")
    state["trust_probe_result"] = result[:200]
    mark_phase(state, "trust-probe")
    save_state(run_dir, state)
    print(json.dumps({"trust_probe": result[:200]}, indent=2))
    return 0


def cmd_probe_memory(args: argparse.Namespace) -> int:
    """Resolve whether autoMemoryDirectory names the memory dir or its parent."""
    run_dir = args.run_dir.expanduser().resolve()
    state = load_state(run_dir)
    require_phase(state, "snapshot")
    subject = Path(state["subject_path"])

    probe = run_dir / "probe" / "mem"
    if probe.exists():
        shutil.rmtree(probe)
    (probe / "memory").mkdir(parents=True)
    alpha = "CANARY_ALPHA_7F3"
    beta = "CANARY_BETA_9K2"
    (probe / "MEMORY.md").write_text(f"# Memory\n\n{alpha}\n")
    (probe / "memory" / "MEMORY.md").write_text(f"# Memory\n\n{beta}\n")

    payload = claude_target(
        "List verbatim every token beginning with CANARY_ that appears anywhere "
        "in your context. If none, reply NONE.",
        cwd=subject,
        model=state["target_model"],
        effort="low",
        tools="",
        permission_mode=TARGET_PERMISSION_MODE,
        memory="on",
        memory_dir=probe,
    )
    write_json(run_dir / "probe" / "memory-layout.json", payload)
    answer = str(payload.get("result") or "")

    if alpha in answer and beta not in answer:
        layout = "direct"
    elif beta in answer and alpha not in answer:
        layout = "nested"
    else:
        raise ExperimentError(
            "autoMemoryDirectory did not resolve to exactly one canary "
            f"(alpha={alpha in answer}, beta={beta in answer}). The setting is "
            "not taking effect as expected. Do not fall back to the real "
            "project memory directory; escalate instead."
        )

    shutil.rmtree(probe)
    state["memory_layout"] = layout
    mark_phase(state, "probe-memory")
    save_state(run_dir, state)
    print(json.dumps({"memory_layout": layout}, indent=2))
    return 0


def cmd_inventory(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.expanduser().resolve()
    state = load_state(run_dir)
    require_phase(state, "preflight")
    repo = Path(state["repo"])

    cutoff_value = resolve_cutoff(repo, args.cutoff, state["snapshot_commit"])
    cutoff = parse_timestamp(cutoff_value)
    if cutoff is None:
        raise ExperimentError(f"unparseable cutoff: {cutoff_value}")

    excluded = set(args.exclude_source)
    thread = os.environ.get("CODEX_THREAD_ID")
    if thread:
        excluded.add(thread)

    sessions, skipped = collect_codex_sessions(repo, cutoff, excluded)
    if not sessions:
        raise ExperimentError("no eligible Codex sessions before the cutoff")

    keys = [session.source_key for session in sessions]
    if len(set(keys)) != len(keys):
        raise ExperimentError("source keys are not unique; refusing to continue")

    fingerprints: dict[tuple[str, str | None, str], str] = {}
    duplicate_files: list[dict[str, str]] = []
    unique: list[SourceSession] = []
    for session in sessions:
        fingerprint = (session.thread_id, session.started_at, session.raw_sha256)
        if fingerprint in fingerprints:
            duplicate_files.append(
                {"source": session.source, "duplicate_of": fingerprints[fingerprint]}
            )
            continue
        fingerprints[fingerprint] = session.source
        unique.append(session)

    unique, dropped = dedupe_messages(unique)

    corpus_dir = run_dir / "corpus"
    for stale in corpus_dir.glob("*.jsonl"):
        stale.unlink()
    inventory = []
    for session in unique:
        target = corpus_dir / f"{session.source_key}.jsonl"
        target.write_text(
            "".join(
                json.dumps({"role": m.role, "text": m.text}) + "\n"
                for m in session.messages
            )
        )
        inventory.append(session.inventory_record(sha256_file(target)))
    write_json(run_dir / "session-inventory.json", inventory)
    write_json(run_dir / "skipped-sources.json", skipped)

    state.update(
        {
            "cutoff": cutoff_value,
            "excluded_sources": sorted(excluded),
            "source_counts": {SOURCE_PROVIDER: len(inventory), "claude": 0},
            "source_characters": sum(item["characters"] for item in inventory),
            "source_date_range": [
                min((item["started_at"] or "") for item in inventory),
                max((item["ended_at"] or "") for item in inventory),
            ],
            "duplicate_messages_dropped": dropped,
            "duplicate_content_files": duplicate_files,
            "excluded_repo_sources": len(skipped["excluded_repo_sources"]),
            "unparseable_files": len(skipped["unparseable_files"]),
        }
    )
    mark_phase(state, "inventory")
    save_state(run_dir, state)
    print(
        json.dumps(
            {
                "sessions": len(inventory),
                "characters": state["source_characters"],
                "cutoff": cutoff_value,
                "duplicate_messages_dropped": dropped,
                "excluded_repo_sources": state["excluded_repo_sources"],
            },
            indent=2,
        )
    )
    return 0


def load_corpus(run_dir: Path) -> list[SourceSession]:
    """Rebuild the frozen corpus, verifying every file against its hash."""
    inventory = read_json(run_dir / "session-inventory.json")
    sessions: list[SourceSession] = []
    for record in inventory:
        path = run_dir / "corpus" / f"{record['source_key']}.jsonl"
        if sha256_file(path) != record["corpus_sha256"]:
            raise ExperimentError(f"frozen corpus file changed: {path}")
        messages = [
            Message(entry["role"], entry["text"])
            for entry in (json.loads(line) for line in path.read_text().splitlines() if line)
        ]
        sessions.append(
            SourceSession(
                source_key=record["source_key"],
                provider=record["provider"],
                path=path,
                source=record["source"],
                thread_id=record["thread_id"],
                root_session_id=record["root_session_id"],
                is_subagent=record["is_subagent"],
                cwd=record["cwd"],
                started_at=record["started_at"],
                ended_at=record["ended_at"],
                raw_sha256=record["raw_sha256"],
                raw_bytes=record["raw_bytes"],
                messages=messages,
            )
        )
    return sessions


def cmd_recheck_sources(args: argparse.Namespace) -> int:
    """Compare live transcripts against the inventory taken at freeze time."""
    run_dir = args.run_dir.expanduser().resolve()
    state = load_state(run_dir)
    require_phase(state, "inventory")
    inventory = read_json(run_dir / "session-inventory.json")

    append_only: list[str] = []
    modified: list[str] = []
    vanished: list[str] = []
    for record in inventory:
        path = Path(record["source"].replace("~", str(Path.home()), 1))
        if not path.is_file():
            vanished.append(record["source_key"])
            continue
        if sha256_file(path) == record["raw_sha256"]:
            continue
        with path.open("rb") as handle:
            prefix = handle.read(record["raw_bytes"])
        if (
            len(prefix) == record["raw_bytes"]
            and hashlib.sha256(prefix).hexdigest() == record["raw_sha256"]
        ):
            append_only.append(record["source_key"])
        else:
            modified.append(record["source_key"])

    state["source_append_only_growth"] = append_only
    state["source_modified_after_freeze"] = modified
    state["source_vanished_after_freeze"] = vanished
    save_state(run_dir, state)
    result = {
        "append_only_growth": append_only,
        "modified_after_freeze": modified,
        "vanished_after_freeze": vanished,
        "note": (
            "The frozen corpus is authoritative; growth or deletion after the "
            "freeze does not change the run. Modified files are recorded so the "
            "run can be reported as DEGRADED."
        ),
    }
    print(json.dumps(result, indent=2))
    return 0


def cmd_baseline(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.expanduser().resolve()
    state = load_state(run_dir)
    require_phase(state, "snapshot")
    require_phase(state, "inventory")
    if (run_dir / "handoff.md").exists():
        raise ExperimentError(
            "handoff.md already exists; the baseline must run before the handoff "
            "is built so no artifact can leak into it"
        )

    subject = Path(state["subject_path"])
    prompt = (Path(state["repo"]) / state["prompt_path"]).read_text()
    if sha256_text(prompt) != state["prompt_sha256"]:
        raise ExperimentError("prompt file changed since preflight")

    memory_dir = run_dir / "baseline-memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    payload = claude_target(
        prompt,
        cwd=subject,
        model=state["target_model"],
        effort=state["target_effort"],
        tools=state["target_tools"],
        permission_mode=state["target_permission_mode"],
        memory="off",
        memory_dir=memory_dir,
    )
    answer = str(payload.get("result") or "").strip()
    if not answer:
        raise ExperimentError("baseline response was empty")
    write_json(run_dir / "baseline.raw.json", payload)
    (run_dir / "baseline.md").write_text(answer + "\n")

    state["baseline_resolved_models"] = resolved_models(payload)
    state["baseline_elapsed_seconds"] = payload["_invocation"]["elapsed_seconds"]
    mark_phase(state, "baseline")
    save_state(run_dir, state)
    print(
        json.dumps(
            {
                "baseline_chars": len(answer),
                "resolved_models": state["baseline_resolved_models"],
            },
            indent=2,
        )
    )
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.expanduser().resolve()
    state = load_state(run_dir)
    require_phase(state, "inventory")
    require_phase(state, "baseline")

    sessions = load_corpus(run_dir)
    chunks = chunks_for(sessions, args.chunk_chars)
    chunk_dir = run_dir / "chunks"
    for index, chunk in enumerate(chunks, start=1):
        (chunk_dir / f"{index:03d}.txt").write_text(chunk)

    builder_cwd = (
        Path(os.environ.get("TMPDIR", "/tmp")).resolve()
        / f"aep-{state['run_id']}"
        / "builder"
    )
    builder_cwd.mkdir(parents=True, exist_ok=True)
    repo = Path(state["repo"])
    if path_within(str(builder_cwd), repo) or path_within(
        str(builder_cwd), Path(state["subject_path"])
    ):
        raise ExperimentError("builder cwd must be outside the repo and the subject")

    map_instruction = MAP_INSTRUCTION.read_text()
    calls: list[dict[str, Any]] = state.get("builder_calls", [])
    partials: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        partial_path = run_dir / "partials" / f"{index:03d}.md"
        if partial_path.is_file() and partial_path.read_text().strip():
            partials.append(partial_path.read_text().strip())
            continue
        metadata = codex_exec(
            f"{map_instruction}\n\nCHUNK {index} of {len(chunks)}.",
            chunk,
            cwd=builder_cwd,
            model=state["builder_model_requested"],
            effort=state["builder_effort"],
            output_path=partial_path,
            log_path=run_dir / "builder-logs" / f"map-{index:03d}.jsonl",
        )
        metadata["stage"] = f"map:{index:03d}"
        calls.append(metadata)
        text = partial_path.read_text().strip()
        if not text:
            raise ExperimentError(f"empty summary for chunk {index}")
        partials.append(text)

    reduce_input = "\n".join(
        f"--- PARTIAL {index} ---\n{value}"
        for index, value in enumerate(partials, start=1)
    )
    handoff_path = run_dir / "handoff.md"
    metadata = codex_exec(
        REDUCE_INSTRUCTION.read_text(),
        reduce_input,
        cwd=builder_cwd,
        model=state["builder_model_requested"],
        effort=state["builder_effort"],
        output_path=handoff_path,
        log_path=run_dir / "builder-logs" / "reduce.jsonl",
    )
    metadata["stage"] = "reduce"
    calls.append(metadata)

    handoff = sanitize_text(handoff_path.read_text())
    if not handoff:
        raise ExperimentError("empty consolidated handoff")
    handoff_path.write_text(handoff + "\n")

    # Re-running `build` after a failed validation reuses the partials and
    # regenerates only the reduce. That retry is allowed once and is recorded,
    # because a handoff that needed several attempts is weaker evidence.
    state["handoff_build_attempts"] = state.get("handoff_build_attempts", 0) + 1
    state["handoff_retry"] = state["handoff_build_attempts"] > 1
    state["builder_calls"] = calls
    state["builder_chunks"] = len(chunks)
    state["builder_cwd"] = str(builder_cwd)
    state["handoff_sha256"] = sha256_file(handoff_path)
    mark_phase(state, "build")
    save_state(run_dir, state)
    print(json.dumps({"chunks": len(chunks), "handoff_chars": len(handoff)}, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.expanduser().resolve()
    state = load_state(run_dir)
    require_phase(state, "build")
    handoff = (run_dir / "handoff.md").read_text()
    report = validate_handoff(handoff)
    write_json(run_dir / "handoff-validation.json", report)
    state["handoff_validation"] = {
        "passed": report["passed"],
        "failed_rules": [r["rule"] for r in report["rules"] if not r["passed"]],
        "warnings": report["warnings"],
    }
    if report["passed"]:
        mark_phase(state, "validate")
    save_state(run_dir, state)
    print(json.dumps(state["handoff_validation"], indent=2))
    if not report["passed"]:
        failures = [r for r in report["rules"] if not r["passed"]]
        detail = "; ".join(f"{r['rule']}: {r['detail']}" for r in failures)
        raise ExperimentError(f"handoff validation failed: {detail}")
    return 0


def cmd_treatment(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.expanduser().resolve()
    state = load_state(run_dir)
    require_phase(state, "validate")
    require_phase(state, "probe-memory")
    require_phase(state, "baseline")

    review_path = run_dir / "handoff-review.json"
    if not review_path.is_file():
        raise ExperimentError(
            "V10 human gate: read handoff.md in full, then record the review as "
            f"{review_path} with reviewed_by and reviewed_at"
        )
    review = read_json(review_path)
    for required in ("reviewed_by", "reviewed_at"):
        if not review.get(required):
            raise ExperimentError(f"handoff-review.json is missing {required}")

    subject = Path(state["subject_path"])
    prompt = (Path(state["repo"]) / state["prompt_path"]).read_text()
    if sha256_text(prompt) != state["prompt_sha256"]:
        raise ExperimentError("prompt file changed since preflight")

    root = run_dir / ("placebo-memory" if args.placebo else "treatment-memory")
    memory_dir = root / "memory" if state["memory_layout"] == "nested" else root
    if root.exists():
        shutil.rmtree(root)
    memory_dir.mkdir(parents=True)
    if not args.placebo:
        (memory_dir / "MEMORY.md").write_text(
            f"<!-- Derived, non-authoritative context. Experimental run "
            f"{state['run_id']}. -->\n\n"
            + (run_dir / "handoff.md").read_text().rstrip()
            + "\n"
        )
        before = sha256_file(memory_dir / "MEMORY.md")
        (run_dir / "treatment-memory.sha256").write_text(before + "\n")

    payload = claude_target(
        prompt,
        cwd=subject,
        model=state["target_model"],
        effort=state["target_effort"],
        tools=state["target_tools"],
        permission_mode=state["target_permission_mode"],
        memory="on",
        memory_dir=root,
    )
    answer = str(payload.get("result") or "").strip()
    if not answer:
        raise ExperimentError("treatment response was empty")

    label = "placebo" if args.placebo else "treatment"
    write_json(run_dir / f"{label}.raw.json", payload)
    (run_dir / f"{label}.md").write_text(answer + "\n")

    if not args.placebo:
        after = sha256_file(memory_dir / "MEMORY.md")
        if after != before:
            raise ExperimentError("treatment memory was modified during the run")
        state["treatment_memory_unchanged"] = True
        state["treatment_resolved_models"] = resolved_models(payload)
        state["treatment_elapsed_seconds"] = payload["_invocation"]["elapsed_seconds"]
        state["handoff_reviewed_by"] = review["reviewed_by"]
        mark_phase(state, "treatment")
    else:
        state["placebo_resolved_models"] = resolved_models(payload)
        mark_phase(state, "placebo")

    shutil.rmtree(root, ignore_errors=True)
    save_state(run_dir, state)
    print(json.dumps({label: len(answer)}, indent=2))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.expanduser().resolve()
    state = load_state(run_dir)
    require_phase(state, "treatment")

    baseline = (run_dir / "baseline.md").read_text()
    treatment = (run_dir / "treatment.md").read_text()
    report, diff = comparison_report(baseline, treatment)
    (run_dir / "comparison.md").write_text(report)
    (run_dir / "answer.diff").write_text(diff)

    blind = run_dir / "blind"
    blind.mkdir(exist_ok=True)
    flip = secrets.randbelow(2) == 1
    assignment = {"A": "treatment", "B": "baseline"} if flip else {"A": "baseline", "B": "treatment"}
    texts = {"baseline": baseline, "treatment": treatment}
    for slot, condition in assignment.items():
        (blind / f"{slot}.md").write_text(normalized_answer(texts[condition]) + "\n")
    key_path = blind / "key.json"
    write_json(key_path, assignment)
    key_path.chmod(0o600)

    mark_phase(state, "report")
    save_state(run_dir, state)
    print(json.dumps({"comparison": str(run_dir / "comparison.md")}, indent=2))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.expanduser().resolve()
    state = load_state(run_dir)
    require_phase(state, "report")

    repo = Path(state["repo"])
    subject = Path(state["subject_path"])
    real_memory = Path(state["real_memory_dir"])
    inventory = read_json(run_dir / "session-inventory.json")
    validation = read_json(run_dir / "handoff-validation.json")
    handoff = (run_dir / "handoff.md").read_text()

    memory_after = hash_tree(real_memory)
    memory_before = (run_dir / "real-memory.before.sha256").read_text().strip().splitlines()
    memory_unchanged = [line for line in memory_before if line] == memory_after
    (run_dir / "real-memory.after.sha256").write_text("\n".join(memory_after) + "\n")

    files_after = tracked_file_hashes(subject) if subject.exists() else []
    files_before = [
        line
        for line in (run_dir / "subject-files.before.sha256").read_text().splitlines()
        if line
    ]
    ignored_after = git_value(subject, "status", "--porcelain", "--ignored=matching") or ""
    (run_dir / "subject-status-ignored.after.txt").write_text(ignored_after + "\n")
    ignored_before = {
        line.strip()
        for line in (run_dir / "subject-status-ignored.before.txt").read_text().splitlines()
        if line.strip()
    }
    ignored_new = sorted(
        {line.strip() for line in ignored_after.splitlines() if line.strip()}
        - ignored_before
    )
    ignored_ok = all(entry.split(maxsplit=1)[-1].startswith(".aep") for entry in ignored_new)

    docs_now = hash_tree(Path(os.environ.get("TMPDIR", "/tmp")) / "aep-provider-docs")
    docs_before = [
        line for line in (run_dir / "provider-docs.sha256").read_text().splitlines() if line
    ]

    baseline_models = state.get("baseline_resolved_models") or []
    treatment_models = state.get("treatment_resolved_models") or []
    ended = [item["ended_at"] for item in inventory]
    cutoff = parse_timestamp(state["cutoff"])
    keys = [item["source_key"] for item in inventory]

    corpus_self_reference = []
    for item in inventory:
        text = (run_dir / "corpus" / f"{item['source_key']}.jsonl").read_text()
        if any(pattern.search(text) for pattern in SELF_REFERENCE_PATTERNS[:4]):
            corpus_self_reference.append(item["source_key"])

    builder_calls = state.get("builder_calls", [])
    builder_isolated = all(
        "--ephemeral" in call["argv"] and "--ignore-user-config" in call["argv"]
        for call in builder_calls
    ) and not path_within(state.get("builder_cwd"), repo)

    criteria: list[tuple[str, str, bool, str, bool]] = [
        # (id, description, passed, detail, fatal)
        ("C1", "subject HEAD is the snapshot commit",
         state.get("subject_head") == state["snapshot_commit"], "", True),
        ("C2", "subject working tree clean after both runs",
         not (git_value(subject, "status", "--porcelain") or ""), "", True),
        ("C3", "tracked subject files unchanged",
         files_before == files_after, "", True),
        ("C4", "only .aep added among ignored paths",
         ignored_ok, f"new: {ignored_new}", True),
        ("C5", "no scaffold in subject",
         not any((subject / p).exists() for p in FORBIDDEN_AFTER_RUN),
         "", True),
        ("C6", "Codex sources only, at least 20, zero Claude",
         len(inventory) >= 20 and state["source_counts"].get("claude") == 0, "", True),
        ("C7", "every source ended at or before the cutoff",
         all((parse_timestamp(value) or cutoff) <= cutoff for value in ended), "", True),
        ("C8", "source keys unique and no duplicate content files",
         len(set(keys)) == len(keys) and not state.get("duplicate_content_files"), "", True),
        ("C9", "frozen corpus hashes still match",
         all(
             sha256_file(run_dir / "corpus" / f"{item['source_key']}.jsonl")
             == item["corpus_sha256"]
             for item in inventory
         ), "", True),
        ("C10", "no harness self-reference entered the corpus",
         not corpus_self_reference, f"keys: {corpus_self_reference}", True),
        ("C11", "builder model and effort pinned and recorded",
         bool(state.get("builder_model_requested")) and state.get("builder_effort") == BUILDER_EFFORT,
         state.get("builder_model_resolution", ""), False),
        ("C12", "builder ephemeral, config-isolated, outside repo and subject",
         builder_isolated, "", True),
        ("C13", "handoff names Codex as the sole source provider",
         "codex" in handoff.lower() and "claude" not in
         section_bodies(handoff).get("## Source coverage", "").lower(), "", False),
        ("C14", "handoff validation passed with no retry",
         validation["passed"] and not state.get("handoff_retry"), "", True),
        ("C15", "handoff human review recorded",
         bool(state.get("handoff_reviewed_by")), "", True),
        ("C16", "target controls identical across arms",
         True, "enforced by construction: one recorded control set per run", False),
        ("C17", "resolved target models match and are non-empty",
         bool(baseline_models) and baseline_models == treatment_models,
         f"baseline={baseline_models} treatment={treatment_models}", True),
        ("C18", "both arms non-persistent with prompt history skipped",
         True, "enforced by claude_target", False),
        ("C19", "baseline memory off and isolated; treatment on and isolated",
         True, "enforced by claude_target", False),
        ("C20", "treatment memory file unchanged after the run",
         bool(state.get("treatment_memory_unchanged")), "", True),
        ("C21", "real project memory unchanged",
         memory_unchanged, "", True),
        ("C22", "provider docs identical across arms",
         docs_before == docs_now, "", False),
        ("C23", "no concurrent Claude sessions in the repo",
         not state.get("concurrent_claude_sessions"), "", False),
        ("C24", "no source modified after freeze",
         not state.get("source_modified_after_freeze"), "", False),
        ("C25", "blinded scoring artifacts present",
         (run_dir / "blind" / "A.md").is_file() and (run_dir / "blind" / "key.json").is_file(),
         "", True),
    ]

    results = [
        {"id": cid, "description": desc, "passed": ok, "detail": detail, "fatal": fatal}
        for cid, desc, ok, detail, fatal in criteria
    ]
    fatal_failures = [r["id"] for r in results if not r["passed"] and r["fatal"]]
    soft_failures = [r["id"] for r in results if not r["passed"] and not r["fatal"]]

    if fatal_failures:
        status = RUN_STATUS_INVALID
    elif not memory_unchanged:
        status = RUN_STATUS_INDETERMINATE
    elif soft_failures:
        status = RUN_STATUS_DEGRADED
    else:
        status = RUN_STATUS_VALID

    verification = {
        "run_status": status,
        "fatal_failures": fatal_failures,
        "soft_failures": soft_failures,
        "real_memory_changed_externally": not memory_unchanged,
        "criteria": results,
    }
    write_json(run_dir / "verification.json", verification)
    state["run_status"] = status
    state["real_memory_changed_externally"] = not memory_unchanged
    state["completed_at"] = datetime.now(timezone.utc).isoformat()
    mark_phase(state, "verify")
    save_state(run_dir, state)

    for item in results:
        flag = "PASS" if item["passed"] else ("FAIL" if item["fatal"] else "WARN")
        detail = f"  [{item['detail']}]" if item["detail"] and not item["passed"] else ""
        print(f"{flag}  {item['id']}  {item['description']}{detail}")
    print(f"\nrun_status: {status}")
    return 0 if status in {RUN_STATUS_VALID, RUN_STATUS_DEGRADED} else 1


def cmd_cleanup(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.expanduser().resolve()
    state = load_state(run_dir)
    removed = []
    for path in (
        run_dir / "treatment-memory",
        run_dir / "placebo-memory",
        run_dir / "baseline-memory",
        run_dir / "probe" / "mem",
        run_dir / "probe" / "trust-memory",
    ):
        if path.exists():
            shutil.rmtree(path)
            removed.append(str(path))
    subject = state.get("subject_path")
    if subject and Path(subject).exists() and not args.keep_subject:
        shutil.rmtree(Path(subject).parent)
        removed.append(subject)
    state["cleanup_removed"] = removed
    mark_phase(state, "cleanup")
    save_state(run_dir, state)
    print(json.dumps({"removed": removed}, indent=2))
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    run_dir = args.run_dir.expanduser().resolve()
    state = load_state(run_dir)
    require_phase(state, "verify")
    if state.get("run_status") == RUN_STATUS_INVALID:
        raise ExperimentError("refusing to publish an INVALID run")
    if not args.confirm_privacy_review:
        raise ExperimentError("publishing requires --confirm-privacy-review")

    review = read_json(run_dir / "privacy-review.json")
    missing = [field_ for field_ in PRIVACY_REVIEW_FIELDS if not review.get(field_)]
    if missing:
        raise ExperimentError(f"privacy-review.json is incomplete: {missing}")

    publish_root = args.publish_root.expanduser()
    if not publish_root.is_absolute():
        publish_root = (Path(state["repo"]) / publish_root).resolve()
    destination = publish_root / state["run_id"]
    if destination.exists():
        raise ExperimentError(f"recording bundle already exists: {destination}")
    destination.mkdir(parents=True)
    copied = []
    for name in PUBLISHABLE_ARTIFACTS:
        source = run_dir / name
        if source.is_file():
            shutil.copy2(source, destination / name)
            copied.append(name)

    state["published_to"] = str(destination)
    mark_phase(state, "publish")
    save_state(run_dir, state)
    print(json.dumps({"published": str(destination), "artifacts": copied}, indent=2))
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    def with_run_dir(sub: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sub.add_argument("--run-dir", type=Path, required=True)
        return sub

    preflight = subparsers.add_parser(
        "preflight", help="initialize a run directory and record environment controls"
    )
    preflight.add_argument("--repo", type=Path, default=Path.cwd())
    preflight.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    preflight.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    preflight.add_argument("--snapshot-commit", default=SNAPSHOT_COMMIT)
    preflight.add_argument("--target-model", default=TARGET_MODEL)
    preflight.add_argument("--target-effort", default=TARGET_EFFORT)
    preflight.add_argument("--builder-model", default=BUILDER_MODEL)
    preflight.add_argument("--builder-effort", default=BUILDER_EFFORT)
    preflight.add_argument("--run-id")
    preflight.add_argument(
        "--real-memory",
        type=Path,
        default=Path.home()
        / ".claude/projects/-Users-julianbuccat-Projects-dev-agentic-engineering-platform/memory",
        help="project auto-memory directory to fingerprint and never touch",
    )
    preflight.add_argument("--allow-concurrent-claude", action="store_true")
    preflight.add_argument("--allow-stale-backup", action="store_true")
    preflight.set_defaults(handler=cmd_preflight)

    snapshot = with_run_dir(subparsers.add_parser("snapshot", help="clone the clean snapshot"))
    snapshot.add_argument("--subject", type=Path)
    snapshot.set_defaults(handler=cmd_snapshot)

    with_run_dir(
        subparsers.add_parser("trust-probe", help="accept workspace trust for the subject")
    ).set_defaults(handler=cmd_trust_probe)

    with_run_dir(
        subparsers.add_parser("probe-memory", help="resolve autoMemoryDirectory layout")
    ).set_defaults(handler=cmd_probe_memory)

    inventory = with_run_dir(
        subparsers.add_parser("inventory", help="freeze the Codex-only source corpus")
    )
    inventory.add_argument(
        "--cutoff",
        required=True,
        help="ISO 8601 instant, or 'commit' to derive from the snapshot commit",
    )
    inventory.add_argument("--exclude-source", action="append", default=[])
    inventory.set_defaults(handler=cmd_inventory)

    with_run_dir(
        subparsers.add_parser("recheck-sources", help="compare live transcripts to the freeze")
    ).set_defaults(handler=cmd_recheck_sources)

    with_run_dir(
        subparsers.add_parser("baseline", help="run the baseline subject")
    ).set_defaults(handler=cmd_baseline)

    build = with_run_dir(subparsers.add_parser("build", help="build the handoff with Codex"))
    build.add_argument("--chunk-chars", type=int, default=180_000)
    build.set_defaults(handler=cmd_build)

    with_run_dir(
        subparsers.add_parser("validate", help="apply the handoff validation gate")
    ).set_defaults(handler=cmd_validate)

    treatment = with_run_dir(
        subparsers.add_parser("treatment", help="run the treatment subject")
    )
    treatment.add_argument(
        "--placebo",
        action="store_true",
        help="run the optional empty-memory arm instead of the treatment",
    )
    treatment.set_defaults(handler=cmd_treatment)

    with_run_dir(
        subparsers.add_parser("report", help="write the comparison and blinded artifacts")
    ).set_defaults(handler=cmd_report)

    with_run_dir(
        subparsers.add_parser("verify", help="evaluate acceptance criteria")
    ).set_defaults(handler=cmd_verify)

    cleanup = with_run_dir(subparsers.add_parser("cleanup", help="remove temporary state"))
    cleanup.add_argument("--keep-subject", action="store_true")
    cleanup.set_defaults(handler=cmd_cleanup)

    publish = with_run_dir(
        subparsers.add_parser("publish", help="copy a reviewed bundle to product-demo/RAW")
    )
    publish.add_argument(
        "--publish-root",
        type=Path,
        default=Path("product-demo/RAW/repo-context-handoff-across-models"),
    )
    publish.add_argument("--confirm-privacy-review", action="store_true")
    publish.set_defaults(handler=cmd_publish)

    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.handler
    return handler(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ExperimentError, subprocess.TimeoutExpired) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
