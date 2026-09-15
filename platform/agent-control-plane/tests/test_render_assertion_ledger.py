from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "render_assertion_ledger.py"
SPEC = importlib.util.spec_from_file_location("render_assertion_ledger", SCRIPT_PATH)
assert SPEC and SPEC.loader
renderer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = renderer
SPEC.loader.exec_module(renderer)


def _row(**overrides):
    base = {
        "id": 1,
        "confirmed": "unlabelled",
        "found": "2026-09-14",
        "foundBy": "claude:2130d90a",
        "where": "x",
        "asserted": "y",
        "actual": "z",
        "direction": "never",
        "countermeasure": "cm-a",
        "caught": "no",
        "fixed": "open",
    }
    base.update(overrides)
    return base


def _source(*rows, countermeasures=("cm-a", "cm-b")):
    return {"countermeasures": list(countermeasures), "instances": list(rows), "readingNotes": ["note"]}


class ValidateTests(unittest.TestCase):
    def test_accepts_minimal_valid_source(self):
        renderer.validate(_source(_row()))

    def test_rejects_unknown_countermeasure(self):
        with self.assertRaisesRegex(ValueError, "not listed under countermeasures"):
            renderer.validate(_source(_row(countermeasure="cm-z")))

    def test_accepts_none_countermeasure(self):
        renderer.validate(_source(_row(countermeasure="none")))

    def test_rejects_bad_enum(self):
        with self.assertRaisesRegex(ValueError, "confirmed="):
            renderer.validate(_source(_row(confirmed="maybe")))

    def test_yellow_requires_note(self):
        with self.assertRaisesRegex(ValueError, "requires confirmedNote"):
            renderer.validate(_source(_row(confirmed="yellow")))
        renderer.validate(_source(_row(confirmed="yellow", confirmedNote="caveat")))

    def test_rejects_duplicate_ids(self):
        with self.assertRaisesRegex(ValueError, "appears twice"):
            renderer.validate(_source(_row(id=1), _row(id=1)))


class TalliesTests(unittest.TestCase):
    def test_counts_caught_and_missed_per_countermeasure(self):
        source = _source(
            _row(id=1, countermeasure="cm-a", caught="no"),
            _row(id=2, countermeasure="cm-a", caught="yes"),
            _row(id=3, countermeasure="none"),
        )
        self.assertEqual(
            renderer.tallies(source),
            [
                ("cm-a", "2", "1", "1"),
                ("cm-b", "0", "n/a", "n/a"),
                ("no countermeasure exists", "1", "n/a", "n/a"),
            ],
        )

    def test_direction_line_omits_zero_counts(self):
        source = _source(_row(id=1, direction="never"), _row(id=2, direction="never"))
        self.assertEqual(renderer.direction_line(source), "By direction: never 2.")


class RenderTests(unittest.TestCase):
    def test_confirmed_is_second_column_and_pipes_are_escaped(self):
        line = renderer.render_instance_row(_row(where="a|b"))
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        self.assertEqual(cells[0], "1")
        self.assertEqual(cells[1], "unlabelled")
        self.assertIn("a\\|b", line)

    def test_render_is_deterministic_and_marked_generated(self):
        source = _source(_row(id=2), _row(id=1))
        out = renderer.render(source)
        self.assertEqual(out, renderer.render(source))
        self.assertIn(renderer.GENERATED_MARKER, out)
        self.assertLess(out.index("| 1 |"), out.index("| 2 |"))

    def test_checked_in_ledger_is_current(self):
        source = renderer.load_source()
        renderer.validate(source)
        self.assertEqual(renderer.render(source), renderer.RENDER_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
