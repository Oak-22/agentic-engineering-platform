from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "local_store.py"
SPEC = importlib.util.spec_from_file_location("local_store", SCRIPT_PATH)
assert SPEC and SPEC.loader
store = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = store
SPEC.loader.exec_module(store)


class StorageRootTests(unittest.TestCase):
    def test_defaults_to_xdg_aep_namespace(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("XDG_DATA_HOME", None)
            root = store.storage_root()
        self.assertEqual(root, Path.home() / ".local" / "share" / "aep")

    def test_honors_xdg_data_home(self):
        with patch.dict(os.environ, {"XDG_DATA_HOME": "/xdg"}):
            self.assertEqual(store.storage_root(), Path("/xdg") / "aep")

    def test_store_env_var_beats_xdg(self):
        with patch.dict(os.environ, {"XDG_DATA_HOME": "/xdg", "AEP_SKILLS_DIR": "/custom"}):
            self.assertEqual(store.storage_root(env_var="AEP_SKILLS_DIR"), Path("/custom"))

    def test_empty_env_var_falls_through_to_xdg(self):
        """An unset-but-present variable must not resolve the store to ''."""
        with patch.dict(os.environ, {"XDG_DATA_HOME": "/xdg", "AEP_SKILLS_DIR": ""}):
            self.assertEqual(store.storage_root(env_var="AEP_SKILLS_DIR"), Path("/xdg") / "aep")

    def test_explicit_base_overrides_every_environment_source(self):
        with patch.dict(os.environ, {"XDG_DATA_HOME": "/xdg", "AEP_SKILLS_DIR": "/custom"}):
            resolved = store.storage_root(base=Path("/explicit"), env_var="AEP_SKILLS_DIR")
        self.assertEqual(resolved, Path("/explicit"))


class StoreRootTests(unittest.TestCase):
    def test_machine_wide_store_has_no_project_segment(self):
        """public-skills travels across projects, so scoping it would defeat it."""
        root = store.store_root("public-skills", project_dir=Path("/repo/aep"), base=Path("/b"))
        self.assertEqual(root, Path("/b") / "skills")

    def test_project_scoped_store_appends_readable_stable_partition(self):
        root = store.store_root("show-me-captures", project_dir=Path("/repo/myHealth"), base=Path("/b"))
        identity = store.repository_identity(Path("/repo/myHealth"))
        self.assertEqual(root, Path("/b") / "show-me-captures" / identity.partition_name)
        self.assertTrue(root.name.startswith("myhealth--"))

    def test_project_scoped_store_requires_project_dir(self):
        with self.assertRaises(ValueError):
            store.store_root("session-snapshots", base=Path("/b"))

    def test_unknown_store_raises_and_names_the_registry(self):
        with self.assertRaises(store.UnknownStore) as caught:
            store.store_root("provider-docs", base=Path("/b"))
        self.assertIn("public-skills", str(caught.exception))

    def test_every_registered_store_resolves(self):
        for name in store.STORES:
            with self.subTest(store=name):
                self.assertTrue(
                    str(store.store_root(name, project_dir=Path("/r/p"), base=Path("/b")))
                )

    def test_registry_dirnames_are_unique(self):
        dirnames = [spec.dirname for spec in store.STORES.values()]
        self.assertEqual(len(dirnames), len(set(dirnames)))


class ProjectViewTests(unittest.TestCase):
    def test_creates_symlink_under_local_mirrors(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, canonical = Path(tmp) / "repo", Path(tmp) / "canonical"
            repo.mkdir()
            canonical.mkdir()
            view = store.project_view(repo, "public-skills", canonical)
            self.assertEqual(view, repo / ".local-mirrors" / "public-skills")
            self.assertTrue(view.is_symlink())
            self.assertEqual(view.resolve(), canonical.resolve())

    def test_existing_correct_view_is_reused_not_recreated(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, canonical = Path(tmp) / "repo", Path(tmp) / "canonical"
            repo.mkdir()
            canonical.mkdir()
            first = store.project_view(repo, "public-skills", canonical)
            second = store.project_view(repo, "public-skills", canonical)
            self.assertEqual(first, second)
            self.assertTrue(second.is_symlink())

    def test_view_pointing_elsewhere_is_reported_not_replaced(self):
        """Silently repointing a user's existing link would lose their intent."""
        with tempfile.TemporaryDirectory() as tmp:
            repo, canonical, other = Path(tmp) / "repo", Path(tmp) / "c", Path(tmp) / "other"
            for directory in (canonical, other):
                directory.mkdir(parents=True)
            (repo / ".local-mirrors").mkdir(parents=True)
            (repo / ".local-mirrors" / "public-skills").symlink_to(other)
            view = store.project_view(repo, "public-skills", canonical)
            self.assertEqual(view, canonical)
            self.assertEqual((repo / ".local-mirrors" / "public-skills").resolve(), other.resolve())

    def test_mirror_parent_is_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, canonical = Path(tmp) / "repo", Path(tmp) / "canonical"
            repo.mkdir()
            canonical.mkdir()
            store.project_view(repo, "public-skills", canonical)
            mode = (repo / ".local-mirrors").stat().st_mode & 0o777
            self.assertEqual(mode, 0o700)

    def test_unknown_store_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(store.UnknownStore):
                store.project_view(Path(tmp), "not-a-store", Path(tmp))


class EnsureStoreTests(unittest.TestCase):
    def test_returns_canonical_only_without_repo_root(self):
        canonical, view = store.ensure_store("public-skills", base=Path("/b"))
        self.assertEqual(canonical, Path("/b") / "skills")
        self.assertIsNone(view)

    def test_create_makes_the_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            canonical, _ = store.ensure_store("public-skills", base=Path(tmp), create=True)
            self.assertTrue(canonical.is_dir())

    def test_links_view_when_repo_root_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            canonical, view = store.ensure_store(
                "public-skills", repo_root=repo, base=Path(tmp) / "b", create=True
            )
            self.assertEqual(view, repo / ".local-mirrors" / "public-skills")
            self.assertEqual(view.resolve(), canonical.resolve())

    def test_project_store_writes_matching_repository_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "Readable Repo"
            repo.mkdir()
            canonical, _ = store.ensure_store(
                "show-me-captures", project_dir=repo, base=Path(tmp) / "data", create=True
            )
            metadata = __import__("json").loads(
                (canonical / "repository.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["partitionName"], canonical.name)
            self.assertEqual(metadata["readableRepositoryName"], "readable-repo")
            self.assertEqual(metadata["repositoryIdentityHash"], canonical.name.rsplit("--", 1)[1])
            self.assertEqual(store.validate_repository_metadata(canonical, store.repository_identity(repo)), [])


class RepositoryIdentityTests(unittest.TestCase):
    def test_remote_forms_normalize_without_credentials(self):
        expected = "git@github.com:Owner/repo.git"
        self.assertEqual(store.normalize_remote("git@github.com:Owner/repo.git"), expected)
        self.assertEqual(store.normalize_remote("https://token@github.com/Owner/repo.git"), expected)
        self.assertNotIn("token", store.normalize_remote("https://token@github.com/Owner/repo.git"))

    def test_same_remote_different_checkout_names_has_same_partition(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = [Path(tmp) / "first", Path(tmp) / "renamed"]
            for root in roots:
                root.mkdir()
                os.system(f"git -C '{root}' init -q")
                os.system(f"git -C '{root}' remote add origin git@github.com:Owner/repo.git")
            self.assertEqual(
                store.repository_identity(roots[0]).partition_name,
                store.repository_identity(roots[1]).partition_name,
            )

    def test_no_remote_same_name_paths_do_not_collide(self):
        first = store.repository_identity(Path("/one/repo"))
        second = store.repository_identity(Path("/two/repo"))
        self.assertNotEqual(first.identity_hash, second.identity_hash)


if __name__ == "__main__":
    unittest.main()
