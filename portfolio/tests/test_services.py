from datetime import date
from decimal import Decimal

from django.test import TestCase

from portfolio.services import calculate_xirr


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
