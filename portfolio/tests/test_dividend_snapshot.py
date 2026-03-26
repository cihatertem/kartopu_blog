import datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from portfolio.models import Asset, DividendPayment, DividendSnapshot


class DividendSnapshotTests(TestCase):
    def setUp(self):
        self.asset_usd = Asset.objects.create(
            name="Apple",
            symbol="AAPL",
            currency=Asset.Currency.USD,
            asset_type=Asset.AssetType.STOCK,
            current_price=Decimal("150.00"),
        )
        self.asset_try = Asset.objects.create(
            name="Eregli",
            symbol="EREGL",
            currency=Asset.Currency.TRY,
            asset_type=Asset.AssetType.BIST,
            current_price=Decimal("40.00"),
        )

    @patch("portfolio.models.fetch_fx_rate")
    @patch("portfolio.models.fetch_fx_rates_bulk")
    def test_dividend_snapshot_uses_saved_dividends(
        self, mock_fetch_fx_rates_bulk, mock_fetch_fx_rate
    ):
        mock_fetch_fx_rate.return_value = Decimal("30.00")
        mock_fetch_fx_rates_bulk.return_value = {("USD", "TRY"): Decimal("30.00")}

        payment_usd = DividendPayment.objects.create(
            asset=self.asset_usd,
            payment_date=datetime.date(2023, 1, 15),
            share_count=Decimal("10"),
            net_dividend_per_share=Decimal("1.00"),  # Total: $10
            average_cost=Decimal("100.00"),
            last_close_price=Decimal("140.00"),
        )

        self.assertEqual(payment_usd.dividends.count(), 3)
        div_try = payment_usd.dividends.get(currency=Asset.Currency.TRY)
        self.assertEqual(div_try.total_net_amount, Decimal("300.00"))

        mock_fetch_fx_rate.return_value = Decimal("40.00")
        mock_fetch_fx_rates_bulk.return_value = {("USD", "TRY"): Decimal("40.00")}

        snapshot = DividendSnapshot.create_snapshot(
            year=2023,
            currency=Asset.Currency.TRY,
            snapshot_date=datetime.date(2023, 12, 31),
        )

        self.assertEqual(snapshot.total_amount, Decimal("300.00"))

        item = snapshot.payment_items.first()
        self.assertIsNotNone(item)
        self.assertEqual(item.total_net_amount, Decimal("300.00"))

        self.assertEqual(
            item.dividend_yield_on_payment_price,
            round(Decimal("1.00") / Decimal("140.00"), 8),
        )
        self.assertEqual(
            item.dividend_yield_on_average_cost,
            round(Decimal("1.00") / Decimal("100.00"), 8),
        )

    @patch("portfolio.models.fetch_fx_rate")
    @patch("portfolio.models.fetch_fx_rates_bulk")
    def test_dividend_snapshot_fallback_when_dividend_missing(
        self, mock_fetch_fx_rates_bulk, mock_fetch_fx_rate
    ):
        mock_fetch_fx_rate.return_value = Decimal("30.00")
        mock_fetch_fx_rates_bulk.return_value = {("USD", "TRY"): Decimal("30.00")}

        payment_usd = DividendPayment.objects.create(
            asset=self.asset_usd,
            payment_date=datetime.date(2023, 1, 15),
            share_count=Decimal("10"),
            net_dividend_per_share=Decimal("1.00"),
            average_cost=Decimal("100.00"),
            last_close_price=Decimal("140.00"),
        )

        self.assertEqual(payment_usd.dividends.count(), 3)
        div_try = payment_usd.dividends.get(currency=Asset.Currency.TRY)
        self.assertEqual(div_try.total_net_amount, Decimal("300.00"))

        payment_usd.dividends.all().delete()

        mock_fetch_fx_rate.return_value = Decimal("40.00")
        mock_fetch_fx_rates_bulk.return_value = {("USD", "TRY"): Decimal("40.00")}

        snapshot = DividendSnapshot.create_snapshot(
            year=2023,
            currency=Asset.Currency.TRY,
            snapshot_date=datetime.date(2023, 12, 31),
        )

        self.assertEqual(snapshot.total_amount, Decimal("400.00"))
