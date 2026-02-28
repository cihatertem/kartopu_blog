from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from portfolio.models import (
    Asset,
    Portfolio,
    PortfolioTransaction,
)


class PortfolioCorporateActionTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="corporate@example.com",
            password="testpass123",
            first_name="Corporate",
        )
        self.portfolio = Portfolio.objects.create(
            owner=self.user,
            name="Kurumsal Eylem Portfoy",
            currency=Portfolio.Currency.TRY,
            target_value=Decimal("100000"),
        )
        self.asset = Asset.objects.create(
            name="Corporate Asset",
            symbol="",
            asset_type=Asset.AssetType.STOCK,
            currency=Asset.Currency.TRY,
            current_price=Decimal("10"),
            price_updated_at=timezone.now(),
        )

    def _create_transaction(
        self,
        *,
        transaction_type: str,
        quantity: str,
        price_per_unit: str,
        trade_date: date,
        capital_increase_rate_pct: str | None = None,
    ) -> None:
        transaction = PortfolioTransaction.objects.create(
            asset=self.asset,
            transaction_type=transaction_type,
            trade_date=trade_date,
            quantity=Decimal(quantity),
            capital_increase_rate_pct=(
                Decimal(capital_increase_rate_pct)
                if capital_increase_rate_pct is not None
                else None
            ),
            price_per_unit=Decimal(price_per_unit),
        )
        transaction.portfolios.add(self.portfolio)

    def test_bonus_capital_increase_updates_quantity_without_changing_cost_basis(
        self,
    ) -> None:
        self._create_transaction(
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            quantity="100",
            price_per_unit="10",
            trade_date=date(2025, 1, 1),
        )
        self._create_transaction(
            transaction_type=PortfolioTransaction.TransactionType.BONUS_CAPITAL_INCREASE,
            quantity="0",
            price_per_unit="0",
            trade_date=date(2025, 2, 1),
            capital_increase_rate_pct="100",
        )

        position = self.portfolio.get_positions()[0]

        self.assertEqual(position["quantity"], Decimal("200"))
        self.assertEqual(position["cost_basis"], Decimal("1000"))
        self.assertEqual(position["average_cost"], Decimal("5"))

    def test_paid_capital_increase_with_rights_exercised_increases_cost_basis(
        self,
    ) -> None:
        self._create_transaction(
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            quantity="100",
            price_per_unit="10",
            trade_date=date(2025, 1, 1),
        )
        self._create_transaction(
            transaction_type=PortfolioTransaction.TransactionType.RIGHTS_EXERCISED,
            quantity="0",
            price_per_unit="8",
            trade_date=date(2025, 2, 1),
            capital_increase_rate_pct="50",
        )

        position = self.portfolio.get_positions()[0]

        self.assertEqual(position["quantity"], Decimal("150"))
        self.assertEqual(position["cost_basis"], Decimal("1400"))
        self.assertEqual(
            position["average_cost"], Decimal("9.333333333333333333333333333")
        )

    def test_paid_capital_increase_without_rights_exercised_records_value_loss(
        self,
    ) -> None:
        self._create_transaction(
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            quantity="100",
            price_per_unit="10",
            trade_date=date(2025, 1, 1),
        )
        self._create_transaction(
            transaction_type=PortfolioTransaction.TransactionType.RIGHTS_NOT_EXERCISED,
            quantity="0",
            price_per_unit="2",
            trade_date=date(2025, 2, 1),
            capital_increase_rate_pct="100",
        )

        position = self.portfolio.get_positions()[0]

        self.assertEqual(position["quantity"], Decimal("100"))
        self.assertEqual(position["cost_basis"], Decimal("1000"))
        self.assertEqual(position["average_cost"], Decimal("10"))
        self.assertEqual(position["market_value"], Decimal("800"))
        self.assertEqual(position["gain_loss"], Decimal("-200"))

    def test_bonus_capital_increase_uses_rate_for_automatic_quantity_calculation(
        self,
    ) -> None:
        self._create_transaction(
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            quantity="20",
            price_per_unit="100",
            trade_date=date(2025, 1, 1),
        )
        self._create_transaction(
            transaction_type=PortfolioTransaction.TransactionType.BONUS_CAPITAL_INCREASE,
            quantity="0",
            price_per_unit="0",
            trade_date=date(2025, 2, 1),
            capital_increase_rate_pct="900",
        )

        position = self.portfolio.get_positions()[0]

        self.assertEqual(position["quantity"], Decimal("200"))
        self.assertEqual(position["cost_basis"], Decimal("2000"))
        self.assertEqual(position["average_cost"], Decimal("10"))
