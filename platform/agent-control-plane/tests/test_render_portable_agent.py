from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1] / "scripts" / "render_portable_agent.py"
)
SPEC = importlib.util.spec_from_file_location("render_portable_agent", SCRIPT)
assert SPEC and SPEC.loader
RENDERER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RENDERER)


class PortableAgentManifestTest(unittest.TestCase):
    def test_renders_github_custom_agent(self) -> None:
        manifest = {
            "schema_version": 1,
            "id": "architecture-steward",
            "name": "Architecture Steward",
            "description": "Use for architecture governance.",
            "tools": ["read", "search", "edit"],
            "instructions": "You are the architecture steward.\n",
        }

        self.assertEqual(
            RENDERER.render(manifest, "github"),
            (
                "---\n"
                "name: Architecture Steward\n"
                'description: "Use for architecture governance."\n'
                "tools: [read, search, edit]\n"
                "---\n"
                "You are the architecture steward.\n"
            ),
        )

    def test_rejects_unknown_fields(self) -> None:
        manifest = {
            "schema_version": 1,
            "id": "architecture-steward",
            "name": "Architecture Steward",
            "description": "Use for architecture governance.",
            "tools": ["read"],
            "instructions": "Act.",
            "model": "expensive-model",
        }

        with self.assertRaisesRegex(RENDERER.ManifestError, "unknown"):
            RENDERER.validate_manifest(manifest)

    def test_adapter_rejects_unsupported_tools(self) -> None:
        manifest = {
            "schema_version": 1,
            "id": "data-agent",
            "name": "Data Agent",
            "description": "Use for data work.",
            "tools": ["read", "productDatabase/*"],
            "instructions": "Act.",
        }

        with self.assertRaisesRegex(RENDERER.ManifestError, "does not support"):
            RENDERER.render_github(manifest)


if __name__ == "__main__":
    unittest.main()
