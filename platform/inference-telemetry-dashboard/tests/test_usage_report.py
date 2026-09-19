from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from dashboard import pricing  # noqa: E402
from dashboard.render_html import render_report  # noqa: E402
from dashboard.usage_model import UNATTRIBUTED, build_report, work_item_key  # noqa: E402


@dataclass(frozen=True)
class Sample:
    """A stand-in for the reader's UsageSample.

    The aggregation reads samples structurally, so the tests do not import
    the control plane's reader — which keeps a failure here pointing at this
    component rather than at the port."""

    runtime: str = "claude"
    session_id: str = "s1"
    timestamp: str | None = "2026-09-01T12:00:00Z"
    model: str | None = "claude-opus-5"
    git_branch: str | None = "feature/AEPI-105-govern-delivery"
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    thinking_tokens: int = 0
    cache_write_1h_tokens: int = 0


class WorkItemKeyTests(unittest.TestCase):
    def test_reads_the_key_out_of_a_delivery_branch(self):
        self.assertEqual(work_item_key("feature/AEPI-105-govern-delivery"), "AEPI-105")

    def test_reads_the_key_regardless_of_change_type_prefix(self):
        for branch in ("fix/AEPI-9-x", "refactor/AEPI-9-x", "agent/AEPI-9-x"):
            self.assertEqual(work_item_key(branch), "AEPI-9")

    def test_branch_naming_no_work_item_is_unattributed(self):
        for branch in ("workbench/local", "main", "agent/publish-platform-work"):
            self.assertEqual(work_item_key(branch), UNATTRIBUTED)

    def test_absent_branch_is_unattributed(self):
        self.assertEqual(work_item_key(None), UNATTRIBUTED)
        self.assertEqual(work_item_key(""), UNATTRIBUTED)

    def test_lowercase_key_shape_is_not_a_work_item(self):
        self.assertEqual(work_item_key("feature/aepi-105-x"), UNATTRIBUTED)

    def test_zero_numbered_key_is_rejected_like_the_contract_pattern(self):
        self.assertEqual(work_item_key("feature/AEPI-0-x"), UNATTRIBUTED)


class PricingTests(unittest.TestCase):
    def test_prices_each_token_class_at_its_own_rate(self):
        # Opus 5: $5 in, $25 out, $0.50 cache read, 1.25x write at 5m TTL.
        sample = Sample(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_read_tokens=1_000_000,
            cache_creation_tokens=1_000_000,
        )
        self.assertAlmostEqual(
            pricing.estimate_cost(sample), 5.0 + 25.0 + 0.50 + 6.25, places=6
        )

    def test_one_hour_cache_writes_bill_at_the_higher_multiple(self):
        sample = Sample(cache_creation_tokens=1_000_000, cache_write_1h_tokens=1_000_000)
        self.assertAlmostEqual(pricing.estimate_cost(sample), 10.0, places=6)

    def test_a_one_hour_portion_larger_than_the_write_is_clamped(self):
        """Defends the arithmetic against a malformed usage block: the split
        is a subset of the total, so it can never bill more than the whole."""
        sample = Sample(cache_creation_tokens=1_000_000, cache_write_1h_tokens=9_000_000)
        self.assertAlmostEqual(pricing.estimate_cost(sample), 10.0, places=6)

    def test_dated_model_snapshot_prices_as_the_undated_model(self):
        dated = Sample(model="claude-haiku-4-5-20251001", output_tokens=1_000_000)
        undated = Sample(model="claude-haiku-4-5", output_tokens=1_000_000)
        self.assertEqual(pricing.estimate_cost(dated), pricing.estimate_cost(undated))
        self.assertTrue(pricing.is_priceable(dated.model))

    def test_unknown_model_is_not_priceable_and_costs_nothing(self):
        sample = Sample(model="some-other-model", output_tokens=1_000_000)
        self.assertFalse(pricing.is_priceable(sample.model))
        self.assertEqual(pricing.estimate_cost(sample), 0.0)

    def test_synthetic_and_absent_models_are_not_priceable(self):
        self.assertFalse(pricing.is_priceable(pricing.SYNTHETIC_MODEL))
        self.assertFalse(pricing.is_priceable(None))

    def test_synthetic_model_is_not_a_pricing_gap(self):
        """A synthetic message genuinely cost nothing, so it is not the same
        kind of unpriced as a model this table simply does not know."""
        self.assertFalse(pricing.is_pricing_gap(pricing.SYNTHETIC_MODEL))

    def test_unknown_and_absent_models_are_pricing_gaps(self):
        self.assertTrue(pricing.is_pricing_gap("some-other-model"))
        self.assertTrue(pricing.is_pricing_gap(None))


class BuildReportTests(unittest.TestCase):
    def _report(self):
        return build_report(
            [
                Sample(output_tokens=100, cache_read_tokens=900, input_tokens=100),
                Sample(
                    git_branch="workbench/local",
                    session_id="s2",
                    output_tokens=50,
                    input_tokens=50,
                ),
                Sample(
                    runtime="codex",
                    session_id="s3",
                    model=None,
                    git_branch="fix/AEPI-9-y",
                    output_tokens=10,
                    input_tokens=10,
                    timestamp="2026-09-02T12:00:00Z",
                ),
            ]
        )

    def test_groups_by_work_item_including_the_unattributed_bucket(self):
        keys = {r.key for r in self._report().by_work_item}
        self.assertEqual(keys, {"AEPI-105", "AEPI-9", UNATTRIBUTED})

    def test_work_items_are_ordered_by_estimated_cost(self):
        costs = [r.estimated_cost for r in self._report().by_work_item]
        self.assertEqual(costs, sorted(costs, reverse=True))

    def test_counts_distinct_sessions_across_runtimes(self):
        self.assertEqual(self._report().session_count, 3)

    def test_unpriced_calls_are_counted_not_silently_zeroed(self):
        codex = next(r for r in self._report().by_runtime if r.key == "codex")
        self.assertEqual(codex.calls, 1)
        self.assertEqual(codex.unpriced_calls, 1)
        self.assertEqual(codex.priced_fraction, 0.0)

    def test_synthetic_model_calls_are_not_counted_as_unpriced(self):
        """A synthetic call is genuinely free, not a pricing gap: counting it
        as unpriced would misreport zero-cost spend as a table miss."""
        report = build_report([Sample(model=pricing.SYNTHETIC_MODEL, output_tokens=10)])
        self.assertEqual(report.total.calls, 1)
        self.assertEqual(report.total.unpriced_calls, 0)
        self.assertEqual(report.unpriced_models, [])

    def test_unpriced_models_are_reported_for_the_limits_block(self):
        self.assertEqual(
            self._report().unpriced_models, ["codex (model not recorded)"]
        )

    def test_cache_read_ratio_is_a_share_of_input_not_of_all_tokens(self):
        report = build_report([Sample(input_tokens=100, cache_read_tokens=900, output_tokens=1000)])
        self.assertAlmostEqual(report.total.cache_read_ratio, 0.9)

    def test_cache_read_ratio_of_zero_input_does_not_divide_by_zero(self):
        self.assertEqual(build_report([Sample(output_tokens=5)]).total.cache_read_ratio, 0.0)

    def test_days_are_ordered_chronologically(self):
        self.assertEqual([r.key for r in self._report().by_day], ["2026-09-01", "2026-09-02"])

    def test_a_sample_without_a_timestamp_lands_in_no_day_bucket(self):
        report = build_report([Sample(timestamp=None, output_tokens=1)])
        self.assertEqual(report.by_day, [])
        self.assertEqual(report.total.calls, 1)

    def test_empty_input_produces_an_empty_report_rather_than_raising(self):
        report = build_report([])
        self.assertEqual(report.total.calls, 0)
        self.assertEqual(report.by_work_item, [])


class RenderReportTests(unittest.TestCase):
    def _html(self):
        report = build_report(
            [
                Sample(output_tokens=1_000_000, input_tokens=1_000_000),
                Sample(git_branch="workbench/local", session_id="s2", output_tokens=10),
                Sample(runtime="codex", session_id="s3", model=None, output_tokens=10),
            ]
        )
        return render_report(report, generated_at="2026-09-08 00:00 UTC", sources="2 sessions")

    def test_page_is_self_contained(self):
        html = self._html()
        for marker in ("http://", "https://", "<script"):
            self.assertNotIn(marker, html)

    def test_declares_all_three_theme_states(self):
        html = self._html()
        self.assertIn("prefers-color-scheme: dark", html)
        self.assertIn(':root[data-theme="dark"]', html)
        self.assertIn(":root {", html)

    def test_states_the_rate_date_so_cost_is_readable_as_an_estimate(self):
        self.assertIn(pricing.AS_OF, self._html())

    def test_names_the_unattributed_bucket_in_the_limits(self):
        self.assertIn(UNATTRIBUTED, self._html())

    def test_flags_the_unpriced_runtime(self):
        self.assertIn("cannot be priced", self._html())

    def test_escapes_a_branch_name_that_carries_markup(self):
        report = build_report([Sample(git_branch="feature/<img src=x>", output_tokens=1)])
        html = render_report(report, generated_at="now", sources="1 session")
        self.assertNotIn("<img src=x>", html)


if __name__ == "__main__":
    unittest.main()
