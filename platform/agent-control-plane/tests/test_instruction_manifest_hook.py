import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
HOOK = (
    REPOSITORY_ROOT
    / "platform"
    / "agent-control-plane"
    / "scripts"
    / "instruction_manifest_hook.py"
)


class InstructionManifestHookTests(unittest.TestCase):
    def run_hook(self, runtime, payload, storage):
        environment = os.environ.copy()
        environment["AEP_INSTRUCTION_MANIFEST_DIR"] = str(storage)
        return subprocess.run(
            ["python3", str(HOOK), "--runtime", runtime],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=False,
            cwd=REPOSITORY_ROOT,
            env=environment,
        )

    def test_claude_observation_seeds_next_prompt_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            instruction = REPOSITORY_ROOT / "AGENTS.md"
            observed = self.run_hook(
                "claude",
                {
                    "hook_event_name": "InstructionsLoaded",
                    "session_id": "claude/session",
                    "cwd": str(REPOSITORY_ROOT),
                    "file_path": str(instruction),
                    "load_reason": "session_start",
                    "memory_type": "Project",
                },
                storage,
            )
            self.assertEqual(observed.returncode, 0, observed.stderr)
            self.assertEqual(observed.stdout, "")

            prompted = self.run_hook(
                "claude",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "claude/session",
                    "prompt_id": "prompt-2",
                    "cwd": str(REPOSITORY_ROOT),
                    "prompt": "private prompt content",
                },
                storage,
            )
            self.assertEqual(prompted.returncode, 0, prompted.stderr)
            output = json.loads(prompted.stdout)
            context = output["hookSpecificOutput"]["additionalContext"]
            self.assertIn("| AGENTS.md | Observed |", context)

            ledger = (storage / "claude_session.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("private prompt content", ledger)
            events = [json.loads(line) for line in ledger.splitlines()]
            self.assertEqual(events[-1]["prompt_id"], "prompt-2")
            self.assertEqual(events[-1]["sources"][0]["evidence"], "Observed")

    def test_claude_excludes_observations_from_another_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            self.run_hook(
                "claude",
                {
                    "hook_event_name": "InstructionsLoaded",
                    "session_id": "claude-session",
                    "prompt_id": "prompt-1",
                    "cwd": str(REPOSITORY_ROOT),
                    "file_path": str(REPOSITORY_ROOT / "AGENTS.md"),
                },
                storage,
            )
            prompted = self.run_hook(
                "claude",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "claude-session",
                    "prompt_id": "prompt-2",
                    "cwd": str(REPOSITORY_ROOT),
                    "prompt": "next prompt",
                },
                storage,
            )
            context = json.loads(prompted.stdout)["hookSpecificOutput"][
                "additionalContext"
            ]
            self.assertNotIn("| AGENTS.md | Observed |", context)

    def test_codex_discovers_repository_agents_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            prompted = self.run_hook(
                "codex",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "codex-session",
                    "turn_id": "turn-1",
                    "cwd": str(REPOSITORY_ROOT),
                    "prompt": "do the work",
                },
                storage,
            )
            self.assertEqual(prompted.returncode, 0, prompted.stderr)
            output = json.loads(prompted.stdout)
            context = output["hookSpecificOutput"]["additionalContext"]
            self.assertIn("| AGENTS.md | Runtime baseline |", context)
            self.assertIn("explicitly invoked skills", context)
            self.assertNotIn("do the work", context)

            ledger_path = storage / "codex-session.jsonl"
            self.assertTrue(ledger_path.is_file())
            ledger = ledger_path.read_text(encoding="utf-8")
            self.assertNotIn("do the work", ledger)


if __name__ == "__main__":
    unittest.main()
