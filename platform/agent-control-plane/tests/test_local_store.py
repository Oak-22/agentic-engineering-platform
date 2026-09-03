from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
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
        self.assertEqual(root, Path("/b"))

    def test_the_developer_store_is_the_namespace_root_itself(self):
        """It is not a subdirectory of anything this platform owns."""
        self.assertIsNone(store.STORES["public-skills"].dirname)

    def test_the_developer_store_sits_outside_this_platform_namespace(self):
        spec = store.STORES["public-skills"]

        self.assertNotEqual(spec.namespace, store.DEFAULT_NAMESPACE)
        self.assertNotIn(store.DEFAULT_NAMESPACE, str(store.store_root("public-skills")))

    def test_platform_stores_stay_in_the_platform_namespace(self):
        for name, spec in store.STORES.items():
            if spec.owner != store.PLATFORM_OWNED:
                continue
            with self.subTest(store=name):
                self.assertEqual(spec.namespace, store.DEFAULT_NAMESPACE)

    def test_project_scoped_store_appends_readable_stable_partition(self):
        root = store.store_root("show-me-captures", project_dir=Path("/repo/ExampleConsumer"), base=Path("/b"))
        identity = store.repository_identity(Path("/repo/ExampleConsumer"))
        self.assertEqual(root, Path("/b") / "show-me-captures" / identity.partition_name)
        self.assertTrue(root.name.startswith("exampleconsumer--"))

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
        self.assertEqual(canonical, Path("/b"))
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

    def test_windows_drive_letter_is_a_path_not_a_host(self):
        """`C:` is a drive; reading it as a host invents `git@c:repo.git`."""
        self.assertEqual(store.normalize_remote("C:/repo"), "C:/repo")
        self.assertEqual(store.normalize_remote("C:\\repo"), "C:\\repo")
        self.assertEqual(store.normalize_remote("/plain/local/path"), "/plain/local/path")

    def test_non_default_port_distinguishes_two_servers(self):
        """Dropping the port would alias separate instances into one store."""
        first = store.normalize_remote("https://git.example.com:8443/owner/repo.git")
        second = store.normalize_remote("https://git.example.com:9443/owner/repo.git")
        self.assertNotEqual(first, second)
        self.assertIn("8443", first)

    def test_default_port_matches_the_portless_form(self):
        portless = store.normalize_remote("https://git.example.com/owner/repo.git")
        self.assertEqual(store.normalize_remote("https://git.example.com:443/owner/repo.git"), portless)
        self.assertEqual(
            store.normalize_remote("ssh://git@github.com:22/Owner/repo.git"),
            store.normalize_remote("ssh://git@github.com/Owner/repo.git"),
        )

    def test_ipv6_literal_survives_normalization(self):
        """Splitting the authority on its first ':' would truncate the address."""
        self.assertIn("::1", store.normalize_remote("https://[::1]:8443/owner/repo.git"))

    def test_established_remote_forms_keep_their_identity(self):
        """Guards the stored partitions: a changed identity orphans them."""
        expected = "git@github.com:Oak-22/agentic-engineering-platform.git"
        for form in (
            "git@github.com:Oak-22/agentic-engineering-platform.git",
            "https://github.com/Oak-22/agentic-engineering-platform",
            "ssh://git@github.com/Oak-22/agentic-engineering-platform.git",
        ):
            with self.subTest(form=form):
                self.assertEqual(store.normalize_remote(form), expected)

    def test_same_remote_different_checkout_names_has_same_partition(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = [Path(tmp) / "first", Path(tmp) / "renamed"]
            for root in roots:
                root.mkdir()
                # check=True reports a failing git directly; without it the run
                # surfaces later as an unexplained partition mismatch, since
                # remoteless roots fall back to their differing paths.
                subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
                subprocess.run(
                    ["git", "-C", str(root), "remote", "add", "origin",
                     "git@github.com:Owner/repo.git"],
                    check=True,
                )
            self.assertEqual(
                store.repository_identity(roots[0]).partition_name,
                store.repository_identity(roots[1]).partition_name,
            )

    def test_no_remote_same_name_paths_do_not_collide(self):
        first = store.repository_identity(Path("/one/repo"))
        second = store.repository_identity(Path("/two/repo"))
        self.assertNotEqual(first.identity_hash, second.identity_hash)


class StoreOwnershipTests(unittest.TestCase):
    def test_every_registered_store_declares_an_owner(self):
        for name, spec in store.STORES.items():
            with self.subTest(store=name):
                self.assertIn(spec.owner, store.STORE_OWNERS)

    def test_a_store_cannot_be_registered_without_an_owner(self):
        """Unstated ownership is what let developer content sit in this namespace."""
        with self.assertRaises(TypeError):
            store.StoreSpec(
                dirname="x", env_var=None, project_scoped=True, summary="s"
            )

    def test_an_unrecognized_owner_is_refused(self):
        with self.assertRaises(ValueError) as raised:
            store.StoreSpec(
                dirname="x",
                env_var=None,
                project_scoped=True,
                summary="s",
                owner="somebody-else",
            )

        self.assertIn("must be one of", str(raised.exception))

    def test_public_skills_is_the_only_developer_owned_store(self):
        """Every other store holds output this platform produced."""
        developer_owned = {
            name
            for name, spec in store.STORES.items()
            if spec.owner == store.DEVELOPER_OWNED
        }

        self.assertEqual(developer_owned, {"public-skills"})


REPO_ROOT = Path(__file__).resolve().parents[3]

#: Every place a runtime auto-loads skills, rules, or instructions from this
#: checkout. The developer store must never be reachable through any of them.
NATIVE_DISCOVERY_SURFACES = (
    ".claude/skills",
    ".claude/rules",
    ".github/skills",
    ".github/instructions",
    ".github/prompts",
    ".codex/skills",
    ".codex/agents",
)


class NativeDiscoveryBoundaryTests(unittest.TestCase):
    """The developer store stays off every runtime's discovery path."""

    def test_local_mirrors_is_gitignored(self):
        """The repo-local view is a convenience path, not a tracked, loadable one."""
        ignored = (REPO_ROOT / ".gitignore").read_text().splitlines()
        self.assertIn(store.MIRROR_DIRNAME + "/", ignored)

    def test_no_discovery_surface_points_into_the_developer_store(self):
        developer_root = store.store_root("public-skills").resolve(strict=False)
        legacy_root = (store.storage_root() / "skills").resolve(strict=False)
        forbidden_fragments = (
            store.STORES["public-skills"].namespace,
            store.MIRROR_DIRNAME,
        )

        leaks: list[str] = []
        for surface in NATIVE_DISCOVERY_SURFACES:
            directory = REPO_ROOT / surface
            if not directory.is_dir():
                continue
            for entry in sorted(directory.iterdir()):
                link_text = os.readlink(entry) if entry.is_symlink() else ""
                resolved = entry.resolve(strict=False)
                reaches_store = resolved == developer_root or resolved == legacy_root or any(
                    parent in (developer_root, legacy_root) for parent in resolved.parents
                )
                names_store = any(fragment in link_text for fragment in forbidden_fragments)
                if reaches_store or names_store:
                    leaks.append(f"{surface}/{entry.name} -> {link_text or resolved}")

        self.assertEqual(leaks, [])


class DeveloperStoreWriteBoundaryTests(unittest.TestCase):
    """Resolution is pure; only an explicit named action creates the store."""

    def test_resolving_the_store_touches_no_filesystem(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "never-created"
            store.store_root("public-skills", base=base)
            store.ensure_store("public-skills", base=base)
            self.assertFalse(base.exists())

    def test_only_the_explicit_create_flag_makes_the_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "store"
            store.ensure_store("public-skills", base=base)
            self.assertFalse(base.exists())
            store.ensure_store("public-skills", base=base, create=True)
            self.assertTrue(base.is_dir())


if __name__ == "__main__":
    unittest.main()
