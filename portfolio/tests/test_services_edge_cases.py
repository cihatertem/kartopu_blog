from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
from django.test import TestCase

from portfolio.services import (
    _safe_decimal,
    fetch_fx_rate,
    fetch_fx_rates_bulk,
    fetch_multiple_fx_rates_bulk,
    fetch_yahoo_finance_price,
)


class ServicesEdgeCaseTests(TestCase):
    def setUp(self):
        super().setUp()
        import logging

        self.services_logger = logging.getLogger("portfolio.services")
        patcher_err = patch.object(self.services_logger, "error")
        patcher_exc = patch.object(self.services_logger, "exception")
        self.mock_logger_error = patcher_err.start()
        self.mock_logger_exception = patcher_exc.start()
        self.addCleanup(patcher_err.stop)
        self.addCleanup(patcher_exc.stop)

    def test_safe_decimal_conversion(self) -> None:
        """Test _safe_decimal with various inputs."""
        self.assertEqual(_safe_decimal(10.5), Decimal("10.5"))
        self.assertEqual(_safe_decimal("10.5"), Decimal("10.5"))
        self.assertIsNone(_safe_decimal(None))
        self.assertIsNone(_safe_decimal("invalid"))
        self.assertIsNone(_safe_decimal([]))

    @patch("portfolio.services._get_ticker")
    def test_fetch_yahoo_finance_price_ticker_failure(
        self, mock_get_ticker: MagicMock
    ) -> None:
        """Test fetch_yahoo_finance_price when ticker initialization fails."""
        mock_get_ticker.return_value = None
        res = fetch_yahoo_finance_price("AAPL")
        self.assertIsNone(res)

    @patch("portfolio.services._get_ticker")
    def test_fetch_yahoo_finance_price_history_empty(
        self, mock_get_ticker: MagicMock
    ) -> None:
        """Test fetch_yahoo_finance_price with empty history."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_get_ticker.return_value = mock_ticker

        res = fetch_yahoo_finance_price("AAPL", price_date=date(2024, 1, 1))
        self.assertIsNone(res)

    @patch("portfolio.services._get_ticker")
    def test_fetch_yahoo_finance_price_history_exception(
        self, mock_get_ticker: MagicMock
    ) -> None:
        """Test fetch_yahoo_finance_price when history request raises an exception."""
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("API error")
        mock_get_ticker.return_value = mock_ticker

        res = fetch_yahoo_finance_price("AAPL", price_date=date(2024, 1, 1))

        self.assertIsNone(res)
        self.mock_logger_error.assert_called_with(
            "Yahoo Finance history request failed."
        )

    @patch("portfolio.services._get_ticker")
    def test_fetch_yahoo_finance_price_exception(
        self, mock_get_ticker: MagicMock
    ) -> None:
        """Test fetch_yahoo_finance_price when price request raises an exception."""
        mock_ticker = MagicMock()
        mock_ticker.fast_info.get.side_effect = Exception("API error")
        mock_get_ticker.return_value = mock_ticker

        res = fetch_yahoo_finance_price("AAPL")

        self.assertIsNone(res)
        self.mock_logger_error.assert_called_with("Yahoo Finance price lookup failed.")

    @patch("portfolio.services.logger.exception")
    @patch("portfolio.services.yf.download")
    def test_fetch_fx_rates_bulk_exception(
        self, mock_download: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Test fetch_fx_rates_bulk when yf.download raises an exception."""
        mock_download.side_effect = Exception("Network error")
        res = fetch_fx_rates_bulk([("USD", "TRY")])
        self.assertEqual(res, {})
        # Verify that it was actually logged, but it won't show in terminal
        mock_logger.assert_called()

    @patch("portfolio.services.logger.exception")
    @patch("portfolio.services.yf.download")
    def test_fetch_multiple_fx_rates_bulk_exception(
        self, mock_download: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Test fetch_multiple_fx_rates_bulk when yf.download raises an exception."""
        mock_download.side_effect = Exception("Network error")
        res = fetch_multiple_fx_rates_bulk({date(2024, 1, 1): {("USD", "TRY")}})
        self.assertEqual(res, {})
        # Verify that it was actually logged
        mock_logger.assert_called()

    @patch("portfolio.services.logger.exception")
    @patch("portfolio.services.yf.download")
    def test_fetch_multiple_fx_rates_bulk_empty_data(
        self, mock_download: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Test fetch_multiple_fx_rates_bulk with empty dataframe from Yahoo."""
        mock_download.return_value = pd.DataFrame()
        res = fetch_multiple_fx_rates_bulk({date(2024, 1, 1): {("USD", "TRY")}})
        self.assertEqual(res, {})

    @patch("portfolio.services.logger.warning")
    @patch("portfolio.services._get_ticker")
    def test_fetch_fx_rate_no_symbol(
        self, mock_get_ticker: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Test fetch_fx_rate with empty symbols."""
        self.assertIsNone(fetch_fx_rate("", "TRY"))
        self.assertIsNone(fetch_fx_rate("USD", ""))
        mock_get_ticker.assert_not_called()

    def test_fetch_fx_rate_same_currency(self) -> None:
        """Test fetch_fx_rate with same base and target currency."""
        res = fetch_fx_rate("TRY", "TRY")
        self.assertEqual(res, Decimal("1"))

    @patch("portfolio.services.logger.exception")
    @patch("portfolio.services._get_ticker")
    def test_fetch_fx_rate_history_none(
        self, mock_get_ticker: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Test fetch_fx_rate when history returns None."""
        mock_ticker = MagicMock()
        with patch("portfolio.services._get_history", return_value=None):
            mock_get_ticker.return_value = mock_ticker
            res = fetch_fx_rate("USD", "TRY", rate_date=date(2024, 1, 1))
            self.assertIsNone(res)
