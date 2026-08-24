import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPOSITORY_ROOT / "platform" / "agent-control-plane" / "scripts"
HOOK = SCRIPTS / "instruction_manifest_hook.py"

sys.path.insert(0, str(SCRIPTS))
import validate_contracts  # noqa: E402

SKILL_ID = "deliver-governed-change"
SKILL_FILE = (
    "platform/agent-control-plane/agent-assets/skills/"
    "deliver-governed-change/SKILL.md"
)
INSTRUCTION_FILE = (
    "platform/agent-control-plane/agent-assets/instructions/"
    "agent-context-routing.md"
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
            self.assertIn("| AGENTS.md | Observed |", context)
            self.assertRegex(context, r"Ledger citation: `[^`]*claude_session\.jsonl:\d+`")
            self.assertNotIn("](<", context)

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
            self.assertIn("| AGENTS.md | Runtime baseline |", context)
            self.assertRegex(
                context, r"Ledger citation: \[[^\]]*\]\(<[^>]*codex-session\.jsonl:\d+>\)"
            )
            self.assertNotIn("`.local-mirrors", context)
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

    def test_copilot_discovers_repository_instructions_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            prompted = self.run_hook(
                "copilot",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "copilot-session",
                    "turn_id": "turn-1",
                    "cwd": str(REPOSITORY_ROOT),
                    "prompt": "do the work",
                },
                storage,
            )
            self.assertEqual(prompted.returncode, 0, prompted.stderr)
            output = json.loads(prompted.stdout)
            context = output["hookSpecificOutput"]["additionalContext"]
            self.assertIn(
                "| .github/copilot-instructions.md | Runtime baseline |", context
            )
            self.assertNotIn("do the work", context)

            ledger_path = self.ledger_for(storage, "copilot-session")
            ledger = ledger_path.read_text(encoding="utf-8")
            record = json.loads(ledger.splitlines()[-1])["sources"][0]
            self.assertEqual(record["evidenceType"], "Runtime baseline")
            self.assertEqual(record["proof"]["runtime"], "copilot")
            self.assertEqual(
                record["proof"]["discoveryMechanism"],
                "copilot-instructions-root-file",
            )

    def test_copilot_does_not_inherit_codex_baseline_mislabeling(self):
        """Regression guard for the claude/else dispatch bug found in AEPI-96.

        Before the three-way dispatch, any non-claude runtime silently fell
        through to codex_baselines(), which stamps every record
        proof["runtime"] == "codex" and discoveryMechanism
        "agents-md-scope-discovery". A copilot run must never carry either.
        """
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            prompted = self.run_hook(
                "copilot",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "copilot-mislabel-session",
                    "turn_id": "turn-1",
                    "cwd": str(REPOSITORY_ROOT),
                },
                storage,
            )
            self.assertEqual(prompted.returncode, 0, prompted.stderr)
            ledger_path = self.ledger_for(storage, "copilot-mislabel-session")
            sources = json.loads(
                ledger_path.read_text(encoding="utf-8").splitlines()[-1]
            )["sources"]
            self.assertTrue(sources, "no records were produced to validate")
            for record in sources:
                self.assertNotEqual(record["proof"].get("runtime"), "codex")
                self.assertNotEqual(
                    record["proof"].get("discoveryMechanism"),
                    "agents-md-scope-discovery",
                )

    def test_copilot_adapter_surface_declares_uncovered_instructions(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            prompted = self.run_hook(
                "copilot",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "copilot-declared-session",
                    "turn_id": "turn-1",
                    "cwd": str(REPOSITORY_ROOT),
                },
                storage,
            )
            self.assertEqual(prompted.returncode, 0, prompted.stderr)
            ledger_path = self.ledger_for(storage, "copilot-declared-session")
            sources = json.loads(
                ledger_path.read_text(encoding="utf-8").splitlines()[-1]
            )["sources"]
            declared = {
                record["instruction"]: record
                for record in sources
                if record["evidenceType"] == "Declared"
            }
            self.assertIn(INSTRUCTION_FILE, declared)
            self.assertEqual(
                declared[INSTRUCTION_FILE]["proof"]["declarationKind"],
                "copilot-instruction-adapter",
            )
            self.assertTrue(
                declared[INSTRUCTION_FILE]["proof"]["adapterPath"].startswith(
                    ".github/"
                )
            )

    def test_store_index_describes_generated_file_classes(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            prompted = self.run_hook(
                "codex",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "index-session",
                    "turn_id": "turn-1",
                    "cwd": str(REPOSITORY_ROOT),
                },
                storage,
            )
            self.assertEqual(prompted.returncode, 0, prompted.stderr)
            ledger_path = self.ledger_for(storage, "index-session")
            index = json.loads(
                (ledger_path.parent / "store-index.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(index["storeType"], "instruction-evidence")
            self.assertEqual(index["schemaVersion"], 1)
            self.assertEqual(
                [file_class["kind"] for file_class in index["fileClasses"]],
                ["metadata", "index", "session-ledger"],
            )

    def test_claude_instruction_observation_records_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            observed = self.run_hook(
                "claude",
                {
                    "hook_event_name": "InstructionsLoaded",
                    "session_id": "claude-session",
                    "cwd": str(REPOSITORY_ROOT),
                    "file_path": str(REPOSITORY_ROOT / "AGENTS.md"),
                },
                storage,
            )
            self.assertEqual(observed.returncode, 0, observed.stderr)
            events = [
                json.loads(line)
                for line in self.ledger_for(storage, "claude-session")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(events[0]["runtime"], "claude")

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
            href = event["sources"][0]["citation"]["href"]
            file_part, _, line_number = href.rpartition(":")
            citation_path = Path(file_part)
            self.assertTrue(citation_path.is_file())
            # The citation lands on the ledger line holding this manifest.
            self.assertEqual(
                json.loads(
                    citation_path.read_text(encoding="utf-8").splitlines()[
                        int(line_number) - 1
                    ]
                )["event"],
                "prompt_manifest",
            )
            self.assertTrue((storage / "view").is_symlink())
            self.assertEqual(citation_path.parent, storage / "view")
            self.assertEqual(
                citation_path.resolve(),
                self.ledger_for(storage, "citation-session").resolve(),
            )


class InstructionEvidenceContractTests(InstructionManifestHookTests):
    """Bind what the hook emits to the contract that describes it."""

    def sources_from(self, storage, session_id):
        event = json.loads(
            self.ledger_for(storage, session_id)
            .read_text(encoding="utf-8")
            .splitlines()[-1]
        )
        return event["sources"]

    def assert_all_conform(self, sources):
        self.assertTrue(sources, "no records were produced to validate")
        for record in sources:
            errors = validate_contracts.validate_record(record)
            self.assertEqual(
                errors, [], f"{record['evidenceType']} record violates contract: {errors}"
            )

    def test_observed_and_declared_records_conform(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            self.run_hook(
                "claude",
                {
                    "hook_event_name": "InstructionsLoaded",
                    "session_id": "contract-session",
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
                    "session_id": "contract-session",
                    "prompt_id": "prompt-1",
                    "cwd": str(REPOSITORY_ROOT),
                },
                storage,
            )
            self.assertEqual(prompted.returncode, 0, prompted.stderr)
            sources = self.sources_from(storage, "contract-session")
            self.assert_all_conform(sources)
            types = {record["evidenceType"] for record in sources}
            self.assertIn("Observed", types)
            self.assertIn("Declared", types)

    def test_codex_baseline_records_conform(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            self.run_hook(
                "codex",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "codex-contract",
                    "turn_id": "turn-1",
                    "cwd": str(REPOSITORY_ROOT),
                },
                storage,
            )
            sources = self.sources_from(storage, "codex-contract")
            self.assert_all_conform(sources)
            self.assertIn(
                "Runtime baseline",
                {record["evidenceType"] for record in sources},
            )

    def test_copilot_baseline_records_conform(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            self.run_hook(
                "copilot",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "copilot-contract",
                    "turn_id": "turn-1",
                    "cwd": str(REPOSITORY_ROOT),
                },
                storage,
            )
            sources = self.sources_from(storage, "copilot-contract")
            self.assert_all_conform(sources)
            self.assertIn(
                "Runtime baseline",
                {record["evidenceType"] for record in sources},
            )

    def test_explicitly_invoked_records_both_invocation_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            self.run_hook(
                "claude",
                {
                    "hook_event_name": "UserPromptExpansion",
                    "session_id": "invoke-session",
                    "prompt_id": "prompt-1",
                    "cwd": str(REPOSITORY_ROOT),
                    "expansion_type": "slash_command",
                    "command_name": SKILL_ID,
                },
                storage,
            )
            self.run_hook(
                "claude",
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "invoke-session",
                    "prompt_id": "prompt-1",
                    "cwd": str(REPOSITORY_ROOT),
                    "tool_name": "Skill",
                    "tool_input": {"skill": "manage-git-workflow"},
                    "tool_use_id": "toolu_skill_01",
                },
                storage,
            )
            self.run_hook(
                "claude",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "invoke-session",
                    "prompt_id": "prompt-1",
                    "cwd": str(REPOSITORY_ROOT),
                },
                storage,
            )
            sources = self.sources_from(storage, "invoke-session")
            self.assert_all_conform(sources)
            invoked = {
                record["instruction"]: record
                for record in sources
                if record["evidenceType"] == "Explicitly invoked"
            }
            self.assertIn(SKILL_FILE, invoked)
            self.assertEqual(
                invoked[SKILL_FILE]["proof"]["invocationKind"], "skill"
            )
            invocation_ids = {
                record["proof"]["invocationId"] for record in invoked.values()
            }
            self.assertEqual(len(invocation_ids), len(invoked))
            self.assertIn("toolu_skill_01", invocation_ids)

    def test_read_during_turn_ignores_non_instruction_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            for file_path, tool_use_id in (
                (INSTRUCTION_FILE, "toolu_read_01"),
                ("platform/agent-control-plane/scripts/validate_contracts.py", "toolu_read_02"),
            ):
                self.run_hook(
                    "claude",
                    {
                        "hook_event_name": "PostToolUse",
                        "session_id": "read-session",
                        "prompt_id": "prompt-1",
                        "cwd": str(REPOSITORY_ROOT),
                        "tool_name": "Read",
                        "tool_input": {"file_path": str(REPOSITORY_ROOT / file_path)},
                        "tool_use_id": tool_use_id,
                    },
                    storage,
                )
            self.run_hook(
                "claude",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "read-session",
                    "prompt_id": "prompt-1",
                    "cwd": str(REPOSITORY_ROOT),
                },
                storage,
            )
            sources = self.sources_from(storage, "read-session")
            self.assert_all_conform(sources)
            read = [
                record
                for record in sources
                if record["evidenceType"] == "Read during turn"
            ]
            self.assertEqual([record["instruction"] for record in read], [INSTRUCTION_FILE])
            self.assertEqual(read[0]["proof"]["toolEventId"], "toolu_read_01")

    def test_declared_yields_to_an_observed_record(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            self.run_hook(
                "claude",
                {
                    "hook_event_name": "InstructionsLoaded",
                    "session_id": "declared-session",
                    "prompt_id": "prompt-1",
                    "cwd": str(REPOSITORY_ROOT),
                    "file_path": str(REPOSITORY_ROOT / INSTRUCTION_FILE),
                },
                storage,
            )
            self.run_hook(
                "claude",
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "declared-session",
                    "prompt_id": "prompt-1",
                    "cwd": str(REPOSITORY_ROOT),
                },
                storage,
            )
            sources = self.sources_from(storage, "declared-session")
            self.assert_all_conform(sources)
            by_instruction = {
                record["instruction"]: record["evidenceType"] for record in sources
            }
            self.assertEqual(by_instruction[INSTRUCTION_FILE], "Observed")
            declared = [
                record for record in sources if record["evidenceType"] == "Declared"
            ]
            self.assertTrue(declared)
            self.assertNotIn(
                INSTRUCTION_FILE, [record["instruction"] for record in declared]
            )

    def test_turn_evidence_survives_the_prompt_it_was_recorded_under(self):
        """A read during turn N must reach turn N+1's manifest.

        Reads and invocations are stamped with the prompt already manifested
        when they happen, so selecting them by the incoming prompt identifier
        strands them permanently. Each turn here uses a distinct prompt_id, as
        a real session does.
        """
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            session = "cross-turn-session"

            # Turn 1 begins: its manifest is written before any tool runs.
            self.run_hook(
                "claude",
                {"hook_event_name": "UserPromptSubmit", "session_id": session,
                 "prompt_id": "prompt-1", "cwd": str(REPOSITORY_ROOT)},
                storage,
            )
            # Turn 1 work: stamped with prompt-1, after prompt-1's manifest.
            self.run_hook(
                "claude",
                {"hook_event_name": "PostToolUse", "session_id": session,
                 "prompt_id": "prompt-1", "cwd": str(REPOSITORY_ROOT),
                 "tool_name": "Read",
                 "tool_input": {"file_path": str(REPOSITORY_ROOT / INSTRUCTION_FILE)},
                 "tool_use_id": "toolu_cross_01"},
                storage,
            )
            self.run_hook(
                "claude",
                {"hook_event_name": "UserPromptExpansion", "session_id": session,
                 "prompt_id": "prompt-1", "cwd": str(REPOSITORY_ROOT),
                 "command_name": SKILL_ID},
                storage,
            )
            # Turn 2 begins under a different prompt identifier.
            self.run_hook(
                "claude",
                {"hook_event_name": "UserPromptSubmit", "session_id": session,
                 "prompt_id": "prompt-2", "cwd": str(REPOSITORY_ROOT)},
                storage,
            )

            sources = self.sources_from(storage, session)
            self.assert_all_conform(sources)
            by_type = {
                record["evidenceType"]: record["instruction"] for record in sources
            }
            self.assertEqual(by_type.get("Read during turn"), INSTRUCTION_FILE)
            self.assertEqual(by_type.get("Explicitly invoked"), SKILL_FILE)

            # Turn 3 must not repeat turn 1's evidence.
            self.run_hook(
                "claude",
                {"hook_event_name": "UserPromptSubmit", "session_id": session,
                 "prompt_id": "prompt-3", "cwd": str(REPOSITORY_ROOT)},
                storage,
            )
            later = {
                record["evidenceType"]
                for record in self.sources_from(storage, session)
            }
            self.assertNotIn("Read during turn", later)
            self.assertNotIn("Explicitly invoked", later)

    def test_citation_line_resolves_to_this_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            for prompt in ("p1", "p2", "p3"):
                self.run_hook(
                    "codex",
                    {"hook_event_name": "UserPromptSubmit", "session_id": "anchor",
                     "turn_id": prompt, "cwd": str(REPOSITORY_ROOT)},
                    storage,
                )
            ledger = self.ledger_for(storage, "anchor")
            lines = ledger.read_text(encoding="utf-8").splitlines()
            event = json.loads(lines[-1])
            href = event["sources"][0]["citation"]["href"]
            _, _, line_number = href.rpartition(":")
            # The anchor points at the manifest carrying this very record.
            self.assertEqual(int(line_number), len(lines))
            self.assertEqual(
                json.loads(lines[int(line_number) - 1])["sources"][0]["recordId"],
                event["sources"][0]["recordId"],
            )

    def test_default_view_citation_is_a_workspace_file_reference(self):
        """The citation must stay inside the workspace to be clickable.

        An absolute path is handed to the external-program handler, which
        requires a URL scheme and rejects a line suffix. Only the default view,
        which resolves inside the repository, exercises this.
        """
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "repo"
            workspace.mkdir()
            for command in (
                ["git", "init", "-q"],
                ["git", "config", "user.email", "test@example.com"],
                ["git", "config", "user.name", "test"],
            ):
                subprocess.run(command, cwd=workspace, check=True, capture_output=True)
            (workspace / "AGENTS.md").write_text("# guidance\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=workspace, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-qm", "init"], cwd=workspace, check=True, capture_output=True
            )

            environment = os.environ.copy()
            environment["AEP_INSTRUCTION_MANIFEST_DIR"] = str(Path(directory) / "store")
            environment.pop("AEP_INSTRUCTION_EVIDENCE_VIEW", None)
            result = subprocess.run(
                ["python3", str(HOOK), "--runtime", "codex"],
                input=json.dumps(
                    {
                        "hook_event_name": "UserPromptSubmit",
                        "session_id": "workspace-session",
                        "turn_id": "t1",
                        "cwd": str(workspace),
                    }
                ),
                text=True,
                capture_output=True,
                check=False,
                cwd=workspace,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

            href = json.loads(
                (Path(directory) / "store").glob("*/workspace-session.jsonl").__next__()
                .read_text(encoding="utf-8")
                .splitlines()[-1]
            )["sources"][0]["citation"]["href"]

            self.assertFalse(href.startswith("/"), f"citation escaped the workspace: {href}")
            self.assertTrue(href.startswith(".local-mirrors/instruction-evidence/"))
            file_part, _, line_number = href.rpartition(":")
            self.assertTrue((workspace / file_part).is_file())
            self.assertGreater(int(line_number), 0)
            # Codex renders an absolute-path markdown link, not a bare reference:
            # Codex has no external-program handler forcing a URL scheme, so the
            # link format restores what Codex used before it was folded into
            # Claude's bare-reference renderer.
            absolute_target = f"{(workspace / file_part).resolve().as_posix()}:{line_number}"
            self.assertIn(f"](<{absolute_target}>)", context)
            self.assertNotIn(f"`{href}`", context)

    def test_every_contract_evidence_type_has_a_producer(self):
        produced = set()
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory)
            session = "coverage-session"
            base = {"session_id": session, "prompt_id": "p1", "cwd": str(REPOSITORY_ROOT)}
            self.run_hook(
                "claude",
                {**base, "hook_event_name": "InstructionsLoaded",
                 "file_path": str(REPOSITORY_ROOT / "AGENTS.md")},
                storage,
            )
            self.run_hook(
                "claude",
                {**base, "hook_event_name": "UserPromptExpansion",
                 "command_name": SKILL_ID},
                storage,
            )
            self.run_hook(
                "claude",
                {**base, "hook_event_name": "PostToolUse", "tool_name": "Read",
                 "tool_input": {"file_path": str(REPOSITORY_ROOT / INSTRUCTION_FILE)},
                 "tool_use_id": "toolu_cov_01"},
                storage,
            )
            self.run_hook(
                "claude", {**base, "hook_event_name": "UserPromptSubmit"}, storage
            )
            claude_sources = self.sources_from(storage, session)
            self.assert_all_conform(claude_sources)
            produced.update(record["evidenceType"] for record in claude_sources)

            self.run_hook(
                "codex",
                {"hook_event_name": "UserPromptSubmit", "session_id": "coverage-codex",
                 "turn_id": "t1", "cwd": str(REPOSITORY_ROOT)},
                storage,
            )
            produced.update(
                record["evidenceType"]
                for record in self.sources_from(storage, "coverage-codex")
            )

        self.assertEqual(produced, set(validate_contracts.evidence_types()))


if __name__ == "__main__":
    unittest.main()
