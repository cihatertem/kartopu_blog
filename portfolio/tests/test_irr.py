from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import TestCase

from portfolio.services import _xnpv, calculate_xirr


class IRRServiceTests(TestCase):
    def test_same_day_irr(self) -> None:
        cash_flows = [
            (date(2025, 12, 31), Decimal("-1000")),
            (date(2025, 12, 31), Decimal("1100")),
        ]
        res = calculate_xirr(cash_flows)
        self.assertAlmostEqual(res, 0.1)

    def test_one_day_high_irr(self) -> None:
        cash_flows = [
            (date(2025, 12, 30), Decimal("-1000")),
            (date(2025, 12, 31), Decimal("1100")),
        ]
        res = calculate_xirr(cash_flows)
        self.assertGreater(res, 1e15)

    def test_one_day_normal_irr(self) -> None:
        cash_flows = [
            (date(2025, 12, 30), Decimal("-1000")),
            (date(2025, 12, 31), Decimal("1001")),
        ]
        res = calculate_xirr(cash_flows)
        self.assertAlmostEqual(res, 0.44025, places=4)

    def test_xnpv_zero_rate(self) -> None:
        cash_flows = [
            (date(2025, 1, 1), Decimal("-1000")),
            (date(2025, 7, 2), Decimal("500")),
            (date(2026, 1, 1), Decimal("600")),
        ]
        # At zero rate, sum should be just sum of cash flows (-1000 + 500 + 600 = 100)
        res = _xnpv(0.0, cash_flows)
        self.assertAlmostEqual(res, 100.0)

    def test_xnpv_positive_rate(self) -> None:
        cash_flows = [
            (date(2025, 1, 1), Decimal("-1000")),
            (date(2026, 1, 1), Decimal("1100")),
        ]
        # At 10% rate, NPv should be exactly 0 (1100 / 1.1 = 1000)
        res = _xnpv(0.1, cash_flows)
        self.assertAlmostEqual(res, 0.0)

    def test_xnpv_negative_rate(self) -> None:
        cash_flows = [
            (date(2025, 1, 1), Decimal("-1000")),
            (date(2026, 1, 1), Decimal("900")),
        ]
        # At -10% rate, NPv should be exactly 0 (900 / 0.9 = 1000)
        res = _xnpv(-0.1, cash_flows)
        self.assertAlmostEqual(res, 0.0)

    def test_xnpv_multiple_years(self) -> None:
        cash_flows = [
            (date(2025, 1, 1), Decimal("-1000")),
            (date(2026, 1, 1), Decimal("500")),
            (date(2027, 1, 1), Decimal("500")),
            (date(2028, 1, 1), Decimal("500")),
        ]
        res = _xnpv(0.1, cash_flows)
        # 500/1.1 + 500/1.21 + 500/1.331 - 1000
        # 454.545 + 413.223 + 375.657 - 1000 = 243.426
        self.assertAlmostEqual(res, 243.426, places=3)

    def test_all_negative_fails(self) -> None:
        cash_flows = [
            (date(2025, 12, 30), Decimal("-1000")),
            (date(2025, 12, 31), Decimal("-1100")),
        ]
        self.assertIsNone(calculate_xirr(cash_flows))

    def test_all_positive_fails(self) -> None:
        cash_flows = [
            (date(2025, 12, 30), Decimal("1000")),
            (date(2025, 12, 31), Decimal("1100")),
        ]
        self.assertIsNone(calculate_xirr(cash_flows))

    def test_unsorted_cash_flows(self) -> None:
        cash_flows = [
            (date(2025, 12, 31), Decimal("1001")),
            (date(2025, 12, 30), Decimal("-1000")),
        ]
        res = calculate_xirr(cash_flows)
        self.assertAlmostEqual(res, 0.44025, places=4)
