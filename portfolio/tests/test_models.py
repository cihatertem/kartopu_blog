import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from portfolio.models import (
    Asset,
    CashFlow,
    CashFlowComparison,
    CashFlowEntry,
    CashFlowSnapshot,
    DividendComparison,
    DividendPayment,
    DividendSnapshot,
    Portfolio,
    PortfolioComparison,
    PortfolioSnapshot,
    PortfolioTransaction,
    SalarySavingsEntry,
    SalarySavingsFlow,
)

User = get_user_model()


class ModelsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="password"
        )


class StringRepresentationTests(ModelsTestCase):
    def test_asset_str(self):
        asset_with_symbol = Asset.objects.create(
            name="Apple",
            symbol="AAPL",
            asset_type=Asset.AssetType.STOCK,
            current_price=10,
        )
        self.assertEqual(str(asset_with_symbol), "Apple (AAPL)")

        asset_without_symbol = Asset.objects.create(
            name="Gold", symbol="", asset_type=Asset.AssetType.GOLD, current_price=10
        )
        self.assertEqual(str(asset_without_symbol), "Gold")

    def test_portfolio_comparison_str(self):
        portfolio = Portfolio.objects.create(
            owner=self.user, name="My Portfolio", target_value=100
        )
        base = PortfolioSnapshot.create_snapshot(
            portfolio=portfolio, period=PortfolioSnapshot.Period.MONTHLY
        )
        compare = PortfolioSnapshot.create_snapshot(
            portfolio=portfolio, period=PortfolioSnapshot.Period.YEARLY
        )
        comparison = PortfolioComparison.objects.create(
            name="My Comparison", base_snapshot=base, compare_snapshot=compare
        )
        self.assertTrue(str(comparison).startswith("my-comparison"))

        comparison_no_name = PortfolioComparison.objects.create(
            base_snapshot=base, compare_snapshot=compare
        )
        self.assertTrue(str(comparison_no_name).startswith("my-portfolio"))

    def test_portfolio_str(self):
        portfolio = Portfolio.objects.create(
            owner=self.user, name="My Portfolio", target_value=100
        )
        self.assertEqual(str(portfolio), "My Portfolio")

    def test_portfolio_transaction_str(self):
        asset = Asset.objects.create(
            name="Apple", asset_type=Asset.AssetType.STOCK, current_price=10
        )
        transaction = PortfolioTransaction.objects.create(
            asset=asset, trade_date="2023-01-01", quantity=10, price_per_unit=100
        )
        self.assertEqual(str(transaction), "Apple")

        portfolio = Portfolio.objects.create(
            owner=self.user, name="P1", target_value=100
        )
        transaction.portfolios.add(portfolio)
        self.assertEqual(str(transaction), "P1 - Apple")

    def test_cashflow_str(self):
        cashflow = CashFlow.objects.create(owner=self.user, name="My Cashflow")
        self.assertEqual(str(cashflow), "My Cashflow")

    def test_cashflow_entry_str(self):
        entry = CashFlowEntry.objects.create(
            entry_date="2023-01-01", category=CashFlowEntry.Category.OTHER, amount=100
        )
        self.assertEqual(str(entry), "Nakit Akışı Yok - Diğer")

        cashflow = CashFlow.objects.create(owner=self.user, name="C1")
        entry.cashflows.add(cashflow)
        self.assertEqual(str(entry), "C1 - Diğer")

    def test_salary_savings_flow_str(self):
        flow = SalarySavingsFlow.objects.create(owner=self.user, name="My Flow")
        self.assertEqual(str(flow), "My Flow")

    def test_salary_savings_entry_str(self):
        flow = SalarySavingsFlow.objects.create(owner=self.user, name="My Flow")
        entry = SalarySavingsEntry.objects.create(
            flow=flow, entry_date="2023-01-01", salary_amount=100, savings_amount=10
        )
        self.assertEqual(str(entry), "My Flow - 2023-01-01")

    @patch("portfolio.models.fetch_fx_rate")
    def test_dividend_payment_str(self, mock_fetch):
        mock_fetch.return_value = Decimal("1.0")
        asset = Asset.objects.create(
            name="Apple", asset_type=Asset.AssetType.STOCK, current_price=10
        )
        payment = DividendPayment.objects.create(
            asset=asset,
            payment_date=datetime.date(2023, 1, 1),
            share_count=10,
            net_dividend_per_share=1,
            average_cost=100,
            last_close_price=150,
        )
        self.assertEqual(str(payment), "Apple - 2023-01-01")

    @patch("portfolio.models.fetch_fx_rate")
    def test_dividend_str(self, mock_fetch):
        mock_fetch.return_value = Decimal("1.0")
        asset = Asset.objects.create(
            name="Apple", asset_type=Asset.AssetType.STOCK, current_price=10
        )
        payment = DividendPayment.objects.create(
            asset=asset,
            payment_date=datetime.date(2023, 1, 1),
            share_count=10,
            net_dividend_per_share=1,
            average_cost=100,
            last_close_price=150,
        )
        dividend = payment.dividends.get(currency=Asset.Currency.TRY)
        self.assertEqual(str(dividend), "Apple - 2023-01-01 (TRY)")

    def test_dividend_snapshot_str(self):
        snapshot = DividendSnapshot.objects.create(
            year=2023, currency=Asset.Currency.TRY, total_amount=100
        )
        self.assertEqual(str(snapshot), snapshot.slug)
        snapshot.slug = ""
        self.assertEqual(str(snapshot), "2023 Temettü Özeti")


class ValidationTests(ModelsTestCase):
    def test_portfolio_comparison_clean(self):
        p1 = Portfolio.objects.create(owner=self.user, name="P1", target_value=100)
        p2 = Portfolio.objects.create(owner=self.user, name="P2", target_value=100)
        base = PortfolioSnapshot.create_snapshot(
            portfolio=p1, period=PortfolioSnapshot.Period.MONTHLY
        )
        compare = PortfolioSnapshot.create_snapshot(
            portfolio=p2, period=PortfolioSnapshot.Period.MONTHLY
        )

        comparison = PortfolioComparison(base_snapshot=base, compare_snapshot=compare)
        with self.assertRaisesMessage(
            ValidationError, "Karşılaştırma snapshotları aynı portföye ait olmalıdır."
        ):
            comparison.clean()

    def test_portfolio_transaction_clean(self):
        asset = Asset.objects.create(
            name="Apple", asset_type=Asset.AssetType.STOCK, current_price=10
        )
        transaction = PortfolioTransaction(
            asset=asset,
            transaction_type=PortfolioTransaction.TransactionType.BONUS_CAPITAL_INCREASE,
            trade_date="2023-01-01",
            quantity=0,
            price_per_unit=0,
        )
        with self.assertRaisesMessage(
            ValidationError, "Sermaye artırımı oranı 0'dan büyük olmalıdır."
        ):
            transaction.clean()

    def test_cashflow_comparison_clean(self):
        c1 = CashFlow.objects.create(owner=self.user, name="C1")
        c2 = CashFlow.objects.create(owner=self.user, name="C2")
        base = CashFlowSnapshot.create_snapshot(
            cashflow=c1, period=CashFlowSnapshot.Period.MONTHLY
        )
        compare = CashFlowSnapshot.create_snapshot(
            cashflow=c2, period=CashFlowSnapshot.Period.MONTHLY
        )

        comparison = CashFlowComparison(base_snapshot=base, compare_snapshot=compare)
        with self.assertRaisesMessage(
            ValidationError,
            "Karşılaştırma snapshotları aynı nakit akışına ait olmalıdır.",
        ):
            comparison.clean()

    def test_dividend_comparison_clean(self):
        base = DividendSnapshot.objects.create(
            year=2023, currency=Asset.Currency.TRY, total_amount=100
        )
        compare = DividendSnapshot.objects.create(
            year=2024, currency=Asset.Currency.USD, total_amount=100
        )

        comparison = DividendComparison(base_snapshot=base, compare_snapshot=compare)
        with self.assertRaisesMessage(
            ValidationError,
            "Karşılaştırma snapshotlarının para birimleri aynı olmalıdır.",
        ):
            comparison.clean()


class LogicTests(ModelsTestCase):
    @patch("portfolio.models.fetch_yahoo_finance_price")
    def test_asset_refresh_price(self, mock_fetch_price):
        mock_fetch_price.return_value = Decimal("150.0")
        asset = Asset(name="Apple", symbol="AAPL", asset_type=Asset.AssetType.STOCK)
        asset.refresh_price()
        self.assertEqual(asset.current_price, Decimal("150.0"))

        # Test save method triggers refresh_price when adding and price is missing
        mock_fetch_price.return_value = Decimal("200.0")
        asset2 = Asset(name="Tesla", symbol="TSLA", asset_type=Asset.AssetType.STOCK)
        asset2.save()
        self.assertEqual(asset2.current_price, Decimal("200.0"))

    def test_get_irr_history(self):
        portfolio = Portfolio.objects.create(
            owner=self.user, name="Portfolio", target_value=100
        )
        PortfolioSnapshot.objects.create(
            portfolio=portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date="2023-01-01",
            total_value=100,
            total_cost=100,
            target_value=100,
            total_return_pct=0,
            irr_pct=Decimal("5.0"),
        )
        PortfolioSnapshot.objects.create(
            portfolio=portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date="2023-02-01",
            total_value=100,
            total_cost=100,
            target_value=100,
            total_return_pct=0,
            irr_pct=Decimal("10.0"),
        )

        history = portfolio.get_irr_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["irr"], 5.0)

        history_filtered = portfolio.get_irr_history(
            until_date=datetime.date(2023, 1, 15)
        )
        self.assertEqual(len(history_filtered), 1)

    @patch("portfolio.models.fetch_fx_rate")
    def test_dividend_payment_sync_dividend_currencies(self, mock_fetch_fx):
        mock_fetch_fx.return_value = Decimal("2.0")
        asset = Asset.objects.create(
            name="Apple",
            currency=Asset.Currency.USD,
            asset_type=Asset.AssetType.STOCK,
            current_price=10,
        )
        # Using save to trigger sync_dividend_currencies
        payment = DividendPayment.objects.create(
            asset=asset,
            payment_date="2023-01-01",
            share_count=10,
            net_dividend_per_share=1,
            average_cost=100,
            last_close_price=150,
        )

        # Apple dividend total = 10 * 1 = 10 USD.
        usd_dividend = payment.dividends.get(currency=Asset.Currency.USD)
        self.assertEqual(usd_dividend.total_net_amount, Decimal("10.0"))

        try_dividend = payment.dividends.get(currency=Asset.Currency.TRY)
        self.assertEqual(try_dividend.total_net_amount, Decimal("20.0"))

    @patch("portfolio.models.fetch_fx_rate")
    def test_dividend_payment_properties(self, mock_fetch):
        mock_fetch.return_value = Decimal("2.0")
        asset = Asset.objects.create(
            name="Apple",
            currency=Asset.Currency.USD,
            asset_type=Asset.AssetType.STOCK,
            current_price=10,
        )
        payment = DividendPayment.objects.create(
            asset=asset,
            payment_date=datetime.date(2023, 1, 1),
            share_count=10,
            net_dividend_per_share=2,
            average_cost=100,
            last_close_price=150,
        )

        self.assertEqual(payment.total_net_amount, Decimal("20.0"))
        self.assertAlmostEqual(
            float(payment.dividend_yield_on_payment_price),
            float(Decimal("2") / Decimal("150")),
            places=4,
        )
        self.assertAlmostEqual(
            float(payment.dividend_yield_on_average_cost),
            float(Decimal("2") / Decimal("100")),
            places=4,
        )
