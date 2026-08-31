#!/usr/bin/env python3
"""Move the developer's skills out of this platform's namespace.

They were stored under `$XDG_DATA_HOME/aep/skills`, which said this platform
owned them. It does not: they are authored by the developer and travel between
projects. This copies them to the namespace `developer_skills.py` resolves,
`$XDG_DATA_HOME/agent-skills`, and repoints the repository mirror at it.

Verification first, following `migrate_local_stores.py`. A plan is printed and
nothing moves without `--execute`; a file that already exists at the target
with different content blocks the run rather than being overwritten. Every
copied file is re-digested after writing, so a truncated or partial copy fails
loudly instead of being reported as migrated.

The source is left in place. Deleting the only copy of content this platform
does not own is not a decision it should make automatically, so removal is a
separate, explicit act.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path


COPY = "copy"
IDENTICAL = "identical"
CONFLICT = "conflict"


SCRIPTS_DIR = Path(__file__).resolve().parent


def _sibling(name: str):
    if name in sys.modules:
        return sys.modules[name]
    # Siblings here import each other by plain module name, so the directory
    # has to be importable however this script was invoked.
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(
        name, SCRIPTS_DIR / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def classify(relative: str, source: Path, target: Path, digest) -> str:
    """What must happen to one file, or why it cannot happen.

    A differing file at the target is a conflict, never an overwrite. This
    content has no other copy and no review step, so guessing which side is
    current would risk destroying the answer.
    """
    if not target.exists():
        return COPY
    return IDENTICAL if digest(source) == digest(target) else CONFLICT


def plan(source: Path, target: Path) -> dict:
    migrate = _sibling("migrate_local_stores")
    entries = [
        {"relative": relative, "action": classify(relative, path, target / relative, migrate.file_digest)}
        for relative, path in sorted(migrate.files_under(source).items())
    ]
    conflicts = [entry["relative"] for entry in entries if entry["action"] == CONFLICT]
    return {
        "source": str(source),
        "target": str(target),
        "entries": entries,
        "conflicts": conflicts,
        "blocked": bool(conflicts),
        "sourcePresent": source.is_dir(),
    }


def execute(plan_value: dict) -> None:
    if plan_value["blocked"]:
        raise RuntimeError(
            "differing files already exist at the target: "
            + ", ".join(plan_value["conflicts"])
        )
    migrate = _sibling("migrate_local_stores")
    source = Path(plan_value["source"])
    target = Path(plan_value["target"])

    for entry in plan_value["entries"]:
        if entry["action"] != COPY:
            continue
        relative = entry["relative"]
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, destination)
        if migrate.file_digest(source / relative) != migrate.file_digest(destination):
            raise RuntimeError(
                f"{relative} did not survive the copy intact; the source is untouched"
            )


def verify(plan_value: dict) -> list[str]:
    """Every source file present at the target with identical content."""
    migrate = _sibling("migrate_local_stores")
    source = Path(plan_value["source"])
    target = Path(plan_value["target"])
    missing: list[str] = []
    for relative in migrate.files_under(source):
        destination = target / relative
        if not destination.exists() or migrate.file_digest(
            source / relative
        ) != migrate.file_digest(destination):
            missing.append(relative)
    return missing


def repoint_view(repo_root: Path) -> Path | None:
    """Point `.local-mirrors/public-skills` at the developer-owned location."""
    store = _sibling("local_store")
    target = store.store_root("public-skills")
    if not target.exists():
        return None
    view = repo_root / store.MIRROR_DIRNAME / "public-skills"
    if view.is_symlink() and view.resolve(strict=False) != target.resolve():
        view.unlink()
    return store.project_view(repo_root, "public-skills", target)


def main(argv: list[str] | None = None) -> int:
    store = _sibling("local_store")
    skills = _sibling("developer_skills")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--source",
        type=Path,
        help="legacy location; defaults to the aep namespace's skills directory",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--remove-source",
        action="store_true",
        help="delete the legacy directory, only after every file is verified at the target",
    )
    args = parser.parse_args(argv)

    source = args.source or (store.storage_root() / "skills")
    target = skills.skills_root()
    value = plan(source.resolve(), target)
    print(json.dumps(value, indent=2, sort_keys=True))

    if not value["sourcePresent"]:
        return 0
    if not args.execute:
        return 2 if value["blocked"] else 0

    try:
        execute(value)
        view = repoint_view(args.repo_root.resolve())
    except (OSError, RuntimeError) as error:
        print(f"migration failed: {error}", file=sys.stderr)
        return 1

    outstanding = verify(value)
    if outstanding:
        print(
            "migration incomplete, source left untouched: " + ", ".join(outstanding),
            file=sys.stderr,
        )
        return 1

    print(f"verified {len(value['entries'])} file(s) at {target}")
    if view:
        print(f"mirror now points at {view.resolve()}")

    if args.remove_source:
        shutil.rmtree(source)
        print(f"removed the legacy directory {source}")
    else:
        print(
            f"the legacy directory {source} was left in place; remove it yourself, "
            "or re-run with --remove-source, once you are satisfied"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
