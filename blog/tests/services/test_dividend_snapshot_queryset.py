from django.test import TestCase

from blog.services import dividend_snapshot_queryset
from portfolio.models import DividendSnapshot


class DividendSnapshotQuerysetTests(TestCase):
    def test_basic_queryset(self):
        qs = dividend_snapshot_queryset()
        self.assertEqual(qs.query.order_by, ("-year", "-created_at"))
        self.assertFalse(qs._prefetch_related_lookups)

    def test_custom_base_queryset(self):
        base_qs = DividendSnapshot.objects.filter(year=2023)
        qs = dividend_snapshot_queryset(base_queryset=base_qs)

        self.assertEqual(qs.query.order_by, ("-year", "-created_at"))
        self.assertIn("2023", str(qs.query))

    def test_include_asset_items(self):
        qs = dividend_snapshot_queryset(include_asset_items=True)
        self.assertEqual(qs.query.order_by, ("-year", "-created_at"))
        self.assertEqual(len(qs._prefetch_related_lookups), 1)

        prefetch = qs._prefetch_related_lookups[0]
        self.assertEqual(prefetch.prefetch_through, "asset_items")
        self.assertIn("asset", prefetch.queryset.query.select_related)

    def test_include_payment_items(self):
        qs = dividend_snapshot_queryset(include_payment_items=True)
        self.assertEqual(qs.query.order_by, ("-year", "-created_at"))
        self.assertEqual(len(qs._prefetch_related_lookups), 1)

        prefetch = qs._prefetch_related_lookups[0]
        self.assertEqual(prefetch.prefetch_through, "payment_items")
        self.assertIn("asset", prefetch.queryset.query.select_related)

    def test_include_both_items(self):
        qs = dividend_snapshot_queryset(
            include_asset_items=True, include_payment_items=True
        )
        self.assertEqual(qs.query.order_by, ("-year", "-created_at"))
        self.assertEqual(len(qs._prefetch_related_lookups), 2)

        prefetch_asset = [
            p
            for p in qs._prefetch_related_lookups
            if p.prefetch_through == "asset_items"
        ][0]
        self.assertIn("asset", prefetch_asset.queryset.query.select_related)

        prefetch_payment = [
            p
            for p in qs._prefetch_related_lookups
            if p.prefetch_through == "payment_items"
        ][0]
        self.assertIn("asset", prefetch_payment.queryset.query.select_related)
