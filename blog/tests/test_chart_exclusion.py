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
)


class ChartExclusionTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="charts@example.com",
            password="testpass123",
            first_name="Charts",
        )

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

        PortfolioSnapshotItem.objects.create(
            snapshot=snapshot,
            asset=asset_nonzero,
            quantity=Decimal("10"),
            average_cost=Decimal("100"),
            cost_basis=Decimal("1000"),
            current_price=Decimal("100"),
            market_value=Decimal("1000"),
            allocation_pct=Decimal("1"),
            gain_loss=Decimal("0"),
            gain_loss_pct=Decimal("0"),
        )
        PortfolioSnapshotItem.objects.create(
            snapshot=snapshot,
            asset=asset_zero,
            quantity=Decimal("0"),
            average_cost=Decimal("0"),
            cost_basis=Decimal("0"),
            current_price=Decimal("0"),
            market_value=Decimal("0"),
            allocation_pct=Decimal("0"),
            gain_loss=Decimal("0"),
            gain_loss_pct=Decimal("0"),
        )

        post = BlogPost.objects.create(
            author=self.user,
            title="Portfolio Charts",
            slug="portfolio-charts",
            content="{{ portfolio_charts }}",
        )
        post.portfolio_snapshots.add(snapshot)

        template = Template("{% load blog_extras %}{% render_post_body post %}")
        rendered = template.render(Context({"post": post}))

        # Check that NVDA is in the chart data, but AMD is not
        self.assertIn("NVDA", rendered)
        self.assertNotIn("AMD", rendered)

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

        post = BlogPost.objects.create(
            author=self.user,
            title="CashFlow Charts",
            slug="cashflow-charts",
            content="{{ cashflow_charts }}",
        )
        post.cashflow_snapshots.add(snapshot)

        template = Template("{% load blog_extras %}{% render_post_body post %}")
        rendered = template.render(Context({"post": post}))

        # "Temettü" might be escaped in JSON as Temett\u00fc
        self.assertIn("Temett", rendered)
        # "Faiz/Nema" should not be there
        self.assertNotIn("Faiz", rendered)

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

        post = BlogPost.objects.create(
            author=self.user,
            title="Dividend Charts",
            slug="dividend-charts",
            content="{{ dividend_charts }}",
        )
        post.dividend_snapshots.add(snapshot)

        template = Template("{% load blog_extras %}{% render_post_body post %}")
        rendered = template.render(Context({"post": post}))

        self.assertIn("APPL", rendered)
        self.assertNotIn("META", rendered)
