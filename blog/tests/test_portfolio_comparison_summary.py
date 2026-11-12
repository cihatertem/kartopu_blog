import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from django.test import TestCase

from blog.templatetags import blog_extras
from blog.templatetags.blog_extras import (
    _format_snapshot_date,
    _render_portfolio_comparison_summary_html,
)


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
    def test_format_snapshot_date(self):
        self.assertEqual(
            _format_snapshot_date(datetime.date(2026, 9, 30)),
            "30.09.2026",
        )
        self.assertEqual(_format_snapshot_date("2026-10-31"), "31.10.2026")
        self.assertEqual(_format_snapshot_date("invalid-date"), "invalid-date")

    def test_render_portfolio_comparison_summary_html(self):
        base = DummySnapshot(
            snapshot_date="2026-01-31",
            total_value="3492833.62",
            total_cost="2294275.12",
            target_value="4000000.00",
            total_return_pct="0.5224",
        )
        compare = DummySnapshot(
            snapshot_date="2026-02-28",
            total_value="3543096.09",
            total_cost="2406345.83",
            target_value="4000000.00",
            total_return_pct="0.4724",
        )
        comparison = DummyComparison(base, compare)

        html = _render_portfolio_comparison_summary_html(comparison)

        self.assertIn("<strong>31.01.2026</strong>", html)
        self.assertIn("<strong>28.02.2026</strong>", html)
        self.assertIn("(Aylık)", html)
        self.assertIn("DEĞİŞİM VE GETİRİ", html)
        self.assertIn("Piyasa Değeri Değişimi", html)
        self.assertIn("Arındırılmış Yatırım Getirisi", html)
        self.assertIn("50.262,47 ₺", html)
        self.assertIn("comparison-metric__icon--up", html)
        self.assertIn(
            '<p class="comparison-metric__value comparison-metric__value--positive">'
            '<span class="comparison-metric__icon comparison-metric__icon--up" aria-hidden="true"></span>'
            "50.262,47 ₺</p>",
            html,
        )
        self.assertIn(
            '<p class="comparison-metric__value comparison-metric__value--negative">~%-1,77</p>',
            html,
        )

    def test_render_portfolio_comparison_summary_html_negative_value_positive_return(
        self,
    ):
        base = DummySnapshot(
            snapshot_date=datetime.date(2026, 9, 30),
            total_value="6233469.12",
            total_cost="5250569.10",
            target_value="22976296.05",
            total_return_pct="0.1872",
        )
        compare = DummySnapshot(
            snapshot_date=datetime.date(2026, 10, 31),
            total_value="5145629.30",
            total_cost="4143189.02",
            target_value="23157647.61",
            total_return_pct="0.2419",
        )
        comparison = DummyComparison(base, compare)

        html = _render_portfolio_comparison_summary_html(comparison)

        self.assertIn("<strong>30.09.2026</strong>", html)
        self.assertIn("<strong>31.10.2026</strong>", html)
        self.assertIn("Toplam Maliyet: 5.250.569,10 ₺", html)
        self.assertIn("Hedef Gerçekleşme: %27,13", html)
        self.assertIn("Toplam Getiri: %18,72", html)
        self.assertIn("Toplam Maliyet: 4.143.189,02 ₺", html)
        self.assertIn("Hedef Gerçekleşme: %22,22", html)
        self.assertIn("Toplam Getiri: %24,19", html)
        self.assertIn(
            '<p class="comparison-metric__value comparison-metric__value--negative">'
            '<span class="comparison-metric__icon comparison-metric__icon--down" aria-hidden="true"></span>'
            "-1.087.839,82 ₺</p>",
            html,
        )
        self.assertIn(
            '<p class="comparison-metric__value comparison-metric__value--positive">~%0,31</p>',
            html,
        )

    def test_render_portfolio_comparison_summary_html_positive_return(self):
        base = DummySnapshot(
            snapshot_date="2026-01-31",
            total_value="1000.00",
            total_cost="800.00",
            target_value="2000.00",
            total_return_pct="0.25",
        )
        compare = DummySnapshot(
            snapshot_date="2026-02-28",
            total_value="1500.00",
            total_cost="1000.00",
            target_value="2000.00",
            total_return_pct="0.50",
        )
        comparison = DummyComparison(base, compare)

        html = _render_portfolio_comparison_summary_html(comparison)

        self.assertIn("Hedef Gerçekleşme: %50,00", html)
        self.assertIn("Hedef Gerçekleşme: %75,00", html)
        self.assertIn("comparison-metric__icon--up", html)
        self.assertIn(
            '<p class="comparison-metric__value comparison-metric__value--positive">~%30,00</p>',
            html,
        )

    def test_render_post_body_preserves_portfolio_comparison_markup(self):
        base = DummySnapshot(
            snapshot_date=datetime.date(2026, 9, 30),
            total_value="6233469.12",
            total_cost="5250569.10",
            target_value=None,
            total_return_pct="0.1872",
        )
        compare = DummySnapshot(
            snapshot_date=datetime.date(2026, 10, 31),
            total_value="5145629.30",
            total_cost="4143189.02",
            target_value=None,
            total_return_pct="0.2419",
        )
        comparison = DummyComparison(base, compare)
        comparison.slug = "portfolio-comparison#abc123"

        post = MagicMock()
        post.content = "{{ portfolio_comparison_summary:abc123 }}"
        post.images.all.return_value = []
        post._prefetched_objects_cache = {"portfolio_comparisons": [comparison]}

        rendered = blog_extras.render_post_body({}, post)

        self.assertIn("comparison-divider__badge", rendered)
        self.assertIn("DEĞİŞİM VE GETİRİ", rendered)
        self.assertIn("Piyasa Değeri Değişimi", rendered)
        self.assertIn("Arındırılmış Yatırım Getirisi", rendered)
        self.assertIn("comparison-metric__icon--down", rendered)
        self.assertIn('aria-hidden="true"', rendered)
        self.assertNotIn("Hedef Gerçekleşme:", rendered)
