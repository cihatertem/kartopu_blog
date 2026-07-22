from django.test import TestCase

from blog.services import portfolio_snapshot_queryset
from portfolio.models import PortfolioSnapshot


class PortfolioSnapshotQuerysetTests(TestCase):
    def test_basic_queryset(self):
        qs = portfolio_snapshot_queryset()
        self.assertIn("portfolio", qs.query.select_related)
        self.assertEqual(qs.query.order_by, ("snapshot_date",))
        self.assertFalse(qs._prefetch_related_lookups)

    def test_custom_base_queryset(self):
        base_qs = PortfolioSnapshot.objects.filter(total_value__gt=1000)
        qs = portfolio_snapshot_queryset(base_queryset=base_qs)

        self.assertIn("portfolio", qs.query.select_related)
        self.assertEqual(qs.query.order_by, ("snapshot_date",))

        # Check that it builds upon the base_qs
        self.assertIn("total_value", str(qs.query))

    def test_include_items(self):
        qs = portfolio_snapshot_queryset(include_items=True)
        self.assertIn("portfolio", qs.query.select_related)
        self.assertEqual(qs.query.order_by, ("snapshot_date",))
        self.assertEqual(len(qs._prefetch_related_lookups), 1)

        prefetch = qs._prefetch_related_lookups[0]
        self.assertEqual(prefetch.prefetch_through, "items")
        self.assertIn("asset", prefetch.queryset.query.select_related)

    def test_include_history(self):
        qs = portfolio_snapshot_queryset(include_history=True)
        self.assertIn("portfolio", qs.query.select_related)
        self.assertEqual(qs.query.order_by, ("snapshot_date",))
        self.assertEqual(len(qs._prefetch_related_lookups), 1)

        prefetch = qs._prefetch_related_lookups[0]
        self.assertEqual(prefetch.prefetch_through, "portfolio__snapshots")
        self.assertEqual(prefetch.to_attr, "prefetched_snapshots")
        self.assertEqual(prefetch.queryset.query.order_by, ("snapshot_date",))

    def test_include_items_and_history(self):
        qs = portfolio_snapshot_queryset(include_items=True, include_history=True)
        self.assertIn("portfolio", qs.query.select_related)
        self.assertEqual(qs.query.order_by, ("snapshot_date",))
        self.assertEqual(len(qs._prefetch_related_lookups), 2)

        prefetch_items = [
            p for p in qs._prefetch_related_lookups if p.prefetch_through == "items"
        ][0]
        self.assertIn("asset", prefetch_items.queryset.query.select_related)

        prefetch_history = [
            p
            for p in qs._prefetch_related_lookups
            if p.prefetch_through == "portfolio__snapshots"
        ][0]
        self.assertEqual(prefetch_history.to_attr, "prefetched_snapshots")
