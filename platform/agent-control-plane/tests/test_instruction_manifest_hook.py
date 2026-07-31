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
    def ledger_for(self, storage, session_id):
        safe_id = session_id.replace("/", "_")
        matches = {
            match.resolve(): match
            for match in storage.glob(f"*/{safe_id}.jsonl")
        }
        self.assertEqual(len(matches), 1)
        return next(iter(matches))

    def run_hook(self, runtime, payload, storage):
        environment = os.environ.copy()
        environment["AEP_INSTRUCTION_MANIFEST_DIR"] = str(storage)
        environment["AEP_INSTRUCTION_EVIDENCE_VIEW"] = str(storage / "view")
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
            self.assertIn("| AGENTS.md | Observed | [", context)
            self.assertIn("](<", context)
            self.assertIn("claude_session.jsonl>)", context)

            ledger_path = self.ledger_for(storage, "claude/session")
            ledger = ledger_path.read_text(encoding="utf-8")
            self.assertNotIn("private prompt content", ledger)
            events = [json.loads(line) for line in ledger.splitlines()]
            self.assertEqual(events[-1]["prompt_id"], "prompt-2")
            record = events[-1]["sources"][0]
            self.assertEqual(record["evidenceType"], "Observed")
            self.assertEqual(
                record["proof"]["eventName"], "InstructionsLoaded"
            )
            self.assertEqual(
                record["citation"]["repositoryId"],
                "git@github.com:Oak-22/agentic-engineering-platform.git",
            )
            self.assertEqual(
                record["citation"]["activeRepositoryId"],
                record["citation"]["repositoryId"],
            )
            self.assertEqual(len(record["citation"]["sha256"]), 64)
            self.assertEqual(len(record["citation"]["gitBlob"]), 40)

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
            self.assertIn("| AGENTS.md | Runtime baseline | [", context)
            self.assertIn("](<", context)
            self.assertIn("codex-session.jsonl>)", context)
            self.assertIn("explicitly invoked skills", context)
            self.assertNotIn("do the work", context)

            ledger_path = self.ledger_for(storage, "codex-session")
            self.assertTrue(ledger_path.is_file())
            ledger = ledger_path.read_text(encoding="utf-8")
            self.assertNotIn("do the work", ledger)
            record = json.loads(ledger.splitlines()[-1])["sources"][0]
            self.assertEqual(record["evidenceType"], "Runtime baseline")
            self.assertEqual(
                record["proof"]["discoveryMechanism"],
                "agents-md-scope-discovery",
            )
            self.assertEqual(record["citation"]["worktreeState"], "clean")

    def test_citation_opens_project_scoped_log_view(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            prompted = self.run_hook(
                "codex",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "citation-session",
                    "turn_id": "turn-1",
                    "cwd": str(REPOSITORY_ROOT),
                },
                storage,
            )
            self.assertEqual(prompted.returncode, 0, prompted.stderr)
            event = json.loads(
                self.ledger_for(storage, "citation-session")
                .read_text(encoding="utf-8")
                .splitlines()[-1]
            )
            citation_path = Path(event["sources"][0]["citation"]["href"])
            self.assertTrue(citation_path.is_file())
            self.assertTrue((storage / "view").is_symlink())
            self.assertEqual(citation_path.parent, storage / "view")
            self.assertEqual(
                citation_path.resolve(),
                self.ledger_for(storage, "citation-session").resolve(),
            )


if __name__ == "__main__":
    unittest.main()
