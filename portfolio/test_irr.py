from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import TestCase

from portfolio.services import calculate_xirr


class IRRServiceTests(TestCase):
    def test_same_day_irr(self) -> None:
        # Same day: buy for 1000, worth 1100 (10% gain)
        cash_flows = [
            (date(2025, 12, 31), Decimal("-1000")),
            (date(2025, 12, 31), Decimal("1100")),
        ]
        res = calculate_xirr(cash_flows)
        self.assertAlmostEqual(res, 0.1)

    def test_one_day_high_irr(self) -> None:
        # 1 day difference: buy for 1000, worth 1100 (10% gain)
        # 1.1^365 - 1 = 1.283e15
        cash_flows = [
            (date(2025, 12, 30), Decimal("-1000")),
            (date(2025, 12, 31), Decimal("1100")),
        ]
        res = calculate_xirr(cash_flows)
        self.assertGreater(res, 1e15)

    def test_one_day_normal_irr(self) -> None:
        # 1 day difference: buy for 1000, worth 1001 (0.1% gain)
        # 1.001^365 - 1 = 0.440
        cash_flows = [
            (date(2025, 12, 30), Decimal("-1000")),
            (date(2025, 12, 31), Decimal("1001")),
        ]
        res = calculate_xirr(cash_flows)
        self.assertAlmostEqual(res, 0.44025, places=4)

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
