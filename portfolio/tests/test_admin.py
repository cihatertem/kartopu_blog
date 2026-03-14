from decimal import Decimal
from unittest.mock import MagicMock

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from portfolio.admin import (
    DividendSnapshotAdmin,
    PortfolioAdmin,
    PortfolioSnapshotAdmin,
    PortfolioTransactionAdmin,
    SalarySavingsEntryAdmin,
    SalarySavingsSnapshotAdmin,
)
from portfolio.models import (
    Asset,
    DividendSnapshot,
    Portfolio,
    PortfolioComparison,
    PortfolioSnapshot,
    PortfolioTransaction,
    SalarySavingsEntry,
    SalarySavingsFlow,
    SalarySavingsSnapshot,
)

User = get_user_model()


class AdminTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_superuser(
            email="admin@example.com", password="password"
        )
        self.client.login(email="admin@example.com", password="password")


class MixinsTests(AdminTestCase):
    def test_staff_owner_admin_mixin(self):
        staff_user = User.objects.create_user(
            email="staff@example.com", password="password", is_staff=True
        )
        model_admin = PortfolioAdmin(Portfolio, admin.site)
        request = self.factory.get("/")
        request.user = staff_user
        initial = model_admin.get_changeform_initial_data(request)
        self.assertEqual(initial["owner"], staff_user.pk)

    def test_snapshot_creator_admin_mixin(self):
        Portfolio.objects.create(
            owner=self.user, name="Portfolio", target_value=Decimal("1000")
        )
        model_admin = PortfolioAdmin(Portfolio, admin.site)
        model_admin.snapshot_model = PortfolioSnapshot
        model_admin.snapshot_relation_field = "portfolio"

        request = self.factory.get("/")
        request.user = self.user

        model_admin.message_user = MagicMock()
        model_admin.create_monthly_snapshot(request, Portfolio.objects.all())
        self.assertEqual(PortfolioSnapshot.objects.count(), 1)

        model_admin.create_yearly_snapshot(request, Portfolio.objects.all())
        self.assertEqual(PortfolioSnapshot.objects.count(), 2)

    def test_snapshot_swap_admin_mixin(self):
        portfolio = Portfolio.objects.create(
            owner=self.user, name="Portfolio", target_value=Decimal("1000")
        )
        base = PortfolioSnapshot.create_snapshot(
            portfolio=portfolio, period=PortfolioSnapshot.Period.MONTHLY
        )
        compare = PortfolioSnapshot.create_snapshot(
            portfolio=portfolio, period=PortfolioSnapshot.Period.YEARLY
        )
        comparison = PortfolioComparison.objects.create(
            base_snapshot=base, compare_snapshot=compare
        )

        from portfolio.admin import PortfolioComparisonAdmin

        model_admin = PortfolioComparisonAdmin(PortfolioComparison, admin.site)
        request = self.factory.get("/")
        request.user = self.user
        model_admin.message_user = MagicMock()

        model_admin.swap_snapshots(request, PortfolioComparison.objects.all())
        comparison.refresh_from_db()

        self.assertEqual(comparison.base_snapshot, compare)
        self.assertEqual(comparison.compare_snapshot, base)


class PortfolioTransactionAdminTests(AdminTestCase):
    def test_portfolio_list(self):
        portfolio1 = Portfolio.objects.create(
            owner=self.user, name="A Portfolio", target_value=Decimal("1000")
        )
        portfolio2 = Portfolio.objects.create(
            owner=self.user, name="B Portfolio", target_value=Decimal("1000")
        )
        asset = Asset.objects.create(
            name="Asset",
            asset_type=Asset.AssetType.STOCK,
            currency=Asset.Currency.TRY,
            current_price=Decimal("100"),
        )
        transaction = PortfolioTransaction.objects.create(
            asset=asset,
            trade_date="2023-01-01",
            quantity=Decimal("10"),
            price_per_unit=Decimal("100"),
        )
        transaction.portfolios.add(portfolio1, portfolio2)

        model_admin = PortfolioTransactionAdmin(PortfolioTransaction, admin.site)
        display = model_admin.portfolio_list(transaction)
        self.assertEqual(display, "A Portfolio, B Portfolio")


class PortfolioSnapshotAdminTests(AdminTestCase):
    def setUp(self):
        super().setUp()
        self.portfolio = Portfolio.objects.create(
            owner=self.user, name="Portfolio", target_value=Decimal("1000")
        )
        self.snapshot = PortfolioSnapshot.create_snapshot(
            portfolio=self.portfolio, period=PortfolioSnapshot.Period.MONTHLY
        )
        self.model_admin = PortfolioSnapshotAdmin(PortfolioSnapshot, admin.site)

    def test_make_featured(self):
        request = self.factory.get("/")
        self.model_admin.message_user = MagicMock()
        self.model_admin.make_featured(request, PortfolioSnapshot.objects.all())
        self.snapshot.refresh_from_db()
        self.assertTrue(self.snapshot.is_featured)

    def test_make_unfeatured(self):
        self.snapshot.is_featured = True
        self.snapshot.save()
        request = self.factory.get("/")
        self.model_admin.message_user = MagicMock()
        self.model_admin.make_unfeatured(request, PortfolioSnapshot.objects.all())
        self.snapshot.refresh_from_db()
        self.assertFalse(self.snapshot.is_featured)


class SalarySavingsEntryAdminTests(AdminTestCase):
    def test_savings_rate_display(self):
        flow = SalarySavingsFlow.objects.create(
            owner=self.user, name="Flow", currency="TRY"
        )
        entry1 = SalarySavingsEntry.objects.create(
            flow=flow,
            entry_date="2023-01-01",
            salary_amount=Decimal("1000"),
            savings_amount=Decimal("200"),
        )
        entry2 = SalarySavingsEntry.objects.create(
            flow=flow,
            entry_date="2023-02-01",
            salary_amount=Decimal("0"),
            savings_amount=Decimal("200"),
        )

        model_admin = SalarySavingsEntryAdmin(SalarySavingsEntry, admin.site)
        self.assertEqual(model_admin.savings_rate_display(entry1), "20.00")
        self.assertEqual(model_admin.savings_rate_display(entry2), "0.00")


class SnapshotSaveModelTests(AdminTestCase):
    def test_salary_savings_snapshot_save_model(self):
        flow = SalarySavingsFlow.objects.create(
            owner=self.user, name="Flow", currency="TRY"
        )
        SalarySavingsEntry.objects.create(
            flow=flow,
            entry_date="2023-01-01",
            salary_amount=Decimal("1000"),
            savings_amount=Decimal("200"),
        )

        model_admin = SalarySavingsSnapshotAdmin(SalarySavingsSnapshot, admin.site)
        request = self.factory.get("/")
        request.user = self.user

        import datetime

        snapshot = SalarySavingsSnapshot(
            flow=flow, snapshot_date=datetime.date(2023, 1, 31)
        )
        model_admin.save_model(request, snapshot, None, False)

        self.assertIsNotNone(snapshot.pk)
        self.assertEqual(snapshot.total_salary, Decimal("1000"))

        persisted_snapshot = SalarySavingsSnapshot.objects.get(pk=snapshot.pk)
        persisted_snapshot.name = "Updated"
        model_admin.save_model(request, persisted_snapshot, None, True)
        persisted_snapshot.refresh_from_db()
        self.assertEqual(persisted_snapshot.name, "Updated")

    def test_dividend_snapshot_save_model(self):
        model_admin = DividendSnapshotAdmin(DividendSnapshot, admin.site)
        request = self.factory.get("/")
        request.user = self.user

        import datetime

        snapshot = DividendSnapshot(
            year=2023, currency="TRY", snapshot_date=datetime.date(2023, 12, 31)
        )
        model_admin.save_model(request, snapshot, None, False)

        self.assertIsNotNone(snapshot.pk)
        self.assertEqual(snapshot.total_amount, Decimal("0"))
