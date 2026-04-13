import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from portfolio.models import CashFlow, CashFlowEntry, CashFlowSnapshot

User = get_user_model()


class CashFlowSnapshotLogicTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="cashflow@example.com", password="password"
        )
        self.cashflow = CashFlow.objects.create(
            owner=self.user, name="Main CashFlow", currency=CashFlow.Currency.TRY
        )

    @patch("portfolio.models.fetch_fx_rates_bulk")
    def test_create_snapshot_multi_currency(self, mock_fetch_fx_bulk):
        # Mock FX rate: 1 USD = 30 TRY
        mock_fetch_fx_bulk.return_value = {("USD", "TRY"): Decimal("30.0")}

        # Entry in TRY
        CashFlowEntry.objects.create(
            entry_date=datetime.date(2024, 1, 10),
            category=CashFlowEntry.Category.DIVIDEND,
            amount=Decimal("100.0"),
            currency=CashFlow.Currency.TRY,
        ).cashflows.add(self.cashflow)

        # Entry in USD
        CashFlowEntry.objects.create(
            entry_date=datetime.date(2024, 1, 15),
            category=CashFlowEntry.Category.INTEREST,
            amount=Decimal("10.0"),
            currency=CashFlow.Currency.USD,
        ).cashflows.add(self.cashflow)

        # Another entry in TRY for same category
        CashFlowEntry.objects.create(
            entry_date=datetime.date(2024, 1, 20),
            category=CashFlowEntry.Category.DIVIDEND,
            amount=Decimal("50.0"),
            currency=CashFlow.Currency.TRY,
        ).cashflows.add(self.cashflow)

        snapshot = CashFlowSnapshot.create_snapshot(
            cashflow=self.cashflow,
            period=CashFlowSnapshot.Period.MONTHLY,
            snapshot_date=datetime.date(2024, 1, 31),
        )

        # Total amount: 100 (TRY) + 50 (TRY) + 10 * 30 (USD to TRY) = 150 + 300 = 450
        self.assertEqual(snapshot.total_amount, Decimal("450.0"))
        self.assertEqual(snapshot.items.count(), 2)

        dividend_item = snapshot.items.get(category=CashFlowEntry.Category.DIVIDEND)
        self.assertEqual(dividend_item.amount, Decimal("150.0"))
        # 150 / 450 = 0.33333333
        self.assertAlmostEqual(
            float(dividend_item.allocation_pct), 0.33333333, places=8
        )

        interest_item = snapshot.items.get(category=CashFlowEntry.Category.INTEREST)
        self.assertEqual(interest_item.amount, Decimal("300.0"))
        # 300 / 450 = 0.66666667
        self.assertAlmostEqual(
            float(interest_item.allocation_pct), 0.66666667, places=8
        )

    def test_create_snapshot_date_range_monthly(self):
        # Entry within range
        CashFlowEntry.objects.create(
            entry_date=datetime.date(2024, 1, 15),
            category=CashFlowEntry.Category.OTHER,
            amount=Decimal("100.0"),
            currency=CashFlow.Currency.TRY,
        ).cashflows.add(self.cashflow)

        # Entry outside range (previous month)
        CashFlowEntry.objects.create(
            entry_date=datetime.date(2023, 12, 31),
            category=CashFlowEntry.Category.OTHER,
            amount=Decimal("50.0"),
            currency=CashFlow.Currency.TRY,
        ).cashflows.add(self.cashflow)

        # Entry outside range (next month)
        CashFlowEntry.objects.create(
            entry_date=datetime.date(2024, 2, 1),
            category=CashFlowEntry.Category.OTHER,
            amount=Decimal("200.0"),
            currency=CashFlow.Currency.TRY,
        ).cashflows.add(self.cashflow)

        snapshot = CashFlowSnapshot.create_snapshot(
            cashflow=self.cashflow,
            period=CashFlowSnapshot.Period.MONTHLY,
            snapshot_date=datetime.date(2024, 1, 31),
        )

        self.assertEqual(snapshot.total_amount, Decimal("100.0"))

    def test_create_snapshot_date_range_yearly(self):
        # Entry within range
        CashFlowEntry.objects.create(
            entry_date=datetime.date(2024, 6, 15),
            category=CashFlowEntry.Category.OTHER,
            amount=Decimal("100.0"),
            currency=CashFlow.Currency.TRY,
        ).cashflows.add(self.cashflow)

        # Entry outside range (previous year)
        CashFlowEntry.objects.create(
            entry_date=datetime.date(2023, 12, 31),
            category=CashFlowEntry.Category.OTHER,
            amount=Decimal("50.0"),
            currency=CashFlow.Currency.TRY,
        ).cashflows.add(self.cashflow)

        snapshot = CashFlowSnapshot.create_snapshot(
            cashflow=self.cashflow,
            period=CashFlowSnapshot.Period.YEARLY,
            snapshot_date=datetime.date(2024, 12, 31),
        )

        self.assertEqual(snapshot.total_amount, Decimal("100.0"))

    @patch("portfolio.models.fetch_fx_rates_bulk")
    def test_create_snapshot_empty_entries(self, mock_fetch_fx_bulk):
        snapshot = CashFlowSnapshot.create_snapshot(
            cashflow=self.cashflow,
            period=CashFlowSnapshot.Period.MONTHLY,
            snapshot_date=datetime.date(2024, 1, 31),
        )
        self.assertEqual(snapshot.total_amount, Decimal("0"))
        self.assertEqual(snapshot.items.count(), 0)
        mock_fetch_fx_bulk.assert_not_called()
