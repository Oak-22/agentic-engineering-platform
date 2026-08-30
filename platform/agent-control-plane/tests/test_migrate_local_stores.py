from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "migrate_local_stores", SCRIPTS / "migrate_local_stores.py"
)
assert SPEC and SPEC.loader
migration = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = migration
SPEC.loader.exec_module(migration)


def make_repo(root: Path) -> None:
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "remote", "add", "origin", "git@github.com:Owner/repo.git"],
        check=True,
    )


class MigrationTests(unittest.TestCase):
    def test_plan_discovers_hash_and_slug_legacy_partitions(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, repo = Path(tmp) / "data", Path(tmp) / "checkout"
            make_repo(repo)
            identity = migration.local_store.repository_identity(repo)
            (base / "instruction-evidence" / identity.identity_hash).mkdir(parents=True)
            (base / "instruction-evidence" / identity.identity_hash / "event.jsonl").write_text("{}\n")
            (base / "show-me-captures" / repo.name).mkdir(parents=True)
            value = migration.plan(repo, base)
            kinds = {(entry["store"], entry["sourceKind"]) for entry in value["entries"]}
            self.assertIn(("instruction-evidence", "hash-only"), kinds)
            self.assertIn(("show-me-captures", "slug-only"), kinds)
            self.assertFalse(value["blocked"])

    def test_execute_copies_and_verifies_without_deleting_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, repo = Path(tmp) / "data", Path(tmp) / "checkout"
            make_repo(repo)
            source = base / "artifact-archive" / repo.name
            source.mkdir(parents=True)
            (source / "artifact.txt").write_text("preserved", encoding="utf-8")
            value = migration.plan(repo, base)
            migration.execute(value)
            target = Path(value["entries"][0]["target"])
            self.assertEqual((target / "artifact.txt").read_text(), "preserved")
            self.assertTrue(source.exists())
            migration.execute(migration.plan(repo, base))
            self.assertEqual((target / "artifact.txt").read_text(), "preserved")
            rerun = migration.plan(repo, base)
            self.assertEqual(rerun["entries"][0]["action"], "already-migrated")

    def test_collision_blocks_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, repo = Path(tmp) / "data", Path(tmp) / "checkout"
            make_repo(repo)
            identity = migration.local_store.repository_identity(repo)
            source = base / "session-snapshots" / repo.name
            target = base / "session-snapshots" / identity.partition_name
            source.mkdir(parents=True)
            target.mkdir(parents=True)
            (source / "same.md").write_text("source")
            (target / "same.md").write_text("target")
            value = migration.plan(repo, base)
            self.assertTrue(value["blocked"])
            with self.assertRaises(RuntimeError):
                migration.execute(value)
            self.assertEqual((target / "same.md").read_text(), "target")

    def test_generated_metadata_and_extended_ledger_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, repo = Path(tmp) / "data", Path(tmp) / "checkout"
            make_repo(repo)
            identity = migration.local_store.repository_identity(repo)
            source = base / "instruction-evidence" / identity.identity_hash
            target = base / "instruction-evidence" / identity.partition_name
            source.mkdir(parents=True)
            target.mkdir(parents=True)
            (source / "repository.json").write_text('{"projectKey":"legacy"}\n')
            (target / "repository.json").write_text('{"schemaVersion":1}\n')
            (source / "events.jsonl").write_text('{"turn":1}\n')
            (target / "events.jsonl").write_text('{"turn":1}\n{"turn":2}\n')
            value = migration.plan(repo, base)
            self.assertFalse(value["blocked"])
            self.assertEqual(value["entries"][0]["action"], "already-migrated")

    def test_repoint_views_follows_the_migrated_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, repo = Path(tmp) / "data", Path(tmp) / "checkout"
            make_repo(repo)
            source = base / "artifact-archive" / repo.name
            source.mkdir(parents=True)
            (source / "artifact.txt").write_text("preserved", encoding="utf-8")
            migration.execute(migration.plan(repo, base))
            migration.repoint_views(repo, base)
            view = repo / migration.local_store.MIRROR_DIRNAME / "artifact-archive"
            expected = migration.local_store.store_root(
                "artifact-archive", project_dir=repo, base=base
            )
            # Resolving through the ambient default namespace instead would
            # leave this view outside the migrated tree entirely.
            self.assertEqual(view.resolve(), expected.resolve())
            self.assertEqual((view / "artifact.txt").read_text(), "preserved")

    def test_starts_with_streams_without_loading_whole_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            short, extended, divergent = (Path(tmp) / name for name in ("a", "b", "c"))
            short.write_bytes(b'{"turn":1}\n')
            extended.write_bytes(b'{"turn":1}\n{"turn":2}\n')
            divergent.write_bytes(b'{"turn":9}\n{"turn":2}\n')
            self.assertTrue(migration.starts_with(extended, short, chunk_size=4))
            self.assertFalse(migration.starts_with(divergent, short, chunk_size=4))
            self.assertFalse(migration.starts_with(short, extended, chunk_size=4))
            self.assertTrue(migration.starts_with(short, short, chunk_size=4))


if __name__ == "__main__":
    unittest.main()
