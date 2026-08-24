from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "validate_contracts.py"
SPEC = importlib.util.spec_from_file_location("validate_contracts", SCRIPT_PATH)
assert SPEC and SPEC.loader
contracts = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contracts
SPEC.loader.exec_module(contracts)


def run_script(*, contracts_dir: Path | None = None) -> subprocess.CompletedProcess:
    """Invoke the module the way an operator would, as a script.

    ``contracts_dir`` rebinds CONTRACTS before main() runs, so a case can
    point the check at a directory it controls without touching the real one.
    """
    if contracts_dir is None:
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True
        )
    program = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('vc', {str(SCRIPT_PATH)!r})\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules['vc'] = module\n"
        "spec.loader.exec_module(module)\n"
        f"module.CONTRACTS = __import__('pathlib').Path({str(contracts_dir)!r})\n"
        "raise SystemExit(module.main())\n"
    )
    return subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True
    )


class ScriptInvocationTests(unittest.TestCase):
    """The module must never exit 0 without having validated something.

    It sits in scripts/, is named validate_*, and is a sibling of
    validate_asset_registries.py, so a clean exit reads as "the contracts
    validated." Before this entry point existed it exited 0 having only
    defined functions.
    """

    def test_compiling_the_real_contracts_succeeds(self):
        result = run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("contracts valid:", result.stdout)

    def test_reports_every_schema_it_compiled(self):
        result = run_script()
        for name in contracts.schema_names():
            self.assertIn(name, result.stdout)

    def test_empty_contracts_directory_fails(self):
        """Zero schemas is a failure, not a vacuous success."""
        with tempfile.TemporaryDirectory() as directory:
            result = run_script(contracts_dir=Path(directory))
        self.assertEqual(result.returncode, 1)
        self.assertIn("no contract schemas found", result.stderr)

    def test_malformed_schema_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / "broken.schema.json"
            broken.write_text("{not json", encoding="utf-8")
            result = run_script(contracts_dir=Path(directory))
        self.assertEqual(result.returncode, 1)
        self.assertIn("contract validation failed:", result.stderr)

    def test_schema_that_is_not_itself_valid_fails(self):
        """check_schema rejects it, not merely instances validated against it."""
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.schema.json"
            invalid.write_text(
                json.dumps({"type": "not-a-real-type"}), encoding="utf-8"
            )
            result = run_script(contracts_dir=Path(directory))
        self.assertEqual(result.returncode, 1)
        self.assertIn("contract validation failed:", result.stderr)


class LibraryUseTests(unittest.TestCase):
    """Adding an entry point must not disturb the importing consumers."""

    def test_every_contract_still_compiles_through_the_library(self):
        for name in contracts.schema_names():
            self.assertIsNotNone(contracts.validator_for(name))

    def test_evidence_types_still_resolve(self):
        self.assertTrue(contracts.evidence_types())


if __name__ == "__main__":
    unittest.main()
