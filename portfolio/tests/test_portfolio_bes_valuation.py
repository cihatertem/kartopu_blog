from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from portfolio.models import (
    Asset,
    Portfolio,
    PortfolioTransaction,
)


class PortfolioBESValuationTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="bes@example.com",
            password="testpass122",
            first_name="BES",
        )
        self.portfolio = Portfolio.objects.create(
            owner=self.user,
            name="BES Portfoy",
            currency=Portfolio.Currency.TRY,
            target_value=Decimal("99999"),
        )
        self.asset = Asset.objects.create(
            name="BES Sözleşmesi",
            symbol="",
            asset_type=Asset.AssetType.BES,
            currency=Asset.Currency.TRY,
            current_price=Decimal("149999"),
            price_updated_at=timezone.now(),
        )

    def test_bes_uses_current_price_as_total_contract_value(self) -> None:
        for month in range(1, 4):
            transaction = PortfolioTransaction.objects.create(
                asset=self.asset,
                transaction_type=PortfolioTransaction.TransactionType.BUY,
                trade_date=date(2024, month, 1),
                quantity=Decimal("1"),
                price_per_unit=Decimal("9999"),
            )
            transaction.portfolios.add(self.portfolio)

        position = self.portfolio.get_positions()[-1]

        self.assertEqual(position["quantity"], Decimal("3"))
        self.assertEqual(position["cost_basis"], Decimal("29997"))
        self.assertEqual(position["market_value"], Decimal("149999"))
