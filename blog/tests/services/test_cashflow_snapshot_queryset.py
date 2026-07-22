from django.test import TestCase

from blog.services import cashflow_snapshot_queryset
from portfolio.models import CashFlowSnapshot


class CashFlowSnapshotQuerysetTests(TestCase):
    def test_basic_queryset(self):
        qs = cashflow_snapshot_queryset()
        self.assertIn("cashflow", qs.query.select_related)
        self.assertEqual(qs.query.order_by, ("snapshot_date",))
        self.assertFalse(qs._prefetch_related_lookups)

    def test_custom_base_queryset(self):
        base_qs = CashFlowSnapshot.objects.filter(total_amount__gt=1000)
        qs = cashflow_snapshot_queryset(base_queryset=base_qs)

        self.assertIn("cashflow", qs.query.select_related)
        self.assertEqual(qs.query.order_by, ("snapshot_date",))

        # Check that it builds upon the base_qs
        self.assertIn("total_amount", str(qs.query))

    def test_include_items(self):
        qs = cashflow_snapshot_queryset(include_items=True)
        self.assertIn("cashflow", qs.query.select_related)
        self.assertEqual(qs.query.order_by, ("snapshot_date",))
        self.assertEqual(len(qs._prefetch_related_lookups), 1)

        prefetch = qs._prefetch_related_lookups[0]
        self.assertEqual(prefetch, "items")

    def test_include_history(self):
        qs = cashflow_snapshot_queryset(include_history=True)
        self.assertIn("cashflow", qs.query.select_related)
        self.assertEqual(qs.query.order_by, ("snapshot_date",))
        self.assertEqual(len(qs._prefetch_related_lookups), 1)

        prefetch = qs._prefetch_related_lookups[0]
        self.assertEqual(prefetch.prefetch_through, "cashflow__snapshots")
        self.assertEqual(prefetch.to_attr, "prefetched_snapshots")
        self.assertEqual(prefetch.queryset.query.order_by, ("snapshot_date",))

    def test_include_items_and_history(self):
        qs = cashflow_snapshot_queryset(include_items=True, include_history=True)
        self.assertIn("cashflow", qs.query.select_related)
        self.assertEqual(qs.query.order_by, ("snapshot_date",))
        self.assertEqual(len(qs._prefetch_related_lookups), 2)

        self.assertIn("items", qs._prefetch_related_lookups)

        prefetch_history = [
            p
            for p in qs._prefetch_related_lookups
            if getattr(p, "prefetch_through", None) == "cashflow__snapshots"
        ][0]
        self.assertEqual(prefetch_history.to_attr, "prefetched_snapshots")
