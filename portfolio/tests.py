from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from portfolio.models import SalarySavingsEntry, SalarySavingsFlow, SalarySavingsSnapshot


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
