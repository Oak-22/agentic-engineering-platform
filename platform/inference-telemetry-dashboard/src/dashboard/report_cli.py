"""Render the inference cost report from local session transcripts.

The only module here that touches the filesystem. It locates sessions
through the control plane's transcript port, filters them to one repository,
folds them through usage_model, and writes the page into the machine-local
telemetry-reports store.

Reads provider state and writes only into this platform's own namespace —
never the reverse.
"""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from pathlib import Path
import sys

from .render_html import render_report
from .usage_model import build_report

#: The control plane's scripts are a flat directory of stdlib-only modules,
#: not an installed package, so they are imported by path the way the other
#: cross-component callers do it. Importing the port is the whole point: a
#: second transcript reader in this component would re-derive per-runtime
#: path patterns that already have one owner.
#:
#: This only resolves inside an editable checkout of this monorepo: the
#: entry point this module registers does not work from a standalone wheel
#: installed elsewhere, because `__file__` would then sit under
#: `site-packages` with no sibling `agent-control-plane` directory. That is
#: validated below rather than left to surface as an opaque ModuleNotFoundError.
_CONTROL_PLANE_SCRIPTS = (
    Path(__file__).resolve().parents[3] / "agent-control-plane" / "scripts"
)
if not (_CONTROL_PLANE_SCRIPTS / "session_transcript_reader.py").is_file():
    raise RuntimeError(
        "dashboard-report requires an editable checkout of the "
        "agentic-engineering-platform monorepo: expected the control "
        f"plane's transcript reader at {_CONTROL_PLANE_SCRIPTS}, which does "
        "not exist. Installing this package as a standalone wheel outside "
        "that checkout is not supported."
    )
if str(_CONTROL_PLANE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_CONTROL_PLANE_SCRIPTS))

import local_store  # noqa: E402
import session_transcript_reader as transcripts  # noqa: E402

RUNTIMES = ("claude", "codex")
STORE = "telemetry-reports"


def repository_root() -> Path:
    """This repository's root, derived from this file's own location."""
    return Path(__file__).resolve().parents[4]


def collect_samples(
    runtimes: list[str], *, project_dir: Path, since: date | None
) -> tuple[list, str]:
    """Read usage from every session that ran in this repository.

    locate_sessions enumerates a runtime's sessions across every project on
    the machine, so the repository filter is this function's job. It reads
    each session's header rather than trusting the file's location, because
    only Claude partitions its files by project and even there the header is
    the runtime's own statement of where it ran."""
    samples = []
    counts = []
    wanted = project_dir.resolve()

    for runtime in runtimes:
        paths = transcripts.locate_sessions(runtime, since)
        kept = 0
        for path in paths:
            context = transcripts.read_session_context(path, runtime)
            if context.cwd is None:
                continue
            try:
                within_repo = Path(context.cwd).resolve().is_relative_to(wanted)
            except (OSError, ValueError):
                within_repo = False
            if not within_repo:
                continue
            kept += 1
            samples.extend(transcripts.read_usage(path, runtime))
        counts.append(f"{kept} {runtime} session{'' if kept == 1 else 's'}")

    return samples, " and ".join(counts)


def write_latest_pointer(report_path: Path) -> Path:
    """Point `latest.html` at the report just written.

    A stable filename to open, beside the dated files that accumulate. The
    link is relative so the store stays movable, and it is replaced rather
    than updated in place because a symlink cannot be rewritten atomically."""
    pointer = report_path.parent / "latest.html"
    if pointer.exists() or pointer.is_symlink():
        pointer.unlink()
    pointer.symlink_to(report_path.name)
    return pointer


def parse_since(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--since expects an ISO date such as 2026-08-01, got {value!r}"
        ) from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dashboard-report",
        description=(
            "Render inference cost per governed engineering outcome from local "
            "session transcripts."
        ),
    )
    parser.add_argument(
        "--runtime",
        default=",".join(RUNTIMES),
        help=f"comma-separated runtimes to read (default: {','.join(RUNTIMES)})",
    )
    parser.add_argument(
        "--since",
        type=parse_since,
        default=None,
        help="only read sessions modified on or after this ISO date",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write here instead of the telemetry-reports store",
    )
    parser.add_argument(
        "--print-path",
        action="store_true",
        help="print only the written path, for piping into an opener",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    runtimes = [name.strip() for name in args.runtime.split(",") if name.strip()]
    unknown = [name for name in runtimes if name not in RUNTIMES]
    if unknown:
        raise SystemExit(
            f"unknown runtime(s): {', '.join(unknown)}; expected one or more of "
            f"{', '.join(RUNTIMES)}"
        )

    project_dir = repository_root()
    samples, sources = collect_samples(
        runtimes, project_dir=project_dir, since=args.since
    )
    if not samples:
        raise SystemExit(
            f"no usage found in {sources or 'any session'} for {project_dir}"
        )

    now = datetime.now(UTC)
    html = render_report(
        build_report(samples),
        generated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
        sources=sources,
    )

    if args.out is not None:
        destination = args.out
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(html, encoding="utf-8")
        pointer = None
    else:
        canonical, _ = local_store.ensure_store(
            STORE, project_dir=project_dir, repo_root=project_dir, create=True
        )
        destination = canonical / f"{now:%Y-%m-%d}-inference-cost.html"
        destination.write_text(html, encoding="utf-8")
        pointer = write_latest_pointer(destination)

    if args.print_path:
        print(pointer or destination)
        return

    print(f"Read {len(samples):,} model calls from {sources}.")
    print(f"Wrote {destination}")
    if pointer is not None:
        print(f"Open  {pointer}")


if __name__ == "__main__":
    main()
