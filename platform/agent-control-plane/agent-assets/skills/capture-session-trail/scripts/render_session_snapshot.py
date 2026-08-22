#!/usr/bin/env python3
"""Render a reviewable text+tool-call snapshot of one agent session.

Consumes ``session_transcript_reader`` (the single shared per-producer
reader) and writes a Markdown snapshot into a machine-local, per-project
directory outside the repository, mirroring resolve_capture_root.py's
placement for show-me captures. A repo-local symlink view exposes the same
files from inside the repository; making a snapshot visible to a teammate
is a separate, deliberate promotion step, not a side effect of capture.

Re-invoking appends only turns recorded since the last capture. The cutoff
lives in a trailing watermark comment inside the snapshot itself, so the
snapshot is the whole state — there is no sidecar file to lose, and
deleting the snapshot fully resets the capture.

Reasoning content is deliberately absent: the producer redacts it (see
platform/agent-control-plane/docs/strategy/session-transcript-reader.md). Nothing here recovers it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import os
from pathlib import Path
import re
import sys
import textwrap
from typing import Iterable, Sequence


DEFAULT_SNAPSHOT_DIRNAME = "session-snapshots"
WATERMARK_PATTERN = re.compile(
    r"^<!-- aep-session-snapshot turns-consumed=(\d+) -->$", re.MULTILINE
)
_RENDERED_ROLES = frozenset({"user", "assistant"})
_PROSE_WRAP_COLUMNS = 72


def _load_reader():
    """Import the canonical reader by path.

    The skill lives under agent-assets/ and the reader under scripts/;
    neither is an installed package, so path-based loading is the same
    mechanism this repository's tests already use."""
    reader_path = (
        Path(__file__).resolve().parents[4] / "scripts" / "session_transcript_reader.py"
    )
    spec = importlib.util.spec_from_file_location("session_transcript_reader", reader_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load session reader at {reader_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- placement


def resolve_snapshot_root(
    *, project_dir: Path | None, snapshot_base: Path | None = None
) -> Path:
    """Return the per-project snapshot directory, outside the repository.

    Defaults under the same provider-neutral XDG ``aep`` namespace
    resolve_capture_root() and instruction_manifest_hook.storage_root()
    use — a snapshot may be captured from Claude Code or Codex, so this
    must not nest under a single provider's own directory."""
    base = snapshot_base or Path(
        os.environ.get(
            "AEP_SESSION_SNAPSHOT_DIR",
            Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "aep",
        )
    ).expanduser()
    project_slug = project_dir.name if project_dir else "unknown-project"
    return base / DEFAULT_SNAPSHOT_DIRNAME / project_slug


def snapshot_project_view(repo_root: Path, canonical_root: Path) -> Path:
    """Return a repo-local view of canonical_root, creating a symlink at
    <repo_root>/.local-mirrors/session-snapshots if one doesn't exist yet.

    `.local-mirrors/` is gitignored, so this exposes a second access path to
    the same machine-local files — it does not make them tracked, shared, or
    visible to anyone else. Falls back to canonical_root when a view already
    exists and points elsewhere."""
    view = repo_root / ".local-mirrors" / DEFAULT_SNAPSHOT_DIRNAME
    view.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not view.exists() and not view.is_symlink():
        view.symlink_to(canonical_root, target_is_directory=True)
    if view.resolve(strict=False) == canonical_root.resolve():
        return view
    return canonical_root


def snapshot_filename(*, runtime: str, session_id: str) -> str:
    """Return '<runtime>-<session-id>.md'.

    Stable per session rather than per capture: re-capturing appends to the
    same file, so this deliberately does not collision-dedupe the way
    capture_filename() does for one-shot show-me captures."""
    return f"{runtime}-{session_id}.md"


# ------------------------------------------------------------- pure render


def format_watermark(*, turns_consumed: int) -> str:
    return f"<!-- aep-session-snapshot turns-consumed={turns_consumed} -->"


def parse_watermark(text: str) -> int | None:
    """Return the turn cutoff recorded in an existing snapshot, or None.

    Reads the last watermark in the file so a hand-edited snapshot that
    accumulated an earlier stray copy still resumes from the real end."""
    matches = WATERMARK_PATTERN.findall(text)
    return int(matches[-1]) if matches else None


def strip_watermark(text: str) -> str:
    """Remove watermark lines so a fresh one can be appended at the end."""
    return WATERMARK_PATTERN.sub("", text).rstrip("\n")


def is_renderable(turn) -> bool:
    """True when a turn carries conversation content worth showing.

    Metadata lines (role="other") and content-free lines are dropped here,
    not in the reader — the reader yields every parsed line on purpose so
    each consumer decides for itself."""
    return turn.role in _RENDERED_ROLES and bool(turn.text.strip() or turn.tool_calls)


def render_turn(turn) -> str:
    """Render one turn as prose followed by its tool-call trail.

    Both are emitted for the same turn, in that order, so a reviewer reads
    what the agent said and what it then did as one unit. A turn with only
    tool activity still renders — that silence is exactly the gap a
    text-only transcript hides."""
    stamp = turn.timestamp or "no timestamp"
    lines = [f"### {turn.role} — {stamp}", ""]
    body = turn.text.strip()
    if body:
        lines.extend([body, ""])
    for summary in turn.tool_calls:
        lines.append(f"- `{summary}`")
    if turn.tool_calls:
        lines.append("")
    return "\n".join(lines)


def render_reasoning_note(thinking_tokens: int) -> str:
    """The 'why' paragraph of the legend, with the session's real number.

    Falls back to the count-free wording at zero. A transcript predating
    the usage field, or a runtime that never recorded it, would otherwise
    render as "0 tokens of thinking happened" — which reads as a positive
    claim that the agent did no reasoning, the opposite of the truth this
    legend exists to convey.

    Wrapped to match the hand-wrapped prose around it, so the raw Markdown
    stays readable in an editor rather than running off as one long line."""
    closing = (
        f" {thinking_tokens:,} tokens of thinking happened in the session "
        "behind this snapshot. None of it is recoverable."
        if thinking_tokens > 0
        else " No setting brings the raw version back."
    )
    note = (
        "**Why it did any of it — not here.** The provider strips the "
        f"reasoning out before this log is ever written.{closing}"
    )
    return "\n".join(textwrap.wrap(note, width=_PROSE_WRAP_COLUMNS))


def render_header(
    *,
    runtime: str,
    session_id: str,
    source: Path,
    captured: dt.date,
    thinking_tokens: int = 0,
) -> str:
    return "\n".join(
        [
            f"# Session snapshot — {runtime} / {session_id}",
            "",
            f"- Source: `{source}` (read-only; never modified by this capture)",
            f"- First captured: {captured.isoformat()}",
            "- Appended in place on re-capture; the trailing watermark is the cutoff.",
            "",
            "## How much to trust what you're reading",
            "",
            "**Tool calls — take them literally.** Every `-` line is lifted straight",
            "from the session log: same tool, same arguments, same result the agent",
            "got back. If it's here, it happened, exactly like this.",
            "",
            "**What the agent said — also literal.** Verbatim message text.",
            "",
            render_reasoning_note(thinking_tokens),
            "",
            '**A "thinking summary" is a hint, not evidence.** If you have that',
            "setting turned on, what you get is the model's own after-the-fact",
            "paraphrase of its reasoning — not the reasoning. Useful for knowing",
            "where to look. Don't quote it as proof of what the agent actually",
            "thought.",
            "",
            "Background: `platform/agent-control-plane/docs/strategy/session-transcript-reader.md`.",
            "",
            "---",
            "",
            "",
        ]
    )


def render_body(turns: Iterable) -> str:
    """Render renderable turns in source order, dropping the rest."""
    return "\n".join(render_turn(turn) for turn in turns if is_renderable(turn))


# --------------------------------------------------------------- selection


def select_new_turns(turns: Sequence, *, consumed: int) -> tuple[list, int]:
    """Return (turns after the cutoff, new total).

    Indexes on the reader's yielded-turn count, not raw line offsets: the
    reader skips unparseable lines, so a mid-write partial final line
    contributes no turn now and one turn once complete. Under an append-only
    producer that only ever adds at the end, so earlier indices never shift.

    Raises ValueError when the source holds fewer turns than were already
    consumed — the file was truncated or rewritten, and blind appending
    would silently drop or duplicate content."""
    total = len(turns)
    if total < consumed:
        raise ValueError(
            f"source has {total} turns but {consumed} were already captured; "
            "the transcript was truncated or rewritten — delete the snapshot "
            "and re-capture rather than appending"
        )
    return list(turns[consumed:]), total


# --------------------------------------------------------------- discovery


def resolve_session_path(
    reader, *, runtime: str, session: str | None, root: Path | None = None
) -> Path:
    """Resolve a session id, a path, or None (most recent) to one file."""
    if session:
        direct = Path(session).expanduser()
        if direct.is_file():
            return direct
    candidates = reader.locate_sessions(runtime, root=root)
    if not candidates:
        raise FileNotFoundError(f"no {runtime} session transcripts found")
    if session:
        matches = [path for path in candidates if session in path.stem]
        if not matches:
            raise FileNotFoundError(f"no {runtime} session matching {session!r}")
        if len(matches) > 1:
            joined = "\n  ".join(str(path) for path in matches)
            raise ValueError(f"{session!r} matches multiple sessions:\n  {joined}")
        return matches[0]
    return max(candidates, key=lambda path: path.stat().st_mtime)


# ------------------------------------------------------------------- write


def write_snapshot(
    destination: Path,
    *,
    header: str,
    body: str,
    turns_consumed: int,
) -> Path:
    """Create or append to the snapshot, leaving one trailing watermark.

    Appending strips the previous watermark first, so the file always ends
    with exactly one cutoff marker and stays valid Markdown."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        content = strip_watermark(destination.read_text(encoding="utf-8"))
        if body:
            content = f"{content}\n\n{body.rstrip()}"
    else:
        content = (header + body).rstrip()
    watermark = format_watermark(turns_consumed=turns_consumed)
    destination.write_text(f"{content}\n\n{watermark}\n", encoding="utf-8")
    return destination


# --------------------------------------------------------------------- cli


def capture(
    *,
    runtime: str,
    session: str | None,
    project_dir: Path,
    repo_root: Path | None,
    snapshot_base: Path | None = None,
    session_root: Path | None = None,
    dry_run: bool = False,
    today: dt.date | None = None,
) -> dict:
    """Orchestrate one capture. Returns a summary dict for the caller."""
    reader = _load_reader()
    source = resolve_session_path(reader, runtime=runtime, session=session, root=session_root)
    turns = list(reader.read_turns(source, runtime))
    # The reader already derives session_id from the filename per runtime;
    # re-deriving it here would fork that rule for no reason.
    session_id = turns[0].session_id if turns else source.stem

    root = resolve_snapshot_root(project_dir=project_dir, snapshot_base=snapshot_base)
    destination = root / snapshot_filename(runtime=runtime, session_id=session_id)
    consumed = (
        parse_watermark(destination.read_text(encoding="utf-8"))
        if destination.exists()
        else None
    ) or 0

    new_turns, total = select_new_turns(turns, consumed=consumed)
    body = render_body(new_turns)
    # Summed over the whole session, not just the new turns: the header is
    # written once, on first capture, and is describing the session as a
    # whole rather than this particular append.
    thinking_tokens = sum(turn.thinking_tokens for turn in turns)
    header = render_header(
        runtime=runtime,
        session_id=session_id,
        source=source,
        captured=today or dt.date.today(),
        thinking_tokens=thinking_tokens,
    )

    summary = {
        "source": source,
        "session_id": session_id,
        "destination": destination,
        "previously_consumed": consumed,
        "total_turns": total,
        "thinking_tokens": thinking_tokens,
        "new_turns": len(new_turns),
        "rendered_turns": sum(1 for turn in new_turns if is_renderable(turn)),
        "preview": (header + body) if not destination.exists() else body,
        "written": False,
        "view": None,
    }
    if dry_run:
        return summary

    write_snapshot(destination, header=header, body=body, turns_consumed=total)
    summary["written"] = True
    if repo_root is not None:
        summary["view"] = snapshot_project_view(repo_root, root)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runtime", default="claude", choices=("claude", "codex"))
    parser.add_argument(
        "--session",
        default=None,
        help="session id, id fragment, or path; defaults to the most recent session",
    )
    parser.add_argument("--project-dir", default=".", type=Path)
    parser.add_argument(
        "--repo-root",
        default=None,
        type=Path,
        help="create/refresh the .local-mirrors view here; omit to skip",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be appended without writing (the redaction review gate)",
    )
    parser.add_argument(
        "--list", action="store_true", help="list candidate sessions and exit"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.list:
        reader = _load_reader()
        for path in sorted(
            reader.locate_sessions(args.runtime),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )[:20]:
            stamp = dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
            print(f"{stamp}  {path}")
        return 0

    try:
        summary = capture(
            runtime=args.runtime,
            session=args.session,
            project_dir=args.project_dir.resolve(),
            repo_root=args.repo_root.resolve() if args.repo_root else None,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(summary["preview"])
        print(
            f"\n--- dry run: {summary['rendered_turns']} turn(s) would be appended to "
            f"{summary['destination']} (nothing written)",
            file=sys.stderr,
        )
        return 0

    print(f"wrote {summary['rendered_turns']} new turn(s) to {summary['destination']}")
    if summary["view"]:
        print(f"repo-local view: {summary['view']} (gitignored — not shared)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
