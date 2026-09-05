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

REAL_GENERALIST_POLICY = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "agent-assets"
        / "execution-policies"
        / "permissions"
        / "generalist-engineering-agent.policy.json"
    ).read_text()
)


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
            "action": [
                "github:pull_request:merge",
                "github:pull_request:create",
                "github:pull_request:update",
                "github:pull_request:review",
            ],
            "resource": ["github:*"] ,
            "condition": {"requiresHumanApproval": True},
        },
        {
            "sid": "AllowJiraMutation",
            "effect": "Allow",
            "action": [
                "jira:issue:create",
                "jira:issue:update",
                "jira:issue:transition",
                "jira:issue:link",
            ],
            "resource": ["jira:*"] ,
            "condition": {"requiresHumanApproval": True},
        },
    ],
}

RESTRICTIVE_POLICY = {
    "policyId": "pol_restrictive-principal",
    "statements": [
        {"sid": "DenyPush", "effect": "Deny", "action": ["git:push"], "resource": ["*"]},
        {
            "sid": "DenyMerge",
            "effect": "Deny",
            "action": [
                "github:pull_request:merge",
                "github:pull_request:create",
                "github:pull_request:update",
                "github:pull_request:review",
            ],
            "resource": ["*"],
        },
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
        self.assertEqual(match.action, "github:pull_request:merge")
        self.assertEqual(match.resource, "github:agentic-engineering-platform:*")

    def test_gh_pr_create_recognized(self):
        match = MODULE.recognize_action("gh pr create --draft", Path("/repo"))
        self.assertEqual(match.action, "github:pull_request:create")

    def test_gh_pr_create_without_draft_is_human_only(self):
        match = MODULE.recognize_action("gh pr create", Path("/repo"))
        self.assertEqual(match.action, "github:pull_request:create-ready")

    def test_governed_publisher_execute_is_distinct_from_direct_push(self):
        with mock.patch.object(
            MODULE, "current_branch", return_value="feature/AEPI-200-safe-publish"
        ):
            match = MODULE.recognize_action(
                "python3 platform/agent-control-plane/scripts/publish_delivery_branch.py --execute",
                Path("/repo"),
            )
        self.assertEqual(match.action, "git:delivery:publish")

    def test_publisher_dry_run_is_not_a_mutation(self):
        match = MODULE.recognize_action(
            "python3 platform/agent-control-plane/scripts/publish_delivery_branch.py",
            Path("/repo"),
        )
        self.assertIsNone(match)

    def test_targeted_cleanup_is_distinct_from_direct_branch_delete(self):
        with mock.patch.object(
            MODULE, "current_branch", return_value="feature/AEPI-200-safe-publish"
        ):
            match = MODULE.recognize_action(
                "python3 .agents/skills/manage-git-workflow/scripts/"
                "delivery_cleanup.py pr --pr 80 --execute",
                Path("/repo"),
            )
        self.assertEqual(match.action, "git:delivery:cleanup")
        self.assertEqual(
            match.resource,
            "git:agentic-engineering-platform:delivery/merged-pr",
        )

    def test_compound_publisher_command_cannot_hide_an_arbitrary_push(self):
        with mock.patch.object(
            MODULE, "current_branch", return_value="feature/AEPI-200-safe-publish"
        ):
            match = MODULE.recognize_action(
                "python3 platform/agent-control-plane/scripts/"
                "publish_delivery_branch.py --execute; git push origin other",
                Path("/repo"),
            )
        self.assertEqual(match.action, "git:push")

    def test_github_mcp_create_uses_the_same_semantic_action(self):
        match = MODULE.recognize_mcp_action(
            "mcp__github__create_pull_request",
            {"owner": "Oak-22", "repo": "agentic-engineering-platform", "draft": True},
        )
        self.assertEqual(match.action, "github:pull_request:create")
        self.assertEqual(match.resource, "github:Oak-22/agentic-engineering-platform:*")

    def test_github_review_methods_have_narrow_actions(self):
        cases = (
            ({"method": "resolve_thread"}, "github:pull_request:review-thread:resolve"),
            ({"method": "unresolve_thread"}, "github:pull_request:review-thread:unresolve"),
            ({"method": "submit_pending", "event": "APPROVE"}, "github:pull_request:approve"),
            (
                {"method": "submit_pending", "event": "REQUEST_CHANGES"},
                "github:pull_request:request-changes",
            ),
        )
        for tool_input, expected in cases:
            with self.subTest(expected=expected):
                match = MODULE.recognize_mcp_action(
                    "mcp__github__pull_request_review_write", tool_input
                )
                self.assertEqual(match.action, expected)

    def test_github_update_separates_ready_from_human_only_changes(self):
        cases = (
            ({"draft": False}, "github:pull_request:ready"),
            ({"base": "other"}, "github:pull_request:retarget"),
            ({"state": "closed"}, "github:pull_request:close"),
            ({"reviewers": ["person"]}, "github:pull_request:reviewer:update"),
        )
        for tool_input, expected in cases:
            with self.subTest(expected=expected):
                match = MODULE.recognize_mcp_action(
                    "mcp__github__update_pull_request", tool_input
                )
                self.assertEqual(match.action, expected)

    def test_copilot_review_and_thread_reply_are_recognized(self):
        for tool, expected in (
            (
                "mcp__github__request_copilot_review",
                "github:pull_request:copilot-review:request",
            ),
            (
                "mcp__github__add_reply_to_pull_request_comment",
                "github:pull_request:review-thread:reply",
            ),
        ):
            with self.subTest(tool=tool):
                self.assertEqual(MODULE.recognize_mcp_action(tool, {}).action, expected)

    def test_non_destination_mcp_tool_is_not_recognized(self):
        self.assertIsNone(MODULE.recognize_mcp_action("mcp__other__write", {}))

    def test_destination_reads_are_classified_as_reads(self):
        for tool, action in (
            ("mcp__github__pull_request_read", "github:tool:read"),
            ("mcp__github__get_file_contents", "github:tool:read"),
            ("mcp__codex_apps__atlassian_rovo_getjiraissue", "jira:tool:read"),
            # The two reads AEPI-131 lost to the old name allowlist.
            ("mcp__atlassian__getTransitionsForJiraIssue", "jira:tool:read"),
            ("mcp__atlassian__getJiraIssueTypeMetaWithFields", "jira:tool:read"),
            ("mcp__atlassian__getConfluencePage", "confluence:tool:read"),
            ("mcp__atlassian__search", "atlassian:tool:read"),
        ):
            with self.subTest(tool=tool):
                self.assertEqual(MODULE.recognize_mcp_action(tool, {}).action, action)

    def test_unknown_destination_tools_pass_without_an_opinion(self):
        # AEPI-132 inverted this: an unmapped destination tool is usable
        # without a gate change, so a connected server can add or rename one.
        for tool in (
            "mcp__github__new_write_tool",
            "mcp__atlassian__newJiraMutation",
        ):
            with self.subTest(tool=tool):
                self.assertIsNone(MODULE.recognize_mcp_action(tool, {}))

    def test_confluence_writes_are_classified_rather_than_invisible(self):
        match = MODULE.recognize_mcp_action(
            "mcp__atlassian__updateConfluencePage", {"spaceKey": "AEP", "pageId": "42"}
        )
        self.assertEqual(match.action, "confluence:page:update")
        self.assertEqual(match.resource, "confluence:AEP:page/42")

    def test_jira_comment_is_a_named_mutation(self):
        match = MODULE.recognize_mcp_action(
            "mcp__atlassian__addCommentToJiraIssue", {"issueIdOrKey": "AEPI-132"}
        )
        self.assertEqual(match.action, "jira:issue:comment")
        self.assertEqual(match.resource, "jira:*:issue/AEPI-132")

    def test_remote_content_writes_bypassing_publication_are_named(self):
        for tool, action in (
            ("mcp__github__create_or_update_file", "github:repository:content:write"),
            ("mcp__github__push_files", "github:repository:content:write"),
            ("mcp__github__delete_file", "github:repository:content:delete"),
            ("mcp__github__create_branch", "github:branch:create"),
            ("mcp__github__delete_repository", "github:repository:delete"),
        ):
            with self.subTest(tool=tool):
                self.assertEqual(MODULE.recognize_mcp_action(tool, {}).action, action)

    def test_jira_mcp_transition_uses_a_jira_resource(self):
        match = MODULE.recognize_mcp_action(
            "mcp__codex_apps__atlassian_rovo_transitionjiraissue",
            {"issueIdOrKey": "AEPI-119"},
        )
        self.assertEqual(match.action, "jira:issue:transition")
        self.assertEqual(match.resource, "jira:*:issue/AEPI-119")

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

    def test_every_runtime_subagent_identity_resolves_to_the_one_policy(self):
        # AEPI-132: the six specialist principals are gone, so a runtime's
        # built-in fallback identity, a former specialist slug, and a custom
        # name all resolve to the single generalist policy. Exercises the
        # real permissions directory on disk, not a mock.
        for identity in (
            "general-purpose",
            "Explore",
            "default",
            "architecture-agent",
            "security-agent",
            "some-custom-subagent",
        ):
            with self.subTest(identity=identity):
                self.assertEqual(
                    MODULE.resolve_agent_type({"agent_type": identity}),
                    MODULE.DEFAULT_AGENT_TYPE,
                )

    def test_identity_passthrough_when_a_policy_document_exists(self):
        self.assertEqual(
            MODULE.resolve_agent_type({"agent_type": "generalist-engineering-agent"}),
            "generalist-engineering-agent",
        )

    def test_exactly_one_policy_document_ships(self):
        self.assertEqual(
            sorted(path.name for path in MODULE.PERMISSIONS_DIR.glob("*.policy.json")),
            ["generalist-engineering-agent.policy.json"],
        )

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

    def test_restrictive_policy_denies_push_outright(self):
        match = MODULE.ActionMatch("git:push", "git:agentic-engineering-platform:branch/feature/x")
        self.assertEqual(MODULE.evaluate_policy(RESTRICTIVE_POLICY, match), "Deny")

    def test_restrictive_policy_denies_github_mcp_write(self):
        match = MODULE.ActionMatch(
            "github:pull_request:create", "github:Oak-22/agentic-engineering-platform:*"
        )
        self.assertEqual(MODULE.evaluate_policy(RESTRICTIVE_POLICY, match), "Deny")

    def test_real_generalist_policy_allows_governed_delivery_without_approval(self):
        for action in (
            "git:delivery:publish",
            "github:pull_request:create",
            "github:pull_request:sync",
            "github:pull_request:ready",
            "github:pull_request:review-thread:reply",
            "github:pull_request:review-thread:resolve",
            "jira:issue:transition",
        ):
            resource = (
                "jira:*:issue/AEPI-200"
                if action.startswith("jira:")
                else "git:agentic-engineering-platform:delivery/merged-pr"
                if action == "git:delivery:cleanup"
                else "git:agentic-engineering-platform:branch/feature/AEPI-200-x"
                if action.startswith("git:")
                else "github:Oak-22/agentic-engineering-platform:*"
            )
            with self.subTest(action=action):
                self.assertEqual(
                    MODULE.evaluate_policy(
                        REAL_GENERALIST_POLICY, MODULE.ActionMatch(action, resource)
                    ),
                    "Allow",
                )

    def test_real_generalist_policy_denies_human_acceptance_actions(self):
        for action in (
            "github:pull_request:merge",
            "github:pull_request:create-ready",
            "github:pull_request:approve",
            "github:pull_request:request-changes",
            "github:pull_request:close",
            "github:pull_request:retarget",
            "github:pull_request:review-thread:unresolve",
        ):
            with self.subTest(action=action):
                self.assertEqual(
                    MODULE.evaluate_policy(
                        REAL_GENERALIST_POLICY,
                        MODULE.ActionMatch(
                            action, "github:Oak-22/agentic-engineering-platform:*"
                        ),
                    ),
                    "Deny",
                )

    def test_real_generalist_policy_keeps_direct_push_approval_gated(self):
        match = MODULE.ActionMatch(
            "git:push",
            "git:agentic-engineering-platform:branch/feature/AEPI-200-x",
        )
        self.assertEqual(
            MODULE.evaluate_policy(REAL_GENERALIST_POLICY, match), "AllowApproval"
        )

    def test_real_generalist_policy_allows_destination_reads_outright(self):
        for action, resource in (
            ("github:tool:read", "github:*"),
            ("jira:tool:read", "jira:*"),
            ("confluence:tool:read", "confluence:*"),
            ("atlassian:tool:read", "atlassian:*"),
        ):
            with self.subTest(action=action):
                self.assertEqual(
                    MODULE.evaluate_policy(
                        REAL_GENERALIST_POLICY, MODULE.ActionMatch(action, resource)
                    ),
                    "Allow",
                )

    def test_real_generalist_policy_gates_confluence_and_content_writes(self):
        for action, resource in (
            ("confluence:page:create", "confluence:AEP:page/*"),
            ("confluence:page:update", "confluence:AEP:page/1"),
            ("github:repository:content:write", "github:agentic-engineering-platform:*"),
            ("github:repository:content:delete", "github:agentic-engineering-platform:*"),
            ("github:branch:create", "github:agentic-engineering-platform:*"),
        ):
            with self.subTest(action=action):
                self.assertEqual(
                    MODULE.evaluate_policy(
                        REAL_GENERALIST_POLICY, MODULE.ActionMatch(action, resource)
                    ),
                    "AllowApproval",
                )

    def test_real_generalist_policy_denies_repository_deletion(self):
        self.assertEqual(
            MODULE.evaluate_policy(
                REAL_GENERALIST_POLICY,
                MODULE.ActionMatch("github:repository:delete", "github:*"),
            ),
            "Deny",
        )

    def test_a_deny_survives_a_broader_allow_over_the_same_action(self):
        # The inversion widens what "not denied" covers, so deny-overrides has
        # to hold even when an Allow statement is written broadly enough to
        # reach a human-acceptance action.
        policy = {
            "policyId": "pol_broad-allow",
            "statements": [
                {
                    "sid": "AllowEverythingOnThisRepository",
                    "effect": "Allow",
                    "action": [
                        "github:pull_request:merge",
                        "github:pull_request:approve",
                        "github:tool:read",
                    ],
                    "resource": ["*"],
                    "condition": {"requiresHumanApproval": False},
                },
                {
                    "sid": "DenyHumanAcceptanceActions",
                    "effect": "Deny",
                    "action": [
                        "github:pull_request:merge",
                        "github:pull_request:approve",
                    ],
                    "resource": ["*"],
                },
            ],
        }
        for action in ("github:pull_request:merge", "github:pull_request:approve"):
            with self.subTest(action=action):
                self.assertEqual(
                    MODULE.evaluate_policy(policy, MODULE.ActionMatch(action, "github:*")),
                    "Deny",
                )
        self.assertEqual(
            MODULE.evaluate_policy(
                policy, MODULE.ActionMatch("github:tool:read", "github:*")
            ),
            "Allow",
        )


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

    def test_a_spawned_subagent_event_gets_the_same_principal_decision(self):
        with mock.patch.object(MODULE, "load_policy", return_value=RESTRICTIVE_POLICY):
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

    def test_github_mcp_write_uses_human_approval_for_generalist(self):
        with mock.patch.object(MODULE, "load_policy", return_value=GENERALIST_POLICY):
            result = MODULE.hook_response(
                {"owner": "Oak-22", "repo": "agentic-engineering-platform", "draft": True},
                {},
                Path("/repo"),
                "claude",
                "mcp__github__create_pull_request",
            )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_github_mcp_write_is_denied_by_a_restrictive_policy(self):
        with mock.patch.object(MODULE, "load_policy", return_value=RESTRICTIVE_POLICY):
            result = MODULE.hook_response(
                {"owner": "Oak-22", "repo": "agentic-engineering-platform", "draft": True},
                {"agent_type": "architecture-agent"},
                Path("/repo"),
                "claude",
                "mcp__github__create_pull_request",
            )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_jira_mcp_write_uses_human_approval_for_generalist(self):
        with mock.patch.object(MODULE, "load_policy", return_value=GENERALIST_POLICY):
            result = MODULE.hook_response(
                {"projectKey": "AEPI"},
                {},
                Path("/repo"),
                "claude",
                "mcp__codex_apps__atlassian_rovo_createjiraissue",
            )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_real_generalist_governed_publish_and_pr_create_emit_an_allow(self):
        with mock.patch.object(MODULE, "load_policy", return_value=REAL_GENERALIST_POLICY):
            publish = MODULE.hook_response(
                {
                    "command": "python3 platform/agent-control-plane/scripts/"
                    "publish_delivery_branch.py --execute"
                },
                {},
                Path("/repo"),
                "codex",
            )
            create = MODULE.hook_response(
                {"owner": "Oak-22", "repo": "agentic-engineering-platform", "draft": True},
                {},
                Path("/repo"),
                "codex",
                "mcp__github__create_pull_request",
            )
        # AEPI-132: an Allow verdict now emits an affirmative allow instead
        # of no opinion, so the runtime skips its own permission prompt.
        for result in (publish, create):
            self.assertEqual(
                result["hookSpecificOutput"]["permissionDecision"], "allow"
            )

    def test_real_generalist_merge_is_denied_for_every_runtime(self):
        with mock.patch.object(MODULE, "load_policy", return_value=REAL_GENERALIST_POLICY):
            for runtime in ("claude", "codex", "copilot"):
                with self.subTest(runtime=runtime):
                    result = MODULE.hook_response(
                        {"owner": "Oak-22", "repo": "agentic-engineering-platform"},
                        {},
                        Path("/repo"),
                        runtime,
                        "mcp__github__merge_pull_request",
                    )
                    payload = result if runtime == "copilot" else result["hookSpecificOutput"]
                    self.assertEqual(payload["permissionDecision"], "deny")


class GovernedDeliveryUnderTheRealPolicyTests(unittest.TestCase):
    """AEPI-132 acceptance: what an ordinary governed delivery actually sees."""

    def setUp(self):
        patcher = mock.patch.object(
            MODULE, "load_policy", return_value=REAL_GENERALIST_POLICY
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        branch = mock.patch.object(
            MODULE, "current_branch", return_value="refactor/AEPI-132-x"
        )
        branch.start()
        self.addCleanup(branch.stop)

    def decide(self, tool_input, tool_name="Bash", runtime="claude"):
        result = MODULE.hook_response(tool_input, {}, Path("/repo"), runtime, tool_name)
        if result is None:
            return None
        return result if runtime == "copilot" else result["hookSpecificOutput"]

    def test_the_reads_aepi_131_lost_now_succeed_without_a_prompt(self):
        for tool in (
            "mcp__atlassian__getTransitionsForJiraIssue",
            "mcp__atlassian__getJiraIssueTypeMetaWithFields",
            "mcp__github__pull_request_read",
        ):
            with self.subTest(tool=tool):
                decision = self.decide({"issueIdOrKey": "AEPI-132"}, tool)
                self.assertEqual(decision["permissionDecision"], "allow")

    def test_writing_the_delivery_record_to_the_issue_now_succeeds(self):
        decision = self.decide(
            {"issueIdOrKey": "AEPI-132"}, "mcp__atlassian__addCommentToJiraIssue"
        )
        self.assertEqual(decision["permissionDecision"], "allow")

    def test_confluence_write_is_gated_rather_than_ungoverned(self):
        decision = self.decide({"pageId": "42"}, "mcp__atlassian__updateConfluencePage")
        self.assertEqual(decision["permissionDecision"], "ask")
        self.assertIn("confluence:page:update", decision["permissionDecisionReason"])

    def test_human_acceptance_actions_stay_denied(self):
        approve = {"method": "submit_pending", "event": "APPROVE"}
        request_changes = {"method": "submit_pending", "event": "REQUEST_CHANGES"}
        for tool_input, tool in (
            ({}, "mcp__github__merge_pull_request"),
            (approve, "mcp__github__pull_request_review_write"),
            (request_changes, "mcp__github__pull_request_review_write"),
            ({"state": "closed"}, "mcp__github__update_pull_request"),
            ({"state": "open"}, "mcp__github__update_pull_request"),
            ({"base": "release"}, "mcp__github__update_pull_request"),
            ({"draft": False}, "mcp__github__create_pull_request"),
        ):
            with self.subTest(tool=tool, tool_input=tool_input):
                decision = self.decide(tool_input, tool)
                self.assertEqual(decision["permissionDecision"], "deny")

    def test_shell_equivalents_of_those_actions_stay_denied(self):
        for command in (
            "gh pr merge 82",
            "gh pr review 82 --approve",
            "gh pr review 82 --request-changes",
            "gh pr close 82",
            "gh pr edit 82 --base release",
        ):
            with self.subTest(command=command):
                decision = self.decide({"command": command})
                self.assertEqual(decision["permissionDecision"], "deny")

    def test_history_rewriting_push_stays_globally_denied(self):
        rewriting = "git " + "push"
        for flag in ("--force", "--force-with-lease", "-f"):
            command = f"{rewriting} {flag} origin refactor/AEPI-132-x"
            with self.subTest(command=command):
                decision = self.decide({"command": command})
                self.assertEqual(decision["permissionDecision"], "deny")

    def test_branch_delete_and_direct_push_stay_human_gated(self):
        for command in (
            "git branch -D refactor/AEPI-132-x",
            "git " + "push origin refactor/AEPI-132-x",
        ):
            with self.subTest(command=command):
                decision = self.decide({"command": command})
                self.assertEqual(decision["permissionDecision"], "ask")

    def test_every_remaining_prompt_names_the_statement_that_caused_it(self):
        for tool_input, tool in (
            ({"command": "git " + "push origin refactor/AEPI-132-x"}, "Bash"),
            ({"command": "git branch -D refactor/AEPI-132-x"}, "Bash"),
            ({"pageId": "42"}, "mcp__atlassian__updateConfluencePage"),
            ({}, "mcp__github__push_files"),
        ):
            with self.subTest(tool=tool):
                decision = self.decide(tool_input, tool)
                self.assertEqual(decision["permissionDecision"], "ask")
                self.assertIn(
                    "requires human approval", decision["permissionDecisionReason"]
                )
                self.assertIn(
                    REAL_GENERALIST_POLICY["policyId"],
                    decision["permissionDecisionReason"],
                )

    def test_the_governed_delivery_path_never_prompts(self):
        publish = (
            "python3 platform/agent-control-plane/scripts/"
            "publish_delivery_branch.py --execute"
        )
        repository = {"owner": "Oak-22", "repo": "agentic-engineering-platform"}
        for tool_input, tool in (
            ({"command": publish}, "Bash"),
            ({**repository, "draft": True}, "mcp__github__create_pull_request"),
            ({**repository, "draft": False}, "mcp__github__update_pull_request"),
            ({"issueIdOrKey": "AEPI-132"}, "mcp__atlassian__transitionJiraIssue"),
            ({"issueIdOrKey": "AEPI-132"}, "mcp__atlassian__addCommentToJiraIssue"),
            ({"issueIdOrKey": "AEPI-132"}, "mcp__atlassian__getJiraIssue"),
        ):
            with self.subTest(tool=tool):
                decision = self.decide(tool_input, tool)
                self.assertEqual(decision["permissionDecision"], "allow")

    def test_a_call_the_gate_does_not_recognize_is_left_to_the_runtime(self):
        # Not an allow: the gate stays silent so the runtime's own permission
        # flow, and the committed `permissions.allow` list, decide.
        self.assertIsNone(self.decide({"command": "git status --short"}))
        self.assertIsNone(self.decide({}, "mcp__github__brand_new_tool"))


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

    def test_run_as_hook_gates_a_github_mcp_tool(self):
        payload = json.dumps(
            {
                "tool_name": "mcp__github__create_pull_request",
                "tool_input": {
                    "owner": "Oak-22",
                    "repo": "agentic-engineering-platform",
                    "draft": True,
                },
            }
        )
        with mock.patch.object(MODULE, "repository_root", return_value=Path("/repo")):
            with mock.patch.object(MODULE, "load_policy", return_value=GENERALIST_POLICY):
                with mock.patch("builtins.print") as printed:
                    MODULE.run_as_hook(payload, Path("/repo"), "claude")
        printed.assert_called_once()
        emitted = json.loads(printed.call_args[0][0])
        self.assertEqual(emitted["hookSpecificOutput"]["permissionDecision"], "ask")


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
