import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "workbench_evidence.py"
SPEC = importlib.util.spec_from_file_location("workbench_evidence", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def commit(sha="a1b2c3d", subject="Do a thing", paths=("docs/one.md",), patch_id="p1"):
    return MODULE.WorkbenchCommit(
        sha=sha, subject=subject, paths=tuple(paths), patch_id=patch_id
    )


class ClassifyCommitTests(unittest.TestCase):
    def classify(self, target=None, **overrides):
        values = {
            "residual_paths": frozenset(),
            "delivery_patch_ids": {},
            "delivery_paths": {},
            "dispositions": {},
        }
        values.update(overrides)
        return MODULE.classify_commit(target or commit(), **values)

    def test_delivered_content_is_represented_however_it_travelled(self):
        """The paths no longer differ, so the outcome reached main somehow."""
        result = self.classify(residual_paths=frozenset())

        self.assertEqual(result.state, MODULE.REPRESENTED)
        self.assertFalse(result.blocks)

    def test_a_reshaped_commit_is_still_represented_despite_a_new_sha(self):
        """Squash, cherry-pick and hunk-level reshaping all change the SHA.

        None of them change whether the content arrived, which is the whole
        reason this classifier does not compare commit identity.
        """
        reshaped = commit(sha="deadbee", patch_id="a-patch-id-nothing-else-has")

        self.assertEqual(self.classify(reshaped).state, MODULE.REPRESENTED)

    def test_undelivered_content_with_no_disposition_is_unresolved(self):
        result = self.classify(residual_paths=frozenset({"docs/one.md"}))

        self.assertEqual(result.state, MODULE.UNRESOLVED)
        self.assertTrue(result.blocks)
        self.assertIn("docs/one.md", result.rationale)

    def test_identical_patch_on_a_delivery_branch_is_in_delivery(self):
        result = self.classify(
            residual_paths=frozenset({"docs/one.md"}),
            delivery_patch_ids={"p1": "feature/PROJ-1-thing"},
        )

        self.assertEqual(result.state, MODULE.IN_DELIVERY)
        self.assertIn("feature/PROJ-1-thing", result.rationale)
        self.assertFalse(result.blocks)

    def test_path_coverage_routes_to_a_branch_without_claiming_delivery(self):
        result = self.classify(
            residual_paths=frozenset({"docs/one.md"}),
            delivery_paths={"fix/PROJ-2-thing": frozenset({"docs/one.md", "docs/two.md"})},
        )

        self.assertEqual(result.state, MODULE.IN_DELIVERY)
        self.assertIn("already changes every remaining path", result.rationale)

    def test_partial_path_coverage_does_not_count_as_in_delivery(self):
        """A branch carrying only some of the paths leaves the rest unaccounted."""
        two_paths = commit(paths=("docs/one.md", "docs/two.md"))

        result = self.classify(
            two_paths,
            residual_paths=frozenset({"docs/one.md", "docs/two.md"}),
            delivery_paths={"fix/PROJ-2-thing": frozenset({"docs/one.md"})},
        )

        self.assertEqual(result.state, MODULE.UNRESOLVED)

    def test_a_commit_is_judged_only_on_paths_that_still_differ(self):
        """Half-delivered work is not represented while any path remains."""
        two_paths = commit(paths=("docs/one.md", "docs/two.md"))

        result = self.classify(two_paths, residual_paths=frozenset({"docs/two.md"}))

        self.assertEqual(result.state, MODULE.UNRESOLVED)
        self.assertIn("docs/two.md", result.rationale)
        self.assertNotIn("docs/one.md", result.rationale)

    def test_recorded_park_decides_an_otherwise_unresolved_outcome(self):
        parked = MODULE.Disposition(MODULE.PARKED, "local experiment", "2026-08-31T00:00:00+00:00")

        result = self.classify(
            residual_paths=frozenset({"docs/one.md"}), dispositions={"p1": parked}
        )

        self.assertEqual(result.state, MODULE.PARKED)
        self.assertIn("local experiment", result.rationale)
        self.assertFalse(result.blocks)

    def test_recorded_supersede_is_reported_with_its_reason(self):
        superseded = MODULE.Disposition(
            MODULE.SUPERSEDED, "replaced by PROJ-9", "2026-08-31T00:00:00+00:00"
        )

        result = self.classify(
            residual_paths=frozenset({"docs/one.md"}), dispositions={"p1": superseded}
        )

        self.assertEqual(result.state, MODULE.SUPERSEDED)
        self.assertIn("replaced by PROJ-9", result.rationale)

    def test_delivery_outranks_a_stale_recorded_disposition(self):
        """Observed facts beat recorded intent: the parking is simply out of date."""
        parked = MODULE.Disposition(MODULE.PARKED, "old note", "2026-08-31T00:00:00+00:00")

        result = self.classify(
            residual_paths=frozenset(),
            dispositions={"p1": parked},
        )

        self.assertEqual(result.state, MODULE.REPRESENTED)

    def test_evidence_identity_prefers_the_patch_over_the_sha(self):
        """The workbench gets re-merged from main constantly; SHAs do not survive."""
        self.assertEqual(commit().evidence_id, "p1")
        self.assertEqual(commit(patch_id=None).evidence_id, "a1b2c3d")

    def test_a_disposition_recorded_against_a_sha_still_applies(self):
        without_patch = commit(patch_id=None)
        parked = MODULE.Disposition(MODULE.PARKED, "binary blob", "2026-08-31T00:00:00+00:00")

        result = self.classify(
            without_patch,
            residual_paths=frozenset({"docs/one.md"}),
            dispositions={"a1b2c3d": parked},
        )

        self.assertEqual(result.state, MODULE.PARKED)


class DispositionTests(unittest.TestCase):
    def test_a_disposition_requires_a_readable_reason(self):
        with self.assertRaises(ValueError):
            MODULE.Disposition(MODULE.PARKED, "   ", "2026-08-31T00:00:00+00:00")

    def test_only_park_and_supersede_are_recordable(self):
        """Represented and in-delivery are observed, never asserted by hand."""
        for state in (MODULE.REPRESENTED, MODULE.IN_DELIVERY, MODULE.UNRESOLVED):
            with self.subTest(state=state), self.assertRaises(ValueError):
                MODULE.Disposition(state, "because", "2026-08-31T00:00:00+00:00")

    def test_dispositions_round_trip_through_the_machine_local_record(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workbench-dispositions.json"

            MODULE.record_disposition(
                path, "p1", MODULE.PARKED, "still exploring", now="2026-08-31T00:00:00+00:00"
            )
            MODULE.record_disposition(
                path, "p2", MODULE.SUPERSEDED, "replaced", now="2026-08-31T00:00:01+00:00"
            )

            loaded = MODULE.load_dispositions(path)

            self.assertEqual(set(loaded), {"p1", "p2"})
            self.assertEqual(loaded["p1"].state, MODULE.PARKED)
            self.assertEqual(loaded["p1"].reason, "still exploring")
            self.assertEqual(loaded["p2"].recorded_at, "2026-08-31T00:00:01+00:00")

    def test_a_missing_record_is_an_empty_set_not_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                MODULE.load_dispositions(Path(directory) / "absent.json"), {}
            )

    def test_an_unreadable_record_is_reported_rather_than_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{not json")

            with self.assertRaises(MODULE.EvidenceError):
                MODULE.load_dispositions(path)

    def test_re_recording_replaces_the_previous_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workbench-dispositions.json"
            MODULE.record_disposition(
                path, "p1", MODULE.PARKED, "first", now="2026-08-31T00:00:00+00:00"
            )
            MODULE.record_disposition(
                path, "p1", MODULE.SUPERSEDED, "second", now="2026-08-31T00:00:02+00:00"
            )

            loaded = MODULE.load_dispositions(path)

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded["p1"].state, MODULE.SUPERSEDED)
            self.assertEqual(loaded["p1"].reason, "second")


class ReportingTests(unittest.TestCase):
    def classified(self, state, **overrides):
        return MODULE.ClassifiedCommit(commit(**overrides), state, "because")

    def test_only_unresolved_evidence_blocks(self):
        items = (
            self.classified(MODULE.REPRESENTED),
            self.classified(MODULE.IN_DELIVERY),
            self.classified(MODULE.PARKED),
            self.classified(MODULE.SUPERSEDED),
            self.classified(MODULE.UNRESOLVED, sha="ffffff1"),
        )

        blocking = MODULE.unresolved(items)

        self.assertEqual(len(blocking), 1)
        self.assertEqual(blocking[0].commit.sha, "ffffff1")

    def test_json_report_carries_state_and_identity_per_commit(self):
        payload = json.loads(
            MODULE.as_json((self.classified(MODULE.UNRESOLVED),))
        )

        self.assertEqual(payload["unresolvedCount"], 1)
        entry = payload["evidence"][0]
        self.assertEqual(entry["state"], MODULE.UNRESOLVED)
        self.assertEqual(entry["evidenceId"], "p1")
        self.assertEqual(entry["paths"], ["docs/one.md"])

    def test_text_report_names_the_required_disposition(self):
        text = MODULE.as_text((self.classified(MODULE.UNRESOLVED),))

        self.assertIn("Unreconciled workbench evidence", text)
        self.assertIn("deliver, park, or supersede", text)

    def test_text_report_summarizes_a_fully_reconciled_workbench(self):
        text = MODULE.as_text(
            (self.classified(MODULE.REPRESENTED), self.classified(MODULE.PARKED))
        )

        self.assertIn("1 parked", text)
        self.assertIn("1 represented", text)
        self.assertNotIn("Unreconciled", text)

    def test_an_empty_workbench_reports_nothing_to_reconcile(self):
        self.assertIn("No workbench-only commits", MODULE.as_text(()))


if __name__ == "__main__":
    unittest.main()
