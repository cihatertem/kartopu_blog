from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from portfolio.models import Asset, Portfolio, PortfolioSnapshot, PortfolioTransaction


class PortfolioSnapshotCurrencyConversionTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="snapshot-currency@example.com",
            password="testpass123",
            first_name="Snapshot",
        )
        self.portfolio = Portfolio.objects.create(
            owner=self.user,
            name="TRY Portfolio",
            currency=Portfolio.Currency.TRY,
            target_value=Decimal("100000"),
        )
        self.asset_usd = Asset.objects.create(
            name="USD Asset",
            symbol="",
            asset_type=Asset.AssetType.STOCK,
            currency=Asset.Currency.USD,
            current_price=Decimal("10"),
            price_updated_at=timezone.now(),
        )
        tx = PortfolioTransaction.objects.create(
            asset=self.asset_usd,
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            trade_date=date(2026, 3, 1),
            quantity=Decimal("5"),
            price_per_unit=Decimal("8"),
        )
        tx.portfolios.add(self.portfolio)

    @patch("portfolio.models.fetch_fx_rates_bulk")
    def test_snapshot_converts_asset_prices_to_portfolio_currency(
        self, mock_fetch_fx_rates_bulk
    ) -> None:
        mock_fetch_fx_rates_bulk.return_value = {("USD", "TRY"): Decimal("32")}

        snapshot = PortfolioSnapshot.create_snapshot(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date=date(2026, 3, 31),
        )

        self.assertEqual(snapshot.total_cost, Decimal("1280"))
        self.assertEqual(snapshot.total_value, Decimal("1600"))

        item = snapshot.items.get()
        self.assertEqual(item.current_price, Decimal("320"))
        self.assertEqual(item.market_value, Decimal("1600"))
