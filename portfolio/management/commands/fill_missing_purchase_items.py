from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Exists, OuterRef

from portfolio.models import PortfolioSnapshot, PortfolioSnapshotPurchaseItem


class Command(BaseCommand):
    help = "Fills missing monthly purchase items for PortfolioSnapshot objects."

    def handle(self, *args, **options):
        purchase_items_subquery = PortfolioSnapshotPurchaseItem.objects.filter(
            snapshot_id=OuterRef("pk")
        )
        snapshots = (
            PortfolioSnapshot.objects.filter(period=PortfolioSnapshot.Period.MONTHLY)
            .annotate(has_purchase_items=Exists(purchase_items_subquery))
            .filter(has_purchase_items=False)
            .select_related("portfolio")
            .order_by("pk")
        )

        created_count = 0
        for snapshot in snapshots.iterator(chunk_size=100):
            with transaction.atomic():
                if snapshot.purchase_items.exists():
                    continue
                PortfolioSnapshot._create_purchase_items(snapshot)
                if snapshot.purchase_items.exists():
                    created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished. Created purchase items for {created_count} snapshots."
            )
        )