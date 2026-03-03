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
