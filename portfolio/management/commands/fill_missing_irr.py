from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from portfolio.models import PortfolioSnapshot


class Command(BaseCommand):
    help = "Fills missing irr_pct values for PortfolioSnapshot objects."

    def handle(self, *args, **options):
        prior_snapshot_subquery = (
            PortfolioSnapshot.objects.filter(portfolio_id=OuterRef("portfolio_id"))
            .exclude(pk=OuterRef("pk"))
            .filter(
                Q(snapshot_date__lt=OuterRef("snapshot_date"))
                | Q(
                    snapshot_date=OuterRef("snapshot_date"),
                    created_at__lt=OuterRef("created_at"),
                )
            )
        )

        snapshots = (
            PortfolioSnapshot.objects.filter(irr_pct__isnull=True)
            .select_related("portfolio")
            .prefetch_related("portfolio__transactions__asset")
            .annotate(has_prior_snapshot=Exists(prior_snapshot_subquery))
        )
        count = snapshots.count()
        self.stdout.write(f"Found {count} snapshots with missing irr_pct.")

        updated_count = 0
        snapshots_to_update = []
        for snapshot in snapshots:
            self.stdout.write(f"Updating snapshot: {snapshot}")
            try:
                irr = snapshot.update_irr(
                    has_prior_snapshot=snapshot.has_prior_snapshot, commit=False
                )
                snapshot.updated_at = timezone.now()
                snapshots_to_update.append(snapshot)

                if irr is not None:
                    self.stdout.write(
                        self.style.SUCCESS(f"Successfully updated IRR to {irr:.2f}%")
                    )
                    updated_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "Could not calculate IRR (possibly insufficient data)"
                        )
                    )
            except (ValueError, TypeError, ArithmeticError) as e:
                self.stdout.write(
                    self.style.ERROR(f"Error updating snapshot {snapshot}: {e}")
                )

        if snapshots_to_update:
            PortfolioSnapshot.objects.bulk_update(
                snapshots_to_update, fields=["irr_pct", "updated_at"], batch_size=1000
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished. Updated {updated_count} out of {count} snapshots."
            )
        )
