import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "validate_examples.py"
)
SPEC = importlib.util.spec_from_file_location("validate_examples", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class RoutingFixtureTests(unittest.TestCase):
    def test_all_examples(self) -> None:
        self.assertEqual(
            VALIDATOR.validate_all(),
            {
                "events": 4,
                "decisions": 4,
                "receipts": 5,
            },
        )


if __name__ == "__main__":
    unittest.main()
