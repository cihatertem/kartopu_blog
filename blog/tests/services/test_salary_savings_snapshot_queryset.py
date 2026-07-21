from django.db.models.query import QuerySet
from django.test import TestCase

from blog.services import salary_savings_snapshot_queryset
from portfolio.models import SalarySavingsFlow, SalarySavingsSnapshot


class SalarySavingsSnapshotQuerysetTests(TestCase):
    def test_basic_queryset(self):
        qs = salary_savings_snapshot_queryset()
        self.assertIn("flow", qs.query.select_related)
        self.assertEqual(qs.query.order_by, ("snapshot_date",))
        self.assertFalse(qs._prefetch_related_lookups)

    def test_custom_base_queryset(self):
        base_qs = SalarySavingsSnapshot.objects.filter(total_salary__gt=1000)
        qs = salary_savings_snapshot_queryset(base_queryset=base_qs)

        self.assertIn("flow", qs.query.select_related)
        self.assertEqual(qs.query.order_by, ("snapshot_date",))

        # Check that it builds upon the base_qs
        self.assertIn("total_salary", str(qs.query))

    def test_include_history(self):
        qs = salary_savings_snapshot_queryset(include_history=True)
        self.assertIn("flow", qs.query.select_related)
        self.assertEqual(qs.query.order_by, ("snapshot_date",))
        self.assertEqual(len(qs._prefetch_related_lookups), 1)

        prefetch = qs._prefetch_related_lookups[0]
        self.assertEqual(prefetch.prefetch_through, "flow__snapshots")
        self.assertEqual(prefetch.to_attr, "prefetched_snapshots")
        self.assertEqual(prefetch.queryset.query.order_by, ("snapshot_date",))
