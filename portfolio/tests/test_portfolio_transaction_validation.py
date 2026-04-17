import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from portfolio.models import Asset, Portfolio, PortfolioTransaction

User = get_user_model()


class PortfolioTransactionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="password"
        )
        self.portfolio = Portfolio.objects.create(
            owner=self.user, name="My Portfolio", target_value=Decimal("1000")
        )
        self.asset = Asset.objects.create(
            name="Stock",
            symbol="STK",
            asset_type=Asset.AssetType.STOCK,
            current_price=Decimal("100"),
        )

    def test_bonus_capital_increase_missing_rate(self):
        # Should raise validation error
        tx = PortfolioTransaction(
            asset=self.asset,
            transaction_type=PortfolioTransaction.TransactionType.BONUS_CAPITAL_INCREASE,
            trade_date=datetime.date(2024, 1, 1),
            quantity=Decimal("10"),
            price_per_unit=Decimal("10"),
        )
        with self.assertRaises(ValidationError) as context:
            tx.full_clean()
        self.assertIn(
            "Sermaye artırımı oranı 0'dan büyük olmalıdır.", str(context.exception)
        )

    def test_rights_exercised_missing_rate(self):
        tx = PortfolioTransaction(
            asset=self.asset,
            transaction_type=PortfolioTransaction.TransactionType.RIGHTS_EXERCISED,
            trade_date=datetime.date(2024, 1, 1),
            quantity=Decimal("10"),
            price_per_unit=Decimal("10"),
        )
        with self.assertRaises(ValidationError) as context:
            tx.full_clean()
        self.assertIn(
            "Sermaye artırımı oranı 0'dan büyük olmalıdır.", str(context.exception)
        )

    def test_rights_not_exercised_missing_rate(self):
        tx = PortfolioTransaction(
            asset=self.asset,
            transaction_type=PortfolioTransaction.TransactionType.RIGHTS_NOT_EXERCISED,
            trade_date=datetime.date(2024, 1, 1),
            quantity=Decimal("10"),
            price_per_unit=Decimal("10"),
        )
        with self.assertRaises(ValidationError) as context:
            tx.full_clean()
        self.assertIn(
            "Sermaye artırımı oranı 0'dan büyük olmalıdır.", str(context.exception)
        )

    def test_capital_increase_negative_rate(self):
        tx = PortfolioTransaction(
            asset=self.asset,
            transaction_type=PortfolioTransaction.TransactionType.BONUS_CAPITAL_INCREASE,
            trade_date=datetime.date(2024, 1, 1),
            quantity=Decimal("10"),
            price_per_unit=Decimal("10"),
            capital_increase_rate_pct=Decimal("-5"),
        )
        with self.assertRaises(ValidationError) as context:
            tx.full_clean()
        self.assertIn(
            "Sermaye artırımı oranı 0'dan büyük olmalıdır.", str(context.exception)
        )

    def test_buy_transaction_with_valid_data(self):
        tx = PortfolioTransaction.objects.create(
            asset=self.asset,
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            trade_date=datetime.date(2024, 1, 1),
            quantity=Decimal("10"),
            price_per_unit=Decimal("100"),
        )
        tx.portfolios.add(self.portfolio)
        self.assertEqual(tx.total_cost, Decimal("1000"))

    @patch("portfolio.models.Asset.refresh_price")
    def test_portfolio_transaction_save_handles_asset_refresh_failure(
        self, mock_refresh_price
    ):
        mock_refresh_price.side_effect = Exception("API Error")

        # Set asset price properties to None to trigger refresh_price in tx.save()
        self.asset.current_price = None
        self.asset.price_updated_at = None
        self.asset.save(update_fields=["current_price", "price_updated_at"])

        tx = PortfolioTransaction(
            asset=self.asset,
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            trade_date=datetime.date(2024, 1, 1),
            quantity=Decimal("10"),
            price_per_unit=Decimal("100"),
        )

        import logging

        # Suppress log noise by capturing the expected exception log.
        # It logs at ERROR level because log_exceptions without include_traceback defaults to logger.error.
        with self.assertLogs("portfolio.models", level=logging.ERROR) as cm:
            try:
                tx.save()
            except Exception as e:
                self.fail(f"tx.save() raised an unexpected exception: {e}")

        self.assertTrue(
            any(
                "Error updating asset price during Transaction Save" in log
                for log in cm.output
            )
        )
        mock_refresh_price.assert_called_once()
        self.assertIsNotNone(tx.pk)
