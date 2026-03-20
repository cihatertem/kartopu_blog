import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase

from blog.templatetags import blog_extras
from blog.templatetags.blog_extras import (
    _coerce_identifier,
    _format_tr_number,
    _get_indexed_item,
    _get_item_by_identifier,
    _get_prefetched_list,
    _render_cashflow_charts_html,
    _render_cashflow_comparison_charts_html,
    _render_cashflow_summary_html,
    _render_dividend_charts_html,
    _render_dividend_comparison_html,
    _render_dividend_summary_html,
    _render_portfolio_category_summary_html,
    _render_portfolio_charts_html,
    _render_portfolio_comparison_charts_html,
    _render_portfolio_irr_charts_html,
    _render_portfolio_summary_html,
    _render_savings_rate_charts_html,
    _render_savings_rate_summary_html,
)


class DummySnapshot:
    def __init__(
        self,
        total_amount=None,
        year=None,
        currency=None,
        payment_items=None,
    ):
        self.total_amount = Decimal(total_amount) if total_amount else Decimal("0")
        self.year = year
        self.currency = currency

        mock_qs = MagicMock()
        mock_qs.select_related.return_value.order_by.return_value = payment_items or []
        self.payment_items = mock_qs
        self.asset_items = mock_qs
        self.items = mock_qs
        self.portfolio = MagicMock(name="Test Portfolio", currency="TRY")
        self.cashflow = MagicMock(name="Test CashFlow", currency="TRY")
        self.flow = MagicMock(name="Test Flow")

        self.snapshot_date = "2025-01-01"
        self.period = "monthly"
        self.total_value = Decimal("1000")
        self.total_cost = Decimal("800")
        self.target_value = Decimal("2000")
        self.total_return_pct = Decimal("0.25")
        self.savings_rate = Decimal("0.40")

    def get_period_display(self):
        return "Aylık"


class TestTemplateTagsHelpers(TestCase):
    def test_format_tr_number(self):
        self.assertEqual(_format_tr_number(Decimal("1000")), "1.000")
        self.assertEqual(_format_tr_number(Decimal("1000.50")), "1.000,50")

    def test_coerce_identifier(self):
        self.assertEqual(_coerce_identifier(None), None)
        self.assertEqual(_coerce_identifier(1), 1)
        self.assertEqual(_coerce_identifier(" 1 "), 1)
        self.assertEqual(_coerce_identifier("slug"), "slug")

    def test_get_indexed_item(self):
        items = ["a", "b", "c"]
        self.assertEqual(_get_indexed_item(None, 1), None)
        self.assertEqual(_get_indexed_item(items, None), "a")
        self.assertEqual(_get_indexed_item(items, 1), "a")
        self.assertEqual(_get_indexed_item(items, 2), "b")
        self.assertEqual(_get_indexed_item(items, 10), None)

    def test_get_item_by_identifier(self):
        class Item:
            def __init__(self, slug):
                self.slug = slug

        i1 = Item("slug1")
        i2 = Item("slug2")
        i3 = Item("slug3#hash")
        items = [i1, i2, i3]

        self.assertEqual(_get_item_by_identifier(None, "1"), None)
        self.assertEqual(_get_item_by_identifier(items, None), i1)
        self.assertEqual(_get_item_by_identifier(items, 2), i2)
        self.assertEqual(_get_item_by_identifier(items, "slug2"), i2)
        self.assertEqual(_get_item_by_identifier(items, "hash"), i3)
        self.assertEqual(_get_item_by_identifier(items, "missing"), None)

    def test_get_prefetched_list(self):
        class Post:
            _prefetched_objects_cache = {"items": ["a"]}

        self.assertEqual(_get_prefetched_list(None, "items", ["b"]), [])
        self.assertEqual(_get_prefetched_list(Post(), "items", ["b"]), ["a"])
        self.assertEqual(_get_prefetched_list(Post(), "missing", ["b"]), ["b"])


class TestRenderHTMLFunctions(TestCase):
    def test_render_portfolio_summary_html(self):
        self.assertEqual(_render_portfolio_summary_html(None), "")
        s = DummySnapshot()
        html = _render_portfolio_summary_html(s)
        self.assertIn("1.000 ₺", html)
        self.assertIn("800 ₺", html)
        self.assertIn("2.000 ₺", html)
        self.assertIn("50.00", html)
        self.assertIn("25.00", html)

    def test_render_portfolio_irr_charts_html(self):
        self.assertEqual(_render_portfolio_irr_charts_html(None), "")
        s = DummySnapshot()
        s.portfolio.get_irr_history.return_value = [{"date": "2025", "irr": 10}]
        html = _render_portfolio_irr_charts_html(s)
        self.assertIn("portfolio-irr-charts", html)

    def test_render_portfolio_charts_html(self):
        self.assertEqual(_render_portfolio_charts_html(None), "")
        s = DummySnapshot()

        class DummyQS:
            def filter(self, *args, **kwargs):
                return self

            def order_by(self, *args, **kwargs):
                return self

            def values_list(self, *args, **kwargs):
                return [(datetime.date(2025, 1, 1), 100)]

        s.__class__.objects = DummyQS()
        html = _render_portfolio_charts_html(s)
        self.assertIn("portfolio-charts", html)

    def test_render_portfolio_category_summary_html(self):
        self.assertEqual(_render_portfolio_category_summary_html(None), "")
        s = DummySnapshot()

        class MItem:
            asset = MagicMock()
            asset.get_asset_type_display.return_value = "Hisse"
            allocation_pct = Decimal("0.5")

        s.items.select_related.return_value.filter.return_value.order_by.return_value = [
            MItem()
        ]
        html = _render_portfolio_category_summary_html(s)
        self.assertIn("Hisse", html)

    def test_render_portfolio_comparison_charts_html(self):
        self.assertEqual(_render_portfolio_comparison_charts_html(None), "")
        c = MagicMock()
        c.base_snapshot = DummySnapshot()
        c.compare_snapshot = DummySnapshot()
        html = _render_portfolio_comparison_charts_html(c)
        self.assertIn("portfolio-comparison-charts", html)

    def test_render_cashflow_summary_html(self):
        self.assertEqual(_render_cashflow_summary_html(None), "")
        s = DummySnapshot(total_amount="1500")

        class CItem:
            amount = 100

            def get_category_display(self):
                return "Kira"

        s.items.order_by.return_value = [CItem()]
        html = _render_cashflow_summary_html(s)
        self.assertIn("1.500 ₺", html)
        self.assertIn("Kira", html)

    def test_render_cashflow_charts_html(self):
        self.assertEqual(_render_cashflow_charts_html(None), "")
        s = DummySnapshot()

        class DummyQS:
            def filter(self, *args, **kwargs):
                return self

            def order_by(self, *args, **kwargs):
                return self

            def values_list(self, *args, **kwargs):
                return [(datetime.date(2025, 1, 1), 100)]

        from portfolio.models import CashFlowSnapshot

        with patch.object(CashFlowSnapshot, "objects", DummyQS()):
            html = _render_cashflow_charts_html(s)
            self.assertIn("cashflow-charts", html)

    def test_render_cashflow_comparison_charts_html(self):
        self.assertEqual(_render_cashflow_comparison_charts_html(None), "")
        c = MagicMock()
        c.base_snapshot = DummySnapshot()
        c.compare_snapshot = DummySnapshot()
        html = _render_cashflow_comparison_charts_html(c)
        self.assertIn("cashflow-comparison-charts", html)

    def test_render_savings_rate_summary_html(self):
        self.assertEqual(_render_savings_rate_summary_html(None), "")
        s = DummySnapshot()
        html = _render_savings_rate_summary_html(s)
        self.assertIn("40.00", html)

    def test_render_savings_rate_charts_html(self):
        self.assertEqual(_render_savings_rate_charts_html(None), "")
        s = DummySnapshot()

        class DummyQS:
            def filter(self, *args, **kwargs):
                return self

            def order_by(self, *args, **kwargs):
                return self

            def values_list(self, *args, **kwargs):
                return [(datetime.date(2025, 1, 1), 0.4)]

        from portfolio.models import SalarySavingsSnapshot

        with patch.object(SalarySavingsSnapshot, "objects", DummyQS()):
            html = _render_savings_rate_charts_html(s)
            self.assertIn("savings-rate-charts", html)

    def test_render_dividend_summary_html(self):
        self.assertEqual(_render_dividend_summary_html(None), "")
        s = DummySnapshot(total_amount="200", year=2025, currency="USD")
        html = _render_dividend_summary_html(s)
        self.assertIn("2025", html)

    def test_render_dividend_charts_html(self):
        self.assertEqual(_render_dividend_charts_html(None), "")
        s = DummySnapshot()
        html = _render_dividend_charts_html(s)
        self.assertIn("dividend-charts", html)

    def test_render_dividend_comparison_html(self):
        self.assertEqual(_render_dividend_comparison_html(None), "")
        c = MagicMock()
        c.base_snapshot = DummySnapshot(total_amount="100", year=2024, currency="USD")
        c.compare_snapshot = DummySnapshot(
            total_amount="200", year=2025, currency="USD"
        )
        html = _render_dividend_comparison_html(c)
        self.assertIn("100.00", html)


class BlogExtrasFiltersTests(TestCase):
    def test_absolute_url(self):
        self.assertEqual(
            blog_extras.absolute_url("/path/", "http://example.com/"),
            "http://example.com/path/",
        )
        self.assertEqual(blog_extras.absolute_url("", "http://example.com/"), "")
        self.assertEqual(blog_extras.absolute_url(None, "http://example.com/"), "")
        self.assertEqual(blog_extras.absolute_url("/path/", ""), "/path/")
        self.assertEqual(blog_extras.absolute_url("/path/", None), "/path/")
        self.assertEqual(
            blog_extras.absolute_url("path/", "http://example.com"),
            "http://example.com/path/",
        )
        self.assertEqual(
            blog_extras.absolute_url("http://other.com/path/", "http://example.com/"),
            "http://other.com/path/",
        )
        self.assertEqual(
            blog_extras.absolute_url(123, "http://example.com/"),
            "http://example.com/123",
        )

    def test_mul100(self):
        self.assertEqual(blog_extras.mul100(0.12), 12.0)
        self.assertEqual(blog_extras.mul100(None), 0)

    def test_safe_float(self):
        self.assertEqual(blog_extras.safe_float("1.23"), 1.23)
        self.assertEqual(blog_extras.safe_float(None), 0.0)
        with self.assertLogs("blog.templatetags.blog_extras", level="ERROR"):
            self.assertEqual(blog_extras.safe_float("invalid"), 0.0)

    def test_format_currency(self):
        self.assertEqual(
            blog_extras.format_currency(Decimal("1000.50"), "TRY"), "1.000,50 ₺"
        )
        self.assertEqual(blog_extras.format_currency(1000, "USD"), "1.000 $")

    def test_preload_stylesheet(self):
        html = blog_extras.preload_stylesheet("css/test.css")
        self.assertIn('link rel="preload"', html)
        self.assertIn("css/test.css", html)

    def test_render_excerpt(self):
        text = "**bold**"
        html = blog_extras.render_excerpt(text)
        self.assertIn("<strong>bold</strong>", html)

    def test_render_post_content(self):
        class MockImage:
            rendition = {
                "src": "/src.jpg",
                "srcset": "/src.jpg 1x",
                "width": 100,
                "height": 100,
            }
            alt_text = "Alt"
            caption = "Cap"

        content = "Line1\n{{ image:1 }}\nLine2"
        images = [MockImage()]

        html = blog_extras.render_post_content(content, images)
        self.assertIn("Line1", html)
        self.assertIn("<figure>", html)
        self.assertIn('src="/src.jpg"', html)
        self.assertIn("Cap", html)
        self.assertIn("Line2", html)


class RenderPostBodyTests(TestCase):
    def test_render_post_body_disclaimer(self):
        class MockPost:
            content = "Hello\n{{ legal_disclaimer }}\nWorld"
            images = MagicMock()
            images.all.return_value = []
            portfolio_snapshots = MagicMock()
            portfolio_comparisons = MagicMock()
            cashflow_snapshots = MagicMock()
            cashflow_comparisons = MagicMock()
            salary_savings_snapshots = MagicMock()
            dividend_snapshots = MagicMock()
            dividend_comparisons = MagicMock()

        post = MockPost()
        html = blog_extras.render_post_body({}, post)
        self.assertIn("YASAL UYARI", html)
        self.assertIn("Hello", html)
        self.assertIn("World", html)

    def test_render_post_body_all_markers(self):
        class MockPost:
            content = "{{ portfolio_summary }} {{ portfolio_charts }} {{ portfolio_irr_charts }} {{ portfolio_category_summary }} {{ portfolio_comparison_summary }} {{ portfolio_comparison_charts }} {{ cashflow_summary }} {{ cashflow_charts }} {{ cashflow_comparison_summary }} {{ cashflow_comparison_charts }} {{ savings_rate_summary }} {{ savings_rate_charts }} {{ dividend_summary }} {{ dividend_charts }} {{ dividend_comparison }}"
            images = MagicMock()
            images.all.return_value = []

            portfolio_snapshots = MagicMock()
            portfolio_comparisons = MagicMock()
            cashflow_snapshots = MagicMock()
            cashflow_comparisons = MagicMock()
            salary_savings_snapshots = MagicMock()
            dividend_snapshots = MagicMock()
            dividend_comparisons = MagicMock()

        post = MockPost()
        html = blog_extras.render_post_body({}, post)
        self.assertEqual(html, "")

        ctx = {"post": post}
        self.assertEqual(blog_extras.portfolio_irr_charts(ctx), "")
        self.assertEqual(blog_extras.portfolio_summary(ctx), "")
        self.assertEqual(blog_extras.portfolio_charts(ctx), "")
        self.assertEqual(blog_extras.portfolio_category_summary(ctx), "")
        self.assertEqual(blog_extras.portfolio_comparison_summary(ctx), "")
        self.assertEqual(blog_extras.portfolio_comparison_charts(ctx), "")
        self.assertEqual(blog_extras.cashflow_summary(ctx), "")
        self.assertEqual(blog_extras.cashflow_charts(ctx), "")
        self.assertEqual(blog_extras.savings_rate_summary(ctx), "")
        self.assertEqual(blog_extras.savings_rate_charts(ctx), "")
        self.assertEqual(blog_extras.cashflow_comparison_summary(ctx), "")
        self.assertEqual(blog_extras.cashflow_comparison_charts(ctx), "")
        self.assertEqual(blog_extras.dividend_summary(ctx), "")
        self.assertEqual(blog_extras.dividend_charts(ctx), "")
        self.assertEqual(blog_extras.dividend_comparison(ctx), "")
