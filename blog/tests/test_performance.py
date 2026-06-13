import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection, reset_queries
from django.test import TestCase, override_settings

from blog.templatetags import blog_extras
from portfolio.models import (
    CashFlow,
    CashFlowComparison,
    CashFlowEntry,
    CashFlowSnapshot,
    CashFlowSnapshotItem,
)

User = get_user_model()


class CashFlowPerformanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="test@example.com")
        self.cashflow = CashFlow.objects.create(owner=self.user, name="CF")

        # Create snapshots and items
        self.s1 = CashFlowSnapshot.objects.create(
            cashflow=self.cashflow,
            period=CashFlowSnapshot.Period.MONTHLY,
            snapshot_date=datetime.date(2025, 1, 1),
            total_amount=Decimal("1000"),
        )
        CashFlowSnapshotItem.objects.create(
            snapshot=self.s1,
            category=CashFlowEntry.Category.DIVIDEND,
            amount=Decimal("1000"),
            allocation_pct=Decimal("1"),
        )

        self.s2 = CashFlowSnapshot.objects.create(
            cashflow=self.cashflow,
            period=CashFlowSnapshot.Period.MONTHLY,
            snapshot_date=datetime.date(2025, 2, 1),
            total_amount=Decimal("2000"),
        )
        CashFlowSnapshotItem.objects.create(
            snapshot=self.s2,
            category=CashFlowEntry.Category.DIVIDEND,
            amount=Decimal("2000"),
            allocation_pct=Decimal("1"),
        )

        self.comparison = CashFlowComparison.objects.create(
            base_snapshot=self.s1, compare_snapshot=self.s2
        )

    def test_redundant_iteration(self):
        # Reset queries
        reset_queries()

        # First call
        context1 = blog_extras._get_cashflow_comparison_context_data(self.comparison)
        queries1 = len(connection.queries)

        # Second call
        context2 = blog_extras._get_cashflow_comparison_context_data(self.comparison)
        queries2 = len(connection.queries)

        # print(f"Queries after 1st call: {queries1}")
        # print(f"Queries after 2nd call: {queries2}")

        # If caching works, queries should not increase significantly,
        # and we can potentially avoid redundant dictionary creation.
        self.assertEqual(queries1, queries2)
