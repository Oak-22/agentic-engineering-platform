from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import sys
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[3]
CONTROL_PLANE = ROOT / "platform" / "agent-control-plane"
SCRIPT_PATH = CONTROL_PLANE / "scripts" / "validate_contracts.py"
SPEC = importlib.util.spec_from_file_location("validate_contracts_for_destinations", SCRIPT_PATH)
assert SPEC and SPEC.loader
contracts = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contracts
SPEC.loader.exec_module(contracts)

GATE_PATH = CONTROL_PLANE / "scripts" / "agent_permission_gate.py"
GATE_SPEC = importlib.util.spec_from_file_location("agent_permission_gate_for_destinations", GATE_PATH)
assert GATE_SPEC and GATE_SPEC.loader
permission_gate = importlib.util.module_from_spec(GATE_SPEC)
sys.modules[GATE_SPEC.name] = permission_gate
GATE_SPEC.loader.exec_module(permission_gate)

INCIDENT_DOC = "docs/operations/incidents/atlassian-mcp-oauth-refresh-token-invalid-2026-07-24.md"

# Obvious committed-secret shapes: a real GitHub token, or an inline bearer /
# password assignment. `${VAR}` references and bare variable names are fine.
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}"),
    re.compile(r"(?i)(password|secret|token)\s*[:=]\s*['\"][^'\"$][^'\"]{7,}['\"]"),
)
MACHINE_PATH_PATTERN = re.compile(r"(?:/Users/|/home/)[A-Za-z0-9._-]+/")


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class DestinationContractTests(unittest.TestCase):
    def assert_valid(self, schema_name: str, instance: dict) -> None:
        errors = list(contracts.validator_for(schema_name).iter_errors(instance))
        self.assertEqual(errors, [], [error.message for error in errors])

    def test_destination_mappings_validate_against_their_contracts(self):
        self.assert_valid(
            "github-delivery/github-delivery-mapping.schema.json",
            load_json("platform/agent-control-plane/adapters/github/github-delivery-mapping.json"),
        )
        self.assert_valid(
            "jira-delivery/jira-delivery-mapping.schema.json",
            load_json("platform/agent-control-plane/adapters/jira/jira-delivery-mapping.json"),
        )

    def test_aepi_jira_field_mapping_validates_against_the_adapter_schema(self):
        schema = load_json(
            "platform/agent-control-plane/adapters/jira/jira-field-mapping.schema.json"
        )
        import jsonschema

        validator_class = jsonschema.validators.validator_for(schema)
        validator_class.check_schema(schema)
        errors = list(
            validator_class(schema).iter_errors(
                load_json(
                    "platform/agent-control-plane/adapters/jira/aepi-field-mapping.json"
                )
            )
        )
        self.assertEqual(errors, [], [error.message for error in errors])

    def test_all_permission_policy_instances_match_the_current_schema(self):
        validator = contracts.validator_for("agent-permission-policy.schema.json")
        policy_dir = CONTROL_PLANE / "agent-assets" / "execution-policies" / "permissions"
        for path in sorted(policy_dir.glob("*.policy.json")):
            with self.subTest(path=path.name):
                errors = list(validator.iter_errors(json.loads(path.read_text())))
                self.assertEqual(errors, [], [error.message for error in errors])

    def test_operation_and_result_contracts_validate_traceable_examples(self):
        self.assert_valid(
            "github-delivery/github-delivery-operation.schema.json",
            {
                "schemaVersion": 1,
                "operation": "pull-request-read",
                "repository": {"owner": "Oak-22", "name": "agentic-engineering-platform"},
                "pullRequestNumber": 69,
            },
        )
        self.assert_valid(
            "github-delivery/github-delivery-result.schema.json",
            {
                "schemaVersion": 1,
                "operation": "pull-request-read",
                "outcome": "succeeded",
                "repository": {"owner": "Oak-22", "name": "agentic-engineering-platform"},
                "nativeUrl": "https://github.com/Oak-22/agentic-engineering-platform/pull/69",
                "pullRequestNumber": 69,
                "commitShas": ["906067e"],
            },
        )
        self.assert_valid(
            "jira-delivery/jira-delivery-result.schema.json",
            {
                "schemaVersion": 1,
                "operation": "work-item-read",
                "outcome": "succeeded",
                "projectKey": "AEPI",
                "issueKey": "AEPI-119",
                "nativeUrl": "https://buccatjulian.atlassian.net/browse/AEPI-119",
                "statusName": "To Do",
            },
        )


GITHUB_MCP_ENDPOINT = "https://api.githubcopilot.com/mcp/"


class RuntimeConfigurationParityTests(unittest.TestCase):
    def test_codex_and_claude_use_the_same_hosted_github_oauth_endpoint(self):
        """ADR-0004: both runtimes reach GitHub through the one hosted server
        over OAuth. Transport is now uniform; no PAT sits in either config."""
        claude = load_json(".mcp.json")["mcpServers"]["github"]
        with (ROOT / ".codex" / "config.toml").open("rb") as handle:
            codex = tomllib.load(handle)["mcp_servers"]["github"]

        self.assertEqual(claude["type"], "http")
        self.assertEqual(claude["url"], GITHUB_MCP_ENDPOINT)
        self.assertEqual(codex["url"], GITHUB_MCP_ENDPOINT)
        self.assertNotIn("command", claude)
        self.assertNotIn("command", codex)
        self.assertNotIn("env", claude)
        self.assertNotIn("env_vars", codex)

        mapping = load_json(
            "platform/agent-control-plane/adapters/github/github-delivery-mapping.json"
        )
        primary = mapping["providers"][mapping["primaryProvider"]]
        self.assertEqual(primary["transport"], "http")
        self.assertEqual(primary["auth"], "oauth")
        self.assertEqual(primary["endpoint"], GITHUB_MCP_ENDPOINT)

    def test_local_docker_provider_is_a_dated_disabled_fallback(self):
        mapping = load_json(
            "platform/agent-control-plane/adapters/github/github-delivery-mapping.json"
        )
        local = mapping["providers"]["github-mcp-local"]
        self.assertFalse(local["enabled"])
        self.assertEqual(local["transport"], "stdio")
        self.assertIn("supersededAsPrimary", local)
        # The pinned Docker invocation is preserved as a commented fallback.
        self.assertIn("github-mcp-server@sha256:", read_text(".codex/config.toml"))

    def test_codex_config_declares_no_direct_atlassian_mcp_server(self):
        """Codex reaches Jira through the hosted Rovo connector. A direct
        `atlassian` server under Codex reproduces the OAuth-refresh incident."""
        with (ROOT / ".codex" / "config.toml").open("rb") as handle:
            codex = tomllib.load(handle)
        self.assertNotIn("atlassian", codex.get("mcp_servers", {}))

    def test_claude_mcp_keeps_the_optional_direct_atlassian_endpoint(self):
        servers = load_json(".mcp.json")["mcpServers"]
        self.assertIn("atlassian", servers)
        self.assertEqual(servers["atlassian"]["type"], "http")

    def test_checked_in_mcp_config_carries_no_secret_material(self):
        for relative in (".mcp.json", ".codex/config.toml"):
            text = read_text(relative)
            for pattern in SECRET_PATTERNS:
                self.assertIsNone(
                    pattern.search(text),
                    f"{relative} matches secret pattern {pattern.pattern}",
                )
        # The hosted OAuth entry carries no token at all; the commented Docker
        # fallback in the Codex config still refers to the token only by name.
        self.assertNotIn("GITHUB_PERSONAL_ACCESS_TOKEN", read_text(".mcp.json"))
        self.assertIn("GITHUB_PERSONAL_ACCESS_TOKEN", read_text(".codex/config.toml"))

    def test_checked_in_mcp_config_has_no_machine_specific_paths(self):
        for relative in (".mcp.json", ".codex/config.toml"):
            match = MACHINE_PATH_PATTERN.search(read_text(relative))
            self.assertIsNone(match, f"{relative} contains a machine-specific path: {match}")


class GithubFallbackRoutingTests(unittest.TestCase):
    def setUp(self):
        self.mapping = load_json(
            "platform/agent-control-plane/adapters/github/github-delivery-mapping.json"
        )

    def test_fallback_order_is_declared_primary_first_terminal_last(self):
        order = self.mapping["fallbackOrder"]
        providers = self.mapping["providers"]
        self.assertEqual(order[0], self.mapping["primaryProvider"])
        self.assertEqual(order[-1], self.mapping["fallbackProvider"])
        self.assertIn("github-mcp-local", order)
        for key in order:
            self.assertIn(key, providers, f"fallbackOrder names undeclared provider {key}")

    def test_every_mutating_github_operation_keeps_one_semantic_action(self):
        for name, operation in self.mapping["operations"].items():
            if not operation["requiresHumanApproval"]:
                continue
            tool = operation["tool"]
            self.assertIn(
                tool,
                permission_gate.GITHUB_MCP_ACTIONS,
                f"operation {name} tool {tool} has no semantic permission action",
            )
            self.assertTrue(permission_gate.GITHUB_MCP_ACTIONS[tool].startswith("github:"))
            self.assertTrue(
                operation.get("fallbackTool", "").startswith("gh "),
                f"operation {name} lacks a `gh` fallback tool",
            )


class JiraRuntimeScopeTests(unittest.TestCase):
    def setUp(self):
        self.mapping = load_json(
            "platform/agent-control-plane/adapters/jira/jira-delivery-mapping.json"
        )

    def test_runtime_scope_marks_rovo_default_and_direct_disabled_for_codex(self):
        providers = self.mapping["providers"]
        self.assertEqual(providers["atlassian-rovo"]["runtimeScope"], "codex-default")
        self.assertTrue(providers["atlassian-rovo"]["enabled"])
        self.assertEqual(providers["atlassian-mcp"]["runtimeScope"], "claude-optional")
        self.assertFalse(providers["atlassian-mcp"]["enabled"])

    def test_every_mutating_jira_operation_keeps_one_semantic_action(self):
        for name, operation in self.mapping["operations"].items():
            if not operation["requiresHumanApproval"]:
                continue
            normalized = re.sub(r"[^a-z0-9]", "", operation["tool"].lower())
            self.assertTrue(
                any(normalized.endswith(key) for key in permission_gate.JIRA_MCP_ACTIONS),
                f"operation {name} tool {operation['tool']} has no semantic permission action",
            )


class IncidentTraceabilityTests(unittest.TestCase):
    def test_incident_doc_exists_and_is_referenced_where_the_boundary_is_set(self):
        self.assertTrue((ROOT / INCIDENT_DOC).is_file())
        basename = Path(INCIDENT_DOC).name
        for relative in (
            "platform/agent-control-plane/agent-assets/mcp-servers/jira-confluence/server.md",
            "platform/agent-control-plane/adapters/jira/README.md",
            ".codex/README.md",
            "docs/architecture/destination-communication-boundaries.md",
        ):
            self.assertIn(basename, read_text(relative), f"{relative} does not cite the incident")


if __name__ == "__main__":
    unittest.main()
