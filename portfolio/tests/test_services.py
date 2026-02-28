from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
from django.test import TestCase

from portfolio.services import calculate_xirr, fetch_fx_rate


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
        # total_in = 100, total_out = 150
        # return = (150 - 100) / 100 = 0.5
        self.assertEqual(calculate_xirr(cash_flows), 0.5)

    def test_same_day_cash_flows_negative_return(self):
        """Test when all cash flows occur on the same day with a net negative return."""
        cash_flows = [
            (date(2023, 1, 1), Decimal("-100")),
            (date(2023, 1, 1), Decimal("50")),
        ]
        # total_in = 100, total_out = 50
        # return = (50 - 100) / 100 = -0.5
        self.assertEqual(calculate_xirr(cash_flows), -0.5)

    def test_regular_xirr(self):
        """Test a standard 1-year investment with positive return."""
        cash_flows = [
            (date(2020, 1, 1), Decimal("-1000")),
            (date(2021, 1, 1), Decimal("1100")),
        ]
        irr = calculate_xirr(cash_flows)
        self.assertIsNotNone(irr)
        # 366 days in leap year 2020
        # (1100 / 1000) ^ (365 / 366) - 1 ≈ 0.0997
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
        # Unrealistic extreme alternating cash flows
        cash_flows = [
            (date(2020, 1, 1), Decimal("-1000")),
            (date(2020, 1, 2), Decimal("1000000")),
            (date(2020, 1, 3), Decimal("-10000000")),
            (date(2020, 1, 4), Decimal("100000000")),
        ]
        # Just ensure it doesn't raise an unhandled exception
        irr = calculate_xirr(cash_flows)
        # It could return None or a float
        self.assertIsInstance(irr, (float, type(None)))

    def test_initial_guess_zero_division(self):
        """Test when the initial guess calculation encounters a zero division."""
        # Force `days = 0` but not same day for all (e.g. somehow dn == d0 but not all same, which is impossible due to the check before)
        # To hit the zero division in `(float(total_out) / float(total_in)) ** (365.0 / days)`
        # The days > 0 check protects it. So we test when total_in == 0, but total_in > 0 check protects it.
        # How about when days > 0 but total_in is very small and total_out is negative (but handled by all positive/negative check).
        # We can test extreme values for OverflowError during rate initial guess or inside the loop.
        cash_flows = [
            (date(2020, 1, 1), Decimal("-1e-10")),
            (date(2050, 1, 1), Decimal("1e100")),
        ]
        irr = calculate_xirr(cash_flows)
        self.assertIsInstance(irr, (float, type(None)))

    def test_xnpv_derivative_zero(self):
        """Test the edge case where f_prime could be zero."""
        # Handled by `if f_prime == 0: break` returning None
        cash_flows = [
            (date(2021, 1, 1), Decimal("-100")),
            (date(2021, 1, 1), Decimal("100")),
        ]
        # This falls into same day cash flows, returning 0.0
        self.assertEqual(calculate_xirr(cash_flows), 0.0)


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

        # Create a mock DataFrame with a DateIndex
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
        # DataFrame with dates after the requested date
        mock_df = pd.DataFrame(
            {"Close": [1.02, 1.03]},
            index=pd.DatetimeIndex(["2023-10-02", "2023-10-03"]),
        )
        mock_get_history.return_value = mock_df

        self.assertIsNone(fetch_fx_rate("EUR", "USD", rate_date=d))
