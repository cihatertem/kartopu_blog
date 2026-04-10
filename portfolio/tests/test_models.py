import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
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
    SalarySavingsSnapshot,
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
    def test_portfolio_total_market_value_and_cost_basis_empty(self):
        portfolio = Portfolio.objects.create(
            owner=self.user, name="Empty Portfolio", target_value=100
        )
        self.assertEqual(portfolio.total_market_value(), Decimal("0"))
        self.assertEqual(portfolio.total_cost_basis(), Decimal("0"))

    @patch("portfolio.models.Portfolio.get_positions")
    def test_portfolio_total_market_value_and_cost_basis_with_positions(
        self, mock_get_positions
    ):
        portfolio = Portfolio.objects.create(
            owner=self.user, name="My Portfolio", target_value=100
        )
        mock_get_positions.return_value = [
            {"market_value": Decimal("150.0"), "cost_basis": Decimal("100.0")},
            {"market_value": Decimal("200.0"), "cost_basis": Decimal("150.0")},
        ]
        self.assertEqual(portfolio.total_market_value(), Decimal("350.0"))
        self.assertEqual(portfolio.total_cost_basis(), Decimal("250.0"))

    def test_portfolio_total_cost_basis_empty(self):
        portfolio = Portfolio.objects.create(
            owner=self.user, name="Empty Portfolio", target_value=100
        )
        self.assertEqual(portfolio.total_cost_basis(), Decimal("0"))

    @patch("portfolio.models.Portfolio.get_positions")
    def test_portfolio_total_cost_basis_with_positions(self, mock_get_positions):
        portfolio = Portfolio.objects.create(
            owner=self.user, name="My Portfolio", target_value=100
        )
        mock_get_positions.return_value = [
            {"cost_basis": Decimal("100.0")},
            {"cost_basis": Decimal("150.0")},
        ]
        self.assertEqual(portfolio.total_cost_basis(), Decimal("250.0"))

    def test_calculate_capital_increase_quantity(self):
        # Normal calculation
        self.assertEqual(
            Portfolio._calculate_capital_increase_quantity(
                current_quantity=Decimal("100"), increase_rate_pct=Decimal("50")
            ),
            Decimal("50"),
        )
        # Negative current_quantity
        self.assertEqual(
            Portfolio._calculate_capital_increase_quantity(
                current_quantity=Decimal("-100"), increase_rate_pct=Decimal("50")
            ),
            Decimal("0"),
        )
        # Zero current_quantity
        self.assertEqual(
            Portfolio._calculate_capital_increase_quantity(
                current_quantity=Decimal("0"), increase_rate_pct=Decimal("50")
            ),
            Decimal("0"),
        )
        # increase_rate_pct is None
        self.assertEqual(
            Portfolio._calculate_capital_increase_quantity(
                current_quantity=Decimal("100"), increase_rate_pct=None
            ),
            Decimal("0"),
        )
        # Negative increase_rate_pct
        self.assertEqual(
            Portfolio._calculate_capital_increase_quantity(
                current_quantity=Decimal("100"), increase_rate_pct=Decimal("-50")
            ),
            Decimal("0"),
        )
        # Zero increase_rate_pct
        self.assertEqual(
            Portfolio._calculate_capital_increase_quantity(
                current_quantity=Decimal("100"), increase_rate_pct=Decimal("0")
            ),
            Decimal("0"),
        )

    @patch("portfolio.models.fetch_yahoo_finance_price")
    def test_asset_refresh_price(self, mock_fetch_price):
        mock_fetch_price.return_value = Decimal("150.0")
        asset = Asset(name="Apple", symbol="AAPL", asset_type=Asset.AssetType.STOCK)
        asset.refresh_price()
        self.assertEqual(asset.current_price, Decimal("150.0"))

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
        payment = DividendPayment.objects.create(
            asset=asset,
            payment_date="2023-01-01",
            share_count=10,
            net_dividend_per_share=1,
            average_cost=100,
            last_close_price=150,
        )

        usd_dividend = payment.dividends.get(currency=Asset.Currency.USD)
        self.assertEqual(usd_dividend.total_net_amount, Decimal("10.0"))

        try_dividend = payment.dividends.get(currency=Asset.Currency.TRY)
        self.assertEqual(try_dividend.total_net_amount, Decimal("20.0"))

        initial_dividend_count = payment.dividends.count()

        mock_fetch_fx.return_value = Decimal("3.0")
        payment.net_dividend_per_share = 2
        payment.save()

        self.assertEqual(payment.dividends.count(), initial_dividend_count)

        usd_dividend.refresh_from_db()
        self.assertEqual(usd_dividend.total_net_amount, Decimal("20.0"))

        try_dividend.refresh_from_db()
        self.assertEqual(try_dividend.total_net_amount, Decimal("60.0"))

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


class SnapshotFallbackNameTests(ModelsTestCase):
    def test_portfolio_snapshot_fallback_name(self):
        portfolio = Portfolio.objects.create(
            owner=self.user, name="My Portfolio", target_value=1000
        )
        snapshot_date = datetime.date(2023, 1, 1)
        snapshot = PortfolioSnapshot.objects.create(
            portfolio=portfolio,
            snapshot_date=snapshot_date,
            period=PortfolioSnapshot.Period.MONTHLY,
            total_value=1000,
            total_cost=800,
            target_value=1200,
            total_return_pct=25,
        )
        self.assertEqual(snapshot.name, f"My Portfolio - {snapshot_date}")

    def test_cashflow_snapshot_fallback_name(self):
        cashflow = CashFlow.objects.create(owner=self.user, name="My CashFlow")
        snapshot_date = datetime.date(2023, 1, 1)
        snapshot = CashFlowSnapshot.objects.create(
            cashflow=cashflow,
            snapshot_date=snapshot_date,
            period=CashFlowSnapshot.Period.MONTHLY,
            total_amount=500,
        )
        self.assertEqual(snapshot.name, f"My CashFlow - {snapshot_date}")

    def test_salary_savings_snapshot_fallback_name(self):
        flow = SalarySavingsFlow.objects.create(owner=self.user, name="My Flow")
        snapshot_date = datetime.date(2023, 1, 1)
        snapshot = SalarySavingsSnapshot.objects.create(
            flow=flow,
            snapshot_date=snapshot_date,
            total_salary=1000,
            total_savings=200,
            savings_rate=20,
        )
        self.assertEqual(snapshot.name, f"My Flow - {snapshot_date}")

    def test_dividend_snapshot_fallback_name(self):
        snapshot = DividendSnapshot.objects.create(
            year=2023,
            currency="TRY",
            total_amount=1000,
        )
        self.assertEqual(snapshot.name, "2023 Temettü Özeti")

    def test_portfolio_snapshot_empty_fallback_name(self):
        snapshot = PortfolioSnapshot()
        self.assertEqual(snapshot._get_fallback_name(), "")

    def test_portfolio_snapshot_empty_fallback_name_missing_portfolio(self):
        snapshot = PortfolioSnapshot(snapshot_date=datetime.date(2023, 1, 1))
        self.assertEqual(snapshot._get_fallback_name(), "")

    def test_portfolio_snapshot_empty_fallback_name_missing_date(self):
        portfolio = Portfolio.objects.create(
            owner=self.user, name="My Portfolio", target_value=1000
        )
        snapshot = PortfolioSnapshot(portfolio=portfolio, snapshot_date=None)
        self.assertEqual(snapshot._get_fallback_name(), "")

    def test_cashflow_snapshot_empty_fallback_name(self):
        snapshot = CashFlowSnapshot()
        self.assertEqual(snapshot._get_fallback_name(), "")

    def test_salary_savings_snapshot_empty_fallback_name(self):
        snapshot = SalarySavingsSnapshot()
        self.assertEqual(snapshot._get_fallback_name(), "")

    def test_cashflow_snapshot_empty_fallback_name_missing_cashflow(self):
        snapshot = CashFlowSnapshot(snapshot_date=datetime.date(2023, 1, 1))
        self.assertEqual(snapshot._get_fallback_name(), "")

    def test_cashflow_snapshot_fallback_name_missing_date(self):
        cashflow = CashFlow.objects.create(owner=self.user, name="My CashFlow")
        snapshot = CashFlowSnapshot(cashflow=cashflow, snapshot_date=None)
        self.assertEqual(snapshot._get_fallback_name(), f"{cashflow}")

    def test_salary_savings_snapshot_empty_fallback_name_missing_flow(self):
        snapshot = SalarySavingsSnapshot(snapshot_date=datetime.date(2023, 1, 1))
        self.assertEqual(snapshot._get_fallback_name(), "")

    def test_salary_savings_snapshot_fallback_name_missing_date(self):
        flow = SalarySavingsFlow.objects.create(owner=self.user, name="My Flow")
        snapshot = SalarySavingsSnapshot(flow=flow, snapshot_date=None)
        self.assertEqual(snapshot._get_fallback_name(), f"{flow}")

    def test_dividend_snapshot_empty_fallback_name(self):
        snapshot = DividendSnapshot()
        self.assertEqual(snapshot._get_fallback_name(), "")

    def test_dividend_snapshot_empty_fallback_name_missing_year(self):
        snapshot = DividendSnapshot(year=None)
        self.assertEqual(snapshot._get_fallback_name(), "")

    def test_snapshot_explicit_name_not_overridden(self):
        portfolio = Portfolio.objects.create(
            owner=self.user, name="My Portfolio", target_value=1000
        )
        snapshot = PortfolioSnapshot.objects.create(
            portfolio=portfolio,
            snapshot_date=datetime.date(2023, 1, 1),
            period=PortfolioSnapshot.Period.MONTHLY,
            name="Custom Name",
            total_value=1000,
            total_cost=800,
            target_value=1200,
            total_return_pct=25,
        )
        self.assertEqual(snapshot.name, "Custom Name")


class FxRateTests(ModelsTestCase):
    def setUp(self):
        super().setUp()
        self.portfolio = Portfolio.objects.create(
            owner=self.user, name="FX Test Portfolio", target_value=100
        )
        cache.clear()

    def test_get_or_fetch_fx_rate_in_dict(self):
        fx_rates = {("USD", "TRY", datetime.date(2023, 1, 1)): Decimal("20.0")}
        rate = self.portfolio._get_or_fetch_fx_rate(
            fx_rates, "USD", "TRY", datetime.date(2023, 1, 1)
        )
        self.assertEqual(rate, Decimal("20.0"))

    def test_get_or_fetch_fx_rate_in_cache(self):
        fx_rates = {}
        rate_date = datetime.date(2023, 1, 1)
        cache_key = f"fx_rate_USD_TRY_{rate_date.isoformat()}"
        cache.set(cache_key, Decimal("25.0"))

        rate = self.portfolio._get_or_fetch_fx_rate(fx_rates, "USD", "TRY", rate_date)

        self.assertEqual(rate, Decimal("25.0"))
        self.assertEqual(fx_rates[("USD", "TRY", rate_date)], Decimal("25.0"))

    @patch("portfolio.models.fetch_fx_rate")
    def test_get_or_fetch_fx_rate_fetch_success(self, mock_fetch):
        mock_fetch.return_value = Decimal("30.0")
        fx_rates = {}
        rate_date = datetime.date(2023, 1, 1)

        rate = self.portfolio._get_or_fetch_fx_rate(fx_rates, "USD", "TRY", rate_date)

        self.assertEqual(rate, Decimal("30.0"))
        self.assertEqual(fx_rates[("USD", "TRY", rate_date)], Decimal("30.0"))
        mock_fetch.assert_called_once_with("USD", "TRY", rate_date=rate_date)

        cache_key = f"fx_rate_USD_TRY_{rate_date.isoformat()}"
        self.assertEqual(cache.get(cache_key), Decimal("30.0"))

    @patch("portfolio.models.fetch_fx_rate")
    def test_get_or_fetch_fx_rate_fetch_none_fallback(self, mock_fetch):
        mock_fetch.return_value = None
        fx_rates = {}
        rate_date = datetime.date(2023, 1, 1)

        rate = self.portfolio._get_or_fetch_fx_rate(fx_rates, "USD", "TRY", rate_date)

        self.assertEqual(rate, Decimal("1"))
        self.assertEqual(fx_rates[("USD", "TRY", rate_date)], Decimal("1"))
        mock_fetch.assert_called_once_with("USD", "TRY", rate_date=rate_date)

        cache_key = f"fx_rate_USD_TRY_{rate_date.isoformat()}"
        self.assertEqual(cache.get(cache_key), Decimal("1"))

    @patch("portfolio.models.fetch_fx_rate")
    def test_get_or_fetch_fx_rate_none_date(self, mock_fetch):
        mock_fetch.return_value = Decimal("35.0")
        fx_rates = {}

        rate = self.portfolio._get_or_fetch_fx_rate(fx_rates, "USD", "TRY", None)

        self.assertEqual(rate, Decimal("35.0"))
        self.assertEqual(fx_rates[("USD", "TRY", None)], Decimal("35.0"))
        mock_fetch.assert_called_once_with("USD", "TRY", rate_date=None)

        cache_key = "fx_rate_USD_TRY_latest"
        self.assertEqual(cache.get(cache_key), Decimal("35.0"))
