from decimal import Decimal
from unittest.mock import MagicMock

from django.test import TestCase

from blog.templatetags.blog_extras import _render_dividend_summary_html


class DummySnapshot:
    def __init__(
        self,
        total_amount,
        year,
        currency,
        payment_items=None,
    ):
        self.total_amount = Decimal(total_amount)
        self.year = year
        self.currency = currency

        # Mocking the RelatedManager or queryset for payment_items
        mock_qs = MagicMock()
        mock_qs.select_related.return_value.order_by.return_value = payment_items or []
        self.payment_items = mock_qs


class TestDividendSummaryHtml(TestCase):
    def test_render_dividend_summary_html(self):
        snapshot = DummySnapshot(
            total_amount="1000.00",
            year=2026,
            currency="TRY",
            payment_items=[],
        )

        html = _render_dividend_summary_html(snapshot)

        self.assertIn("1.000 ₺", html)
        self.assertIn("2026", html)


from django.template import Context, Template

from blog.templatetags import blog_extras


class BlogExtrasFiltersTests(TestCase):
    def test_absolute_url(self):
        self.assertEqual(
            blog_extras.absolute_url("/path/", "http://example.com/"),
            "http://example.com/path/",
        )
        self.assertEqual(blog_extras.absolute_url("", "http://example.com/"), "")
        self.assertEqual(blog_extras.absolute_url("/path/", ""), "/path/")

    def test_mul100(self):
        self.assertEqual(blog_extras.mul100(0.12), 12.0)
        self.assertEqual(blog_extras.mul100(None), 0)

    def test_safe_float(self):
        self.assertEqual(blog_extras.safe_float("1.23"), 1.23)
        self.assertEqual(blog_extras.safe_float(None), 0.0)
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
