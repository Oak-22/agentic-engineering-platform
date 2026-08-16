from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).parents[1] / "scripts" / "provider_docs_session_start.py"
)
SPEC = importlib.util.spec_from_file_location("provider_docs_session_start", SCRIPT_PATH)
assert SPEC and SPEC.loader
provider_docs = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = provider_docs
SPEC.loader.exec_module(provider_docs)


class Response:
    def __init__(self, body: bytes):
        self.body = io.BytesIO(body)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, size: int = -1) -> bytes:
        return self.body.read(size)


class ProviderDocsSessionStartTests(unittest.TestCase):
    def test_fresh_cache_avoids_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manual = root / "codex-manual.md"
            manual.write_text("local manual", encoding="utf-8")
            os.utime(manual, (1_000, 1_000))
            opener = mock.Mock(side_effect=AssertionError("network was used"))

            path, status = provider_docs.ensure_manual(
                "codex", root=root, now=1_001, opener=opener
            )

            self.assertEqual(path, manual)
            self.assertEqual(status, "fresh local cache")
            opener.assert_not_called()

    def test_missing_cache_fetches_official_manual(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "provider-docs"
            opener = mock.Mock(return_value=Response(b"# Provider manual\n"))

            path, status = provider_docs.ensure_manual(
                "claude", root=root, now=2_000, opener=opener
            )

            self.assertEqual(path.read_text(encoding="utf-8"), "# Provider manual\n")
            self.assertEqual(
                status, "refreshed from official provider documentation"
            )
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            request = opener.call_args.args[0]
            self.assertEqual(
                request.full_url, "https://code.claude.com/docs/llms-full.txt"
            )

    def test_failed_refresh_preserves_stale_manual(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manual = root / "codex-manual.md"
            manual.write_text("stale but useful", encoding="utf-8")
            os.utime(manual, (1, 1))

            path, status = provider_docs.ensure_manual(
                "codex",
                root=root,
                now=100_000,
                opener=mock.Mock(side_effect=OSError("offline")),
            )

            self.assertEqual(path.read_text(encoding="utf-8"), "stale but useful")
            self.assertEqual(status, "stale local cache; refresh unavailable")

    def test_hook_output_is_compact_and_runtime_specific(self):
        for runtime in ("codex", "claude"):
            with self.subTest(runtime=runtime):
                with tempfile.TemporaryDirectory() as directory:
                    fake_repo = Path(directory) / "repo"
                    fake_repo.mkdir()
                    docs_root = Path(directory) / "docs-cache"
                    docs_root.mkdir()
                    manual = docs_root / f"{runtime}-manual.md"
                    manual.write_text("manual", encoding="utf-8")
                    with mock.patch.object(
                        provider_docs,
                        "ensure_manual",
                        return_value=(manual, "fresh local cache"),
                    ):
                        output = provider_docs.handle(
                            runtime,
                            {"hook_event_name": "SessionStart", "cwd": str(fake_repo)},
                        )

                assert output is not None
                hook_output = output["hookSpecificOutput"]
                self.assertEqual(hook_output["hookEventName"], "SessionStart")
                context = hook_output["additionalContext"]
                self.assertIn(str(manual), context)
                self.assertIn("Consult the local manual first", context)
                self.assertLess(len(context), 1_000)


class ProviderDocsViewTests(unittest.TestCase):
    def test_creates_symlink_on_first_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_root = root / "repo"
            repo_root.mkdir()
            canonical_root = root / "docs-cache"
            canonical_root.mkdir()

            view = provider_docs.provider_docs_view(repo_root, canonical_root)

            self.assertEqual(view, repo_root / ".local-mirrors" / "provider-docs")
            self.assertTrue(view.is_symlink())
            self.assertEqual(view.resolve(), canonical_root.resolve())

    def test_falls_back_to_canonical_root_when_view_points_elsewhere(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_root = root / "repo"
            repo_root.mkdir()
            canonical_root = root / "docs-cache"
            canonical_root.mkdir()
            other_root = root / "other"
            other_root.mkdir()

            view_path = repo_root / ".local-mirrors" / "provider-docs"
            view_path.parent.mkdir(parents=True)
            view_path.symlink_to(other_root, target_is_directory=True)

            result = provider_docs.provider_docs_view(repo_root, canonical_root)

            self.assertEqual(result, canonical_root)


if __name__ == "__main__":
    unittest.main()
