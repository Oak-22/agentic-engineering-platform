from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest


SCRIPT_PATH = (
    Path(__file__).parents[1] / "scripts" / "verify_hook_registrations.py"
)
SPEC = importlib.util.spec_from_file_location("verify_hook_registrations", SCRIPT_PATH)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = verifier
SPEC.loader.exec_module(verifier)


def load_registry() -> dict:
    return json.loads((verifier.ROOT / verifier.REGISTRY).read_text(encoding="utf-8"))


def errors(findings) -> list[str]:
    return [f.message for f in findings if f.severity == "error"]


def unconfirmed(findings) -> list[str]:
    return [f.message for f in findings if f.severity == "unconfirmed"]


class LiveRegistryTests(unittest.TestCase):
    """The checked-in registry and the checked-in registrations agree."""

    def setUp(self):
        self.registry = load_registry()

    def test_the_repository_state_verifies_clean(self):
        self.assertEqual(errors(verifier.verify(self.registry)), [])

    def test_both_registry_shapes_are_flattened(self):
        """`centralized` legs and the flat `runtime-owned` entry both resolve."""
        flattened = {(leg.hook_id, leg.runtime) for leg in verifier.legs(self.registry)}
        self.assertIn(("instruction-manifest", "claude"), flattened)
        self.assertIn(("artifact-archive", "claude"), flattened)
        self.assertIn(("protect-main-commit", "git"), flattened)

    def test_unverified_legs_are_reported_without_failing(self):
        findings = verifier.verify(self.registry)
        self.assertEqual(errors(findings), [])
        reported = unconfirmed(findings)
        self.assertEqual(len(reported), 2)
        for message in reported:
            self.assertIn("github-copilot", message)
            self.assertIn("verified: false", message)


class MismatchTests(unittest.TestCase):
    """A deliberately introduced mismatch fails; the original passes."""

    def setUp(self):
        self.registry = load_registry()

    def mutate(self, hook_id: str, **changes) -> dict:
        registry = copy.deepcopy(self.registry)
        for hook in registry["hooks"]:
            if hook["id"] == hook_id:
                for entry in hook.get("runtimes", [hook]):
                    entry.update(changes)
        return registry

    def test_a_missing_registration_file_is_named(self):
        registry = self.mutate(
            "provider-docs-session-start", registration=".codex/does-not-exist.json"
        )
        messages = errors(verifier.verify(registry))
        self.assertTrue(any("does not exist" in message for message in messages))
        self.assertTrue(
            any("provider-docs-session-start" in message for message in messages)
        )

    def test_an_undeclared_event_fails_with_the_hook_runtime_and_file(self):
        registry = self.mutate("governed-task-preflight", events=["SessionEnd"])
        messages = errors(verifier.verify(registry))
        self.assertTrue(
            any(
                "governed-task-preflight" in message
                and "SessionEnd" in message
                and ".claude/settings.json" in message
                for message in messages
            ),
            messages,
        )

    def test_a_registration_absent_from_the_registry_is_reported(self):
        """Drift in the other direction: live config the registry omits."""
        registry = copy.deepcopy(self.registry)
        registry["hooks"] = [
            hook for hook in registry["hooks"] if hook["id"] != "artifact-archive"
        ]
        messages = errors(verifier.verify(registry))
        self.assertTrue(
            any(
                "archive_artifact_publish.py" in message
                and "does not declare" in message
                for message in messages
            ),
            messages,
        )

    def test_an_unparseable_registration_is_reported_not_raised(self):
        registry = self.mutate("protect-main-commit", registration="README.md")
        messages = errors(verifier.verify(registry))
        self.assertTrue(messages)


class EventCasingTests(unittest.TestCase):
    def test_event_names_match_across_runtime_casing_conventions(self):
        """Copilot spells the event `userPromptSubmit`; the registry does not."""
        self.assertEqual(
            verifier.normalize_event("UserPromptSubmit"),
            verifier.normalize_event("userPromptSubmit"),
        )


if __name__ == "__main__":
    unittest.main()
