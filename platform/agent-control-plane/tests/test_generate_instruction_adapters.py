from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).parents[1] / "scripts" / "generate_instruction_adapters.py"
)
SPEC = importlib.util.spec_from_file_location("generate_instruction_adapters", SCRIPT_PATH)
assert SPEC and SPEC.loader
generator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generator
SPEC.loader.exec_module(generator)


class RenderClaudeAdapterTests(unittest.TestCase):
    def test_renders_universal_scope(self):
        import_line = generator.canonical_import_line("general-agent")
        content = generator.render_claude_adapter(["**/*"], import_line)
        self.assertEqual(
            content,
            '---\npaths:\n  - "**/*"\n---\n\n'
            "@../../platform/agent-control-plane/agent-assets/instructions/general-agent.md\n",
        )

    def test_renders_single_extension_scope(self):
        import_line = generator.canonical_import_line("python")
        content = generator.render_claude_adapter(["**/*.py"], import_line)
        self.assertEqual(
            content,
            '---\npaths:\n  - "**/*.py"\n---\n\n'
            "@../../platform/agent-control-plane/agent-assets/instructions/python.md\n",
        )

    def test_renders_multi_glob_scope(self):
        globs = ["AGENTS.md", "CLAUDE.md", ".agents/**"]
        import_line = generator.canonical_import_line("agent-context-routing")
        content = generator.render_claude_adapter(globs, import_line)
        self.assertEqual(
            content,
            '---\npaths:\n  - "AGENTS.md"\n  - "CLAUDE.md"\n  - ".agents/**"\n---\n\n'
            "@../../platform/agent-control-plane/agent-assets/instructions/agent-context-routing.md\n",
        )


class RenderCopilotAdapterTests(unittest.TestCase):
    def test_renders_single_glob_applyto(self):
        import_line = generator.canonical_import_line("python")
        content = generator.render_copilot_adapter(
            "Portable Python code standards", ["**/*.py"], import_line
        )
        self.assertEqual(
            content,
            '---\ndescription: "Portable Python code standards"\n'
            'applyTo: "**/*.py"\n---\n\n'
            "@../../platform/agent-control-plane/agent-assets/instructions/python.md\n",
        )

    def test_joins_multiple_globs_with_commas_no_brace_collapse(self):
        import_line = generator.canonical_import_line("artifact-formatting")
        globs = ["**/*.md", "**/*.json", "**/*.yml", "**/*.yaml", "**/*.toml", "**/*.py", "**/*.sh"]
        content = generator.render_copilot_adapter(
            "Formatting guidance for code-adjacent artifacts, docs, and agent-facing outputs.",
            globs,
            import_line,
        )
        self.assertIn(
            'applyTo: "**/*.md,**/*.json,**/*.yml,**/*.yaml,**/*.toml,**/*.py,**/*.sh"',
            content,
        )
        self.assertNotIn("{", content)


class RenderAllTests(unittest.TestCase):
    def test_skips_adapterless_instruction(self):
        registry = {
            "instructions": [
                {
                    "id": "prose-writing-rules",
                    "runtimeAdapters": [],
                },
                {
                    "id": "python",
                    "scopeGlobs": ["**/*.py"],
                    "copilotDescription": "Portable Python code standards",
                    "runtimeAdapters": [
                        ".github/instructions/python.instructions.md",
                        ".claude/rules/python.md",
                    ],
                },
            ]
        }
        root = Path("/repo")
        rendered = generator.render_all(root, registry)
        self.assertEqual(
            set(rendered),
            {
                root / ".github/instructions/python.instructions.md",
                root / ".claude/rules/python.md",
            },
        )

    def test_matches_adapter_paths_by_suffix_not_list_order(self):
        registry = {
            "instructions": [
                {
                    "id": "python",
                    "scopeGlobs": ["**/*.py"],
                    "copilotDescription": "Portable Python code standards",
                    "runtimeAdapters": [
                        ".claude/rules/python.md",
                        ".github/instructions/python.instructions.md",
                    ],
                },
            ]
        }
        root = Path("/repo")
        rendered = generator.render_all(root, registry)
        claude_content = rendered[root / ".claude/rules/python.md"]
        copilot_content = rendered[root / ".github/instructions/python.instructions.md"]
        self.assertIn("paths:", claude_content)
        self.assertIn("applyTo:", copilot_content)


class WriteIfChangedTests(unittest.TestCase):
    def test_writes_new_file_then_is_idempotent_then_rewrites_on_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adapter.md"

            first = generator.write_if_changed(path, "content-a")
            self.assertTrue(first)
            self.assertEqual(path.read_text(encoding="utf-8"), "content-a")

            second = generator.write_if_changed(path, "content-a")
            self.assertFalse(second)

            third = generator.write_if_changed(path, "content-b")
            self.assertTrue(third)
            self.assertEqual(path.read_text(encoding="utf-8"), "content-b")


if __name__ == "__main__":
    unittest.main()
