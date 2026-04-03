from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from portfolio.models import Portfolio, PortfolioSnapshot

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

        def mock_update_irr_side_effect(self_obj):
            if self_obj.snapshot_date.isoformat() == "2023-01-01":
                self_obj.irr_pct = Decimal("5.0")
                self_obj.save(update_fields=["irr_pct"])
                return Decimal("5.0")
            else:
                self_obj.irr_pct = None
                self_obj.save(update_fields=["irr_pct"])
                return None

        with patch.object(
            PortfolioSnapshot,
            "update_irr",
            autospec=True,
            side_effect=mock_update_irr_side_effect,
        ) as mock_update_irr:
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
            side_effect=Exception("Test error"),
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
