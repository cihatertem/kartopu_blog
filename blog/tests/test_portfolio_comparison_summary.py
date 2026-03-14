from decimal import Decimal

from django.test import TestCase

from blog.templatetags.blog_extras import _render_portfolio_comparison_summary_html


class DummyPortfolio:
    currency = "TRY"


class DummySnapshot:
    def __init__(
        self,
        snapshot_date,
        total_value,
        total_cost,
        target_value,
        total_return_pct,
    ):
        self.snapshot_date = snapshot_date
        self.total_value = Decimal(total_value)
        self.total_cost = Decimal(total_cost)
        self.target_value = Decimal(target_value) if target_value else None
        self.total_return_pct = Decimal(total_return_pct)
        self.portfolio = DummyPortfolio()

    def get_period_display(self):
        return "Aylık"


class DummyComparison:
    def __init__(self, base, compare):
        self.base_snapshot = base
        self.compare_snapshot = compare


class TestPortfolioComparisonSummaryHtml(TestCase):
    def test_render_portfolio_comparison_summary_html(self):
        base = DummySnapshot(
            snapshot_date="2026-01-31",
            total_value="3492833.62",
            total_cost="2294275.12",
            target_value="4000000.00",  # Example target for coverage
            total_return_pct="0.5224",  # 52.24%
        )
        compare = DummySnapshot(
            snapshot_date="2026-02-28",
            total_value="3543096.09",
            total_cost="2406345.83",
            target_value="4000000.00",
            total_return_pct="0.4724",  # 47.24% (-5% difference)
        )
        comparison = DummyComparison(base, compare)

        html = _render_portfolio_comparison_summary_html(comparison)

        self.assertIn("puan", html)
        self.assertIn("Getiri -500 puan", html)

        self.assertIn("50.262,47", html)
        self.assertIn("~%-1,77", html)

        self.assertIn("<strong>Değişim:</strong>", html)

    def test_render_portfolio_comparison_summary_html_positive_return(self):
        base = DummySnapshot(
            snapshot_date="2026-01-31",
            total_value="1000.00",
            total_cost="800.00",
            target_value="2000.00",
            total_return_pct="0.25",  # 25%
        )
        compare = DummySnapshot(
            snapshot_date="2026-02-28",
            total_value="1500.00",
            total_cost="1000.00",
            target_value="2000.00",
            total_return_pct="0.50",  # 50% (+25% diff)
        )
        comparison = DummyComparison(base, compare)

        html = _render_portfolio_comparison_summary_html(comparison)

        self.assertIn("Getiri +2500 puan", html)
        self.assertIn("Hedef Gerçekleşme +2500 puan", html)

        self.assertIn("~%30,00", html)
