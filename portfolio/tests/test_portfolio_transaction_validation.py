import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
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
        with self.assertRaises(Exception):  # Assuming ValidationError is raised
            tx.full_clean()

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
