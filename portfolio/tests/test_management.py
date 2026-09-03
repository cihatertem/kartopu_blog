from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from portfolio.models import Asset, Portfolio, PortfolioSnapshot, PortfolioTransaction

User = get_user_model()


class FillMissingIrrCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="password"
        )
        self.portfolio = Portfolio.objects.create(
            owner=self.user, name="My Portfolio", target_value=Decimal("1000")
        )

    @patch("sys.stdout.write")
    @patch("sys.stderr.write")
    def test_fill_missing_irr_command(self, mock_stderr_write, mock_stdout_write):
        PortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date="2023-01-01",
            total_value=Decimal("100"),
            total_cost=Decimal("100"),
            target_value=Decimal("1000"),
            total_return_pct=Decimal("0.0"),
            irr_pct=None,
        )
        PortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date="2023-02-01",
            total_value=Decimal("100"),
            total_cost=Decimal("100"),
            target_value=Decimal("1000"),
            total_return_pct=Decimal("0.0"),
            irr_pct=None,
        )

        def mock_update_irr_side_effect(self_obj, has_prior_snapshot=None, commit=True):
            if self_obj.snapshot_date.isoformat() == "2023-01-01":
                self_obj.irr_pct = Decimal("5.0")
                if commit:
                    self_obj.save(update_fields=["irr_pct"])
                return Decimal("5.0")
            else:
                self_obj.irr_pct = None
                if commit:
                    self_obj.save(update_fields=["irr_pct"])
                return None

        with (
            patch.object(
                PortfolioSnapshot,
                "update_irr",
                autospec=True,
                side_effect=mock_update_irr_side_effect,
            ) as mock_update_irr,
            patch.object(
                type(PortfolioSnapshot.objects),
                "bulk_update",
                autospec=True,
                side_effect=lambda self, objs, fields, **kwargs: [
                    o.save(update_fields=fields) for o in objs
                ],
            ),
        ):
            call_command("fill_missing_irr")

            self.assertEqual(mock_update_irr.call_count, 2)

            updated_snapshots = PortfolioSnapshot.objects.filter(irr_pct__isnull=False)
            self.assertEqual(updated_snapshots.count(), 1)
            self.assertEqual(updated_snapshots.first().irr_pct, Decimal("5.0"))
            self.assertEqual(
                updated_snapshots.first().snapshot_date.isoformat(), "2023-01-01"
            )

            null_snapshots = PortfolioSnapshot.objects.filter(irr_pct__isnull=True)
            self.assertEqual(null_snapshots.count(), 1)
            self.assertEqual(
                null_snapshots.first().snapshot_date.isoformat(), "2023-02-01"
            )

    @patch("sys.stdout.write")
    @patch("sys.stderr.write")
    def test_fill_missing_irr_command_exception(
        self, mock_stderr_write, mock_stdout_write
    ):
        snapshot = PortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date="2023-01-01",
            total_value=Decimal("100"),
            total_cost=Decimal("100"),
            target_value=Decimal("1000"),
            total_return_pct=Decimal("0.0"),
            irr_pct=None,
        )

        with patch.object(
            PortfolioSnapshot,
            "update_irr",
            autospec=True,
            side_effect=ValueError("Test error"),
        ) as mock_update_irr:
            call_command("fill_missing_irr")

            self.assertEqual(mock_update_irr.call_count, 1)

            # Assert that the command wrote the error to stdout
            output_calls = [call[0][0] for call in mock_stdout_write.call_args_list]
            self.assertTrue(
                any(
                    f"Error updating snapshot {snapshot}: Test error" in call
                    for call in output_calls
                )
            )


class FillMissingPurchaseItemsCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="purchase-command@example.com", password="password"
        )
        self.portfolio = Portfolio.objects.create(
            owner=self.user,
            name="Purchase Portfolio",
            target_value=Decimal("1000"),
        )
        self.asset = Asset.objects.create(
            name="Test Asset",
            symbol="TEST",
            asset_type=Asset.AssetType.STOCK,
            current_price=Decimal("100"),
            price_updated_at=timezone.now(),
        )

    def create_snapshot(self, period: str) -> PortfolioSnapshot:
        return PortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            period=period,
            snapshot_date=date(2026, 3, 31),
            total_value=Decimal("100"),
            total_cost=Decimal("100"),
            target_value=Decimal("1000"),
            total_return_pct=Decimal("0"),
        )

    def test_command_fills_only_missing_monthly_purchase_items_idempotently(self):
        monthly_snapshot = self.create_snapshot(PortfolioSnapshot.Period.MONTHLY)
        yearly_snapshot = self.create_snapshot(PortfolioSnapshot.Period.YEARLY)
        transaction = PortfolioTransaction.objects.create(
            asset=self.asset,
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            trade_date=date(2026, 3, 15),
            quantity=Decimal("2"),
            price_per_unit=Decimal("50"),
        )
        transaction.portfolios.add(self.portfolio)

        call_command("fill_missing_purchase_items")
        call_command("fill_missing_purchase_items")

        self.assertEqual(monthly_snapshot.purchase_items.count(), 1)
        self.assertEqual(
            monthly_snapshot.purchase_items.get().total_amount, Decimal("100")
        )
        self.assertFalse(yearly_snapshot.purchase_items.exists())
