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
    SalarySavingsEntry,
    SalarySavingsFlow,
    SalarySavingsSnapshot,
)


class SalarySavingsSnapshotTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="salary@example.com",
            password="testpass123",
            first_name="Salary",
        )
        self.flow = SalarySavingsFlow.objects.create(
            owner=self.user,
            name="Maaş Akışı",
            currency=SalarySavingsFlow.Currency.TRY,
        )

    def test_monthly_snapshot_aggregates_entries_and_rate(self) -> None:
        SalarySavingsEntry.objects.create(
            flow=self.flow,
            entry_date=date(2026, 1, 5),
            salary_amount=Decimal("10000"),
            savings_amount=Decimal("4000"),
        )
        SalarySavingsEntry.objects.create(
            flow=self.flow,
            entry_date=date(2026, 1, 18),
            salary_amount=Decimal("2000"),
            savings_amount=Decimal("600"),
        )
        SalarySavingsEntry.objects.create(
            flow=self.flow,
            entry_date=date(2025, 12, 31),
            salary_amount=Decimal("999"),
            savings_amount=Decimal("999"),
        )
        SalarySavingsEntry.objects.create(
            flow=self.flow,
            entry_date=date(2026, 1, 25),
            salary_amount=Decimal("500"),
            savings_amount=Decimal("500"),
        )

        snapshot = SalarySavingsSnapshot.create_snapshot(
            flow=self.flow,
            snapshot_date=date(2026, 1, 20),
        )

        self.assertEqual(snapshot.total_salary, Decimal("12000"))
        self.assertEqual(snapshot.total_savings, Decimal("4600"))
        self.assertEqual(snapshot.savings_rate, Decimal("4600") / Decimal("12000"))


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


class PortfolioBESValuationTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="bes@example.com",
            password="testpass123",
            first_name="BES",
        )
        self.portfolio = Portfolio.objects.create(
            owner=self.user,
            name="BES Portfoy",
            currency=Portfolio.Currency.TRY,
            target_value=Decimal("100000"),
        )
        self.asset = Asset.objects.create(
            name="BES Sözleşmesi",
            symbol="",
            asset_type=Asset.AssetType.BES,
            currency=Asset.Currency.TRY,
            current_price=Decimal("150000"),
            price_updated_at=timezone.now(),
        )

    def test_bes_uses_current_price_as_total_contract_value(self) -> None:
        for month in range(1, 4):
            transaction = PortfolioTransaction.objects.create(
                asset=self.asset,
                transaction_type=PortfolioTransaction.TransactionType.BUY,
                trade_date=date(2025, month, 1),
                quantity=Decimal("1"),
                price_per_unit=Decimal("10000"),
            )
            transaction.portfolios.add(self.portfolio)

        position = self.portfolio.get_positions()[0]

        self.assertEqual(position["quantity"], Decimal("3"))
        self.assertEqual(position["cost_basis"], Decimal("30000"))
        self.assertEqual(position["market_value"], Decimal("150000"))
