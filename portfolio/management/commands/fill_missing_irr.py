from django.core.management.base import BaseCommand

from portfolio.models import PortfolioSnapshot


class Command(BaseCommand):
    help = "Fills missing irr_pct values for PortfolioSnapshot objects."

    def handle(self, *args, **options):
        snapshots = PortfolioSnapshot.objects.filter(irr_pct__isnull=True)
        count = snapshots.count()
        self.stdout.write(f"Found {count} snapshots with missing irr_pct.")

        updated_count = 0
        for snapshot in snapshots:
            self.stdout.write(f"Updating snapshot: {snapshot}")
            irr = snapshot.update_irr()
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

        self.stdout.write(
            self.style.SUCCESS(
                f"Finished. Updated {updated_count} out of {count} snapshots."
            )
        )
