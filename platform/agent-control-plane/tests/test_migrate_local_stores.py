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


if __name__ == "__main__":
    unittest.main()
