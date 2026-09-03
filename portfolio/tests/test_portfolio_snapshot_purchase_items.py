from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from portfolio.models import Asset, Portfolio, PortfolioSnapshot, PortfolioTransaction


class PortfolioSnapshotPurchaseItemTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            email="purchase-items@example.com",
            password="testpass123",
        )
        self.portfolio = Portfolio.objects.create(
            owner=self.user,
            name="Purchase Portfolio",
            currency=Portfolio.Currency.TRY,
            target_value=Decimal("100000"),
        )

    def create_asset(self, *, symbol: str, currency: str = Asset.Currency.TRY) -> Asset:
        return Asset.objects.create(
            name=symbol,
            symbol=symbol,
            asset_type=Asset.AssetType.STOCK,
            currency=currency,
            current_price=Decimal("100"),
            price_updated_at=timezone.now(),
        )

    def create_purchase(
        self,
        asset: Asset,
        trade_date: date,
        quantity: Decimal,
        price_per_unit: Decimal,
    ) -> None:
        transaction = PortfolioTransaction.objects.create(
            asset=asset,
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            trade_date=trade_date,
            quantity=quantity,
            price_per_unit=price_per_unit,
        )
        transaction.portfolios.add(self.portfolio)

    def test_monthly_snapshot_groups_calendar_month_purchases_by_asset(self) -> None:
        stock = self.create_asset(symbol="STOCK")
        fund = Asset.objects.create(
            name="Fund",
            symbol="FUND",
            asset_type=Asset.AssetType.FON,
            currency=Asset.Currency.TRY,
            current_price=Decimal("100"),
            price_updated_at=timezone.now(),
        )
        self.create_purchase(stock, date(2026, 3, 1), Decimal("2"), Decimal("100"))
        self.create_purchase(stock, date(2026, 3, 31), Decimal("1"), Decimal("150"))
        self.create_purchase(fund, date(2026, 3, 15), Decimal("4"), Decimal("25"))
        self.create_purchase(stock, date(2026, 2, 28), Decimal("1"), Decimal("500"))
        self.create_purchase(stock, date(2026, 4, 1), Decimal("1"), Decimal("500"))

        snapshot = PortfolioSnapshot.create_snapshot(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date=date(2026, 3, 10),
        )

        amounts = dict(
            snapshot.purchase_items.values_list("asset__symbol", "total_amount")
        )
        self.assertEqual(amounts, {"STOCK": Decimal("350"), "FUND": Decimal("100")})

    @patch("portfolio.models.fetch_multiple_fx_rates_bulk")
    @patch("portfolio.models.fetch_fx_rates_bulk")
    def test_monthly_snapshot_converts_purchase_amounts_and_ignores_non_positive_totals(
        self, mock_fetch_fx_rates_bulk, mock_fetch_multiple_fx_rates_bulk
    ) -> None:
        usd_asset = self.create_asset(symbol="USD", currency=Asset.Currency.USD)
        zero_asset = self.create_asset(symbol="ZERO")
        self.create_purchase(usd_asset, date(2026, 3, 5), Decimal("2"), Decimal("10"))
        self.create_purchase(zero_asset, date(2026, 3, 6), Decimal("0"), Decimal("10"))
        mock_fetch_fx_rates_bulk.return_value = {("USD", "TRY"): Decimal("32")}
        mock_fetch_multiple_fx_rates_bulk.return_value = {
            ("USD", "TRY", date(2026, 3, 31)): Decimal("32")
        }

        snapshot = PortfolioSnapshot.create_snapshot(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date=date(2026, 3, 31),
        )

        self.assertEqual(snapshot.purchase_items.count(), 1)
        item = snapshot.purchase_items.get()
        self.assertEqual(item.asset, usd_asset)
        self.assertEqual(item.total_amount, Decimal("640"))

    def test_yearly_snapshot_does_not_create_purchase_items(self) -> None:
        asset = self.create_asset(symbol="STOCK")
        self.create_purchase(asset, date(2026, 3, 5), Decimal("1"), Decimal("100"))

        snapshot = PortfolioSnapshot.create_snapshot(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.YEARLY,
            snapshot_date=date(2026, 3, 31),
        )

        self.assertFalse(snapshot.purchase_items.exists())
