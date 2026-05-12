from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import TestCase

from blog.models import BlogPost
from portfolio.models import (
    Asset,
    CashFlow,
    CashFlowSnapshot,
    CashFlowSnapshotItem,
    DividendSnapshot,
    DividendSnapshotAssetItem,
    Portfolio,
    PortfolioSnapshot,
    PortfolioSnapshotItem,
    SalarySavingsFlow,
    SalarySavingsSnapshot,
)


class ChartExclusionTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="charts@example.com",
            password="testpass123",
            first_name="Charts",
        )

    def _create_portfolio_item(self, snapshot, asset, value):
        return PortfolioSnapshotItem.objects.create(
            snapshot=snapshot,
            asset=asset,
            quantity=Decimal("10") if value > 0 else Decimal("0"),
            average_cost=Decimal("100") if value > 0 else Decimal("0"),
            cost_basis=value,
            current_price=Decimal("100") if value > 0 else Decimal("0"),
            market_value=value,
            allocation_pct=Decimal("1") if value > 0 else Decimal("0"),
            gain_loss=Decimal("0"),
            gain_loss_pct=Decimal("0"),
        )

    def _render_post(self, title, content, snapshot_relation_attr, snapshot):
        post = BlogPost.objects.create(
            author=self.user,
            title=title,
            slug=title.lower().replace(" ", "-"),
            content=content,
        )
        getattr(post, snapshot_relation_attr).add(snapshot)
        template = Template("{% load blog_extras %}{% render_post_body post %}")
        return template.render(Context({"post": post}))

    def test_portfolio_charts_exclude_zero_value_items(self) -> None:
        portfolio = Portfolio.objects.create(
            owner=self.user,
            name="Test Portfolio",
            currency=Portfolio.Currency.TRY,
            target_value=Decimal("100000"),
        )
        snapshot = PortfolioSnapshot.objects.create(
            portfolio=portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date=date(2025, 1, 1),
            total_value=Decimal("1000"),
            total_cost=Decimal("1000"),
            target_value=Decimal("100000"),
            total_return_pct=Decimal("0"),
        )
        asset_nonzero = Asset.objects.create(
            name="Nvidia", symbol="NVDA", asset_type=Asset.AssetType.STOCK
        )
        asset_zero = Asset.objects.create(
            name="Amd", symbol="AMD", asset_type=Asset.AssetType.STOCK
        )

        self._create_portfolio_item(snapshot, asset_nonzero, Decimal("1000"))
        self._create_portfolio_item(snapshot, asset_zero, Decimal("0"))

        rendered = self._render_post(
            "Portfolio Charts",
            "{{ portfolio_charts }}",
            "portfolio_snapshots",
            snapshot,
        )

        self.assertIn("NVDA", rendered)
        self.assertNotIn("AMD", rendered)

    def test_portfolio_timeseries_excludes_snapshots_after_selected_snapshot(
        self,
    ) -> None:
        portfolio = Portfolio.objects.create(
            owner=self.user,
            name="Dated Portfolio",
            currency=Portfolio.Currency.TRY,
            target_value=Decimal("100000"),
        )
        past_snapshot = PortfolioSnapshot.objects.create(
            portfolio=portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date=date(2025, 1, 1),
            total_value=Decimal("900"),
            total_cost=Decimal("900"),
            target_value=Decimal("100000"),
            total_return_pct=Decimal("0"),
        )
        selected_snapshot = PortfolioSnapshot.objects.create(
            portfolio=portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date=date(2025, 2, 1),
            total_value=Decimal("1000"),
            total_cost=Decimal("1000"),
            target_value=Decimal("100000"),
            total_return_pct=Decimal("0"),
        )
        PortfolioSnapshot.objects.create(
            portfolio=portfolio,
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date=date(2025, 3, 1),
            total_value=Decimal("1100"),
            total_cost=Decimal("1100"),
            target_value=Decimal("100000"),
            total_return_pct=Decimal("0"),
        )
        asset = Asset.objects.create(
            name="Selected Asset", symbol="SEL", asset_type=Asset.AssetType.STOCK
        )
        self._create_portfolio_item(selected_snapshot, asset, Decimal("1000"))

        rendered = self._render_post(
            "Portfolio Timeseries",
            "{{ portfolio_charts }}",
            "portfolio_snapshots",
            selected_snapshot,
        )

        self.assertIn(past_snapshot.snapshot_date.isoformat(), rendered)
        self.assertIn(selected_snapshot.snapshot_date.isoformat(), rendered)
        self.assertNotIn("2025-03-01", rendered)

    def test_cashflow_charts_exclude_zero_amount_items(self) -> None:
        cashflow = CashFlow.objects.create(
            owner=self.user,
            name="Test CashFlow",
            currency=CashFlow.Currency.TRY,
        )
        snapshot = CashFlowSnapshot.objects.create(
            cashflow=cashflow,
            period=CashFlowSnapshot.Period.MONTHLY,
            snapshot_date=date(2025, 1, 1),
            total_amount=Decimal("1000"),
        )
        CashFlowSnapshotItem.objects.create(
            snapshot=snapshot,
            category="dividend",
            amount=Decimal("1000"),
            allocation_pct=Decimal("1"),
        )
        CashFlowSnapshotItem.objects.create(
            snapshot=snapshot,
            category="interest",
            amount=Decimal("0"),
            allocation_pct=Decimal("0"),
        )

        rendered = self._render_post(
            "CashFlow Charts", "{{ cashflow_charts }}", "cashflow_snapshots", snapshot
        )

        self.assertIn("Temett", rendered)
        self.assertNotIn("Faiz", rendered)

    def test_cashflow_timeseries_excludes_snapshots_after_selected_snapshot(
        self,
    ) -> None:
        cashflow = CashFlow.objects.create(
            owner=self.user,
            name="Dated CashFlow",
            currency=CashFlow.Currency.TRY,
        )
        past_snapshot = CashFlowSnapshot.objects.create(
            cashflow=cashflow,
            period=CashFlowSnapshot.Period.MONTHLY,
            snapshot_date=date(2025, 1, 1),
            total_amount=Decimal("900"),
        )
        selected_snapshot = CashFlowSnapshot.objects.create(
            cashflow=cashflow,
            period=CashFlowSnapshot.Period.MONTHLY,
            snapshot_date=date(2025, 2, 1),
            total_amount=Decimal("1000"),
        )
        CashFlowSnapshot.objects.create(
            cashflow=cashflow,
            period=CashFlowSnapshot.Period.MONTHLY,
            snapshot_date=date(2025, 3, 1),
            total_amount=Decimal("1100"),
        )
        CashFlowSnapshotItem.objects.create(
            snapshot=selected_snapshot,
            category="dividend",
            amount=Decimal("1000"),
            allocation_pct=Decimal("1"),
        )

        rendered = self._render_post(
            "CashFlow Timeseries",
            "{{ cashflow_charts }}",
            "cashflow_snapshots",
            selected_snapshot,
        )

        self.assertIn(past_snapshot.snapshot_date.isoformat(), rendered)
        self.assertIn(selected_snapshot.snapshot_date.isoformat(), rendered)
        self.assertNotIn("2025-03-01", rendered)

    def test_savings_rate_timeseries_excludes_snapshots_after_selected_snapshot(
        self,
    ) -> None:
        flow = SalarySavingsFlow.objects.create(
            owner=self.user,
            name="Dated Savings",
            currency=SalarySavingsFlow.Currency.TRY,
        )
        past_snapshot = SalarySavingsSnapshot.objects.create(
            flow=flow,
            snapshot_date=date(2025, 1, 1),
            total_salary=Decimal("1000"),
            total_savings=Decimal("300"),
            savings_rate=Decimal("0.30"),
        )
        selected_snapshot = SalarySavingsSnapshot.objects.create(
            flow=flow,
            snapshot_date=date(2025, 2, 1),
            total_salary=Decimal("1000"),
            total_savings=Decimal("400"),
            savings_rate=Decimal("0.40"),
        )
        SalarySavingsSnapshot.objects.create(
            flow=flow,
            snapshot_date=date(2025, 3, 1),
            total_salary=Decimal("1000"),
            total_savings=Decimal("500"),
            savings_rate=Decimal("0.50"),
        )

        rendered = self._render_post(
            "Savings Timeseries",
            "{{ savings_rate_charts }}",
            "salary_savings_snapshots",
            selected_snapshot,
        )

        self.assertIn(past_snapshot.snapshot_date.isoformat(), rendered)
        self.assertIn(selected_snapshot.snapshot_date.isoformat(), rendered)
        self.assertNotIn("2025-03-01", rendered)

    def test_dividend_charts_exclude_zero_amount_items(self) -> None:
        snapshot = DividendSnapshot.objects.create(
            year=2025,
            currency="TRY",
            snapshot_date=date(2025, 12, 31),
            total_amount=Decimal("1000"),
        )
        asset_nonzero = Asset.objects.create(
            name="Apple", symbol="APPL", asset_type=Asset.AssetType.STOCK
        )
        asset_zero = Asset.objects.create(
            name="Meta", symbol="META", asset_type=Asset.AssetType.STOCK
        )

        DividendSnapshotAssetItem.objects.create(
            snapshot=snapshot,
            asset=asset_nonzero,
            total_amount=Decimal("1000"),
            allocation_pct=Decimal("1"),
        )
        DividendSnapshotAssetItem.objects.create(
            snapshot=snapshot,
            asset=asset_zero,
            total_amount=Decimal("0"),
            allocation_pct=Decimal("0"),
        )

        rendered = self._render_post(
            "Dividend Charts", "{{ dividend_charts }}", "dividend_snapshots", snapshot
        )

        self.assertIn("APPL", rendered)
        self.assertNotIn("META", rendered)
