from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from portfolio.models import (
    Asset,
    Portfolio,
    PortfolioSnapshot,
    PortfolioTransaction,
)


class PortfolioSnapshotIRRTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="portfolio@example.com",
            password="testpass123",
            first_name="Portfolio",
        )
        self.portfolio = Portfolio.objects.create(
            owner=self.user,
            name="Test Portfoy",
            currency=Portfolio.Currency.TRY,
            target_value=Decimal("100000"),
        )
        self.asset = Asset.objects.create(
            name="Test Asset",
            symbol="",
            asset_type=Asset.AssetType.STOCK,
            currency=Asset.Currency.TRY,
            current_price=Decimal("100"),
            price_updated_at=timezone.now(),
        )
        transaction = PortfolioTransaction.objects.create(
            asset=self.asset,
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            trade_date=date(2025, 12, 30),
            quantity=Decimal("10"),
            price_per_unit=Decimal("100"),
        )
        transaction.portfolios.add(self.portfolio)

    def test_first_snapshot_irr_is_skipped(self) -> None:
        first_snapshot = PortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date=date(2025, 12, 31),
            total_value=Decimal("1100"),
            total_cost=Decimal("1000"),
            target_value=self.portfolio.target_value,
            total_return_pct=Decimal("0.1"),
        )

        irr = first_snapshot.update_irr()

        self.assertIsNone(irr)
        first_snapshot.refresh_from_db()
        self.assertIsNone(first_snapshot.irr_pct)

    def test_second_snapshot_calculates_irr(self) -> None:
        first_snapshot = PortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date=date(2025, 12, 31),
            total_value=Decimal("1100"),
            total_cost=Decimal("1000"),
            target_value=self.portfolio.target_value,
            total_return_pct=Decimal("0.1"),
        )
        first_snapshot.update_irr()

        second_snapshot = PortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date=date(2026, 1, 31),
            total_value=Decimal("1200"),
            total_cost=Decimal("1000"),
            target_value=self.portfolio.target_value,
            total_return_pct=Decimal("0.2"),
        )

        irr = second_snapshot.update_irr()

        self.assertIsNotNone(irr)
        second_snapshot.refresh_from_db()
        self.assertIsNotNone(second_snapshot.irr_pct)
