import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from portfolio.models import (
    SalarySavingsEntry,
    SalarySavingsFlow,
    SalarySavingsSnapshot,
)

User = get_user_model()


class SalarySavingsBulkSnapshotTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="salary@example.com", password="password"
        )
        self.flow1 = SalarySavingsFlow.objects.create(
            owner=self.user, name="Flow 1", currency=SalarySavingsFlow.Currency.TRY
        )
        self.flow2 = SalarySavingsFlow.objects.create(
            owner=self.user, name="Flow 2", currency=SalarySavingsFlow.Currency.TRY
        )

    def test_bulk_create_snapshots(self):
        # Data for flow 1
        SalarySavingsEntry.objects.create(
            flow=self.flow1,
            entry_date=datetime.date(2024, 1, 10),
            salary_amount=Decimal("10000.0"),
            savings_amount=Decimal("2000.0"),
        )
        # Data for flow 2
        SalarySavingsEntry.objects.create(
            flow=self.flow2,
            entry_date=datetime.date(2024, 1, 15),
            salary_amount=Decimal("20000.0"),
            savings_amount=Decimal("5000.0"),
        )

        snapshots = SalarySavingsSnapshot.bulk_create_snapshots(
            flows=[self.flow1, self.flow2],
            snapshot_date=datetime.date(2024, 1, 31),
        )

        self.assertEqual(len(snapshots), 2)
        self.assertEqual(SalarySavingsSnapshot.objects.count(), 2)

        s1 = SalarySavingsSnapshot.objects.get(flow=self.flow1)
        self.assertEqual(s1.total_salary, Decimal("10000.0"))
        self.assertEqual(s1.total_savings, Decimal("2000.0"))
        self.assertEqual(s1.savings_rate, Decimal("0.2"))

        s2 = SalarySavingsSnapshot.objects.get(flow=self.flow2)
        self.assertEqual(s2.total_salary, Decimal("20000.0"))
        self.assertEqual(s2.total_savings, Decimal("5000.0"))
        self.assertEqual(s2.savings_rate, Decimal("0.25"))

    def test_bulk_create_snapshots_duplicate_names_slugs(self):
        # Both flows having same name (edge case for slug generation)
        flow_a = SalarySavingsFlow.objects.create(owner=self.user, name="Same Name")
        flow_b = SalarySavingsFlow.objects.create(owner=self.user, name="Same Name")

        snapshots = SalarySavingsSnapshot.bulk_create_snapshots(
            flows=[flow_a, flow_b],
            snapshot_date=datetime.date(2024, 1, 31),
            name="Same Snapshot Name",
        )

        self.assertEqual(len(snapshots), 2)
        # Verify both have unique slugs
        self.assertNotEqual(snapshots[0].slug, snapshots[1].slug)
        # Since they have the same base name 'Same Snapshot Name', check that both have a '#hash' part
        self.assertTrue(snapshots[0].slug.startswith("same-snapshot-name#"))
        self.assertTrue(snapshots[1].slug.startswith("same-snapshot-name#"))

    @patch(
        "core.services.portfolio.generate_unique_slug",
        side_effect=["salary-flow-1", "salary-flow-2"],
    )
    def test_bulk_create_snapshots_uses_single_entry_aggregate_query(
        self, mock_generate_unique_slug
    ):
        SalarySavingsEntry.objects.create(
            flow=self.flow1,
            entry_date=datetime.date(2024, 1, 10),
            salary_amount=Decimal("10000.0"),
            savings_amount=Decimal("2000.0"),
        )
        SalarySavingsEntry.objects.create(
            flow=self.flow2,
            entry_date=datetime.date(2024, 1, 15),
            salary_amount=Decimal("20000.0"),
            savings_amount=Decimal("5000.0"),
        )

        with CaptureQueriesContext(connection) as captured_queries:
            SalarySavingsSnapshot.bulk_create_snapshots(
                flows=[self.flow1, self.flow2],
                snapshot_date=datetime.date(2024, 1, 31),
            )

        entry_queries = [
            query_info["sql"]
            for query_info in captured_queries.captured_queries
            if "portfolio_salarysavingsentry" in query_info["sql"].lower()
        ]

        self.assertEqual(mock_generate_unique_slug.call_count, 2)
        self.assertEqual(len(entry_queries), 1)
        self.assertIn("group by", entry_queries[0].lower())
