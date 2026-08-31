from __future__ import annotations

import importlib.util
import json
from pathlib import Path
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


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


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


class RuntimeConfigurationParityTests(unittest.TestCase):
    def test_codex_and_claude_use_the_same_github_image_and_tools(self):
        claude = load_json(".mcp.json")["mcpServers"]["github"]
        with (ROOT / ".codex" / "config.toml").open("rb") as handle:
            codex = tomllib.load(handle)["mcp_servers"]["github"]

        claude_args = claude["args"]
        codex_args = codex["args"]
        claude_image = next(arg for arg in claude_args if arg.startswith("ghcr.io/"))
        codex_image = next(arg for arg in codex_args if arg.startswith("ghcr.io/"))
        claude_tools = next(arg for arg in claude_args if arg.startswith("--tools="))
        codex_tools = next(arg for arg in codex_args if arg.startswith("--tools="))

        self.assertEqual(claude_image, codex_image)
        self.assertEqual(claude_tools, codex_tools)
        self.assertIn("GITHUB_PERSONAL_ACCESS_TOKEN", claude["env"])
        self.assertIn("GITHUB_PERSONAL_ACCESS_TOKEN", codex["env_vars"])
        self.assertEqual(claude["command"], codex["command"])
        self.assertIn("atlassian", load_json(".mcp.json")["mcpServers"])

        mapping = load_json(
            "platform/agent-control-plane/adapters/github/github-delivery-mapping.json"
        )
        mapping_tools = mapping["providers"]["github-mcp"]["tools"]
        configured_tools = claude_tools.removeprefix("--tools=").split(",")
        self.assertEqual(configured_tools, mapping_tools)


if __name__ == "__main__":
    unittest.main()
