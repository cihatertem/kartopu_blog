from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from portfolio.admin import ExchangeRateAdmin
from portfolio.models import (
    Asset,
    BaseSnapshot,
    Dividend,
    DividendPayment,
    ExchangeRate,
    Portfolio,
)

User = get_user_model()


class ExchangeRateFallbackTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(  # pyright: ignore[reportCallIssue]
            email="fxtest@example.com",
            password="password",
        )
        self.portfolio = Portfolio.objects.create(
            owner=self.user,
            name="FX Test Portfolio",
            target_value=Decimal("100000"),
            currency=Portfolio.Currency.TRY,
        )
        self.asset_usd = Asset.objects.create(
            name="Apple Inc.",
            symbol="AAPL",
            asset_type=Asset.AssetType.STOCK,
            currency=Asset.Currency.USD,
            current_price=Decimal("150"),
        )
        cache.clear()

    def test_exchange_rate_model_str(self) -> None:
        rate_obj = ExchangeRate.objects.create(
            base_currency="USD",
            target_currency="TRY",
            rate_date=date(2024, 1, 15),
            rate=Decimal("30.25"),
        )
        self.assertEqual(str(rate_obj), "USD/TRY (2024-01-15): 30.25")

    def test_record_rate_and_cache(self) -> None:
        rate = Decimal("32.50")
        d = date(2024, 6, 1)
        rate_obj = ExchangeRate.record_rate("USD", "TRY", rate, rate_date=d)

        self.assertIsNotNone(rate_obj)
        assert rate_obj is not None
        self.assertEqual(rate_obj.rate, rate)

        # Check DB
        in_db = ExchangeRate.objects.get(
            base_currency="USD", target_currency="TRY", rate_date=d
        )
        self.assertEqual(in_db.rate, rate)

        # Check cache
        cache_key = f"fx_rate_USD_TRY_{d.isoformat()}"
        self.assertEqual(cache.get(cache_key), rate)
        self.assertEqual(cache.get("fx_rate_latest_valid_USD_TRY"), rate)

    def test_record_rate_invalid_inputs(self) -> None:
        self.assertIsNone(ExchangeRate.record_rate("", "TRY", Decimal("30")))
        self.assertIsNone(ExchangeRate.record_rate("TRY", "TRY", Decimal("1")))
        self.assertIsNone(ExchangeRate.record_rate("USD", "TRY", Decimal("0")))
        self.assertIsNone(ExchangeRate.record_rate("USD", "TRY", Decimal("-5")))

    def test_record_rates_bulk(self) -> None:
        d1 = date(2024, 5, 1)
        d2 = date(2024, 5, 2)
        rates: dict[tuple[str, str, date | None], Decimal] = {
            ("USD", "TRY", d1): Decimal("32.10"),
            ("EUR", "TRY", d2): Decimal("34.50"),
            ("TRY", "TRY", d1): Decimal("1.0"),  # identical, should be skipped
        }
        ExchangeRate.record_rates_bulk(rates)

        self.assertEqual(
            ExchangeRate.objects.get(base_currency="USD", rate_date=d1).rate,
            Decimal("32.10"),
        )
        self.assertEqual(
            ExchangeRate.objects.get(base_currency="EUR", rate_date=d2).rate,
            Decimal("34.50"),
        )
        self.assertFalse(
            ExchangeRate.objects.filter(
                base_currency="TRY", target_currency="TRY"
            ).exists()
        )

    def test_get_last_known_rate_exact_and_prior_date(self) -> None:
        ExchangeRate.objects.create(
            base_currency="USD",
            target_currency="TRY",
            rate_date=date(2024, 1, 10),
            rate=Decimal("29.90"),
        )
        ExchangeRate.objects.create(
            base_currency="USD",
            target_currency="TRY",
            rate_date=date(2024, 1, 20),
            rate=Decimal("30.20"),
        )

        # Exact date match
        rate = ExchangeRate.get_last_known_rate(
            "USD", "TRY", as_of_date=date(2024, 1, 10)
        )
        self.assertEqual(rate, Decimal("29.90"))

        # Between dates -> should get the one on or before as_of_date (2024-01-10)
        rate = ExchangeRate.get_last_known_rate(
            "USD", "TRY", as_of_date=date(2024, 1, 15)
        )
        self.assertEqual(rate, Decimal("29.90"))

        # After both dates -> should get 2024-01-20
        rate = ExchangeRate.get_last_known_rate(
            "USD", "TRY", as_of_date=date(2024, 1, 25)
        )
        self.assertEqual(rate, Decimal("30.20"))

        # Prior to both dates -> must return None (no future rates leak)
        rate = ExchangeRate.get_last_known_rate(
            "USD", "TRY", as_of_date=date(2023, 12, 31)
        )
        self.assertIsNone(rate)

        # No as_of_date -> gets latest
        rate = ExchangeRate.get_last_known_rate("USD", "TRY", as_of_date=None)
        self.assertEqual(rate, Decimal("30.20"))

    def test_get_last_known_rate_inverse_pair(self) -> None:
        # Only USD -> TRY is recorded: 30.0
        ExchangeRate.objects.create(
            base_currency="USD",
            target_currency="TRY",
            rate_date=date(2024, 1, 10),
            rate=Decimal("30.0"),
        )

        # Asking for TRY -> USD should compute 1 / 30.0
        rate = ExchangeRate.get_last_known_rate(
            "TRY", "USD", as_of_date=date(2024, 1, 10)
        )
        self.assertIsNotNone(rate)
        assert rate is not None
        expected = Decimal("1") / Decimal("30.0")
        self.assertAlmostEqual(float(rate), float(expected), places=6)

    def test_get_last_known_rate_cache_fallback(self) -> None:
        # Nothing in DB, but cached latest valid rate exists
        cache.set("fx_rate_latest_valid_EUR_TRY", Decimal("35.50"), timeout=None)
        rate = ExchangeRate.get_last_known_rate("EUR", "TRY")
        self.assertEqual(rate, Decimal("35.50"))

    @patch("portfolio.models.fetch_fx_rate")
    def test_portfolio_get_or_fetch_fx_rate_fallback_to_last_known(
        self, mock_fetch: MagicMock
    ) -> None:
        """When fetch_fx_rate returns None, _get_or_fetch_fx_rate must use last known valid rate."""
        ExchangeRate.objects.create(
            base_currency="USD",
            target_currency="TRY",
            rate_date=date(2024, 1, 5),
            rate=Decimal("29.80"),
        )
        mock_fetch.return_value = None

        fx_rates: dict[tuple[str, str, date | None], Decimal] = {}
        target_date = date(2024, 1, 8)

        rate = self.portfolio._get_or_fetch_fx_rate(fx_rates, "USD", "TRY", target_date)

        self.assertEqual(rate, Decimal("29.80"))
        self.assertEqual(fx_rates[("USD", "TRY", target_date)], Decimal("29.80"))
        self.assertEqual(
            cache.get(f"fx_rate_USD_TRY_{target_date.isoformat()}"),
            Decimal("29.80"),
        )

    @patch("portfolio.models.fetch_fx_rate")
    def test_portfolio_get_or_fetch_fx_rate_success_records_rate(
        self, mock_fetch: MagicMock
    ) -> None:
        """When fetch_fx_rate succeeds, rate must be recorded in ExchangeRate and cache."""
        mock_fetch.return_value = Decimal("31.25")
        fx_rates: dict[tuple[str, str, date | None], Decimal] = {}
        target_date = date(2024, 2, 10)

        rate = self.portfolio._get_or_fetch_fx_rate(fx_rates, "USD", "TRY", target_date)

        self.assertEqual(rate, Decimal("31.25"))
        # Verify in DB
        db_rate = ExchangeRate.objects.get(
            base_currency="USD", target_currency="TRY", rate_date=target_date
        )
        self.assertEqual(db_rate.rate, Decimal("31.25"))

    @patch("portfolio.models.fetch_multiple_fx_rates_bulk")
    def test_fetch_and_cache_missing_rates_fallback_to_last_known(
        self, mock_bulk: MagicMock
    ) -> None:
        """When bulk fetch misses a pair, it falls back to last known rate."""
        ExchangeRate.objects.create(
            base_currency="USD",
            target_currency="TRY",
            rate_date=date(2024, 1, 1),
            rate=Decimal("29.50"),
        )
        mock_bulk.return_value = {}  # returns empty dict (API failure)

        fx_rates: dict[tuple[str, str, date | None], Decimal] = {}
        target_date = date(2024, 1, 3)

        self.portfolio._fetch_and_cache_missing_rates(
            {target_date: {("USD", "TRY")}}, fx_rates
        )

        self.assertEqual(fx_rates[("USD", "TRY", target_date)], Decimal("29.50"))

    @patch("portfolio.models.fetch_fx_rates_bulk")
    def test_base_snapshot_get_cached_fx_rates_fallback(
        self, mock_bulk: MagicMock
    ) -> None:
        """BaseSnapshot._get_cached_fx_rates falls back to last known rate if fetch returns empty."""
        ExchangeRate.objects.create(
            base_currency="USD",
            target_currency="TRY",
            rate_date=date(2024, 1, 1),
            rate=Decimal("30.00"),
        )
        mock_bulk.return_value = {}

        rates = BaseSnapshot._get_cached_fx_rates(
            source_currencies={"USD"},
            target_currency="TRY",
            rate_date=date(2024, 1, 5),
        )

        self.assertEqual(rates[("USD", "TRY", date(2024, 1, 5))], Decimal("30.00"))

    @patch("portfolio.models.fetch_fx_rates_bulk")
    def test_dividend_sync_currencies_fallback(self, mock_bulk: MagicMock) -> None:
        """DividendPayment.sync_dividend_currencies uses last known rate when fetch returns empty."""
        ExchangeRate.objects.create(
            base_currency="USD",
            target_currency="TRY",
            rate_date=date(2024, 1, 1),
            rate=Decimal("30.00"),
        )
        mock_bulk.return_value = {}

        payment = DividendPayment.objects.create(
            asset=self.asset_usd,
            payment_date=date(2024, 1, 15),
            share_count=Decimal("10"),
            net_dividend_per_share=Decimal("2.00"),
            average_cost=Decimal("100"),
            last_close_price=Decimal("150"),
        )

        # In TRY, 10 shares * $2.00 = $20.00 * 30.00 = 600.00 TRY
        try_dividend = Dividend.objects.get(
            payment=payment, currency=Asset.Currency.TRY
        )
        self.assertEqual(try_dividend.total_net_amount, Decimal("600.00"))

    def test_admin_registration(self) -> None:
        self.assertIn(ExchangeRate, admin.site._registry)
        self.assertIsInstance(admin.site._registry[ExchangeRate], ExchangeRateAdmin)
