import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "agent_permission_gate.py"
)
SPEC = importlib.util.spec_from_file_location("agent_permission_gate", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


GENERALIST_POLICY = {
    "policyId": "pol_generalist-engineering-agent",
    "statements": [
        {
            "sid": "AllowFeatureBranchPush",
            "effect": "Allow",
            "action": ["git:push"],
            "resource": ["git:agentic-engineering-platform:branch/feature/*"],
            "condition": {"requiresHumanApproval": True},
        },
        {
            "sid": "AllowPrMerge",
            "effect": "Allow",
            "action": ["gh:pr:merge"],
            "resource": ["*"],
            "condition": {"requiresHumanApproval": True},
        },
    ],
}

SPECIALIST_POLICY = {
    "policyId": "pol_architecture-agent",
    "statements": [
        {"sid": "DenyPush", "effect": "Deny", "action": ["git:push"], "resource": ["*"]},
        {"sid": "DenyMerge", "effect": "Deny", "action": ["gh:pr:merge"], "resource": ["*"]},
    ],
}


class RecognizeActionTests(unittest.TestCase):
    def test_none_for_an_unrelated_command(self):
        self.assertIsNone(MODULE.recognize_action("ls -la", Path("/repo")))

    def test_git_push_resolves_to_named_branch(self):
        match = MODULE.recognize_action("git push origin feature/PROJ-1-x", Path("/repo"))
        self.assertEqual(match.action, "git:push")
        self.assertEqual(match.resource, "git:agentic-engineering-platform:branch/feature/PROJ-1-x")

    def test_bare_git_push_falls_back_to_current_branch(self):
        with mock.patch.object(MODULE, "current_branch", return_value="feature/PROJ-2-y"):
            match = MODULE.recognize_action("git push", Path("/repo"))
        self.assertEqual(match.resource, "git:agentic-engineering-platform:branch/feature/PROJ-2-y")

    def test_gh_pr_merge_recognized(self):
        match = MODULE.recognize_action("gh pr merge 46 --squash", Path("/repo"))
        self.assertEqual(match.action, "gh:pr:merge")

    def test_gh_pr_create_recognized(self):
        match = MODULE.recognize_action("gh pr create --draft", Path("/repo"))
        self.assertEqual(match.action, "gh:pr:create")

    def test_branch_delete_recognized_from_git_branch(self):
        match = MODULE.recognize_action("git branch -D fix/PROJ-3-z", Path("/repo"))
        self.assertEqual(match.action, "git:branch:delete")

    def test_branch_delete_recognized_from_push_delete_flag(self):
        match = MODULE.recognize_action("git push origin --delete fix/PROJ-3-z", Path("/repo"))
        self.assertEqual(match.action, "git:branch:delete")

    def test_push_wrapped_in_a_subshell_is_still_recognized(self):
        match = MODULE.recognize_action('bash -c "git push origin feature/PROJ-1-x"', Path("/repo"))
        self.assertEqual(match.action, "git:push")


class GlobalDenyReasonTests(unittest.TestCase):
    def test_none_for_a_plain_push(self):
        with mock.patch.object(MODULE, "current_branch", return_value="feature/x"):
            self.assertIsNone(MODULE.global_deny_reason("git push origin feature/x", Path("/repo")))

    def test_force_push_denied(self):
        reason = MODULE.global_deny_reason("git push --force origin feature/x", Path("/repo"))
        self.assertIsNotNone(reason)
        self.assertIn("global deny", reason)

    def test_force_with_lease_denied(self):
        reason = MODULE.global_deny_reason("git push --force-with-lease origin feature/x", Path("/repo"))
        self.assertIsNotNone(reason)

    def test_short_force_flag_denied(self):
        reason = MODULE.global_deny_reason("git push -f origin feature/x", Path("/repo"))
        self.assertIsNotNone(reason)

    def test_commit_no_verify_denied(self):
        reason = MODULE.global_deny_reason('git commit --no-verify -m "x"', Path("/repo"))
        self.assertIsNotNone(reason)
        self.assertIn("--no-verify", reason)

    def test_commit_on_main_denied(self):
        with mock.patch.object(MODULE, "current_branch", return_value="main"):
            reason = MODULE.global_deny_reason('git commit -m "x"', Path("/repo"))
        self.assertIsNotNone(reason)
        self.assertIn("main", reason)

    def test_commit_on_feature_branch_not_denied(self):
        with mock.patch.object(MODULE, "current_branch", return_value="feature/PROJ-1-x"):
            reason = MODULE.global_deny_reason('git commit -m "x"', Path("/repo"))
        self.assertIsNone(reason)


class ResolveAgentTypeTests(unittest.TestCase):
    def test_defaults_to_generalist_when_absent(self):
        self.assertEqual(MODULE.resolve_agent_type({}), MODULE.DEFAULT_AGENT_TYPE)

    def test_defaults_to_generalist_for_an_unmapped_runtime_subagent_type(self):
        self.assertEqual(
            MODULE.resolve_agent_type({"agent_type": "general-purpose"}),
            MODULE.DEFAULT_AGENT_TYPE,
        )

    def test_resolves_a_mapped_alias(self):
        with mock.patch.dict(MODULE.AGENT_TYPE_ALIASES, {"architecture": "architecture-agent"}):
            self.assertEqual(
                MODULE.resolve_agent_type({"agent_type": "architecture"}),
                "architecture-agent",
            )

    def test_identity_passthrough_for_a_real_translated_specialist(self):
        # AEPI-94: a Claude/Codex/Copilot subagent file whose native identity
        # field is set to a real Agent Registry slug should resolve to that
        # slug directly, with no alias table entry required. Exercises the
        # real permissions directory on disk (AEPI-92), not a mock.
        for slug in (
            "architecture-agent",
            "implementation-agent",
            "evaluation-agent",
            "security-agent",
            "documentation-agent",
            "release-operations-agent",
        ):
            with self.subTest(slug=slug):
                self.assertEqual(MODULE.resolve_agent_type({"agent_type": slug}), slug)

    def test_unrecognized_agent_type_still_defaults_never_default_permits(self):
        self.assertEqual(
            MODULE.resolve_agent_type({"agent_type": "totally-unknown-agent"}),
            MODULE.DEFAULT_AGENT_TYPE,
        )


class EvaluatePolicyTests(unittest.TestCase):
    def test_none_when_no_statement_addresses_the_action(self):
        match = MODULE.ActionMatch("jira:transition", "jira:AEPI:issue/1")
        self.assertIsNone(MODULE.evaluate_policy(GENERALIST_POLICY, match))

    def test_allow_with_approval_condition(self):
        match = MODULE.ActionMatch("git:push", "git:agentic-engineering-platform:branch/feature/x")
        self.assertEqual(MODULE.evaluate_policy(GENERALIST_POLICY, match), "AllowApproval")

    def test_deny_beats_allow_in_the_same_policy(self):
        policy = {
            "statements": [
                {"sid": "A", "effect": "Allow", "action": ["git:push"], "resource": ["*"]},
                {"sid": "B", "effect": "Deny", "action": ["git:push"], "resource": ["*"]},
            ]
        }
        match = MODULE.ActionMatch("git:push", "git:agentic-engineering-platform:branch/feature/x")
        self.assertEqual(MODULE.evaluate_policy(policy, match), "Deny")

    def test_specialist_denies_push_outright(self):
        match = MODULE.ActionMatch("git:push", "git:agentic-engineering-platform:branch/feature/x")
        self.assertEqual(MODULE.evaluate_policy(SPECIALIST_POLICY, match), "Deny")


class HookResponseTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            mock.patch.object(MODULE, "current_branch", return_value="feature/PROJ-1-x"),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_none_for_an_unrelated_command(self):
        result = MODULE.hook_response({"command": "ls -la"}, {}, Path("/repo"), "claude")
        self.assertIsNone(result)

    def test_global_deny_wins_even_over_an_allowing_policy(self):
        # A force push matches git:push, which the generalist policy Allows
        # (with approval) — but the global immutable deny is checked first
        # and no policy statement can override it.
        with mock.patch.object(MODULE, "load_policy", return_value=GENERALIST_POLICY):
            result = MODULE.hook_response(
                {"command": "git push --force origin feature/x"}, {}, Path("/repo"), "claude"
            )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("global deny", result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_omitted_agent_type_resolves_to_generalist_not_silent_allow(self):
        with mock.patch.object(MODULE, "load_policy", return_value=GENERALIST_POLICY) as loader:
            result = MODULE.hook_response(
                {"command": "git push origin feature/x"}, {}, Path("/repo"), "claude"
            )
        loader.assert_called_once_with(MODULE.DEFAULT_AGENT_TYPE)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_specialist_deny_cannot_be_bypassed_by_a_spawned_subagent_event(self):
        with mock.patch.dict(MODULE.AGENT_TYPE_ALIASES, {"architecture": "architecture-agent"}):
            with mock.patch.object(MODULE, "load_policy", return_value=SPECIALIST_POLICY):
                result = MODULE.hook_response(
                    {"command": "git push origin feature/x"},
                    {"agent_id": "sub-1", "agent_type": "architecture"},
                    Path("/repo"),
                    "claude",
                )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_ask_on_claude_becomes_deny_on_codex(self):
        with mock.patch.object(MODULE, "load_policy", return_value=GENERALIST_POLICY):
            claude_result = MODULE.hook_response(
                {"command": "git push origin feature/x"}, {}, Path("/repo"), "claude"
            )
            codex_result = MODULE.hook_response(
                {"command": "git push origin feature/x"}, {}, Path("/repo"), "codex"
            )
        self.assertEqual(claude_result["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertEqual(codex_result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("human approval", codex_result["hookSpecificOutput"]["permissionDecisionReason"])

    def test_no_policy_for_the_principal_falls_through_silently(self):
        with mock.patch.object(MODULE, "load_policy", return_value=None):
            result = MODULE.hook_response(
                {"command": "git push origin feature/x"}, {}, Path("/repo"), "claude"
            )
        self.assertIsNone(result)


class HostilePathMatrixTests(unittest.TestCase):
    """The same principal's decision must not depend on how the action was invoked."""

    def setUp(self):
        self.patches = [
            mock.patch.object(MODULE, "current_branch", return_value="feature/PROJ-1-x"),
            mock.patch.object(MODULE, "load_policy", return_value=GENERALIST_POLICY),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def _decision(self, command: str, event: dict | None = None) -> str:
        result = MODULE.hook_response({"command": command}, event or {}, Path("/repo"), "claude")
        return result["hookSpecificOutput"]["permissionDecision"] if result else None

    def test_direct_push_and_subshell_wrapped_push_match(self):
        direct = self._decision("git push origin feature/x")
        subshell = self._decision('bash -c "git push origin feature/x"')
        self.assertEqual(direct, subshell)
        self.assertEqual(direct, "ask")

    def test_direct_push_and_subagent_issued_push_match_for_the_same_principal(self):
        direct = self._decision("git push origin feature/x")
        via_subagent = self._decision(
            "git push origin feature/x", {"agent_id": "sub-1", "agent_type": "unmapped-type"}
        )
        self.assertEqual(direct, via_subagent)


class CopilotOutputShapeTests(unittest.TestCase):
    """AEPI-94: Copilot's hook response is unwrapped, unlike Claude/Codex."""

    def setUp(self):
        self.patches = [
            mock.patch.object(MODULE, "current_branch", return_value="feature/PROJ-1-x"),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_deny_has_no_hookSpecificOutput_wrapper(self):
        result = MODULE.deny_decision("some reason", "copilot")
        self.assertNotIn("hookSpecificOutput", result)
        self.assertEqual(result["permissionDecision"], "deny")
        self.assertEqual(result["permissionDecisionReason"], "some reason")

    def test_ask_has_no_hookSpecificOutput_wrapper(self):
        result = MODULE.ask_decision("some reason", "copilot")
        self.assertNotIn("hookSpecificOutput", result)
        self.assertEqual(result["permissionDecision"], "ask")

    def test_claude_and_codex_keep_the_wrapper(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                result = MODULE.deny_decision("some reason", runtime)
                self.assertIn("hookSpecificOutput", result)
                self.assertEqual(
                    result["hookSpecificOutput"]["permissionDecision"], "deny"
                )

    def test_copilot_gets_ask_not_a_preemptive_deny(self):
        # Unlike Codex (ask fails open, so this gate substitutes deny),
        # Copilot's own runtime downgrades ask to deny itself when no human
        # is available — this gate does not need to pre-empt it.
        with mock.patch.object(MODULE, "load_policy", return_value=GENERALIST_POLICY):
            result = MODULE.hook_response(
                {"command": "git push origin feature/x"}, {}, Path("/repo"), "copilot"
            )
        self.assertEqual(result["permissionDecision"], "ask")
        self.assertNotIn("hookSpecificOutput", result)

    def test_run_as_hook_skips_the_bash_tool_name_filter_for_copilot(self):
        payload = json.dumps(
            {"tool_name": "shell", "tool_input": {"command": "git push --force origin feature/x"}}
        )
        with mock.patch.object(MODULE, "repository_root", return_value=Path("/repo")):
            with mock.patch("builtins.print") as printed:
                MODULE.run_as_hook(payload, Path("/repo"), "copilot")
        printed.assert_called_once()
        emitted = json.loads(printed.call_args[0][0])
        self.assertNotIn("hookSpecificOutput", emitted)
        self.assertEqual(emitted["permissionDecision"], "deny")

    def test_run_as_hook_still_filters_by_tool_name_for_claude(self):
        payload = json.dumps(
            {"tool_name": "Read", "tool_input": {"command": "git push --force origin feature/x"}}
        )
        with mock.patch("builtins.print") as printed:
            MODULE.run_as_hook(payload, Path("/repo"), "claude")
        printed.assert_not_called()


class RunAsHookTests(unittest.TestCase):
    def test_silent_on_malformed_stdin(self):
        with mock.patch("builtins.print") as printed:
            exit_code = MODULE.run_as_hook("not json", Path("/repo"), "claude")
        printed.assert_not_called()
        self.assertEqual(exit_code, 0)

    def test_silent_for_a_non_bash_tool(self):
        payload = json.dumps({"tool_name": "Read", "tool_input": {}})
        with mock.patch("builtins.print") as printed:
            exit_code = MODULE.run_as_hook(payload, Path("/repo"), "claude")
        printed.assert_not_called()
        self.assertEqual(exit_code, 0)

    def test_silent_outside_a_git_worktree(self):
        payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "git push origin feature/x"}}
        )
        with mock.patch.object(MODULE, "repository_root", return_value=None):
            with mock.patch("builtins.print") as printed:
                exit_code = MODULE.run_as_hook(payload, Path("/elsewhere"), "claude")
        printed.assert_not_called()
        self.assertEqual(exit_code, 0)

    def test_prints_deny_json_for_a_force_push(self):
        payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "git push --force origin feature/x"}}
        )
        with mock.patch.object(MODULE, "repository_root", return_value=Path("/repo")):
            with mock.patch("builtins.print") as printed:
                exit_code = MODULE.run_as_hook(payload, Path("/repo"), "claude")
        self.assertEqual(exit_code, 0)
        printed.assert_called_once()
        emitted = json.loads(printed.call_args[0][0])
        self.assertEqual(emitted["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
