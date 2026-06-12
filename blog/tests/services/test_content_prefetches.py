from django.db.models import Prefetch
from django.test import SimpleTestCase

from blog.services import get_content_prefetches_for_markers


class TestGetContentPrefetchesForMarkers(SimpleTestCase):
    def test_empty_markers(self):
        prefetches = get_content_prefetches_for_markers(set())
        self.assertEqual(prefetches, [])

    def test_portfolio_snapshot_markers(self):
        prefetches = get_content_prefetches_for_markers({"portfolio_summary"})
        self.assertEqual(len(prefetches), 1)
        self.assertEqual(prefetches[0].prefetch_to, "portfolio_snapshots")

    def test_portfolio_comparison_markers(self):
        prefetches = get_content_prefetches_for_markers(
            {"portfolio_comparison_summary"}
        )
        self.assertEqual(len(prefetches), 1)
        self.assertEqual(prefetches[0].prefetch_to, "portfolio_comparisons")

    def test_cashflow_snapshot_markers(self):
        prefetches = get_content_prefetches_for_markers({"cashflow_charts"})
        self.assertEqual(len(prefetches), 1)
        self.assertEqual(prefetches[0].prefetch_to, "cashflow_snapshots")

    def test_cashflow_comparison_markers(self):
        prefetches = get_content_prefetches_for_markers({"cashflow_comparison_charts"})
        self.assertEqual(len(prefetches), 1)
        self.assertEqual(prefetches[0].prefetch_to, "cashflow_comparisons")

    def test_salary_savings_markers(self):
        prefetches = get_content_prefetches_for_markers({"savings_rate_summary"})
        self.assertEqual(len(prefetches), 1)
        self.assertEqual(prefetches[0].prefetch_to, "salary_savings_snapshots")

    def test_dividend_snapshot_markers(self):
        prefetches = get_content_prefetches_for_markers({"dividend_summary"})
        self.assertEqual(len(prefetches), 1)
        self.assertEqual(prefetches[0].prefetch_to, "dividend_snapshots")

    def test_dividend_comparison_markers(self):
        prefetches = get_content_prefetches_for_markers({"dividend_comparison"})
        self.assertEqual(len(prefetches), 1)
        self.assertEqual(prefetches[0].prefetch_to, "dividend_comparisons")

    def test_multiple_markers(self):
        prefetches = get_content_prefetches_for_markers(
            {"portfolio_summary", "cashflow_summary", "dividend_comparison"}
        )
        self.assertEqual(len(prefetches), 3)
        prefetch_targets = {p.prefetch_to for p in prefetches}
        self.assertSetEqual(
            prefetch_targets,
            {"portfolio_snapshots", "cashflow_snapshots", "dividend_comparisons"},
        )

    def test_unrelated_markers(self):
        prefetches = get_content_prefetches_for_markers(
            {"unrelated_marker", "another_one"}
        )
        self.assertEqual(prefetches, [])
