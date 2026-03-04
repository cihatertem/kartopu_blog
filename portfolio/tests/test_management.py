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
        # Create snapshots with null irr_pct
        snap1 = PortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date="2023-01-01",
            total_value=Decimal("100"),
            total_cost=Decimal("100"),
            target_value=Decimal("1000"),
            total_return_pct=Decimal("0.0"),
            irr_pct=None,
        )
        snap2 = PortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date="2023-02-01",
            total_value=Decimal("100"),
            total_cost=Decimal("100"),
            target_value=Decimal("1000"),
            total_return_pct=Decimal("0.0"),
            irr_pct=None,
        )

        # Mock update_irr to return predictable results
        with patch.object(
            PortfolioSnapshot, "update_irr", side_effect=[Decimal("5.0"), None]
        ) as mock_update_irr:
            call_command("fill_missing_irr")

            # Ensure it was called for both missing snapshots
            self.assertEqual(mock_update_irr.call_count, 2)

            # Since update_irr is mocked, the DB instances won't actually be modified in this test.
            # However, the management command's logic of finding null ones, iterating over them,
            # calling update_irr, and printing status messages is fully exercised.
