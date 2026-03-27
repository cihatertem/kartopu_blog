from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from portfolio.models import (
    Asset,
    Portfolio,
    PortfolioTransaction,
)


class PortfolioCalculateIRRTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="irrtest@example.com",
            password="testpass123",
            first_name="IRRTest",
        )
        self.portfolio = Portfolio.objects.create(
            owner=self.user,
            name="IRR Test Portfolio",
            currency=Portfolio.Currency.TRY,
            target_value=Decimal("100000"),
        )
        self.asset_try = Asset.objects.create(
            name="TRY Asset",
            symbol="TRYAST",
            asset_type=Asset.AssetType.STOCK,
            currency=Asset.Currency.TRY,
            current_price=Decimal("100"),
            price_updated_at=timezone.now(),
        )
        self.asset_usd = Asset.objects.create(
            name="USD Asset",
            symbol="USDAST",
            asset_type=Asset.AssetType.STOCK,
            currency=Asset.Currency.USD,
            current_price=Decimal("10"),
            price_updated_at=timezone.now(),
        )

    def test_calculate_irr_no_transactions(self) -> None:
        irr = self.portfolio.calculate_irr(
            as_of_date=date(2025, 1, 1), current_value=Decimal("0")
        )
        self.assertIsNone(irr)

    def test_calculate_irr_single_buy(self) -> None:
        PortfolioTransaction.objects.create(
            asset=self.asset_try,
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            trade_date=date(2024, 1, 1),
            quantity=Decimal("10"),
            price_per_unit=Decimal("100"),  # Total cost 1000
        ).portfolios.add(self.portfolio)

        irr = self.portfolio.calculate_irr(
            as_of_date=date(2025, 1, 1), current_value=Decimal("1100")
        )
        self.assertIsNotNone(irr)
        self.assertAlmostEqual(float(irr), 10.0, places=1)

    def test_calculate_irr_buy_and_sell(self) -> None:
        PortfolioTransaction.objects.create(
            asset=self.asset_try,
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            trade_date=date(2024, 1, 1),
            quantity=Decimal("10"),
            price_per_unit=Decimal("100"),  # Outflow 1000
        ).portfolios.add(self.portfolio)

        PortfolioTransaction.objects.create(
            asset=self.asset_try,
            transaction_type=PortfolioTransaction.TransactionType.SELL,
            trade_date=date(2024, 7, 1),
            quantity=Decimal("5"),
            price_per_unit=Decimal("120"),  # Inflow 600
        ).portfolios.add(self.portfolio)

        irr = self.portfolio.calculate_irr(
            as_of_date=date(2025, 1, 1), current_value=Decimal("500")
        )
        self.assertIsNotNone(irr)
        self.assertAlmostEqual(float(irr), 14.1, places=1)

    def test_calculate_irr_with_bonus_capital_increase(self) -> None:
        PortfolioTransaction.objects.create(
            asset=self.asset_try,
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            trade_date=date(2024, 1, 1),
            quantity=Decimal("10"),
            price_per_unit=Decimal("100"),  # Outflow 1000
        ).portfolios.add(self.portfolio)

        PortfolioTransaction.objects.create(
            asset=self.asset_try,
            transaction_type=PortfolioTransaction.TransactionType.BONUS_CAPITAL_INCREASE,
            trade_date=date(2024, 6, 1),
            quantity=Decimal("0"),
            capital_increase_rate_pct=Decimal("100"),
            price_per_unit=Decimal("0"),
        ).portfolios.add(self.portfolio)

        irr = self.portfolio.calculate_irr(
            as_of_date=date(2025, 1, 1), current_value=Decimal("1200")
        )
        self.assertIsNotNone(irr)
        self.assertAlmostEqual(float(irr), 19.9, places=1)

    def test_calculate_irr_with_rights_exercised(self) -> None:
        PortfolioTransaction.objects.create(
            asset=self.asset_try,
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            trade_date=date(2024, 1, 1),
            quantity=Decimal("10"),
            price_per_unit=Decimal("100"),  # Outflow 1000
        ).portfolios.add(self.portfolio)

        PortfolioTransaction.objects.create(
            asset=self.asset_try,
            transaction_type=PortfolioTransaction.TransactionType.RIGHTS_EXERCISED,
            trade_date=date(2024, 7, 1),
            quantity=Decimal("0"),
            capital_increase_rate_pct=Decimal(
                "50"
            ),  # 50% paid increase -> 5 new shares
            price_per_unit=Decimal("20"),  # 5 shares * 20 = 100 additional outflow
        ).portfolios.add(self.portfolio)

        irr = self.portfolio.calculate_irr(
            as_of_date=date(2025, 1, 1), current_value=Decimal("1200")
        )
        self.assertIsNotNone(irr)
        self.assertAlmostEqual(float(irr), 9.5, places=1)

    def test_calculate_irr_prefetched_transactions(self) -> None:
        PortfolioTransaction.objects.create(
            asset=self.asset_try,
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            trade_date=date(2024, 1, 1),
            quantity=Decimal("10"),
            price_per_unit=Decimal("100"),  # Total cost 1000
        ).portfolios.add(self.portfolio)

        portfolio_with_prefetch = Portfolio.objects.prefetch_related(
            "transactions__asset"
        ).get(pk=self.portfolio.pk)
        self.assertTrue(hasattr(portfolio_with_prefetch, "_prefetched_objects_cache"))
        self.assertIn("transactions", portfolio_with_prefetch._prefetched_objects_cache)

        irr = portfolio_with_prefetch.calculate_irr(
            as_of_date=date(2025, 1, 1), current_value=Decimal("1100")
        )
        self.assertIsNotNone(irr)
        self.assertAlmostEqual(float(irr), 10.0, places=1)

    @patch("portfolio.models.Portfolio._get_or_fetch_fx_rate")
    def test_calculate_irr_different_currency(self, mock_get_or_fetch_fx_rate) -> None:
        mock_get_or_fetch_fx_rate.return_value = Decimal("30.0")

        PortfolioTransaction.objects.create(
            asset=self.asset_usd,
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            trade_date=date(2024, 1, 1),
            quantity=Decimal("10"),
            price_per_unit=Decimal("100"),  # Total cost 1000 USD
        ).portfolios.add(self.portfolio)

        irr = self.portfolio.calculate_irr(
            as_of_date=date(2025, 1, 1), current_value=Decimal("33000")
        )
        self.assertIsNotNone(irr)
        self.assertAlmostEqual(float(irr), 10.0, places=1)
