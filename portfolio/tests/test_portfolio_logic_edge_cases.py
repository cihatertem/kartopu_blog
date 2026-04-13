from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from portfolio.models import Asset, Portfolio, PortfolioTransaction
from portfolio.services import calculate_xirr

User = get_user_model()


class PortfolioLogicEdgeCaseTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="edgecase@example.com", password="password"
        )
        self.portfolio = Portfolio.objects.create(
            owner=self.user,
            name="Edge Case Portfolio",
            target_value=Decimal("10000"),
            currency=Portfolio.Currency.TRY,
        )
        self.asset_usd = Asset.objects.create(
            name="US Stock",
            symbol="USSTK",
            asset_type=Asset.AssetType.STOCK,
            currency=Asset.Currency.USD,
            current_price=Decimal("100"),
        )
        cache.clear()

    @patch("portfolio.models.fetch_fx_rate")
    def test_get_or_fetch_fx_rate_fallback(self, mock_fetch: MagicMock) -> None:
        """Test that _get_or_fetch_fx_rate defaults to 1 when fetch fails."""
        mock_fetch.return_value = None
        fx_rates: dict[tuple[str, str, date | None], Decimal] = {}

        # Should call fetch_fx_rate, get None, and fallback to 1
        rate = self.portfolio._get_or_fetch_fx_rate(
            fx_rates, "USD", "TRY", date(2024, 1, 1)
        )

        self.assertEqual(rate, Decimal("1"))
        self.assertEqual(fx_rates[("USD", "TRY", date(2024, 1, 1))], Decimal("1"))
        mock_fetch.assert_called_once()

    @patch("portfolio.models.fetch_multiple_fx_rates_bulk")
    def test_prefetch_fx_rates_mixed_cache(self, mock_bulk_fetch: MagicMock) -> None:
        """Test prefetching when some rates are already in cache."""
        # 1. Put one rate in cache
        cache_key_cached = f"fx_rate_USD_TRY_{date(2024, 1, 1).isoformat()}"
        cache.set(cache_key_cached, Decimal("30.5"))

        # 2. Setup transactions
        tx1 = PortfolioTransaction(
            asset=self.asset_usd,
            trade_date=date(2024, 1, 1),
            quantity=Decimal("10"),
            price_per_unit=Decimal("100"),
        )
        tx2 = PortfolioTransaction(
            asset=self.asset_usd,
            trade_date=date(2024, 1, 2),
            quantity=Decimal("10"),
            price_per_unit=Decimal("100"),
        )

        # 3. Mock bulk fetch for the missing one
        mock_bulk_fetch.return_value = {
            ("USD", "TRY", date(2024, 1, 2)): Decimal("31.0")
        }

        fx_rates: dict[tuple[str, str, date | None], Decimal] = {}
        self.portfolio._prefetch_fx_rates([tx1, tx2], fx_rates)

        # Verify both are in fx_rates
        self.assertEqual(fx_rates[("USD", "TRY", date(2024, 1, 1))], Decimal("30.5"))
        self.assertEqual(fx_rates[("USD", "TRY", date(2024, 1, 2))], Decimal("31.0"))

        # Verify bulk fetch was only called with the missing date
        # The key in pairs_by_date is date | None
        call_args = mock_bulk_fetch.call_args[0][0]
        self.assertIn(date(2024, 1, 2), call_args)
        self.assertNotIn(date(2024, 1, 1), call_args)

    def test_calculate_capital_increase_quantity_edge_cases(self) -> None:
        """Test _calculate_capital_increase_quantity with various inputs."""
        # Zero quantity
        res = Portfolio._calculate_capital_increase_quantity(
            current_quantity=Decimal("0"), increase_rate_pct=Decimal("100")
        )
        self.assertEqual(res, Decimal("0"))

        # Zero rate
        res = Portfolio._calculate_capital_increase_quantity(
            current_quantity=Decimal("100"), increase_rate_pct=Decimal("0")
        )
        self.assertEqual(res, Decimal("0"))

        # None rate
        res = Portfolio._calculate_capital_increase_quantity(
            current_quantity=Decimal("100"), increase_rate_pct=None
        )
        self.assertEqual(res, Decimal("0"))

        # Negative rate
        res = Portfolio._calculate_capital_increase_quantity(
            current_quantity=Decimal("100"), increase_rate_pct=Decimal("-10")
        )
        self.assertEqual(res, Decimal("0"))

    def test_apply_transaction_sequence(self) -> None:
        """Test a full sequence of different transaction types on a position."""
        data = {
            "asset": self.asset_usd,
            "quantity": Decimal("0"),
            "cost_basis": Decimal("0"),
            "value_adjustment": Decimal("0"),
        }
        fx_rate = Decimal("30")

        # 1. BUY 10 units at $100
        tx_buy = PortfolioTransaction(
            transaction_type=PortfolioTransaction.TransactionType.BUY,
            quantity=Decimal("10"),
            price_per_unit=Decimal("100"),
        )
        self.portfolio._apply_transaction_to_position(tx_buy, data, fx_rate)
        # 10 units, cost = 10 * 100 * 30 = 30000
        self.assertEqual(data["quantity"], Decimal("10"))
        self.assertEqual(data["cost_basis"], Decimal("30000"))

        # 2. BONUS_CAPITAL_INCREASE 100%
        tx_bonus = PortfolioTransaction(
            transaction_type=PortfolioTransaction.TransactionType.BONUS_CAPITAL_INCREASE,
            capital_increase_rate_pct=Decimal("100"),
        )
        self.portfolio._apply_transaction_to_position(tx_bonus, data, fx_rate)
        # 20 units, cost remains 30000
        self.assertEqual(data["quantity"], Decimal("20"))
        self.assertEqual(data["cost_basis"], Decimal("30000"))

        # 3. SELL 5 units
        tx_sell = PortfolioTransaction(
            transaction_type=PortfolioTransaction.TransactionType.SELL,
            quantity=Decimal("5"),
        )
        self.portfolio._apply_transaction_to_position(tx_sell, data, fx_rate)
        # Average cost = 30000 / 20 = 1500
        # Sell 5 units: new quantity = 15, new cost = 30000 - (5 * 1500) = 22500
        self.assertEqual(data["quantity"], Decimal("15"))
        self.assertEqual(data["cost_basis"], Decimal("22500"))

        # 4. RIGHTS_NOT_EXERCISED 20%
        # current quantity 15, 20% increase means 3 units rights
        # if rights_not_exercised, value_adjustment decreases by rights * price_per_unit * fx
        tx_rights = PortfolioTransaction(
            transaction_type=PortfolioTransaction.TransactionType.RIGHTS_NOT_EXERCISED,
            capital_increase_rate_pct=Decimal("20"),
            price_per_unit=Decimal("1"),  # Right price
        )
        self.portfolio._apply_transaction_to_position(tx_rights, data, fx_rate)
        # 3 units * $1 * 30 = 90 loss
        self.assertEqual(data["quantity"], Decimal("15"))
        self.assertEqual(data["value_adjustment"], Decimal("-90"))

    def test_xirr_edge_cases(self) -> None:
        """Test calculate_xirr with problematic inputs."""
        # Empty
        self.assertIsNone(calculate_xirr([]))

        # Only positive
        self.assertIsNone(calculate_xirr([(date(2024, 1, 1), Decimal("100"))]))

        # Only negative
        self.assertIsNone(calculate_xirr([(date(2024, 1, 1), Decimal("-100"))]))

        # Same day cash flows (should return simple return)
        flows = [
            (date(2024, 1, 1), Decimal("-100")),
            (date(2024, 1, 1), Decimal("150")),
        ]
        # (150 - 100) / 100 = 0.5
        self.assertAlmostEqual(calculate_xirr(flows), 0.5)  # type: ignore

        # Same day with zero denominator
        flows_zero = [
            (date(2024, 1, 1), Decimal("0")),
            (date(2024, 1, 1), Decimal("150")),
        ]
        self.assertIsNone(calculate_xirr(flows_zero))
