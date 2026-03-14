from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
from django.test import TestCase

from portfolio.services import (
    calculate_xirr,
    fetch_fx_rate,
    fetch_fx_rates_bulk,
    fetch_yahoo_finance_price,
)


class CalculateXIRRTests(TestCase):
    def test_empty_cash_flows(self):
        """Test with an empty list of cash flows."""
        self.assertIsNone(calculate_xirr([]))

    def test_all_zero_cash_flows(self):
        """Test with a list of cash flows where all amounts are zero."""
        cash_flows = [
            (date(2023, 1, 1), Decimal("0")),
            (date(2023, 2, 1), Decimal("0.0")),
        ]
        self.assertIsNone(calculate_xirr(cash_flows))

    def test_all_positive_cash_flows(self):
        """Test with a list of cash flows where all amounts are positive."""
        cash_flows = [
            (date(2023, 1, 1), Decimal("100")),
            (date(2023, 2, 1), Decimal("200")),
        ]
        self.assertIsNone(calculate_xirr(cash_flows))

    def test_all_negative_cash_flows(self):
        """Test with a list of cash flows where all amounts are negative."""
        cash_flows = [
            (date(2023, 1, 1), Decimal("-100")),
            (date(2023, 2, 1), Decimal("-200")),
        ]
        self.assertIsNone(calculate_xirr(cash_flows))

    def test_same_day_cash_flows_positive_return(self):
        """Test when all cash flows occur on the same day with a net positive return."""
        cash_flows = [
            (date(2023, 1, 1), Decimal("-100")),
            (date(2023, 1, 1), Decimal("150")),
        ]
        self.assertEqual(calculate_xirr(cash_flows), 0.5)

    def test_same_day_cash_flows_negative_return(self):
        """Test when all cash flows occur on the same day with a net negative return."""
        cash_flows = [
            (date(2023, 1, 1), Decimal("-100")),
            (date(2023, 1, 1), Decimal("50")),
        ]
        self.assertEqual(calculate_xirr(cash_flows), -0.5)

    def test_regular_xirr(self):
        """Test a standard 1-year investment with positive return."""
        cash_flows = [
            (date(2020, 1, 1), Decimal("-1000")),
            (date(2021, 1, 1), Decimal("1100")),
        ]
        irr = calculate_xirr(cash_flows)
        self.assertIsNotNone(irr)
        self.assertAlmostEqual(irr, 0.0997, places=3)  # type: ignore

    def test_regular_xirr_negative_return(self):
        """Test a standard investment with negative return."""
        cash_flows = [
            (date(2021, 1, 1), Decimal("-1000")),
            (date(2022, 1, 1), Decimal("900")),
        ]
        irr = calculate_xirr(cash_flows)
        self.assertIsNotNone(irr)
        self.assertAlmostEqual(irr, -0.1, places=3)  # type: ignore

    def test_complex_xirr(self):
        """Test multiple cash flows across different dates."""
        cash_flows = [
            (date(2020, 1, 1), Decimal("-1000")),
            (date(2020, 7, 1), Decimal("-500")),
            (date(2021, 1, 1), Decimal("1650")),
        ]
        irr = calculate_xirr(cash_flows)
        self.assertIsNotNone(irr)
        self.assertTrue(0.11 < irr < 0.13)  # type: ignore

    def test_xirr_max_iterations_or_divergence(self):
        """Test that a diverging or difficult series returns None or gracefully exits."""
        cash_flows = [
            (date(2020, 1, 1), Decimal("-1000")),
            (date(2020, 1, 2), Decimal("1000000")),
            (date(2020, 1, 3), Decimal("-10000000")),
            (date(2020, 1, 4), Decimal("100000000")),
        ]
        irr = calculate_xirr(cash_flows)
        self.assertIsInstance(irr, (float, type(None)))

    def test_initial_guess_zero_division(self):
        """Test when the initial guess calculation encounters a zero division."""
        cash_flows = [
            (date(2020, 1, 1), Decimal("-1e-10")),
            (date(2050, 1, 1), Decimal("1e100")),
        ]
        irr = calculate_xirr(cash_flows)
        self.assertIsInstance(irr, (float, type(None)))

    def test_xnpv_derivative_zero(self):
        """Test the edge case where f_prime could be zero."""
        cash_flows = [
            (date(2021, 1, 1), Decimal("-100")),
            (date(2021, 1, 1), Decimal("100")),
        ]
        self.assertEqual(calculate_xirr(cash_flows), 0.0)


class FetchYahooFinancePriceTests(TestCase):
    def test_empty_symbol(self):
        """Test with empty symbol."""
        self.assertIsNone(fetch_yahoo_finance_price(""))

    @patch("portfolio.services._get_ticker")
    @patch("portfolio.services._get_price")
    @patch("portfolio.services._safe_decimal")
    def test_no_date_success(self, mock_safe_decimal, mock_get_price, mock_get_ticker):
        """Test fetching current price successfully."""
        mock_ticker = MagicMock()
        mock_get_ticker.return_value = mock_ticker
        mock_get_price.return_value = 150.5
        mock_safe_decimal.return_value = Decimal("150.5")

        price = fetch_yahoo_finance_price("AAPL")

        self.assertEqual(price, Decimal("150.5"))
        mock_get_ticker.assert_called_once_with("AAPL")
        mock_get_price.assert_called_once_with(mock_ticker)
        mock_safe_decimal.assert_called_once_with(150.5)

    @patch("portfolio.services._get_ticker")
    def test_no_date_ticker_none(self, mock_get_ticker):
        """Test when ticker initialization fails."""
        mock_get_ticker.return_value = None

        self.assertIsNone(fetch_yahoo_finance_price("AAPL"))
        mock_get_ticker.assert_called_once_with("AAPL")

    @patch("portfolio.services._get_ticker")
    @patch("portfolio.services._get_price")
    def test_no_date_price_none(self, mock_get_price, mock_get_ticker):
        """Test when price lookup fails."""
        mock_ticker = MagicMock()
        mock_get_ticker.return_value = mock_ticker
        mock_get_price.return_value = None

        self.assertIsNone(fetch_yahoo_finance_price("AAPL"))
        mock_get_ticker.assert_called_once_with("AAPL")
        mock_get_price.assert_called_once_with(mock_ticker)

    @patch("portfolio.services._get_ticker")
    @patch("portfolio.services._get_history")
    @patch("portfolio.services._safe_decimal")
    def test_with_date_success(
        self, mock_safe_decimal, mock_get_history, mock_get_ticker
    ):
        """Test fetching price for a specific date successfully."""
        mock_ticker = MagicMock()
        mock_get_ticker.return_value = mock_ticker

        d = date(2023, 10, 1)
        mock_df = pd.DataFrame(
            {"Close": [149.0, 150.0]},
            index=pd.DatetimeIndex(["2023-09-30", "2023-10-01"]),
        )
        mock_get_history.return_value = mock_df
        mock_safe_decimal.return_value = Decimal("150.0")

        price = fetch_yahoo_finance_price("AAPL", price_date=d)

        self.assertEqual(price, Decimal("150.0"))
        mock_get_ticker.assert_called_once_with("AAPL")
        mock_safe_decimal.assert_called_once_with(150.0)

    @patch("portfolio.services._get_ticker")
    def test_with_date_ticker_none(self, mock_get_ticker):
        """Test fetching price with date but ticker is None."""
        mock_get_ticker.return_value = None
        d = date(2023, 10, 1)

        self.assertIsNone(fetch_yahoo_finance_price("AAPL", price_date=d))
        mock_get_ticker.assert_called_once_with("AAPL")

    @patch("portfolio.services._get_ticker")
    @patch("portfolio.services._get_history")
    def test_with_date_history_none(self, mock_get_history, mock_get_ticker):
        """Test fetching price with date but history returns None."""
        mock_ticker = MagicMock()
        mock_get_ticker.return_value = mock_ticker
        mock_get_history.return_value = None
        d = date(2023, 10, 1)

        self.assertIsNone(fetch_yahoo_finance_price("AAPL", price_date=d))

    @patch("portfolio.services._get_ticker")
    @patch("portfolio.services._get_history")
    def test_with_date_history_empty(self, mock_get_history, mock_get_ticker):
        """Test fetching price with date but history is empty initially."""
        mock_ticker = MagicMock()
        mock_get_ticker.return_value = mock_ticker
        mock_get_history.return_value = pd.DataFrame()
        d = date(2023, 10, 1)

        self.assertIsNone(fetch_yahoo_finance_price("AAPL", price_date=d))

    @patch("portfolio.services._get_ticker")
    @patch("portfolio.services._get_history")
    def test_with_date_history_filtered_empty(self, mock_get_history, mock_get_ticker):
        """Test fetching price with date but history is empty after date filtering."""
        mock_ticker = MagicMock()
        mock_get_ticker.return_value = mock_ticker

        d = date(2023, 10, 1)
        mock_df = pd.DataFrame(
            {"Close": [149.0, 150.0]},
            index=pd.DatetimeIndex(["2023-10-02", "2023-10-03"]),
        )
        mock_get_history.return_value = mock_df

        self.assertIsNone(fetch_yahoo_finance_price("AAPL", price_date=d))


class FetchFXRatesBulkTests(TestCase):
    def test_empty_currency_pairs(self):
        self.assertEqual(fetch_fx_rates_bulk([]), {})

    def test_only_identical_pairs(self):
        pairs = [("USD", "USD"), ("TRY", "TRY")]
        result = fetch_fx_rates_bulk(pairs)
        self.assertEqual(
            result, {("USD", "USD"): Decimal("1"), ("TRY", "TRY"): Decimal("1")}
        )

    @patch("portfolio.services.logger.exception")
    @patch("portfolio.services.yf.download")
    def test_yf_download_exception(self, mock_download, mock_logger_exception):
        mock_download.side_effect = Exception("Download failed")
        pairs = [("USD", "TRY")]
        self.assertEqual(fetch_fx_rates_bulk(pairs), {})

    @patch("portfolio.services.yf.download")
    def test_yf_download_empty_dataframe(self, mock_download):
        mock_download.return_value = pd.DataFrame()
        pairs = [("USD", "TRY")]
        self.assertEqual(fetch_fx_rates_bulk(pairs), {})

    @patch("portfolio.services.yf.download")
    @patch("portfolio.services._safe_decimal")
    def test_single_series_parsing(self, mock_safe_decimal, mock_download):
        mock_df = pd.DataFrame(
            {"Close": [30.0, 31.0]},
            index=pd.DatetimeIndex(["2023-10-01", "2023-10-02"]),
        )
        mock_download.return_value = mock_df
        mock_safe_decimal.return_value = Decimal("31.0")

        pairs = [("USD", "TRY"), ("TRY", "TRY")]
        d = date(2023, 10, 2)
        result = fetch_fx_rates_bulk(pairs, rate_date=d)

        self.assertEqual(result.get(("USD", "TRY")), Decimal("31.0"))
        self.assertEqual(result.get(("TRY", "TRY")), Decimal("1"))
        mock_safe_decimal.assert_called_once_with(31.0)

    @patch("portfolio.services.yf.download")
    @patch("portfolio.services._safe_decimal")
    def test_multi_index_dataframe_parsing(self, mock_safe_decimal, mock_download):
        data = {
            "USDTRY=X": [30.0, 31.0],
            "EURTRY=X": [32.0, 33.0],
        }
        mock_df = pd.DataFrame(
            data, index=pd.DatetimeIndex(["2023-10-01", "2023-10-02"])
        )
        mock_df = pd.concat([mock_df], axis=1, keys=["Close"])
        mock_download.return_value = mock_df

        mock_safe_decimal.side_effect = [Decimal("31.0"), Decimal("33.0")]

        pairs = [("USD", "TRY"), ("EUR", "TRY")]
        d = date(2023, 10, 2)
        result = fetch_fx_rates_bulk(pairs, rate_date=d)

        self.assertEqual(result.get(("USD", "TRY")), Decimal("31.0"))
        self.assertEqual(result.get(("EUR", "TRY")), Decimal("33.0"))

    @patch("portfolio.services.yf.download")
    def test_yf_download_empty_after_date_filter(self, mock_download):
        """Test returning empty dictionary when DataFrame is empty after date filtering."""
        mock_df = pd.DataFrame(
            {"Close": [30.0, 31.0]},
            index=pd.DatetimeIndex(["2023-10-03", "2023-10-04"]),
        )
        mock_download.return_value = mock_df

        pairs = [("USD", "TRY")]
        d = date(2023, 10, 2)
        self.assertEqual(fetch_fx_rates_bulk(pairs, rate_date=d), {})

    @patch("portfolio.services.yf.download")
    def test_no_close_column_in_data(self, mock_download):
        """Test returning empty dictionary when 'Close' is not present in data."""
        mock_df = pd.DataFrame(
            {"Open": [30.0, 31.0]},
            index=pd.DatetimeIndex(["2023-10-01", "2023-10-02"]),
        )
        mock_download.return_value = mock_df

        pairs = [("USD", "TRY")]
        self.assertEqual(fetch_fx_rates_bulk(pairs), {})

    @patch("portfolio.services.logger.exception")
    @patch("portfolio.services.yf.download")
    def test_multi_symbol_missing_from_close_data(
        self, mock_download, mock_logger_exception
    ):
        """Test when multiple pairs requested but one is missing from 'Close' data."""
        data = {
            "USDTRY=X": [30.0, 31.0],
        }
        mock_df = pd.DataFrame(
            data, index=pd.DatetimeIndex(["2023-10-01", "2023-10-02"])
        )
        mock_df = pd.concat([mock_df], axis=1, keys=["Close"])
        mock_download.return_value = mock_df

        pairs = [("USD", "TRY"), ("EUR", "TRY")]
        result = fetch_fx_rates_bulk(pairs)

        self.assertIn(("USD", "TRY"), result)
        self.assertNotIn(("EUR", "TRY"), result)

    @patch("portfolio.services.yf.download")
    def test_series_empty_after_dropna(self, mock_download):
        """Test when series becomes empty after dropna()."""
        mock_df = pd.DataFrame(
            {"Close": [float("nan"), float("nan")]},
            index=pd.DatetimeIndex(["2023-10-01", "2023-10-02"]),
        )
        mock_download.return_value = mock_df

        pairs = [("USD", "TRY")]
        self.assertEqual(fetch_fx_rates_bulk(pairs), {})

    @patch("portfolio.services.yf.download")
    @patch("portfolio.services._safe_decimal")
    def test_parse_fx_rate_exception(self, mock_safe_decimal, mock_download):
        """Test handling of exception during single symbol parsing."""
        mock_df = pd.DataFrame(
            {"Close": [30.0, 31.0]},
            index=pd.DatetimeIndex(["2023-10-01", "2023-10-02"]),
        )
        mock_download.return_value = mock_df
        mock_safe_decimal.side_effect = Exception("Parsing error")

        pairs = [("USD", "TRY")]

        with patch("portfolio.services.logger") as mock_logger:
            result = fetch_fx_rates_bulk(pairs)

        self.assertEqual(result, {})
        mock_logger.exception.assert_called_once()


class FetchFXRateTests(TestCase):
    def test_empty_currencies(self):
        """Test with empty base or target currency."""
        self.assertIsNone(fetch_fx_rate("", "USD"))
        self.assertIsNone(fetch_fx_rate("EUR", ""))
        self.assertIsNone(fetch_fx_rate("", ""))

    def test_same_currencies(self):
        """Test when base and target currency are the same."""
        self.assertEqual(fetch_fx_rate("TRY", "TRY"), Decimal("1"))
        self.assertEqual(fetch_fx_rate("USD", "USD"), Decimal("1"))

    @patch("portfolio.services._get_ticker")
    @patch("portfolio.services._get_price")
    @patch("portfolio.services._safe_decimal")
    def test_no_date_success(self, mock_safe_decimal, mock_get_price, mock_get_ticker):
        """Test fetching current rate successfully."""
        mock_ticker = MagicMock()
        mock_get_ticker.return_value = mock_ticker
        mock_get_price.return_value = 1.05
        mock_safe_decimal.return_value = Decimal("1.05")

        rate = fetch_fx_rate("EUR", "USD")

        self.assertEqual(rate, Decimal("1.05"))
        mock_get_ticker.assert_called_once_with("EURUSD=X")
        mock_get_price.assert_called_once_with(mock_ticker)
        mock_safe_decimal.assert_called_once_with(1.05)

    @patch("portfolio.services._get_ticker")
    def test_no_date_ticker_none(self, mock_get_ticker):
        """Test when ticker initialization fails."""
        mock_get_ticker.return_value = None

        self.assertIsNone(fetch_fx_rate("EUR", "USD"))
        mock_get_ticker.assert_called_once_with("EURUSD=X")

    @patch("portfolio.services._get_ticker")
    @patch("portfolio.services._get_price")
    def test_no_date_price_none(self, mock_get_price, mock_get_ticker):
        """Test when price lookup fails."""
        mock_ticker = MagicMock()
        mock_get_ticker.return_value = mock_ticker
        mock_get_price.return_value = None

        self.assertIsNone(fetch_fx_rate("EUR", "USD"))
        mock_get_ticker.assert_called_once_with("EURUSD=X")
        mock_get_price.assert_called_once_with(mock_ticker)

    @patch("portfolio.services._get_ticker")
    @patch("portfolio.services._get_history")
    @patch("portfolio.services._safe_decimal")
    def test_with_date_success(
        self, mock_safe_decimal, mock_get_history, mock_get_ticker
    ):
        """Test fetching rate for a specific date successfully."""
        mock_ticker = MagicMock()
        mock_get_ticker.return_value = mock_ticker

        d = date(2023, 10, 1)
        mock_df = pd.DataFrame(
            {"Close": [1.02, 1.03]},
            index=pd.DatetimeIndex(["2023-09-30", "2023-10-01"]),
        )
        mock_get_history.return_value = mock_df
        mock_safe_decimal.return_value = Decimal("1.03")

        rate = fetch_fx_rate("EUR", "USD", rate_date=d)

        self.assertEqual(rate, Decimal("1.03"))
        mock_get_ticker.assert_called_once_with("EURUSD=X")
        mock_safe_decimal.assert_called_once_with(1.03)

    @patch("portfolio.services._get_ticker")
    def test_with_date_ticker_none(self, mock_get_ticker):
        """Test fetching rate with date but ticker is None."""
        mock_get_ticker.return_value = None
        d = date(2023, 10, 1)

        self.assertIsNone(fetch_fx_rate("EUR", "USD", rate_date=d))
        mock_get_ticker.assert_called_once_with("EURUSD=X")

    @patch("portfolio.services._get_ticker")
    @patch("portfolio.services._get_history")
    def test_with_date_history_none(self, mock_get_history, mock_get_ticker):
        """Test fetching rate with date but history returns None."""
        mock_ticker = MagicMock()
        mock_get_ticker.return_value = mock_ticker
        mock_get_history.return_value = None
        d = date(2023, 10, 1)

        self.assertIsNone(fetch_fx_rate("EUR", "USD", rate_date=d))

    @patch("portfolio.services._get_ticker")
    @patch("portfolio.services._get_history")
    def test_with_date_history_empty(self, mock_get_history, mock_get_ticker):
        """Test fetching rate with date but history is empty initially."""
        mock_ticker = MagicMock()
        mock_get_ticker.return_value = mock_ticker
        mock_get_history.return_value = pd.DataFrame()
        d = date(2023, 10, 1)

        self.assertIsNone(fetch_fx_rate("EUR", "USD", rate_date=d))

    @patch("portfolio.services._get_ticker")
    @patch("portfolio.services._get_history")
    def test_with_date_history_filtered_empty(self, mock_get_history, mock_get_ticker):
        """Test fetching rate with date but history is empty after date filtering."""
        mock_ticker = MagicMock()
        mock_get_ticker.return_value = mock_ticker

        d = date(2023, 10, 1)
        mock_df = pd.DataFrame(
            {"Close": [1.02, 1.03]},
            index=pd.DatetimeIndex(["2023-10-02", "2023-10-03"]),
        )
        mock_get_history.return_value = mock_df

        self.assertIsNone(fetch_fx_rate("EUR", "USD", rate_date=d))
